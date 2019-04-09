import logging
import mimetypes
import os
import subprocess

from ..plugin import InputBase

logger = logging.getLogger(__name__)


class RCloneInput(InputBase):
    plugin_name = 'rclone'
    protocols = ['rclone']
    _open_file = None
    _pos = None

    def __init__(self, item, path, size, rclone_path=None, config_path=None):
        self.item = item
        self.path = path
        self.size = size
        self._rclone_path = rclone_path
        self._config_path = config_path
        self.filename, self.content_type = self.get_info()

    def _rclone_execute(self, cmd, *args):
        full_cmd = [
            self._rclone_path or 'rclone',
            cmd,
            '--fast-list',
        ]

        if self._config_path:
            full_cmd += ['--config', self._config_path]

        full_cmd += args

        return subprocess.Popen(full_cmd, stdout=subprocess.PIPE, bufsize=-1)

    def get_info(self):
        logger.info('Getting info about %r' % (self.path, ))
        content_type = mimetypes.guess_type(self.path)[0] or 'bytes'
        return os.path.basename(self.path), content_type

    def seek(self, pos, whence=0):
        logger.debug('Seeking to %s' % (pos, ))
        if not self._open_file:
            if whence == os.SEEK_SET or whence == os.SEEK_CUR:
                self._pos = pos
                self._open_file = self._rclone_execute('cat', self.path, '--offset', str(pos))
            elif whence == os.SEEK_END:
                self._pos = self.size - pos
                self._open_file = self._rclone_execute('cat', self.path, '--tail', str(pos))

    def read(self, num_bytes=1024 * 8):
        if not self._open_file:
            self.seek(0)

        d = self._open_file.stdout.read(num_bytes)
        self._pos += len(d)
        return d

    def tell(self):
        return self._pos

    def close(self):
        if self._open_file:
            logger.debug('Closing file')
            self._open_file.terminate()
            self._open_file.wait()
        self._open_file = None

    def get_read_items(self):
        return [self.item]
