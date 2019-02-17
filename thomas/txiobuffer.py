"""
Opens and reads in a thread, fills a local buffer with data (TODO)
to avoid too many / limit thread calls.

This should avoid twisted blocking.
"""
import logging
import os

from twisted.internet import defer, threads

logger = logging.getLogger(__name__)


class TwistedIOBuffer(object):
    def __init__(self, fileObject):
        self.lock = defer.DeferredLock()
        self.fileObject = fileObject

    @defer.inlineCallbacks
    def seek(self, pos):
        yield self.lock.acquire()

        try:
            yield threads.deferToThread(self.fileObject.seek, pos)
        except:
            logger.exception('Failed to seek')
            raise
        finally:
            self.lock.release()

    @defer.inlineCallbacks
    def read(self, num):
        yield self.lock.acquire()

        try:
            data = yield threads.deferToThread(self.fileObject.read, num)
        except:
            logger.exception('Failed to read')
            raise
        finally:
            self.lock.release()
        defer.returnValue(data)

    @defer.inlineCallbacks
    def close(self):
        yield self.lock.acquire()

        try:
            yield threads.deferToThread(self.fileObject.close)
        except:
            logger.exception('Failed to close')
            raise
        finally:
            self.lock.release()
