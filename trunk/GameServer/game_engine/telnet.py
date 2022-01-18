import asyncore, asynchat, socket, logging
from connector import GameConnector
from settings import SHOW_VERSIONS

log = logging.getLogger('Telnet')

BAN_LIST = []

WILL, WONT, DO, DONT = 251, 252, 253, 254
SB, SE = 250, 240
TTYPE = 24
IP = 244

class TelnetChannel(asynchat.async_chat):
    version = 'HackerTelnetd v1.5 $Rev: 325 $'
    def __init__(self, sock, addr):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        self.state = 'init'
        self.ctype = 'Telnet'
        self.__real_terminator = '\r'
        self.set_terminator('\r')
        self.ibuffer = ''
        self.iac_data = ''
        self.prompt = ''
        self.mask = False
        self.cpos = 0
        self.tsize = (25,80)
        self.raw_mode = False
        self.notifications = []
        self.live_notification = True
        self.away_mode = False
        self.abuse_count = 0
        if SHOW_VERSIONS:
            self.transmit(self.version)
        if addr in BAN_LIST:
            self.transmit(' * You have been temporarily banned, please try back later.')
            self.close()
            return
        self.game = None
        self.game = GameConnector(self, 'login')
        self.linemode()
        self.get_termsize()
    def send_payload(self, data):
        self.push(data)
    def handle_close(self):
        if self.game and self.game.connected and not self.game.closing:
            self.game.close()
        self.close()
    def collect_incoming_data(self, data):
        try:
            self.real__collect_incoming_data(data)
        except:
            raise
    def real__collect_incoming_data(self, data):
        if len(data) > 1024:
            self.abuse_count+=1
            log.critical('%s sent over 1k of data into buffer!' % self.addr)
            if self.abuse_count > 3:
                self.ban_ip(self.addr)
                return
            self.transmit(' ** Detected an abnormally large buffer!')
            return
        if data == '\n':
            self.__real_terminator = '\r\n'
            self.set_terminator('\r\n')
            log.debug('Switched terminator, detected \\n')
            self.ctype = 'WinTelnet'
            self.game.ctype(self.ctype)
            return
        if self.game is None:
            self.handle_close()
        if chr(255) in data:
            data = self.parse_iac(data)
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
            if data == chr(0):
                data = '\n'
            self.game.process(data)
            return
        editing = False
        if data == chr(127) or data == chr(8):
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
            self.game.ctrl('t'+self.ibuffer)
        elif data == chr(3):
            self.game.ctrl('C')
        elif data == chr(26):
            self.game.ctrl('Z')
        elif data == chr(4):
            self.game.ctrl('D')
        elif len(data) > 0 and data[0] == chr(27):
            if self.process_esc(data[2:]):
                return
        elif data == chr(0):
            return
        else:
            if self.cpos < len(self.ibuffer):
                b = list(self.ibuffer)
                b.insert(self.cpos, data)
                self.ibuffer = ''.join(b)
                self.csi('%sC' % len(data))
                self.cpos+=len(data)
                self.csi('s')
                editing = True
            else:
                self.ibuffer += data
                self.cpos+=len(data)
        if len(self.prompt+self.ibuffer) > self.tsize[1]-2:
            self.ibuffer = self.ibuffer[:-1]
        if self.cpos != len(self.ibuffer):
            self.csi('s')
            editing = True
        self.draw_prompt()
        if editing:
            self.csi('u')
    def draw_prompt(self):
        buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
        self.push('\r'+chr(27)+'[K'+self.prompt+buf)
    def found_terminator(self):
        if self.raw_mode:
            return
        self.push('\r\n')
        self.cpos = 0
        data = self.ibuffer.replace(chr(0), '').replace(chr(27), '')
        self.ibuffer = ''
        self.game.process(data)
        self.away_mode = False
    def linemode(self):
        self.push(chr(255)+chr(251)+chr(1))
        self.push(chr(255)+chr(253)+chr(34))
    def esc(self, code):
        self.push(chr(27)+code)
    def csi(self, code):
        self.esc('[%s' % code)
    def get_termsize(self):
        self.csi('s')
        self.csi('999;999H')
        self.csi('6n')
        self.csi('u')
    def enable_mouse(self):
        self.csi('?1002h')
    def disable_mouse(self):
        self.csi('?1002l')
    def transmit(self, data):
        self.push(data+'\r\n')
    def set_prompt(self, data):
        if self.raw_mode:
            return
        while self.notifications != []:
            self.transmit(self.notifications.pop())
        self.prompt = data
        self.push('\r'+chr(27)+'[K'+self.prompt)
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
    def parse_iac(self, data):
        iac = data.index(chr(255))
        if data[iac+1] in (chr(WILL), chr(WONT), chr(DO), chr(DONT)):
            if len(data[iac+1:iac+3]) > 1:
                self.process_iac(data[iac+1:iac+3])
            data = data[:iac]+data[iac+3:]
        elif data[iac+1] == chr(SB):
            if chr(SE) not in data:
                log.critical('Invalid SB packet: %s' % ','.join([str(ord(c)) for c in data]))
                #self.transmit('\r\n*** Client side error has occurred, please reconnect.')
                #self.close_when_done()
                return ''
            eb = data.index(chr(SE))
            sb = data[iac+1:eb-1]
            if sb[1] == chr(TTYPE) and sb[2] == chr(0):
                self.ctype = sb[3:]
                self.transmit('Terminal Type: %s' % self.ctype)
                self.enable_mouse()
                self.game.on_connect()
            data = data[:iac]+data[eb+1:]
        else:
            self.process_iac(data[iac+1:iac+2])
            data = data[:iac]+data[iac+2:]
        if chr(255) in data:
            data = self.parse_iac(data)
        return data
    def process_iac(self, iac):
        # There is little need for this server to process IAC packets.
        if iac[0] == chr(IP):
            log.debug('IAC Suspend')
            self.last_iac = iac[0]
        elif iac[0] == chr(237):
            log.debug('IAC 237?')
            self.last_iac = iac[0]
        elif iac[0] == chr(WILL):
            if iac[1] == chr(TTYPE):
                self.push(chr(255)+chr(SB)+chr(TTYPE)+chr(1)+chr(255)+chr(SE))
            else:
                log.debug('IAC DONT: %s' % ord(iac[1]))
                self.push(chr(255)+chr(DONT)+iac[1])
        elif iac[0] == chr(253):
            if iac[1] != chr(1):
                log.debug('IAC WONT: %s' % ord(iac[1]))
                self.push(chr(255)+chr(WONT)+iac[1])
            if iac[1] == chr(6):
                log.debug('IAC Timing mark...')
                self.transmit('')
                if self.last_iac == chr(244):
                    self.last_iac = None
                    self.game.cbreak()
                elif self.last_iac == chr(237):
                    self.last_iac = None
                    self.game.suspend()
        else:
            log.warning('Unhandled IAC: %s' % ','.join([str(ord(c)) for c in iac]))
    def notify(self, data):
        if self.live_notification and not self.raw_mode:
            if self.away_mode:
                self.transmit('\a')
            self.transmit('\r'+chr(27)+'[K'+data)
            buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
            self.push('\r'+chr(27)+'[K'+self.prompt+buf)
        else:
            self.notifications.insert(0, data)
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

class TelnetServer(asyncore.dispatcher):
    """ This is the main telnet server class, the class which listens for incoming connections. """
    def __init__(self, addr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(addr)
        self.listen(5)
        log.info("Listening on port %s." % addr[1])
    def handle_accept(self):
        channel, addr = self.accept()
        c = TelnetChannel(channel, addr[0])
    def log_info(self, message, type='info'):
        log.critical(message)
