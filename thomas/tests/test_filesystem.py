import unittest

from io import BytesIO

from ..filesystem import Item, Router


def open_dummy(item, data):
    return BytesIO(data)


def list_dummy(item, items):
    item.nested_items = items
    return item


class DummyStream(object):
    def __init__(self, expected_evaluation, stream_value):
        self.expected_evaluation = expected_evaluation
        self.stream_value = stream_value

    def evaluate(self):
        return self.expected_evaluation

    def stream(self):
        return self.stream_value


def stream_dummy(item, expected_evaluation, stream_value):
    return DummyStream(expected_evaluation, stream_value)


class TestFilesystem(unittest.TestCase):
    def setUp(self):
        self.router = Router()
        self.router.register_handler('dummy_file', open_dummy, True, False, False)
        self.router.register_handler('dummy_list', list_dummy, False, True, False)
        self.router.register_handler('dummy_stream', stream_dummy, False, False, True)

    def test_readable(self):
        f = Item('testname')
        f.readable = True
        f['size'] = 500
        f['date'] = 1500000000
        f['various_data'] = 'happy testcase'

        self.assertFalse(f.is_listable)
        self.assertTrue(f.is_readable)

        self.assertEqual(f.serialize(), {
            'id': 'testname',
            'attributes': {
                'size': 500,
                'date': 1500000000,
                'various_data': 'happy testcase',
            },
            'readable': True,
            'expandable': False,
            'streamable': False,
            'nested_items': None,
        })

        new_f = Item.unserialize(f.serialize())

        self.assertEqual(new_f['size'], 500)
        self.assertEqual(new_f['various_data'], 'happy testcase')
        self.assertEqual(new_f.id, 'testname')
        self.assertTrue(new_f.readable)
        self.assertFalse(new_f.expandable)

        self.assertEqual(new_f.serialize(), f.serialize())

    def test_listable(self):
        folder = Item('testfolder')
        folder['various_data'] = 'happy testcase'
        self.assertFalse(folder.is_readable)
        self.assertFalse(folder.is_listable)

        folder.add_item(Item('item1'))
        folder.add_item(Item('item2'))
        folder.add_item(Item('item3'))

        self.assertTrue(folder.is_listable)

        self.assertEqual(folder.serialize(), {
            'id': 'testfolder',
            'attributes': {
                'various_data': 'happy testcase',
            },
            'readable': False,
            'expandable': False,
            'streamable': False,
            'nested_items': [
                {'id': 'item1', 'attributes': {}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
                {'id': 'item2', 'attributes': {}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
                {'id': 'item3', 'attributes': {}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
            ],
        })

        new_folder = Item.unserialize(folder.serialize())

        self.assertEqual(new_folder.serialize(), folder.serialize())

        self.assertEqual(len(new_folder.list()), 3)
        self.assertEqual(len(folder.list()), 3)

    def test_router_read(self):
        f = Item('testfolder', router=self.router)
        f.readable = True
        f['size'] = 8
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'testdata'})
        self.assertEqual(f.open().read(), b'testdata')

    def test_router_expand(self):
        folder = Item('testfolder', router=self.router)
        folder.expandable = True
        items = [Item('item1'), Item('item2'), Item('item3')]
        folder.add_route('dummy_list', False, True, False, kwargs={'items': items})
        listed_items = folder.list()
        self.assertEqual(items, listed_items)

    def test_router_choices_same_type(self):
        f = Item('testfolder', router=self.router)
        f.readable = True
        f['size'] = 10
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'badchoice2'}, priority=0)
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'goodchoice'}, priority=10)
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'badchoice1'}, priority=0)
        self.assertEqual(f.open().read(), b'goodchoice')

    def test_router_choices_mixed_type(self):
        f = Item('testfolder', router=self.router)
        f.readable = True
        f.expandable = True
        f['size'] = 10
        items = [Item('item1')]
        f.add_route('dummy_file', False, True, False, kwargs={'data': b'goodchoice'}, priority=0)
        f.add_route('dummy_list', True, False, False, kwargs={'items': items}, priority=10)
        self.assertEqual(f.open().read(), b'goodchoice')
        self.assertEqual(items, f.list())

    def test_router_serialize(self):
        f = Item('testfolder')
        f.readable = True
        f['size'] = 8
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'testdata'})
        self.assertNotIn('routes', f.serialize())
        new_f = Item.unserialize(f.serialize(include_routes=True), router=self.router)
        self.assertEqual(new_f.open().read(), b'testdata')

    def test_router_unserialize_add_route(self):
        f = Item('testfolder')
        f.readable = True
        f['size'] = 8
        f.add_route('dummy_file', True, False, False, kwargs={'data': b'testdata'})
        self.assertNotIn('routes', f.serialize())
        routes = [{'handler': 'dummy_file', 'can_open': True, 'can_list': False, 'can_stream': False, 'kwargs': {'data': b'testdata'}}]
        new_f = Item.unserialize(f.serialize(), router=self.router, routes=routes)
        self.assertEqual(new_f.open().read(), b'testdata')

    def test_router_routing_not_possible(self):
        f = Item('testfolder', router=self.router)
        f.readable = True
        f['size'] = 8
        self.assertEqual(f.open(), None)

    def test_merge_file(self):
        file_1 = Item(id='file', attributes={'only_1': 'a', 'shared': 'b', 'size': 10})
        file_2 = Item(id='file', attributes={'only_2': 'c', 'shared': 'd', 'size': 15})
        file_1.merge(file_2)

        self.assertEqual(file_1.serialize(), {
            'id': 'file',
            'attributes': {'only_1': 'a', 'shared': 'b', 'only_2': 'c', 'size': 15},
            'readable': False,
            'expandable': False,
            'streamable': False,
            'nested_items': None,
        })

    def test_merge_folder_files(self):
        folder_1 = Item(id='folder')
        folder_1.add_item(Item('item1', attributes={'a': 'b'}))
        folder_1.add_item(Item('item2', attributes={'a': 'b'}))

        folder_2 = Item(id='folder')
        folder_2.add_item(Item('item2', attributes={'b': 'c'}))
        folder_2.add_item(Item('item3', attributes={'b': 'c'}))

        folder_1.merge(folder_2)

        self.assertEqual(folder_1.serialize(), {
            'id': 'folder',
            'attributes': {},
            'readable': False,
            'expandable': False,
            'streamable': False,
            'nested_items': [
                {'id': 'item1', 'attributes': {'a': 'b'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
                {'id': 'item2', 'attributes': {'a': 'b', 'b': 'c'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
                {'id': 'item3', 'attributes': {'b': 'c'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None},
            ],
        })

    def test_merge_folder_folders(self):
        folder_1 = Item(id='folder')

        folder_1_1 = Item(id='folder1')
        folder_1_1.add_item(Item(id='file', attributes={'a': 'b'}))

        folder_1_2 = Item(id='folder2')
        folder_1_2.add_item(Item(id='file', attributes={'b': 'c'}))

        folder_1.add_item(folder_1_1)
        folder_1.add_item(folder_1_2)

        folder_2 = Item(id='folder')

        folder_2_2 = Item(id='folder2')
        folder_2_2.add_item(Item(id='file', attributes={'c': 'd'}))

        folder_2_3 = Item(id='folder3')
        folder_2_3.add_item(Item(id='file', attributes={'d': 'e'}))

        folder_2.add_item(folder_2_2)
        folder_2.add_item(folder_2_3)

        folder_1.merge(folder_2)

        self.assertEqual(folder_1.serialize(), {
            'id': 'folder',
            'attributes': {},
            'readable': False,
            'expandable': False,
            'streamable': False,
            'nested_items': [
                {
                    'id': 'folder1',
                    'attributes': {},
                    'readable': False,
                    'expandable': False,
                    'streamable': False,
                    'nested_items': [
                        {'id': 'file', 'attributes': {'a': 'b'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None}
                    ]
                },
                {
                    'id': 'folder2',
                    'attributes': {},
                    'readable': False,
                    'expandable': False,
                    'streamable': False,
                    'nested_items': [
                        {'id': 'file', 'attributes': {'b': 'c', 'c': 'd'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None}
                    ]
                },
                {
                    'id': 'folder3',
                    'attributes': {},
                    'readable': False,
                    'expandable': False,
                    'streamable': False,
                    'nested_items': [
                        {'id': 'file', 'attributes': {'d': 'e'}, 'readable': False, 'expandable': False, 'streamable': False, 'nested_items': None}
                    ]
                },

            ],
        })

    def test_merge_route(self):
        file_1 = Item(id='file', attributes={'size': 10})
        file_1.readable = True
        file_1.add_route('file', True, False, False, kwargs={'a': 'b'})
        file_2 = Item(id='file', attributes={'size': 10})
        file_2.readable = True
        file_2.add_route('file', True, False, False, kwargs={'b': 'c'})

        file_1.merge(file_2)

        self.assertEqual(file_1.serialize(include_routes=True), {
            'id': 'file',
            'attributes': {'size': 10},
            'readable': True,
            'expandable': False,
            'streamable': False,
            'nested_items': None,
            'routes': [
                {'handler': 'file', 'can_open': True, 'can_list': False, 'can_stream': False, 'priority': 0, 'kwargs': {'a': 'b'}},
                {'handler': 'file', 'can_open': True, 'can_list': False, 'can_stream': False, 'priority': 0, 'kwargs': {'b': 'c'}},
            ]
        })

    def test_merge_route_mixed(self):
        file_1 = Item(id='item', attributes={'size': 10})
        file_1.readable = True
        file_1.add_route('file', True, False, False, kwargs={'a': 'b'})

        folder_1 = Item(id='item', attributes={'size': 10})
        folder_1.expandable = True
        folder_1.add_route('folder', False, True, False, kwargs={'b': 'c'})

        file_1.merge(folder_1)

        self.assertEqual(file_1.serialize(include_routes=True), {
            'id': 'item',
            'attributes': {'size': 10},
            'readable': True,
            'expandable': True,
            'streamable': False,
            'nested_items': None,
            'routes': [
                {'handler': 'file', 'can_open': True, 'can_list': False, 'can_stream': False, 'priority': 0, 'kwargs': {'a': 'b'}},
                {'handler': 'folder', 'can_open': False, 'can_list': True, 'can_stream': False, 'priority': 0, 'kwargs': {'b': 'c'}},
            ]
        })

    def test_stream(self):
        item = Item(id='stream', router=self.router)
        item.streamable = True
        item.add_route('dummy_stream', False, False, True, kwargs={'expected_evaluation': 10, 'stream_value': 'works'})
        self.assertEqual(item.stream(), 'works')

    def test_stream_multiple(self):
        item = Item(id='stream', router=self.router)
        item.streamable = True
        item.add_route('dummy_stream', False, False, True, kwargs={'expected_evaluation': 10, 'stream_value': 'works10'})
        item.add_route('dummy_stream', False, False, True, kwargs={'expected_evaluation': 20, 'stream_value': 'works20'})
        item.add_route('dummy_stream', False, False, True, kwargs={'expected_evaluation': 15, 'stream_value': 'works15'})
        self.assertEqual(item.stream(), 'works20')

    def test_deduplicate_routes(self):
        item = Item(id='item', attributes={'size': 10})
        item.readable = True
        item.expandable = True
        item.add_route('file', True, False, False, kwargs={'a': 'b'})
        self.assertEqual(len(item.routes), 1)
        item.add_route('file', True, False, False, kwargs={'a': 'b'})
        self.assertEqual(len(item.routes), 1)
        item.add_route('file', True, True, False, kwargs={'a': 'b'})
        self.assertEqual(len(item.routes), 2)
        item.add_route('file', True, True, False, kwargs={'a': 'b'})
        self.assertEqual(len(item.routes), 2)
        item.add_route('file', True, False, False, kwargs={'a': 'b'})
        self.assertEqual(len(item.routes), 2)

    def test_list_decorator(self):
        folder = Item('testfolder')
        item = Item('item1')
        folder.add_item(item)

        def list_decorator(f, item, **kwargs):
            item['list_decorator_called'] = True
            return f(item, **kwargs)

        self.router.list_decorator = list_decorator

        self.assertEqual(folder.list()[0], item)
        self.assertFalse(item.get('list_decorator_called', False))

        folder = Item('testfolder', router=self.router)
        folder.expandable = True
        items = [Item('item1')]
        folder.add_route('dummy_list', False, True, False, kwargs={'items': items})
        listed_items = folder.list()
        self.assertEqual(items, listed_items)
        self.assertFalse(item.get('list_decorator_called', False))

    def test_equality(self):
        self.assertEqual(Item('item1'), Item('item1'))
        self.assertEqual(Item('item1', attributes={'a': 'b'}), Item('item1', attributes={'a': 'b'}))

        self.assertNotEqual(Item('item1'), Item('item2'))
        self.assertNotEqual(Item('item1', attributes={'a': 'b'}), Item('item1', attributes={'a': 'c'}))
