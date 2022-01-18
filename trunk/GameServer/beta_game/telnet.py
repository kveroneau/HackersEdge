import time, asyncore, socket, logging, sys
from sessions import SHM, clean_sessions, asynclock
from game import HackersEdge
from settings import SHOW_VERSIONS
from exceptions import CloseSession

log = logging.getLogger('Telnet')

WILL, WONT, DO, DONT = 251, 252, 253, 254
SB, SE = 250, 240
TTYPE = 24
IP = 244

class TelnetChannel(asynclock):
    version = 'HackerTelnetd v0.7.9 $Revision: 198 $'
    def __init__(self, ip_addr, sock=None, map=None):
        asynclock.__init__(self, sock=sock, map=map)
        self.ip_addr = ip_addr
        self.__real_terminator = '\r'
        self.set_terminator('\r')
        self.ibuffer = ''
        self.mask = False
        self.cpos = 0
        self.prompt = ''
        self.tsize = (25,80)
        self.raw_mode = False
        #self.push(chr(255)+chr(DO)+chr(TTYPE))
        self.linemode()
        self.get_termsize()
        if SHOW_VERSIONS:
            self.transmit(self.version)
        sid = SHM.add_session(self)
        self.game = HackersEdge(sid, self)
        self.last_seen = time.time()
        self.ctype = 'Telnet'
        self.last_iac = None
        self.notifications = []
        self.live_notification = True
        self.away_mode = False
        self.abuse_count = 0
        self.accept_input = False
        try:
            self.game.on_connect()
        except CloseSession, e:
            del self.game
            self.transmit(str(e))
            self.close_when_done()
    def iac(self, op, code):
        self.push(chr(255)+chr(op)+chr(code))
    def process_iac(self, iac):
        # There is little need for this server to process IAC packets.
        if iac[0] == chr(IP):
            log.info('IAC Suspend')
            self.last_iac = iac[0]
        elif iac[0] == chr(237):
            log.info('IAC 237?')
            self.last_iac = iac[0]
        elif iac[0] == chr(WILL):
            if iac[1] == chr(TTYPE):
                self.push(chr(255)+chr(SB)+chr(TTYPE)+chr(1)+chr(255)+chr(SE))
            else:
                log.info('IAC DONT: %s' % ord(iac[1]))
                self.push(chr(255)+chr(DONT)+iac[1])
        elif iac[0] == chr(253):
            if iac[1] != chr(1):
                log.info('IAC WONT: %s' % ord(iac[1]))
                self.push(chr(255)+chr(WONT)+iac[1])
            if iac[1] == chr(6):
                log.info('IAC Timing mark...')
                self.transmit('')
                if self.last_iac == chr(244):
                    self.last_iac = None
                    self.game.cbreak()
                elif self.last_iac == chr(237):
                    self.last_iac = None
                    self.game.suspend()
        else:
            log.info('Unhandled IAC: %s' % ','.join([str(ord(c)) for c in iac]))
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
            self.push('\r'+chr(27)+'[K')
            self.push('\t'.join(data)+'\r\n')
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
            self.abuse_count+=1
            log.critical('User %s from %s sent over 1k of data into buffer!' % (self.game.username, self.ip_addr))
            if self.abuse_count > 3:
                raise ValueError('Buffer exceeded 1k more than 3 times!')
            self.transmit(' ** Detected an abnormally large buffer!')
            return
        editing = False
        if data == '\n':
            self.__real_terminator = '\r\n'
            self.set_terminator('\r\n')
            log.info('Switched terminator, detected \\n')
            self.ctype = 'WinTelnet'
            return
        if chr(255) in data:
            data = self.parse_iac(data)
        #if not self.accept_input:
        #    return
        if self.raw_mode:
            self.ibuffer = ''
            self.game.process(data)
            return
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
        elif data == chr(0):
            pass
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
            self.editing = True
        buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
        self.push('\r'+chr(27)+'[K'+self.prompt+buf)
        if editing:
            self.csi('u')
    def found_terminator(self):
        self.accept_input = False
        if self.away_mode:
            self.away_mode = False
            self.notify(' * Idle mode disabled.')
        self.last_seen = time.time()
        self.push('\r\n')
        self.cpos = 0
        data = self.ibuffer.replace(chr(0), '').replace(chr(27), '')
        self.ibuffer = ''
        if self.ctype is None:
            return
        try:
            self.game.process(data)
        except CloseSession, e:
            SHM.del_udata(self.game.username)
            del self.game
            self.transmit(str(e))
            self.close_when_done()
        except:
            log.critical('Game Process failed, closing connection %s' % self.ip_addr)
            try:
                del self.game.ooc
                del self.game
            except:
                pass
            self.close()
            return
    def transmit(self, data):
        self.push(data+'\r\n')
    def notify(self, data):
        if self.live_notification and not self.raw_mode:
            if self.away_mode:
                self.transmit('\a')
            self.transmit('\r'+chr(27)+'[K'+data)
            buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
            self.push('\r'+chr(27)+'[K'+self.prompt+buf)
        else:
            self.notifications.insert(0, data)
    def echo(self, state):
        self.mask = state
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
    def set_prompt(self, data):
        self.accept_input = True
        if self.raw_mode:
            return
        while self.notifications != []:
            self.transmit(self.notifications.pop())
        self.prompt = data
        self.push('\r'+chr(27)+'[K'+self.prompt)
    def pure_raw_mode(self, state):
        self.accept_input = True
        if state:
            self.set_terminator(None)
            self.raw_mode = True
        else:
            self.set_terminator(self.__real_terminator)
            self.raw_mode = False
    def log_info(self, message, type='info'):
        log.info(message)
    def log(self, message):
        log.info(message)
    def stdout(self, data):
        self.push(data)
    def handle_close(self):
        log.info('handle_close: %s' % self.ip_addr)
        self.close()

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
        channel = None
        try:
            log.info('handle_accept start.')
            channel, addr = self.accept()
            log.info('Before ++telnet')
            SHM.total_telnet +=1
            log.info('Before clean_sessions.')
            clean_sessions()
            log.info("Connection from: %s" % addr[0])
            if addr[0] in SHM.blocklist:
                channel.send('*** You have been temporarily banned, please try back later.\r\n')
                channel.close()
                log.info('Blocked connection from: %s' % addr[0])
                return
            c = TelnetChannel(addr[0], channel)
        except:
            if channel is None:
                raise
            channel.close()
            log.critical('Unhandled exception in Server module:[%s] %s' % (sys.exc_info()[0], sys.exc_info()[1]))
    def log_info(self, message, type='info'):
        log.critical(message)
    #def handle_error(self):
    #    log.critical('Unhandled exception in Server module:[%s] %s' % (sys.exc_info()[0], sys.exc_info()[1]))
    #    log.critical('Server shutting down...')
    #    self.close()
