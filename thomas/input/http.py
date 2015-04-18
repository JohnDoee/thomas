import logging

import requests
import rfc6266

from ..exceptions import InvalidInputException
from ._base import BaseInput

logger = logging.getLogger(__name__)

class HTTPInput(BaseInput):
    def get_piece_config(self):
        logger.info('Getting piece config from url %r' % self.url.geturl())
        
        r = requests.head(self.url.geturl(), verify=False)
        size = r.headers.get('content-length')
        if not size:
            raise InvalidInputException('Size is invalid (%r), unable to segmented download.' % size)
        
        filename = None
        if r.headers.get('content-disposition'):
            filename = rfc6266.parse_headers(r.headers['content-disposition']).filename_sanitized
        
        if not filename:
            url_filename = self.url.path.split('?')[0].split('/')[-1]
            if url_filename:
                filename = url_filename
        
        return int(size), filename
    
    def start(self, fp, pieces):
        range_header = ','.join(['%i-%i' % (p.start_byte, p.end_byte-1) for p in pieces])
        r = requests.get(self.url.geturl(), headers={'range': 'bytes=%s' % range_header}, stream=True, verify=False)
        is_multipart = 'multipart/byteranges' in r.headers.get('content-type')

        r_iter = r.iter_content(8196*2)
        buffer = b''
        
        for piece in pieces:
            logger.debug('Starting to fetch piece: %r' % piece)
            fp.seek(piece.start_byte)
            bytes_left = piece.bytes
            
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
                fp.write(bytes_to_write)
                bytes_left -= len(bytes_to_write)
                self.bytes_downloaded += len(bytes_to_write)
                
                if bytes_left <= 0:
                    piece.downloaded = True
                    break
            
            logger.debug('Done fetching piece: %r' % piece)
        
        logger.debug('Done doing a round.')