import asyncore, asynchat, socket, logging, struct
from connector import GameConnector
from settings import SHOW_VERSIONS

log = logging.getLogger('HTTP')

BAN_LIST = []

class WebChannel(asynchat.async_chat):
    version = 'HackerWSd v1.5 $Rev: 325 $'
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    def __init__(self, sock, addr):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        self.set_terminator('\r\n\r\n')
        self.ibuffer = ''
        self.mask = False
        self.cpos = 0
        self.state = 'handshake'
        self.ws = False
        self.ctype = 'Web'
        self.notifications = []
        self.away_mode = False
        self.live_notification = True
        self.tsize = (21,91)
        self.raw_mode = False
        self.accept_input = False
        self.game = None
    def get_payload(self, data, mask, lenth):
        payload, i = '', 0
        for b in data:
            payload += chr(ord(b) ^ ord(mask[i % 4]))
            i+=1
        return payload
    def dispatch(self, data):
        handler = getattr(self, 'do_%s' % self.state, None)
        if handler:
            handler(data)
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
        self.game.ctrl('t'+self.ibuffer)
    def collect_incoming_data(self, data):
        try:
            self.real__collect_incoming_data(data)
        except:
            raise
    def real__collect_incoming_data(self, data):
        if len(data) > 1024:
            log.critical('IP %s sent over 1k of data into buffer!' % self.addr)
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
                    self.ibuffer = ''
                    if data == chr(27)+'[17~':
                        self.game.ctrl('F6')
                        return
                    if data == chr(26):
                        self.game.ctrl('Z')
                        return
                    if data[0:3] == chr(27)+'[M':
                        self.process_esc(data[2:])
                        return
                    if data == '\r':
                        data = '\n'
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
                    self.game.ctrl('C')
                elif data == chr(26):
                    self.game.ctrl('Z')
                elif data == chr(4):
                    self.game.ctrl('D')
                elif len(data) > 0 and data[0] == chr(27):
                    if self.process_esc(data[2:]):
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
                    log.warning('Weird key sent: %s' % ord(data[0]))
                if len(self.prompt+self.ibuffer) > self.tsize[1]-2:
                    self.ibuffer = self.ibuffer[:-1]
                self.draw_prompt()
                if editing:
                    self.csi('u')
            elif hdr[1] == 0x8:
                log.debug('Session closed via 0x8 payload.')
                self.handle_close()
            elif hdr[1] == 0x9:
                self.send_pong(data)
            elif hdr[1] == 0xA:
                pass
            else:
                log.critical('Unhandled OpCode: %s' % hex(hdr[1]))
                self.handle_close()
        else:
            self.ibuffer += data
        if len(self.ibuffer) > 1024:
            log.warning('Buffer exceeded: %s' % self.opid)
            self.close()
    def process_esc(self, esc):
        if esc == 'A':
            return self.game.ctrl('UP')
        elif esc == 'B':
            return self.game.ctrl('DN')
        elif esc == 'C':
            self.cpos+=1
            if self.cpos > len(self.ibuffer):
                self.cpos = len(self.ibuffer)
            else:
                self.csi('C')
        elif esc == 'D':
            self.cpos-=1
            if self.cpos < 0:
                self.cpos = 0
            else:
                self.csi('D')
        elif esc == 'F':
            self.cpos = len(self.ibuffer)
        elif esc == 'H':
            self.cpos = 0
            self.csi('%sD' % len(self.ibuffer))
            return True
        elif esc == 'P':
            self.game.ctrl('F1')
        elif esc == 'Q':
            self.game.ctrl('F2')
        elif esc == 'R':
            self.game.ctrl('F3')
        elif esc == 'S':
            self.game.ctrl('F4')
        elif esc == '15~':
            self.game.ctrl('F5')
        elif esc == '17~':
            self.game.ctrl('F6')
        elif esc == '18~':
            self.game.ctrl('F7')
        elif esc == '19~':
            self.game.ctrl('F8')
        elif esc == '20~':
            self.game.ctrl('F9')
        elif esc == '21~':
            self.game.ctrl('F10')
        elif esc == '23~':
            self.game.ctrl('F11')
        elif esc == '24~':
            self.game.ctrl('F12')
        elif len(esc) == 0:
            log.debug('ESC pressed.')
            self.game.ctrl('ESC')
        elif esc[-1] == 'R':
            self.tsize = tuple([int(i) for i in esc[:-1].split(';')])
            log.debug('Rows: %s, Cols: %s' % self.tsize)
        elif esc[0] == 'M':
            but = ord(esc[1])-32
            col = ord(esc[2])-32
            row = ord(esc[3])-32
            log.debug('Mouse: %s, %s, %s' % (but, col, row))
            self.game.mouse(but, col, row)
        else:
            log.warning('Escape code Unhandled: %s' % esc)
            return
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
            self.addr = headers['x-real-ip']
            log.info("Connection from: %s" % self.addr)
        if 'sec-websocket-key' not in headers:
            log.warning('Direct HTTP Access from %s' % self.addr)
            self.transmit('HTTP/1.1 200 OK')
            self.transmit('Content-Type: text/plain\r\n')
            self.transmit(self.version)
            self.close_when_done()
            return
        self.transmit('HTTP/1.1 101 Switching Protocols')
        self.transmit('Upgrade: WebSocket')
        self.transmit('Connection: Upgrade')
        self.transmit('Sec-WebSocket-Accept: %s\r\n' % self.get_wskey(headers['sec-websocket-key']))
        self.state = 'socket'
        log.debug('Connection upgraded to WebSockets.')
        self.set_terminator(None)
        self.ws = True
        if SHOW_VERSIONS:
            self.transmit(self.version)
        if self.addr in BAN_LIST:
            self.transmit(' * You have been temporarily banned, please try back later.')
            self.close()
            return
        self.game = GameConnector(self, 'login')
        self.get_termsize()
    def do_socket(self, data):
        self.game.process(data)
    def set_prompt(self, data):
        self.accept_input = True
        if self.raw_mode:
            return
        while self.notifications != []:
            self.transmit(self.notifications.pop())
        self.prompt = data
        self.send_payload('\r'+chr(27)+'[K'+self.prompt)
    def draw_prompt(self):
        buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
        self.send_payload('\r'+chr(27)+'[K'+self.prompt+buf)
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
        log.info('Closing connection from %s' % self.addr)
        if self.game and self.game.connected and not self.game.closing:
            self.game.close()
        self.close()
    def ban_ip(self, data):
        if data not in BAN_LIST:
            BAN_LIST.append(data)
        if self.addr == data:
            self.handle_close()
    def unban_ip(self, data):
        if data in BAN_LIST:
            BAN_LIST.remove(data)
    def get_ban_list(self):
        self.transmit(', '.join(BAN_LIST))
    def handle_disco(self, reason):
        if reason == 1:
            self.transmit("Hacker's Edge is currently offline, please try back later.")

class WebServer(asyncore.dispatcher):
    def __init__(self, addr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(addr)
        self.listen(5)
        log.info("Listening on port %s." % addr[1])
        self.port = addr[1]
    def handle_accept(self):
        channel, addr = self.accept()
        log.info("Connection from: %s" % addr[0])
        c = WebChannel(channel, addr[0])
    def log_info(self, message, type='info'):
        log.critical(message)
