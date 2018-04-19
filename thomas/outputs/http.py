import base64
import logging

from datetime import datetime, timedelta

from twisted.python.compat import intToBytes, networkString
from twisted.internet import defer, task
from twisted.python import log, randbytes
from twisted.web import http, resource, server, static

from ..httpserver import ROOT_RESOURCE
from ..plugin import OutputBase

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

    def serve_item(self, item):
        token = self.generate_secure_token()
        self.filelist[token] = {
            'expiration': datetime.now() + URL_LIFETIME,
            'item': item,
            'content_type': static.getTypeAndEncoding(item.id, MIMETYPES, {}, 'application/octet-stream')[0],
        }

        return '/%s/%s/%s' % (self.url_prefix, token.decode('ascii'), item.id, )

    def generate_secure_token(self):
        return base64.urlsafe_b64encode(randbytes.RandomFactory().secureRandom(21, True))

    def cleanup_old_urls(self):
        to_delete = []
        for token, value in self.filelist.items():
            if value['expiration'] < datetime.now():
                to_delete.append(token)

        for token in to_delete:
            del self.filelist[token]


class NoRangeStaticProducer(static.NoRangeStaticProducer):
    @defer.inlineCallbacks
    def resumeProducing(self):
        if not self.request:
            return
        data = yield defer.maybeDeferred(self.fileObject.read, self.bufferSize)
        if data:
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        else:
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()


class SingleRangeStaticProducer(static.SingleRangeStaticProducer):
    @defer.inlineCallbacks
    def resumeProducing(self):
        if not self.request:
            return
        data = yield defer.maybeDeferred(self.fileObject.read,
            min(self.bufferSize, self.size - self.bytesWritten))
        if data:
            self.bytesWritten += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.bytesWritten == self.size:
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()


class MultipleRangeStaticProducer(static.MultipleRangeStaticProducer):
    @defer.inlineCallbacks
    def resumeProducing(self):
        if not self.request:
            return
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
            if self.request and self._partBytesWritten == self._partSize:
                try:
                    self._nextRange()
                except StopIteration:
                    done = True
                    break
        self.request.write(''.join(data))
        if done:
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None


class FilelikeObjectResource(static.File):
    isLeaf = True
    contentType = None
    fileObject = None
    encoding = 'bytes'

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
            request.setHeader(b'content-disposition', networkString('attachment; filename="%s"' % (self.filename.replace('"', ''), )))

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
            log.msg("Ignoring malformed Range header %r" % (byteRange,))
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

        producer.start()
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET
    render_HEAD = render_GET


class FileServeResource(resource.Resource):
    def getChild(self, path, request):
        if path in self.filelist:
            item = self.filelist[path]['item']
            content_type = self.filelist[path]['content_type']
            return FilelikeObjectResource(item.open(), item['size'], contentType=content_type, filename=item.id)

        return resource.NoResource()
