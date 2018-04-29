import unittest

from io import BytesIO

from ..filesystem import Item, Router
from ..processors.virtualfile import VirtualFileProcessor


class DummyIO(object):
    def __init__(self, item, byte=b'\x00'):
        self.filename = item.id
        self.byte = byte
        self.size = item['size']
        self.pos = 0

    def read(self, num_bytes=1024 * 8):
        num_bytes = min(self.size, self.pos + num_bytes) - self.pos
        self.pos += num_bytes
        return self.byte * num_bytes

    def seek(self, pos, whence=0):
        self.pos = pos

    def close(self):
        pass


def open_dummy(item, byte):
    return DummyIO(item, byte)


def open_dummy_bytesio(item, data):
    return BytesIO(data)


class TestProcessorVirtualFile(unittest.TestCase):
    def setUp(self):
        self.router = Router()
        self.router.register_handler('dummy_file', open_dummy, True, False, False)
        self.router.register_handler('dummy_file_bytesio', open_dummy_bytesio, True, False, False)

    def _read_all_data(self, vfp, seek=0):
        vfpf = vfp.open()
        vfpf.seek(seek)

        data = b''
        for _ in range(100):
            d = vfpf.read(2)
            if len(d) > 2:
                self.fail('Returning more than read')
            if not d:
                break
            data += d
        else:
            self.fail('Kept reading data while it should be finished')

        return data

    def test_read(self):
        item = Item('test', attributes={'size': 10}, router=self.router)
        item.readable = True
        item.add_route('dummy_file', True, False, False, kwargs={'byte': b'\x00'})
        vfp = VirtualFileProcessor(item, [{'item': item, 'read_size': 10, 'seek': 0}])

        data = self._read_all_data(vfp)
        self.assertEqual(data, b'\x00' * 10)

    def test_read_multiple(self):
        item_1 = Item('test', attributes={'size': 10}, router=self.router)
        item_1.readable = True
        item_1.add_route('dummy_file', True, False, False, kwargs={'byte': b'\x00'})

        item_2 = Item('test', attributes={'size': 12}, router=self.router)
        item_2.readable = True
        item_2.add_route('dummy_file', True, False, False, kwargs={'byte': b'\x01'})

        vfp = VirtualFileProcessor(item_1, [{'item': item_1, 'read_size': 10, 'seek': 0},
                                            {'item': item_2, 'read_size': 12, 'seek': 0}])

        data = self._read_all_data(vfp)
        self.assertEqual(data, b'\x00' * 10 + b'\x01' * 12)

    def test_read_partial_shifted(self):
        item_1 = Item('test', attributes={'size': 8}, router=self.router)
        item_1.readable = True
        item_1.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x00\x01\x02\x03\x04\x05\x06\x07'})

        item_2 = Item('test', attributes={'size': 7}, router=self.router)
        item_2.readable = True
        item_2.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x08\x09\x0a\x0b\x0c\x0d\x0e'})

        vfp = VirtualFileProcessor(item_1, [{'item': item_1, 'read_size': 3, 'seek': 3},
                                            {'item': item_2, 'read_size': 4, 'seek': 2}])

        data = self._read_all_data(vfp)
        self.assertEqual(data, b'\x03\x04\x05\x0a\x0b\x0c\x0d')

    def test_read_partial_shifted_seek(self):
        item_1 = Item('test', attributes={'size': 8}, router=self.router)
        item_1.readable = True
        item_1.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x00\x01\x02\x03\x04\x05\x06\x07'})

        item_2 = Item('test', attributes={'size': 7}, router=self.router)
        item_2.readable = True
        item_2.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x08\x09\x0a\x0b\x0c\x0d\x0e'})

        vfp = VirtualFileProcessor(item_1, [{'item': item_1, 'read_size': 3, 'seek': 3},
                                            {'item': item_2, 'read_size': 4, 'seek': 2}])


        data = self._read_all_data(vfp, 1)
        self.assertEqual(data, b'\x04\x05\x0a\x0b\x0c\x0d')

    def test_read_partial_shifted_seek_next_item(self):
        item_1 = Item('test', attributes={'size': 8}, router=self.router)
        item_1.readable = True
        item_1.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x00\x01\x02\x03\x04\x05\x06\x07'})

        item_2 = Item('test', attributes={'size': 7}, router=self.router)
        item_2.readable = True
        item_2.add_route('dummy_file_bytesio', True, False, False, kwargs={'data': b'\x08\x09\x0a\x0b\x0c\x0d\x0e'})

        vfp = VirtualFileProcessor(item_1, [{'item': item_1, 'read_size': 3, 'seek': 3},
                                            {'item': item_2, 'read_size': 4, 'seek': 2}])


        data = self._read_all_data(vfp, 4)
        self.assertEqual(data, b'\x0b\x0c\x0d')
