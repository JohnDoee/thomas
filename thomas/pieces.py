from __future__ import division

import logging

from math import ceil

logger = logging.getLogger(__name__)

class PieceStatus(object):
    def __init__(self, piece_index, start_byte, end_byte):
        self.piece_index = piece_index
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.downloaded = False
        self.downloader = None
    
    @property
    def bytes(self):
        return self.end_byte - self.start_byte
    
    def __str__(self):
        return 'index:%i' % self.piece_index
    
    def __repr__(self):
        return 'PieceStatus(%i, %i, %i)' % (self.piece_index, self.start_byte, self.end_byte)

class Pieces(object):
    def __init__(self, size, segments, piece_size=None):
        self.size = size
        self.segments = segments
        
        if not piece_size:
            piece_size = self.calc_piece_size(size)
        self.piece_size = piece_size
        self.piece_count = int(ceil(size / piece_size))
        
        self.piece_map = {}
        for i in range(self.piece_count):
            start_byte = i*piece_size
            end_byte = min(start_byte + piece_size, size)
            self.piece_map[i] = PieceStatus(i, start_byte, end_byte)
        
        logger.debug('Created Pieces with piece_size %i, resulting in %i pieces' % (piece_size, len(self.piece_map)))
    
    def calc_piece_size(self, size):
        """
        Calculates a good piece size for a size
        """
        logger.debug('Calculating piece size for %i' % size)
        
        for i in range(20, 29):
            if size / (2**i) < 1000:
                break
        return 2**i
    
    def get_pieces(self, num, downloader):
        """
        Prepares a number of pieces to download with downloader
        """
        pieces = []
        i = 0
        while i < self.piece_count:
            piece = self.piece_map[i]
            if piece.downloaded or piece.downloader is not None:
                i += 1
                continue
            
            piece.downloader = downloader
            pieces.append(piece)
            i += self.segments
            
            if len(pieces) >= num:
                break
        
        return pieces