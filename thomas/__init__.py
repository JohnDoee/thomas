from .filesystem import Item, Router, router

from .plugin import InputBase, StreamerBase, OutputBase, ProcessorBase

for plugin in InputBase.get_all_plugins():
    router.register_handler(plugin.plugin_name, plugin, True, False, False)

for plugin in StreamerBase.get_all_plugins():
    router.register_handler(plugin.plugin_name, plugin, False, False, True)