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

    @abstractproperty
    def protocols(self):
        """List of supported protocols"""

    @staticmethod
    def find_plugin(protocol):
        for plugin in InputBase.plugin_registry.values():
            if protocol in plugin.protocols:
                return plugin


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


def register_from_module(module):
    path = importlib.import_module(module).__path__
    for module_loader, name, ispkg in pkgutil.iter_modules(path, prefix='%s.' % (module, )):
        try:
            importlib.import_module(name)
        except:
            logger.exception('Failed to auto-load %s' % (module, ))


register_from_module('thomas.inputs')
register_from_module('thomas.outputs')
