class BaseInput(object):
    bytes_downloaded = 0 # bytes currently downloaded
    bundling = 10 # How many pieces to bundle together
    head = 0 # Current head least ahead, to facilitate stopping of pointless downloads (e.g. user seeking).
    
    def __init__(self, url):
        self.url = url
    
    def get_piece_config(self):
        raise NotImplemented()
    
    def fetch(self, fp, pieces):
        raise NotImplemented()