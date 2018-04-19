from ..plugin import StreamerBase


class DirectStreamer(StreamerBase):
    plugin_name = 'direct'

    def __init__(self, item, allowed_extensions=None):
        self.item = item
        self.allowed_extensions = [x.lower() for x in allowed_extensions or []]

    def _find_best_item(self, item):
        best_size, best_item = 0, None

        if item.is_listable:
            for listed_item in item.list():
                found_size, found_item = self._find_best_item(listed_item)
                if found_size > best_size:
                    best_size = found_size
                    best_item = found_item

        if item.is_readable:
            if item['size'] > best_size and (not self.allowed_extensions or
                    item.id.split('.')[-1].lower() in self.allowed_extensions):
                best_size = item['size']
                best_item = item

        return best_size, best_item

    def evaluate(self):
        best_size, best_item = self._find_best_item(self.item)
        return best_size or None

    def stream(self):
        best_size, best_item = self._find_best_item(self.item)
        return best_item
