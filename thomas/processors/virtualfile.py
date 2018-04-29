import logging

from ..plugin import ProcessorBase

logger = logging.getLogger(__name__)


class VirtualFileProcessor(ProcessorBase, dict):
    plugin_name = 'virtualfile'

    def __init__(self, item, file_elements):
        """
        A single file element is a dictionary with the following keys
        {
            "read_size": bytes to read from the item
            "seek": Where to seek to on open
            "item": A normal Item that can be opened and read
        }
        """
        self.file_elements = file_elements
        self.item = item
        self['size'] = sum(x['read_size'] for x in file_elements)

    def open(self):
        return VirtualFileProcessorFile(self.item, self.file_elements, self['size'])


class VirtualFileProcessorFile(object):
    _pos = None
    _open_file = None
    _bytes_read = None
    _last_index = None
    _last_file_element = None

    def __init__(self, item, file_elements, size):
        self.file_elements = file_elements
        self.filename = item.id
        self.size = size

    def seek(self, pos, whence=0):
        logger.debug('Seeking to %s' % (pos, ))
        if self._pos is not None:
            raise IOError('Unable to seek already sought file')

        self._pos = pos

    def _open_next_file(self):
        if self._pos is None:
            self.seek(0)

        logger.debug('Opening next file from position %i' % (self._pos, ))

        if self._last_index is None:
            pos = self._pos
            for i, file_element in enumerate(self.file_elements):
                pos -= file_element['read_size']
                if pos > 0:
                    continue

                additional_seek = file_element['read_size'] + pos
                self._last_index = i
                self._last_file_element = file_element
                break
            else:
                raise IOError('Trying to read out of bounds')
        else:
            self._last_index += 1
            self._last_file_element = self.file_elements[self._last_index]
            additional_seek = 0

        file_element = self._last_file_element
        item = file_element['item']
        self._open_file = item.open() # TODO: add support for kwargs?
        self._open_file.seek(file_element['seek'] + additional_seek)
        self._bytes_read = additional_seek

    def read(self, num_bytes=1024 * 8):
        if self._pos is not None and self._pos >= self.size:
            return b''

        if not self._open_file:
            self._open_next_file()

        file_element = self._last_file_element
        max_read_size = file_element['read_size']
        num_bytes = min(max_read_size, self._bytes_read + num_bytes) - self._bytes_read
        self._bytes_read += num_bytes
        self._pos += num_bytes

        d = self._open_file.read(num_bytes)
        if self._bytes_read == max_read_size:
            self._open_file.close()
            self._open_file = None

        return d

    def tell(self):
        return self._pos

    def close(self):
        if self._open_file:
            logger.debug('Closing file')
            self._open_file.close()
        self._open_file = None
