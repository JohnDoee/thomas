class BaseOutput(object):
    def __init__(self, url, filename, size):
        self.url = url
        self.filename = filename
        self.size = size
    
    def get_fp(self):
        raise NotImplemented()