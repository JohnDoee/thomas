from __future__ import division

import logging

from io import BytesIO, SEEK_END
from math import ceil
from threading import Event, Lock

logger = logging.getLogger(__name__)

__all__ = [
    'calc_piece_size',
    'split_pieces',
    'create_pieces',
    'Piece',
]

def calc_piece_size(size, min_piece_size=20, max_piece_size=29, max_piece_count=1000):
    """
    Calculates a good piece size for a size
    """
    logger.debug('Calculating piece size for %i' % size)

    for i in range(min_piece_size, max_piece_size): # 20 = 1MB
        if size / (2**i) < max_piece_count:
            break
    return 2**i


def split_pieces(piece_list, segments, num):
    """
    Prepare a list of all pieces grouped together
    """
    piece_groups = []
    pieces = list(piece_list)
    while pieces:
        for i in range(segments):
            p = pieces[i::segments][:num]
            if not p:
                break
            piece_groups.append(p)
        pieces = pieces[num * segments:]

    return piece_groups


def create_pieces(size, segments, piece_size=None, start_position=0):
    size = size - start_position

    if not piece_size:
        piece_size = calc_piece_size(size)
    piece_count = int(ceil(size / piece_size))

    piece_list = []
    for i in range(piece_count):
        start_byte = i * piece_size
        end_byte = min(start_byte + piece_size, size)
        p = Piece(i, start_byte + start_position, end_byte + start_position)
        piece_list.append(p)

    p.last_piece = True

    logger.debug('Created Pieces with piece_size %i, resulting in %i pieces' % (piece_size, len(piece_list)))
    return piece_list


class Piece(object):
    def __init__(self, piece_index, start_byte, end_byte):
        self.piece_index = piece_index
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.data = BytesIO()
        self.can_download = Event()
        self.is_complete = Event()
        self.last_piece = False
        self.data_lock = Lock()

    def set_complete(self):
        self.is_complete.set()

    @property
    def size(self):
        return self.end_byte - self.start_byte

    def __str__(self):
        return 'index:%i' % self.piece_index

    def __repr__(self):
        return 'Piece(%i, %i, %i)' % (self.piece_index, self.start_byte, self.end_byte)

    def write(self, data):
        with self.data_lock:
            current_pos = self.data.tell()
            self.data.seek(0, SEEK_END)
            self.data.write(data)
            self.data.seek(current_pos)

    def read(self, num_bytes):
        if not self.is_complete.is_set():
            while True:
                with self.data_lock:
                    d = self.data.read(num_bytes)

                if d or self.is_complete.is_set():
                    return d

                self.is_complete.wait(0.1)
        else:
            return self.data.read(num_bytes)