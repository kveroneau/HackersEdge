import asyncore, socket, logging
from connector import FEChannel
from settings import SHOW_VERSIONS

log = logging.getLogger('Bridge')

class BridgeChannel(FEChannel):
    version = 'HackerBridge v0.1 $Rev: 277 $'
    def init(self):
        self.state = 'auth'
        self.ctype = 'Bridge'
        self.set_terminator(chr(255))
        if SHOW_VERSIONS:
            self.transmit(self.version)
    def transmit(self, data):
        self.push('P'+str(data)+chr(255))
    def found_terminator(self):
        handler = getattr(self, 'do_%s' % self.state, None)
        if handler:
            handler(self.ibuffer)
        self.ibuffer = ''
    def do_auth(self, data):
        authdata = data.split(chr(0))
        if len(authdata) != 2:
            self.close()
        username = authdata[0].replace(chr(0), '').replace(chr(255), '')
        api_key = authdata[1].replace(chr(0), '').replace(chr(255), '')
        log.info('Authenticating user %s' % username)
        self.game.process(str(username)+chr(0)+str(api_key))
    def do_op(self, data):
        if data[0] == 'H':
            self.game.connhost(data[1:])
        elif data[0] == 'D':
            self.game.process(data[1:])
    def on_authok(self):
        log.info('Authentication successful.')
        self.push('@'+chr(255))
        self.state = 'op'
    def on_authfail(self):
        log.info('General failure.')
        self.push('F'+chr(255))
        self.handle_close()
    on_denied = on_authfail
    def on_complete(self):
        log.info('Process complete, closing connection.')
        self.handle_close()
    def handle_close(self):
        self.game.close()
        self.close()

class BridgeServer(asyncore.dispatcher):
    def __init__(self, addr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(addr)
        self.listen(5)
        log.info("Listening on port %s." % addr[1])
    def handle_accept(self):
        channel, addr = self.accept()
        log.info('New connection from: %s' % addr[0])
        c = BridgeChannel(channel, addr[0])
    def log_info(self, message, type='info'):
        log.critical(message)
