from __future__ import division

import logging
import time

from collections import deque
from contextlib import closing
from threading import Thread

from .humanize import humanize_bytes

logger = logging.getLogger(__name__)

class Manager(object):
    def __init__(self, input_handler, output_handler, pieces, segments):
        self.input_handler = input_handler
        self.output_handler = output_handler
        self.pieces = pieces
        self.segments = segments
        self.last_speeds = deque(maxlen=3)
    
    def _actual_thread(self, pieces):
        with closing(self.output_handler.get_fp()) as fp:
            self.input_handler.start(fp, pieces)
    
    def start_thread(self, identity):
        pieces = self.pieces.get_pieces(self.input_handler.bundling, identity)
        if not pieces:
            logger.info('Got no pieces')
            return None
        
        pdt = Thread(target=self._actual_thread, args=(pieces, ))
        pdt.daemon = True
        pdt.start()
        
        return pdt
    
    def print_status(self):
        finished_data = 0
        found_unfinished = False
        progress_lines = ''
        for i, piece in sorted(self.pieces.piece_map.items()):
            if piece.downloaded:
                value = 'D'
                if not found_unfinished:
                    finished_data += piece.bytes
            elif piece.downloader is not None:
                value = str(piece.downloader)
                found_unfinished = True
            else:
                value = 'Q'
                found_unfinished = True
            
            progress_lines += value
        
        print('Piece status:')
        pieces_per_line = 80
        for i in range((len(progress_lines) // pieces_per_line) + 1):
            print('  %s' % progress_lines[pieces_per_line*i:pieces_per_line*(i+1)])
        
        current_speed = humanize_bytes(sum(self.last_speeds) / len(self.last_speeds))
        data_downloaded = humanize_bytes(self.input_handler.bytes_downloaded)
        total_size = humanize_bytes(self.pieces.size)
        download_percent = int((self.input_handler.bytes_downloaded / self.pieces.size) * 10000) / 100
        finished_data = humanize_bytes(finished_data)
        print('')
        print('Current speed: %s/s - Current progress %s/%s (%s%%) - Currently finished from beginning %s' % (current_speed, data_downloaded,
                                                                                                              total_size, download_percent,
                                                                                                              finished_data))
    
    def start(self):
        logger.info('Starting to download from %r to %r' % (self.input_handler, self.output_handler))
        start_time = time.time()
        
        pdts = {}
        for i in range(self.segments):
            logger.debug('Starting segment %i of %i with identity %i' % (i+1, self.segments, i))
            pdt = self.start_thread(i)
            if not pdt:
                logger.error('Seems like the thread failed to get pieces and start')
                continue
            
            pdts[i] = pdt
        
        logger.info('All segments started')
        bytes_downloaded = 0
        last_check = time.time()
        
        while True:
            logger.debug('Checking downloaders.')
            for i, pdt in pdts.items():
                if pdt.is_alive():
                    continue
                
                logger.info('Downloader %i is finished' % i)
                pdt = self.start_thread(i)
                if pdt is None:
                    logger.info('Downloader %i does not have more pieces to fetch.' % i)
                    del pdts[i]
                    continue
            
                pdts[i] = pdt
            
            if not pdts:
                logger.info('No downloaders left, done!')
                total_size = self.pieces.size
                total_time = time.time() - start_time
                
                avg_speed = humanize_bytes(self.pieces.size / total_time)
                total_size = humanize_bytes(total_size)
                
                print('')
                print('Finished downloading %s in %s seconds (%s/s)' % (total_size, total_time, avg_speed))
                
                return
            
            logger.debug('Sleeping for some time and checking again')
            
            current_check = time.time()
            current_speed = (self.input_handler.bytes_downloaded-bytes_downloaded) / (current_check-last_check)
            self.last_speeds.append(current_speed)
            
            bytes_downloaded = self.input_handler.bytes_downloaded
            last_check = current_check
            self.print_status()
            
            time.sleep(2)
        
        