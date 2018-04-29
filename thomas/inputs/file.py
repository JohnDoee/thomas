import logging
import mimetypes
import os

from ..plugin import InputBase

logger = logging.getLogger(__name__)


class FileInput(InputBase):
    plugin_name = 'file'
    protocols = ['file']
    _open_file = None

    def __init__(self, item, path):
        self.path = path
        self.size, self.filename, self.content_type = self.get_info()

    def get_info(self):
        logger.info('Getting info about %r' % (self.path, ))

        content_type = mimetypes.guess_type(self.path)[0] or 'bytes'

        return os.path.getsize(self.path), os.path.basename(self.path), content_type

    def seek(self, pos, whence=0):
        logger.debug('Seeking to %s' % (pos, ))
        if not self._open_file:
            self._open_file = open(self.path, 'rb')

        self._open_file.seek(pos, whence)

    def read(self, num_bytes=1024 * 8):
        if not self._open_file:
            self.seek(0)

        d = self._open_file.read(num_bytes)
        return d

    def tell(self):
        return self._open_file.tell()

    def close(self):
        if self._open_file:
            logger.debug('Closing file')
            self._open_file.close()
        self._open_file = None
