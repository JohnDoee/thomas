import base64
import logging

from datetime import datetime, timedelta

from rfc6266 import build_header

from six.moves import urllib

from twisted.python.compat import intToBytes, networkString
from twisted.internet import abstract, defer, task
from twisted.internet.interfaces import IPushProducer
from twisted.python import log, randbytes
from twisted.web import http, resource, server, static

from zope.interface import implementer

from ..httpserver import ROOT_RESOURCE
from ..plugin import OutputBase
from ..txiobuffer import TwistedIOBuffer

logger = logging.getLogger(__name__)

URL_LIFETIME = timedelta(days=1)
MIMETYPES = static.loadMimeTypes()


class HttpOutput(OutputBase):
    plugin_name = 'http'

    def __init__(self, url_prefix='http'):
        self.filelist = {}
        self.url_prefix = url_prefix.strip('/')

    def start(self):
        self.cleanup_old_urls_loop = task.LoopingCall(self.cleanup_old_urls)
        self.cleanup_old_urls_loop.start(30 * 60)

        self.resource = FileServeResource()
        self.resource.filelist = self.filelist
        ROOT_RESOURCE.putChild(self.url_prefix.split('/')[-1], self.resource)

    def stop(self):
        self.cleanup_old_urls_loop.stop()
        del ROOT_RESOURCE.children[self.url_prefix.split('/')[-1]]

    def serve_item(self, item, as_inline=False):
        token = self.generate_secure_token()
        self.filelist[token] = {
            'expiration': datetime.now() + URL_LIFETIME,
            'item': item,
            'as_inline': as_inline,
            'content_type': static.getTypeAndEncoding(item.id, MIMETYPES, {}, 'application/octet-stream')[0],
        }

        return '/%s/%s/%s' % (self.url_prefix, token.decode('ascii'), urllib.parse.quote_plus(item.id), )

    def generate_secure_token(self):
        return base64.urlsafe_b64encode(randbytes.RandomFactory().secureRandom(21, True))

    def cleanup_old_urls(self):
        to_delete = []
        for token, value in self.filelist.items():
            if value['expiration'] < datetime.now():
                to_delete.append(token)

        for token in to_delete:
            del self.filelist[token]


@implementer(IPushProducer)
class StaticProducer(object):
    bufferSize = abstract.FileDescriptor.bufferSize
    can_produce = False

    def __init__(self, request, fileObject):
        """
        Initialize the instance.
        """
        self.request = request
        self.fileObject = fileObject
        self.ready = defer.Deferred()

    def pauseProducing(self):
        self.can_produce = False

    @defer.inlineCallbacks
    def resumeProducing(self):
        raise NotImplementedError()

    def stopProducing(self):
        try:
            self._stopProducing()
        except:
            logger.exception('Failed to stopProducing')
            raise

    def _stopProducing(self):
        if self.request:
            self.can_produce = False
            self.fileObject.close()
            self.request = None


class NoRangeStaticProducer(StaticProducer):
    @defer.inlineCallbacks
    def resumeProducing(self):
        try:
            yield self._resumeProducing()
        except:
            logger.exception('Failed NoRangeStaticProducer')
            raise

    @defer.inlineCallbacks
    def _resumeProducing(self):
        if self.can_produce:
            logger.warning('Trying to double-produce')
            defer.returnValue(None)

        self.can_produce = True
        while self.can_produce:
            data = yield defer.maybeDeferred(self.fileObject.read, self.bufferSize)
            if not self.request:
                break
            if data:
                # this .write will spin the reactor, calling .doWrite and then
                # .resumeProducing again, so be prepared for a re-entrant call
                self.request.write(data)
            else:
                self.request.unregisterProducer()
                self.request.finish()
                self.stopProducing()
                break

    def start(self):
        self.request.registerProducer(self, True)
        self.resumeProducing()


class SingleRangeStaticProducer(StaticProducer):
    def __init__(self, request, fileObject, offset, size):
        StaticProducer.__init__(self, request, fileObject)
        self.offset = offset
        self.size = size

    @defer.inlineCallbacks
    def start(self):
        yield self.fileObject.seek(self.offset)
        self.bytesWritten = 0
        self.request.registerProducer(self, True)
        self.resumeProducing()

    @defer.inlineCallbacks
    def resumeProducing(self):
        try:
            yield self._resumeProducing()
        except:
            logger.exception('Failed SingleRangeStaticProducer')
            raise

    @defer.inlineCallbacks
    def _resumeProducing(self):
        if self.can_produce:
            logger.warning('Trying to double-produce')
            defer.returnValue(None)

        self.can_produce = True
        while self.can_produce:
            data = yield defer.maybeDeferred(self.fileObject.read,
                min(self.bufferSize, self.size - self.bytesWritten))
            if not self.request:
                break
            if data:
                self.bytesWritten += len(data)
                # this .write will spin the reactor, calling .doWrite and then
                # .resumeProducing again, so be prepared for a re-entrant call
                self.request.write(data)
            if self.request and self.bytesWritten == self.size:
                self.request.unregisterProducer()
                self.request.finish()
                self.stopProducing()
                break


class MultipleRangeStaticProducer(StaticProducer):
    def __init__(self, request, fileObject, rangeInfo):
        StaticProducer.__init__(self, request, fileObject)
        self.rangeInfo = rangeInfo

    @defer.inlineCallbacks
    def start(self):
        self.rangeIter = iter(self.rangeInfo)
        yield self._nextRange()
        self.request.registerProducer(self, True)
        self.resumeProducing()

    @defer.inlineCallbacks
    def _nextRange(self):
        self.partBoundary, partOffset, self._partSize = next(self.rangeIter)
        self._partBytesWritten = 0
        self.fileObject.seek(partOffset)

    @defer.inlineCallbacks
    def resumeProducing(self):
        try:
            yield self._resumeProducing()
        except:
            logger.exception('Failed MultipleRangeStaticProducer')
            raise

    @defer.inlineCallbacks
    def _resumeProducing(self):
        if self.can_produce:
            logger.warning('Trying to double-produce')
            defer.returnValue(None)

        self.can_produce = True
        while self.can_produce:
            if not self.request:
                break
            data = []
            dataLength = 0
            done = False
            while dataLength < self.bufferSize:
                if self.partBoundary:
                    dataLength += len(self.partBoundary)
                    data.append(self.partBoundary)
                    self.partBoundary = None
                p = yield defer.maybeDeferred(self.fileObject.read,
                    min(self.bufferSize - dataLength,
                        self._partSize - self._partBytesWritten))
                self._partBytesWritten += len(p)
                dataLength += len(p)
                data.append(p)
                if not self.request:
                    break
                if self._partBytesWritten == self._partSize:
                    try:
                        yield self._nextRange()
                    except StopIteration:
                        done = True
                        break
            if self.request:
                self.request.write(''.join(data))
                if done:
                    self.request.unregisterProducer()
                    self.request.finish()
                    self.request = None
                    break


class FilelikeObjectResource(static.File):
    isLeaf = True
    contentType = None
    fileObject = None
    encoding = None

    def __init__(self, fileObject, size, contentType='bytes', filename=None):
        self.contentType = contentType
        self.fileObject = fileObject
        self.fileSize = size
        self.filename = filename
        resource.Resource.__init__(self)

    def _setContentHeaders(self, request, size=None):
        if size is None:
            size = self.getFileSize()

        if size:
            request.setHeader(b'content-length', intToBytes(size))
        if self.contentType:
            request.setHeader(b'content-type', networkString(self.contentType))
        if self.encoding:
            request.setHeader(b'content-encoding', networkString(self.encoding))
        if self.filename:
            request.setHeader(b'content-disposition', build_header(self.filename).encode('latin-1'))

    def makeProducer(self, request, fileForReading):
        """
        Make a L{StaticProducer} that will produce the body of this response.

        This method will also set the response code and Content-* headers.

        @param request: The L{Request} object.
        @param fileForReading: The file object containing the resource.
        @return: A L{StaticProducer}.  Calling C{.start()} on this will begin
            producing the response.
        """
        byteRange = request.getHeader(b'range')
        if byteRange is None or not self.getFileSize():
            self._setContentHeaders(request)
            request.setResponseCode(http.OK)
            return NoRangeStaticProducer(request, fileForReading)
        try:
            parsedRanges = self._parseRangeHeader(byteRange)
        except ValueError:
            logger.warning("Ignoring malformed Range header %r" % (byteRange,))
            self._setContentHeaders(request)
            request.setResponseCode(http.OK)
            return NoRangeStaticProducer(request, fileForReading)

        if len(parsedRanges) == 1:
            offset, size = self._doSingleRangeRequest(
                request, parsedRanges[0])
            self._setContentHeaders(request, size)
            return SingleRangeStaticProducer(
                request, fileForReading, offset, size)
        else:
            rangeInfo = self._doMultipleRangeRequest(request, parsedRanges)
            return MultipleRangeStaticProducer(
                request, fileForReading, rangeInfo)

    def getFileSize(self):
        return self.fileSize

    def render_GET(self, request):
        """
        Begin sending the contents of this L{File} (or a subset of the
        contents, based on the 'range' header) to the given request.
        """
        request.setHeader(b'accept-ranges', b'bytes')

        producer = self.makeProducer(request, self.fileObject)

        if request.method == b'HEAD':
            return b''

        def done(ign):
            producer.stopProducing()

        request.notifyFinish().addCallbacks(done, done)
        producer.start()
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET
    render_HEAD = render_GET


class FileServeResource(resource.Resource):
    filelist = None

    def getChild(self, path, request):
        if self.filelist and path in self.filelist:
            item = self.filelist[path]['item']
            content_type = self.filelist[path]['content_type']

            if self.filelist[path]['as_inline']:
                filename = None
            else:
                filename = item.id or 'unknown'

            return FilelikeObjectResource(TwistedIOBuffer(item.open()), item['size'], contentType=content_type, filename=filename)

        return resource.NoResource()
