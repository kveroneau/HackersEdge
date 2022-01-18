import time, struct, logging, asyncore, socket, sys
from sessions import SHM, clean_sessions, close_session, asynclock
from xmlrpc import dispatcher
from game import HackersEdge
from settings import SHOW_VERSIONS
from exceptions import CloseSession

log = logging.getLogger('HTTP')

class WebChannel(asynclock):
    version = 'HackerWSd v0.7.6 $Revision: 196 $'
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    def __init__(self, sock=None, map=None):
        asynclock.__init__(self, sock=sock, map=map)
        self.set_terminator('\r\n\r\n')
        self.ibuffer = ''
        self.mask = False
        self.cpos = 0
        self.state = 'handshake'
        self.ws = False
        self.last_ping = self.last_seen = time.time()
        self.ctype = 'Web'
        self.notifications = []
        self.away_mode = False
        self.live_notification = True
        self.tsize = (21,91)
        self.raw_mode = False
        self.accept_input = False
    def get_payload(self, data, mask, lenth):
        payload, i = '', 0
        for b in data:
            payload += chr(ord(b) ^ ord(mask[i % 4]))
            i+=1
        return payload
    def dispatch(self, data):
        try:
            self.last_seen = time.time()
            handler = getattr(self, 'do_%s' % self.state, None)
            if handler:
                handler(data)
        except CloseSession, e:
            SHM.del_udata(self.game.username)
            del self.game
            self.transmit(str(e))
            self.close_when_done()
    def esc(self, code):
        self.send_payload(chr(27)+code)
    def csi(self, code):
        self.esc('[%s' % code)
    def get_termsize(self):
        self.csi('s')
        self.csi('999;999H')
        self.csi('6n')
        self.csi('u')
    def enable_mouse(self):
        self.csi('?9h')
    def disable_mouse(self):
        self.csi('?9l')
    def process_tab(self):
        data = self.game.tab_completion(self.ibuffer)
        if len(data) == 1:
            if ' ' in self.ibuffer:
                self.ibuffer = self.ibuffer.split(' ')[0]+' '+data[0]
            else:
                self.ibuffer = data[0]+' '
            self.cpos = len(self.ibuffer)
        elif len(data) == 0:
            return
        else:
            self.send_payload('\r'+chr(27)+'[K')
            self.send_payload('\t'.join(data)+'\r\n')
    def collect_incoming_data(self, data):
        try:
            self.real__collect_incoming_data(data)
        except CloseSession, e:
            SHM.del_udata(self.game.username)
            try:
                del self.game.ooc
            except:
                pass
            del self.game
            self.transmit(str(e))
            self.close_when_done()
        except:
            log.critical('Invalid state in collect_incoming_data, closing connection for %s' % self.ip_addr)
            try:
                del self.game.ooc
                del self.game
            except:
                pass
            self.close()
            return
    def real__collect_incoming_data(self, data):
        if len(data) > 1024:
            log.critical('IP %s sent over 1k of data into buffer!' % self.ip_addr)
            raise ValueError('Buffer exceeded 1k.')
        editing = False
        if self.ws:
            hdr = (ord(data[0]) & 0x80, ord(data[0]) & 0x0F)
            pkt = (ord(data[1]) & 0x80, ord(data[1]) & 0x7F)
            mask = data[2:6]
            if hdr[1] == 0x1:
                if not self.accept_input:
                    return
                data = self.get_payload(data[6:], mask, pkt[1])
                if self.raw_mode:
                    self.game.process(data)
                    return
                if data == chr(13):
                    self.accept_input = False
                    self.send_payload('\r\n')
                    data = self.ibuffer
                    self.ibuffer = ''
                    self.cpos = 0
                    self.dispatch(data)
                    return
                elif data == chr(127):
                    if self.cpos < len(self.ibuffer) and self.cpos > 0:
                        b = list(self.ibuffer)
                        del b[self.cpos-1]
                        self.ibuffer = ''.join(b)
                        self.csi('D')
                        self.cpos-=1
                        self.csi('s')
                        editing = True
                    else:
                        self.ibuffer = self.ibuffer[:-1]
                        self.cpos-=1
                        if self.cpos<0:
                            self.cpos=0
                elif data == chr(9):
                    self.process_tab()
                elif data == chr(3):
                    self.game.cbreak()
                elif data == chr(26):
                    self.game.suspend()
                elif data == chr(4):
                    self.game.eof()
                elif len(data) > 0 and data[0] == chr(27):
                    if self.game.process_esc(data[2:]):
                        return
                elif len(data) == 1 and ord(data[0]) < 127:
                    if self.cpos < len(self.ibuffer):
                        b = list(self.ibuffer)
                        b.insert(self.cpos, data)
                        self.ibuffer = ''.join(b)
                        self.csi('C')
                        self.cpos+=len(data)
                        self.csi('s')
                        editing = True
                    else:
                        self.ibuffer += data
                        self.cpos+=1
                elif len(data) > 0:
                    log.info('Weird key sent: %s' % ord(data[0]))
                if len(self.prompt+self.ibuffer) > self.tsize[1]-2:
                    self.ibuffer = self.ibuffer[:-1]
                buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
                self.send_payload('\r'+chr(27)+'[K'+self.prompt+buf)
                if editing:
                    self.csi('u')
            elif hdr[1] == 0x8:
                log.debug('Session closed via 0x8 payload.')
                close_session(self.game.sid)
                raise CloseSession
            elif hdr[1] == 0x9:
                self.send_pong(data)
                self.last_ping = time.time()
            elif hdr[1] == 0xA:
                self.last_ping = time.time()
            else:
                log.critical('Unhandled OpCode: %s' % hex(hdr[1]))
        else:
            self.ibuffer += data
        if len(self.ibuffer) > 1024:
            log.info('Buffer exceeded: %s' % self.opid)
            self.close()
    def found_terminator(self):
        if isinstance(self.terminator, str):
            data = self.ibuffer.replace(self.terminator, '')
        else:
            data = self.ibuffer
        self.ibuffer = ''
        self.cpos = 0
        self.dispatch(data)
    def send_payload(self, data):
        hdr = ''
        if len(data) <= 125:
            hdr = chr(len(data))
        elif len(data) >= 126 and len(data) <= 65535:
            hdr = chr(126)+struct.pack("!H", len(data))
        else:
            hdr = chr(127)+struct.pack("!Q", len(data))
        self.push(chr(0x81)+hdr+data)
    def send_ping(self):
        self.push(chr(0x89)+chr(4)+'PING')
    def send_pong(self, data='PONG'):
        self.push(chr(0x8A)+chr(len(data))+data)
    def transmit(self, data):
        if self.state == 'socket':
            self.send_payload(data+'\r\n')
            return
        self.push(data+self.terminator)
    def notify(self, data):
        if self.live_notification and not self.raw_mode:
            self.transmit('\r'+chr(27)+'[K'+data)
            buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
            self.send_payload('\r'+chr(27)+'[K'+self.prompt+buf)
        else:
            self.notifications.insert(0, data)
    def parse_headers(self, headers):
        data = {}
        for line in headers:
            parts = line.split(':')
            data.update({parts[0].strip().lower():parts[1].strip()})
        return data
    def abort_on_error(self, func, *args):
        try:
            return func(*args)
        except:
            self.close()
            raise
            return False
    def get_wskey(self, key):
        import base64, hashlib # Local scope import to save overall memory.
        return base64.b64encode(hashlib.sha1(key + self.GUID).digest())
    def do_handshake(self, header):
        self.set_terminator('\r\n')
        lines = header.split('\r\n')
        request = lines[0].split(' ')
        headers = self.abort_on_error(self.parse_headers, lines[1:])
        if not headers:
            return
        if 'x-real-ip' in headers:
            self.ip_addr = headers['x-real-ip']
            log.info("Connection from: %s" % self.ip_addr)
            if self.ip_addr in SHM.blocklist:
                self.transmit('*** You have been temporarily banned, please try back later.\r\n')
                log.info('Blocked connection from: %s' % self.ip_addr)
                self.close_when_done()
                return
        if 'sec-websocket-key' not in headers:
            if 'content-length' not in headers:
                log.info('Direct HTTP Access from %s' % self.ip_addr)
                self.transmit('HTTP/1.1 200 OK')
                self.transmit('Content-Type: text/plain\r\n')
                self.transmit(self.version)
                self.close_when_done()
            else:
                self.set_terminator(int(headers['content-length']))
                self.state = 'xmlrpc'
            return
        self.transmit('HTTP/1.1 101 Switching Protocols')
        self.transmit('Upgrade: WebSocket')
        self.transmit('Connection: Upgrade')
        self.transmit('Sec-WebSocket-Accept: %s\r\n' % self.get_wskey(headers['sec-websocket-key']))
        self.state = 'socket'
        log.info('Connection upgraded to WebSockets.')
        self.set_terminator(None)
        self.ws = True
        log.info('Before ++web')
        SHM.total_web +=1
        log.info('Before add_session')
        sid = SHM.add_session(self)
        if SHOW_VERSIONS:
            self.transmit(self.version)
        log.info('Before engine create')
        self.game = HackersEdge(sid, self)
        log.info('Before get_termsize')
        self.get_termsize()
        try:
            log.info('Before game.on_connect')
            self.game.on_connect()
        except CloseSession, e:
            del self.game
            self.transmit(str(e))
            self.close_when_done()
    def do_socket(self, data):
        #log.info('[%s] %s' % (self.game.state, data))
        #handler = getattr(self.game, 'do_%s' % self.game.state, None)
        #if handler:
        #    handler(data)
        self.game.process(data)
    def do_xmlrpc(self, data):
        self.set_terminator('')
        self.transmit('HTTP/1.1 200 OK')
        self.transmit('Content-Type: application/xml')
        data = dispatcher._marshaled_dispatch(data)
        self.transmit('Content-Length: %s\r\n' % len(data))
        self.transmit(data)
        self.close_when_done()
    def set_prompt(self, data):
        self.accept_input = True
        if self.raw_mode:
            return
        while self.notifications != []:
            self.transmit(self.notifications.pop())
        self.prompt = data
        self.send_payload('\r'+chr(27)+'[K'+self.prompt)
    def echo(self, state):
        self.mask = state
    def pure_raw_mode(self, state):
        self.accept_input = True
        if state:
            self.raw_mode = True
        else:
            self.raw_mode = False
    def log_info(self, message, type='info'):
        log.info(message)
    def log(self, message):
        log.info(message)
    def stdout(self, data):
        self.send_payload(data)
    def handle_close(self):
        log.info('handle_close: %s' % self.ip_addr)
        self.close()

class WebServer(asyncore.dispatcher):
    def __init__(self, addr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(addr)
        self.listen(5)
        log.info("Listening on port %s." % addr[1])
        self.port = addr[1]
        self.timer = None
    def handle_accept(self):
        channel = None
        try:
            log.info('handle_accept start.')
            channel, addr = self.accept()
            log.info('Before clean_sessions.')
            clean_sessions()
            log.info("Connection from: %s" % addr[0])
            if addr[0] in SHM.blocklist:
                channel.close()
                log.info('Blocked connection from: %s' % addr[0])
                return
            c = WebChannel(channel)
            c.ip_addr = addr[0]
        except:
            if channel is None:
                raise
            channel.close()
            log.critical('Unhandled exception in Server module:[%s] %s' % (sys.exc_info()[0], sys.exc_info()[1]))
    def log_info(self, message, type='info'):
        log.critical(message)
