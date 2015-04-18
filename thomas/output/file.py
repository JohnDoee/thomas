import logging
import os

from ._base import BaseOutput

logger = logging.getLogger(__name__)

class FileOutput(BaseOutput):
    def create_file(self, path):
        logger.info('Creating sparse file %r of size %i' % (path, self.size))
        with open(path, 'ab') as f:
            f.truncate(self.size)
    
    def get_fp(self):
        path = self.url.path or '.'
        if os.path.isdir(path) or path.endswith('/'):
            path = os.path.join(self.url.path, self.filename)
        
        if not os.path.isfile(path):
            logger.info('File %r does not exist' % path)
            self.create_file(path)
        
        return open(path, 'r+b')
    