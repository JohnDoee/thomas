import argparse
import json
import logging
import os
import sys

import progressbar

from six.moves.urllib.parse import urlsplit
from six.moves import input

from .plugin import OutputBase, InputBase


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.
    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).
    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        print(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL to download", type=str, default="", nargs="?")
    parser.add_argument("--plugin-config", help="Configuration for config, can be used multiple times. Syntax example: 'input.http={\"some\":\"json\"}'", type=str, action="append")
    parser.add_argument("--verbose", help="Increase output verbosity", action="store_true", dest="verbose")
    # parser.add_argument("--serve", help="Run a service to serve files", dest="serve", choices=OutputBase.get_all_plugins())

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                            format='%(asctime)-15s:%(levelname)s:%(name)s:%(message)s')

    plugin_configs = {}
    if args.plugin_config:
        for plugin_config in args.plugin_config:
            plugin_name, cfg = plugin_config.split('=', 1)
            plugin_configs[plugin_name] = json.loads(cfg)

    # if args.serve:
    #     plugin_cls = OutputBase.find_plugin(args.serve)
    #     print('Starting to serve from %r' % (plugin_cls, ))
    #     plugin_cls_args = plugin_configs.get('output.%s' % plugin_cls.name, {})
    #     plugin_cls_args['plugin_configs'] = plugin_configs
    #     plugin = plugin_cls(**plugin_cls_args)
    #     plugin.start()
    # elif args.url:
    if args.url:
        parsed_url = urlsplit(args.url)
        plugin_cls = InputBase.find_plugin(parsed_url.scheme)
        if not plugin_cls:
            sys.stderr.write('Unknown scheme %s\n' % (parsed_url.scheme, ))
            quit(1)

        # TODO: Fix up to work with new stuff and not just a fast http downloader
        # Also fix Item instead of None
        plugin = plugin_cls(None, args.url, **plugin_configs.get('input.%s' % plugin_cls.plugin_name, {}))
        file_modes = 'wb'
        current_byte = 0
        if os.path.isfile(plugin.filename):
            size = os.path.getsize(plugin.filename)

            if size > plugin.size:
                print('File %s already exists and is bigger than the file you are trying to download' % (plugin.filename, ))
                if not query_yes_no('Do you want to overwrite your local file?', 'no'):
                    quit()
                os.remove(plugin.filename)
            else:
                print('File %s already exists and is smaller than the file you are trying to download' % (plugin.filename, ))
                if query_yes_no('Do you want to resume downloading to your local file?', 'yes'):
                    file_modes = 'ab'

                plugin.seek(size)
                current_byte = size

        print('Started downloading %s' % (plugin.filename,))
        widgets = [
            ' ', progressbar.Percentage(),
            ' ', progressbar.DataSize(), ' of ', progressbar.DataSize(variable='max_value'),
            ' ', progressbar.Bar(),
            ' ', progressbar.ETA(),
            ' ', progressbar.FileTransferSpeed(),
        ]

        bar = progressbar.ProgressBar(max_value=plugin.size, widgets=widgets)
        bar.update(1)
        with open(plugin.filename, file_modes) as f:
            while True:
                d = plugin.read()
                if not d:
                    quit()
                f.write(d)
                current_byte += len(d)
                bar.update(current_byte)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()