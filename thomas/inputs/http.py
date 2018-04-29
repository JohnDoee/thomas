from __future__ import division

import logging

try:
    import Queue as queue
except ImportError:
    import queue

import requests
import rfc6266

from threading import Event, Thread

from six.moves.urllib.parse import urlsplit

from ..piece import *
from ..plugin import InputBase

logger = logging.getLogger(__name__)


class HttpInput(InputBase):
    plugin_name = 'http'
    protocols = ['http', 'https']

    current_piece = None
    pieces = None
    initial_pieces = None
    finished = False

    def __init__(self, item, url, buffer_size=3, segments=6, piece_group_size=100, piece_config=None):
        self.url = urlsplit(url)
        self.size, self.filename, self.content_type = self.get_info()
        self.buffer_size = buffer_size * segments
        self.downloaders = []
        self.segments = segments
        self.piece_group_size = piece_group_size
        self.piece_config = piece_config

    def get_info(self):
        logger.info('Getting piece config from url %r' % (self.url, ))

        r = requests.head(self.url.geturl(), verify=False)
        try:
            size = r.headers.get('content-length')
            size = int(size)
        except ValueError:
            raise Exception('Size is invalid (%r), unable to segmented download.' % (size, ))
            #raise InvalidInputException('Size is invalid (%r), unable to segmented download.' % size)

        filename = None
        if r.headers.get('content-disposition'):
            filename = rfc6266.parse_headers(r.headers['content-disposition']).filename_unsafe

        if not filename:
            url_filename = self.url.path.split('?')[0].split('/')[-1]
            if url_filename:
                filename = url_filename

        return int(size), filename, r.headers.get('content-type')

    def seek(self, pos):
        logger.debug('Seeking to %s' % (pos, ))
        if self.pieces is not None:
            raise Exception('Unable to seek in an already sought file')

        if self.piece_config:
            piece_size = calc_piece_size(self.size, **self.piece_config)
        else:
            piece_size = None

        self.initial_pieces = self.pieces = create_pieces(self.size, self.segments, piece_size=piece_size, start_position=pos)
        q = queue.Queue()
        for piece_group in split_pieces(self.pieces, self.segments, self.piece_group_size):
            q.put(piece_group)

        for i in range(self.segments):
            d = Downloader(i, self.url, q)
            pdt = Thread(target=d.start)
            pdt.daemon = True
            pdt.start()
            d.thread = pdt
            self.downloaders.append(d)
        self.set_current_piece()

    def set_current_piece(self):
        for piece in self.pieces[:self.buffer_size]:
            piece.can_download.set()

        if self.pieces:
            self.current_piece = self.pieces.pop(0)

    def read(self, *args, **kwargs):
        try:
            return self._read(*args, **kwargs)
        except:
            logger.exception('Exception while reading')

    def _read(self, num_bytes=1024*8):
        if self.pieces is None:
            self.seek(0)

        if self.finished:
            return b''

        d = self.current_piece.read(num_bytes)
        if not d:
            self.set_current_piece()
            d = self.current_piece.read(num_bytes)

            if not d:
                self.finished = True

        return d

    def close(self):
        for downloader in self.downloaders:
            downloader.stop()


class Downloader(object):
    def __init__(self, name, url, piece_queue):
        self.name = name
        self.url = url
        self.piece_queue = piece_queue
        self.should_die = Event()

    def start(self):
        logging.info('Starting downloader %s' % (self.name, ))
        while not self.piece_queue.empty() and not self.should_die.is_set():
            try:
                pieces = self.piece_queue.get_nowait()
            except queue.Empty:
                logger.info('Piece queue empty %s, bailing' % (self.name, ))
                break

            logger.info('We got pieces: %r' % (pieces, ))

            range_header = ','.join(['%i-%i' % (p.start_byte, p.end_byte - (p.last_piece and 1 or 0)) for p in pieces])
            r = requests.get(self.url.geturl(), headers={'range': 'bytes=%s' % range_header}, stream=True, verify=False)
            is_multipart = 'multipart/byteranges' in r.headers.get('content-type')

            r_iter = r.iter_content(8196*2)
            buffer = b''

            while pieces:
                piece = pieces.pop(0)
                while not piece.can_download.wait(2):
                    logger.debug('Waiting for piece %r to be downloadable' % (piece, ))
                    if self.should_die.is_set():
                        return

                logger.debug('Starting to fetch piece: %r' % piece)
                bytes_left = piece.size

                first = True
                for chunk in r_iter:
                    if not chunk:
                        logger.error('End of data before end of piece.')

                    buffer += chunk

                    if first and is_multipart:
                        try:
                            end_of = buffer.index(b'\r\n\r\n')
                        except ValueError:
                            logger.warning('End of header was not in the first part of the chunk, trying to read more data')
                            continue

                        first = False
                        buffer = buffer[end_of+4:]

                    bytes_to_write = buffer[:bytes_left]
                    buffer = buffer[bytes_left:]
                    piece.write(bytes_to_write)
                    bytes_left -= len(bytes_to_write)

                    if bytes_left <= 0:
                        piece.set_complete()
                        break

                    if self.should_die.is_set():
                        return

                logger.debug('Done fetching piece: %r' % piece)
        logger.info('Downloader %s dying' % (self.name, ))

    def stop(self):
        logger.info('Stopping %s' % (self.name, ))
        self.should_die.set()
