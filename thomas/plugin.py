"""
Contains the base for the plugin system used by thomas
"""
import importlib
import logging
import pkgutil

from abc import ABCMeta, abstractproperty, abstractmethod

from six import with_metaclass

logger = logging.getLogger(__name__)


class AutoRegisteringPlugin(ABCMeta):
    def __new__(cls, name, parents, dct):
        if dct.get('is_abstract'):
            dct['plugin_registry'] = {}

        obj = super(AutoRegisteringPlugin, cls).__new__(cls, name, parents, dct)

        if not dct.get('is_abstract'):
            obj.plugin_registry[dct['plugin_name']] = obj

        return obj


class PluginBase(with_metaclass(AutoRegisteringPlugin)):
    is_abstract = True

    @abstractproperty
    def plugin_name(self):
        """Plugin name, used to identify this plugin"""


class InputBase(PluginBase):
    is_abstract = True

    size = None
    filename = None
    content_type = None

    @abstractmethod
    def __init__(self, url, **kwargs):
        pass

    @abstractproperty
    def protocols(self):
        """List of supported protocols"""

    @staticmethod
    def find_plugin(protocol):
        for plugin in InputBase.plugin_registry.values():
            if protocol in plugin.protocols:
                return plugin

    @abstractmethod
    def seek(self, pos):
        """Seek the input"""

    @abstractmethod
    def read(self, num):
        """Read bytes from input"""

    @abstractmethod
    def close(self):
        """Close input"""

    # @abstractmethod
    # def tell(self):
    #     """Current position"""

    @staticmethod
    def get_all_plugins():
        return InputBase.plugin_registry.values()


class OutputBase(PluginBase):
    is_abstract = True

    @staticmethod
    def get_all_plugins():
        return OutputBase.plugin_registry.keys()

    @staticmethod
    def find_plugin(plugin_name):
        for plugin in OutputBase.plugin_registry.values():
            if plugin_name in plugin.plugin_name:
                return plugin

    @abstractmethod
    def start(self):
        """Start the Output Plugin"""

    @abstractmethod
    def stop(self):
        """Stop the Output Plugin"""

    @abstractmethod
    def serve_item(self, item):
        """Return an url where iten can be accessed"""


class ProcessorBase(InputBase):
    is_abstract = True
    protocols = None

    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @staticmethod
    def get_all_plugins():
        return ProcessorBase.plugin_registry.values()

    @staticmethod
    def find_plugin(plugin_name):
        for plugin in ProcessorBase.plugin_registry.values():
            if plugin_name in plugin.plugin_name:
                return plugin


class StreamerBase(PluginBase):
    is_abstract = True

    def __init__(self, item, **kwargs):
        self.item = item

    @staticmethod
    def get_all_plugins():
        return StreamerBase.plugin_registry.values()

    @staticmethod
    def find_plugin(plugin_name):
        for plugin in StreamerBase.plugin_registry.values():
            if plugin_name in plugin.plugin_name:
                return plugin

    @abstractmethod
    def evaluate(self):
        """
        How good is this stream, it can be e.g. file-size
        when trying to stream the best video file.

        The biggest value wins.
        """

    @abstractmethod
    def stream(self):
        """
        Create a stream, return either a URL
        or an Item. Any postprocessing of output
        is left up to the user.
        """


def register_from_module(module):
    path = importlib.import_module(module).__path__
    for module_loader, name, ispkg in pkgutil.iter_modules(path, prefix='%s.' % (module, )):
        try:
            importlib.import_module(name)
        except:
            logger.exception('Failed to auto-load %s' % (module, ))


register_from_module('thomas.inputs')
register_from_module('thomas.outputs')
register_from_module('thomas.processors')
register_from_module('thomas.streamers')