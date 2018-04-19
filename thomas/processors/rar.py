import logging
import mimetypes

import rarfile

from ..plugin import ProcessorBase

logger = logging.getLogger(__name__)


class RarProcessor(ProcessorBase, dict):
    plugin_name = 'rar'

    def __init__(self, filesystem, entry_item):
        self.filesystem = filesystem
        self.entry_item = entry_item

        self.vrf = VirtualRarFile(entry_item.open(), filesystem=filesystem)
        self.infofile = self.vrf.infolist()[0]

        self['size'] = self.size = self.infofile.file_size
        self.filename = self.infofile.filename.split('/')[-1]
        self.content_type = mimetypes.guess_type(self.filename)[0] or 'bytes'

    def open(self):
        return RarProcessorFile(self.vrf, self.infofile)


class RarProcessorFile:
    def __init__(self, vrf, infofile):
        self.vrf = vrf
        self.infofile = infofile

    def seek(self, pos):
        logger.debug('Seeking to %s' % (pos, ))
        if not self._open_file:
            self._open_file = self.vrf.open(self.infofile)

        self._open_file.seek(pos)

    def read(self, num_bytes=1024*8):
        if not self._open_file:
            self.seek(0)

        return self._open_file.read(num_bytes)

    def close(self):
        self._open_file.close()


class BetterXFile(rarfile.XFile):
    def __init__(self, xfile, bufsize=1024):
        self._need_close = True
        if rarfile.is_filelike(xfile):
            self._fd = xfile
        else:
            self._fd = open(xfile, 'rb', bufsize)

rarfile.XFile = BetterXFile

RAR_ID = b"Rar!\x1a\x07\x00"
RAR5_ID = b"Rar!\x1a\x07\x01"

def _get_rar_version(xfile):
    """Check quickly whether file is rar archive.
    """
    buf = xfile.read(len(RAR5_ID))
    if buf.startswith(RAR_ID):
        return 3
    elif buf.startswith(RAR5_ID):
        xfile.read(1)
        return 5
    return 0


class VirtualDirectReader(rarfile.DirectReader):
    def _open_next(self):
        """Proceed to next volume."""

        # is the file split over archives?
        if (self._cur.flags & rarfile.RAR_FILE_SPLIT_AFTER) == 0:
            return False

        if self._fd:
            self._fd.close()
            self._fd = None

        # open next part
        self._volfile = self._parser._next_volname(self._volfile)
        fd = rarfile.XFile(self._volfile)
        self._fd = fd
        sig = fd.read(len(self._parser._expect_sig))
        if sig != self._parser._expect_sig:
            raise rarfile.BadRarFile("Invalid signature")

        # loop until first file header
        while 1:
            cur = self._parser._parse_header(fd)
            if not cur:
                raise rarfile.BadRarFile("Unexpected EOF")
            if cur.type in (rarfile.RAR_BLOCK_MARK, rarfile.RAR_BLOCK_MAIN):
                if cur.add_size:
                    fd.seek(cur.add_size, 1)
                continue
            if cur.orig_filename != self._inf.orig_filename:
                raise rarfile.BadRarFile("Did not found file entry")
            self._cur = cur
            self._cur_avail = cur.add_size
            return True

    def _check(self): # TODO: fix?
        """Do not check final CRC."""
        if self._returncode:
            rarfile.check_returncode(self, '')
        if self._remain != 0:
            raise rarfile.BadRarFile("Failed the read enough data")


class VirtualCommonParser(object):
    _direct_reader = VirtualDirectReader

    def _get_item_from_filename(self, filename):
        items = [item for item in self._filesystem.list() if item.id.lower() == filename.lower()]
        if not items:
            return None # TODO: exception?

        return items[0]

    def _next_volname_to_item(self, filename):
        if self._main.flags & rarfile.RAR_MAIN_NEWNUMBERING:
            filename = rarfile._next_newvol(filename)
        else:
            filename = rarfile._next_oldvol(filename)

        return self._get_item_from_filename(filename)

    def _next_volname(self, volfile):
        item = self._next_volname_to_item(volfile.filename)
        if item is None:
            return None

        return item.open()

    def _open_clear(self, inf):
        return self._direct_reader(self, inf)


class VirtualRAR3Parser(VirtualCommonParser, rarfile.RAR3Parser):
    def __init__(self, filesystem, rarfile_xfile, *args, **kwargs):
        self._filesystem = filesystem
        self._rarfile_xfile = rarfile_xfile
        super().__init__(*args, **kwargs)


class VirtualRAR5Parser(VirtualCommonParser, rarfile.RAR5Parser):
    def __init__(self, filesystem, rarfile_xfile, *args, **kwargs):
        self._filesystem = filesystem
        self._rarfile_xfile = rarfile_xfile
        super().__init__(*args, **kwargs)


class VirtualRarFile(rarfile.RarFile):
    _rar3parser = VirtualRAR3Parser
    _rar5parser = VirtualRAR5Parser

    def __init__(self, *args, filesystem=None, **kwargs):
        """Filesystem must be a folder containing rar files"""
        self._filesystem = filesystem

        super().__init__(*args, **kwargs)

    def _parse(self):
        rarfile_xfile = rarfile.XFile(self._rarfile)
        ver = _get_rar_version(rarfile_xfile)
        rarfile_xfile.seek(0)
        if ver == 3 and self._rar3parser:
            p3 = self._rar3parser(self._filesystem, rarfile_xfile, self._rarfile, self._password,
                                  self._crc_check, self._charset, self._strict, self._info_callback)
            self._file_parser = p3  # noqa
        elif ver == 5 and self._rar5parser:
            p5 = self._rar5parser(self._filesystem, rarfile_xfile, self._rarfile, self._password,
                                  self._crc_check, self._charset, self._strict, self._info_callback)
            self._file_parser = p5  # noqa
        else:
            raise rarfile.BadRarFile("Not a RAR file")

        self._file_parser.parse()
        self.comment = self._file_parser.comment
