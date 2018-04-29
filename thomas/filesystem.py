import logging
import queue

import pytz

from datetime import datetime

from threading import Thread

__all__ = [
    'Item',
    'Router',
]

logger = logging.getLogger(__name__)


class Router(object):
    def __init__(self):
        self.registry = {}
        self.list_decorator = None

    def register_handler(self, handler_id, handler, can_open, can_list, can_stream):
        self.registry[handler_id] = {
            'handler': handler,
            'can_open': can_open,
            'can_list': can_list,
            'can_stream': can_stream,
        }

    def unregister_handler(self, handler_id):
        if handler_id in self.registry:
            del self.registry[handler_id]

    def open(self, item, **kwargs):
        if not item.routes:
            return None

        for route in sorted(item.routes, key=lambda x:x.get('priority', 0), reverse=True):
            handler = self.registry.get(route['handler'])
            if not handler or not handler['can_open']:
                continue

            logger.debug('Opening with handler %s args %r' % (route['handler'], route['kwargs']))
            kwargs.update(route['kwargs'])
            return handler['handler'](item, **kwargs)

        return None

    def list(self, item, **kwargs):
        if not item.routes:
            return item

        orig_item = item

        # Create a vanilla item that all the listings can merge into
        item = orig_item.duplicate(clear_routes=True, clear_nested=True)

        item_copies = []
        thread_queue = queue.Queue()
        threads = []
        for route in orig_item.routes:
            handler = self.registry.get(route['handler'])
            if not handler or not handler['can_list']:
                continue

            logger.debug('Listing with handler %s args %r' % (route['handler'], route['kwargs']))
            item_copy = item.duplicate()
            item_copies.append(item_copy)
            kwargs_copy = dict(kwargs)
            kwargs_copy.update(route['kwargs'])

            def list_thread(q, f, *args, **kwargs):
                q.put(f(*args, **kwargs))

            if self.list_decorator:
                thread = Thread(target=list_thread, args=(thread_queue, self.list_decorator, handler['handler'], item_copy, ), kwargs=kwargs_copy)
            else:
                thread = Thread(target=list_thread, args=(thread_queue, handler['handler'], item_copy, ), kwargs=kwargs_copy)

            thread.daemon = True
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        while not thread_queue.empty():
            item_copy = thread_queue.get_nowait()
            if item_copy:
                item.merge(item_copy)

        return item

    def stream(self, item, **kwargs):
        # turn the item into a readable URL of some kind
        # given stream preparators, they each find their best and turn the item into a streamable URL
        # these can be ...
        if not item.routes:
            return []

        # use evaluate to find the best one
        best_evaluation = -1
        best_plugin = None

        for route in sorted(item.routes, key=lambda x:x.get('priority', 0), reverse=True):
            handler = self.registry.get(route['handler'])
            if not handler or not handler['can_stream']:
                continue

            logger.debug('Found streaming plugin with handler %s args %r, evaluating' % (route['handler'], route['kwargs']))
            kwargs.update(route['kwargs'])
            plugin = handler['handler'](item, **kwargs)

            evaluation = plugin.evaluate()
            logger.debug('Evaluated with %s to %s' % (route['handler'], evaluation))
            if evaluation is None:
                continue

            if evaluation > best_evaluation:
                best_evaluation = evaluation
                best_plugin = plugin

        if best_plugin is None:
            return None

        return best_plugin.stream()

router = Router()


class Item(dict):
    parent_item = None
    readable = False
    expandable = False
    streamable = False
    nested_items = None
    routes = None
    _modified = None

    def __init__(self, id, router=router, attributes=None):
        self.id = id
        self.router = router
        if attributes is not None:
            self.update(attributes)

    @property
    def path(self):
        if self.parent_item:
            return '%s/%s' % (self.parent_item.path, self.id)
        else:
            return self.id

    @property
    def modified(self):
        if not self._modified:
            modified = 'modified' in self and self['modified'] or self.get('date', 0)
            self._modified = datetime.fromtimestamp(modified, pytz.UTC)

        return self._modified

    def open(self, **kwargs):
        if not self.is_readable:
            raise IOError('This is not readable')

        return self.router.open(self, **kwargs)

    def stream(self, **kwargs):
        if not self.is_streamable:
            raise IOError('This is not streamable')

        return self.router.stream(self, **kwargs)

    def initiate_nested_items(self):
        if self.nested_items is None:
            self.nested_items = []

    def add_item(self, item):
        item.parent_item = self
        self.initiate_nested_items()
        self.nested_items.append(item)

    def get_item_from_path(self, path):
        if not self.is_expanded:
            return

        if not isinstance(path, list):
            path = path.split('/')

        if self.id:
            path = path[1:]

        if not path:
            return self

        nested_item = [x for x in self.nested_items if x.id == path[0]]
        if not nested_item:
            return None
        nested_item = nested_item[0]

        if len(path) > 1:
            return nested_item.get_item_from_path(path)
        else:
            return nested_item

    @property
    def is_readable(self):
        return self.readable and 'size' in self

    @property
    def is_listable(self):
        return self.expandable or self.nested_items is not None

    @property
    def is_expanded(self):
        return self.nested_items is not None

    @property
    def is_streamable(self):
        return self.streamable

    def list(self, **kwargs):
        if not self.is_listable:
            return None

        if self.nested_items is None:
            self.nested_items = []
            self.merge(self.router.list(self, **kwargs))

        return self.nested_items

    def add_route(self, handler, can_open, can_list, can_stream, priority=0, kwargs=None):
        if not (can_open == self.is_readable == True) and not (can_list == self.is_listable == True) and not (can_stream == self.is_streamable == True):
            return

        if self.routes is None:
            self.routes = []

        self.routes.append({
            'handler': handler,
            'can_open': can_open,
            'can_list': can_list,
            'can_stream': can_stream,
            'priority': priority,
            'kwargs': kwargs or {},
        })

        self.deduplicate_routes()

    def remove_routes(self, handler=None, can_open=False, can_list=False, can_stream=False):
        if not self.routes:
            return

        new_routes = []
        for route in self.routes:
            if handler and route['handler'] == handler:
                continue

            if can_open and route['can_open']:
                continue

            if can_list and route['can_list']:
                continue

            if can_stream and route['can_stream']:
                continue

            new_routes.append(route)

        self.routes = new_routes

    def deduplicate_routes(self):
        if not self.routes or len(self.routes) == 1:
            return

        new_routes = []
        for route in self.routes:
            for new_route in new_routes:
                for k, v in new_route.items():
                    if route[k] != v:
                        break
                else:
                    break
            else:
                new_routes.append(route)

        self.routes = new_routes

    def merge(self, item):
        if self.id != item.id:
            return

        key_skiplist = ['date', 'modified', 'size']
        for key, value in item.items():
            if key in key_skiplist:
                continue

            if key not in self or not self[key]:
                self[key] = value
            elif isinstance(self[key], dict) and isinstance(value, dict):
                self[key].update(value)

        for key in key_skiplist:
            if key not in self and key not in item:
                continue

            self[key] = max(self.get(key, 0), item.get(key, 0))

        if not self.routes and item.routes:
            self.routes = item.routes
        elif self.routes and item.routes:
            self.routes += item.routes

        self.deduplicate_routes()

        self.expandable = self.expandable or item.expandable
        self.readable = self.readable or item.readable
        self.streamable = self.streamable or item.streamable

        if not self.nested_items and item.nested_items:
            self.nested_items = item.nested_items
        elif self.nested_items and item.nested_items:
            self_keys = {x.id: x for x in self.nested_items}
            item_keys = {x.id: x for x in item.nested_items}

            for key in set(item_keys.keys()) - set(self_keys.keys()):
                self.nested_items.append(item_keys[key])

            for key in set(item_keys.keys()) & set(self_keys.keys()):
                self_keys[key].merge(item_keys[key])

        if self.nested_items:
            for nested_item in self.nested_items:
                nested_item.parent_item = self

    def serialize(self, include_routes=False, include_nested=True):
        retval = {
            'id': self.id,
            'attributes': {k: v for (k, v) in self.items() if not k.startswith('_')},
            'readable': self.readable,
            'streamable': self.streamable,
            'expandable': self.expandable,
        }

        if include_nested and self.nested_items is not None:
            retval['nested_items'] = [item.serialize(include_routes) for item in self.nested_items]
        else:
            retval['nested_items'] = None

        if include_routes:
            retval['routes'] = self.routes or []

        return retval

    @classmethod
    def unserialize(cls, data, router=router, routes=None):
        item = cls(id=data['id'], router=router)

        if data['nested_items'] is not None:
            for nested_item_data in data['nested_items']:
                item.add_item(cls.unserialize(nested_item_data, router=router, routes=routes))

        need_routes = False
        if data['expandable']:
            item.expandable = True
            need_routes = True

        if data['readable']:
            item.readable = True
            need_routes = True

        if data['streamable']:
            item.streamable = True
            need_routes = True

        item.update(data['attributes'])
        if data.get('routes'):
            item.routes = data['routes']

        elif need_routes and routes:
            for route in routes:
                item.add_route(**route)

        return item

    def duplicate(self, clear_routes=True, clear_nested=False):
        item = self.__class__.unserialize(self.serialize(include_routes=(not clear_routes)), router=self.router)
        if clear_routes:
            item.expandable = False
            item.readable = False
            item.streamable = False

        if clear_nested:
            item.nested_items = None

        return item

    def __repr__(self):
        self_repr = super().__repr__()
        if len(self_repr) > 30:
            self_repr = self_repr[:30] + '...}'

        return 'Item(%r, attributes=%s)' % (self.id, self_repr)

    def __bool__(self):
        return True

    def __eq__(self, other):
        if self.id != other.id:
            return False

        if self.readable != other.readable:
            return False

        if self.streamable != other.streamable:
            return False

        if self.expandable != other.expandable:
            return False

        if self.nested_items != other.nested_items:
            return False

        if self.routes != other.routes:
            return False

        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self == other
