import re

from rarfile import _next_newvol, _next_oldvol

from ..plugin import StreamerBase, ProcessorBase


class RarStreamer(StreamerBase):
    plugin_name = 'rar'

    def __init__(self, item, lazy=False):
        self.item = item
        self.lazy = lazy

    def _find_all_first_files(self, item):
        """
        Does not support the full range of ways rar can split
        as it'd require reading the file to ensure you are using the
        correct way.
        """
        for listed_item in item.list():
            new_style = re.findall(r'(?i)\.part(\d+)\.rar^', listed_item.id)
            if new_style:
                if int(new_style[0]) == 1:
                    yield 'new', listed_item
            elif listed_item.id.lower().endswith('.rar'):
                yield 'old', listed_item

    def _find_all_filesets(self, item):
        items = {listed_item.id.lower(): listed_item for listed_item in item.list() if listed_item.is_readable}
        filesets = []
        for style, first_item in self._find_all_first_files(item):
            fileset = []
            fileset.append(first_item)
            last_item_id = first_item.id.lower()
            while True:
                if style == 'old':
                    next_item_id = _next_oldvol(last_item_id)
                elif style == 'new':
                    next_item_id = _next_newvol(last_item_id)

                if next_item_id not in items:
                    break

                fileset.append(items[next_item_id])
                last_item_id = next_item_id

            filesets.append(fileset)

        return filesets

    def _find_biggest_fileset(self, item):
        filesets = self._find_all_filesets(item)
        best_fileset_size, best_fileset = 0, None
        for fileset in filesets:
            fileset_size = sum(x['size'] for x in fileset)
            if fileset_size > best_fileset_size:
                best_fileset = fileset
                best_fileset_size = fileset_size

        return best_fileset_size, best_fileset

    def evaluate(self):
        best_fileset_size, best_fileset = self._find_biggest_fileset(self.item)

        # we would prefer the same file if it is extracted
        # so lets add a small factor to take overhead into
        # consideration
        return int(best_fileset_size * 0.99)

    def stream(self):
        best_fileset_size, best_fileset = self._find_biggest_fileset(self.item)
        rar_processor_cls = ProcessorBase.find_plugin('rar')
        return rar_processor_cls(self.item, best_fileset[0], lazy=self.lazy)
