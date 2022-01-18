import asynchat, socket, urlparse, logging
from settings import HACKER_TOKEN

log = logging.getLogger('AsyncHTTP')

class HTTPClient(asynchat.async_chat):
    def __init__(self, owner, url, data):
        asynchat.async_chat.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__owner = owner
        self.__url = urlparse.urlsplit(url)
        self.__post_data = data
        addr = self.__url.netloc.split(':')
        if len(addr) == 1:
            addr.append('80')
        addr[1] = int(addr[1])
        self.connect(tuple(addr))
        self.set_terminator('\r\n\r\n')
        self.ibuffer = ''
        self.headers = None
        self.result = None
    def handle_connect(self):
        self.push('POST %s HTTP/1.1\r\n' % self.__url.path)
        self.push('Host: %s\r\n' % self.__url.netloc)
        self.push('User-Agent: HackerEngine/1.0\r\n')
        self.push('Connection: close\r\n')
        self.push('X-Hacker-Token: %s\r\n' % HACKER_TOKEN)
        self.push('Content-Length: %s\r\n' % len(self.__post_data))
        self.push('\r\n')
        self.push(self.__post_data)
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        if self.headers is None:
            self.headers = self.ibuffer.split('\r\n')
            self.set_terminator(chr(255))
        else:
            self.result = self.ibuffer.split(chr(0))
        self.ibuffer = ''
    def handle_close(self):
        self.close()
        self.__owner.http_callback(self.result)
        del self.__owner
    """
    def handle_error(self):
        self.__owner.http_callback(['ERR'])
        self.close()
    """
    def log_info(self, message, type='info'):
        self.__owner.http_callback(['ERR'])
        self.close()
        log.critical(message)
