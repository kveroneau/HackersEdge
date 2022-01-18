import asynchat, socket, logging, asyncore, os, pickle, hashlib
from databases import hosts, get_host_dir
from settings import ENGINE_SERVER

log = logging.getLogger('Connector')

class GameConnector(asynchat.async_chat):
    def __init__(self, tty, state):
        asynchat.async_chat.__init__(self)
        self.__tty = tty
        self.__state = state
        try:
            if ':' in ENGINE_SERVER:
                self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
                addr = ENGINE_SERVER.split(':')
                self.connect((addr[0], int(addr[1])))
            else:
                self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.connect(ENGINE_SERVER)
        except socket.error:
            log.critical('Unable to connect to game engine.')
            self.__tty.transmit(" * Hacker's Edge is current offline.")
            self.close()
            return
        self.set_terminator(chr(255)+chr(0))
        self.ibuffer = ''
    @property
    def tty(self):
        if self.__tty is not None and self.__tty.connected:
            return self.__tty
        else:
            if self.connected:
                self.handle_close()
            return None
    def handle_connect(self):
        if self.tty is not None:
            self.push(chr(255)+self.tty.ctype+chr(255)+self.tty.addr+chr(255)+self.__state+chr(255)+chr(0))
        else:
            self.close()
    def handle_close(self):
        self.close()
        if self.tty and self.tty.connected:
            self.tty.handle_close()
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        data = self.ibuffer
        self.ibuffer = ''
        if self.tty is not None:
            if data[0] == chr(255):
                if data[1] == chr(1):
                    self.tty.send_payload(data[2:])
                else:
                    self.tty.transmit(data[1:])
            elif data[0] == chr(254):
                self.tty.set_prompt(data[1:])
            elif data[0] == chr(253):
                self.tty.csi(data[1:])
            elif data[0] == chr(252):
                self.tty.notify(data[1:])
            elif data[0] == chr(251):
                self.tty.mask = True if data[1] == chr(1) else False
            elif data[0] == chr(250):
                self.tty.ibuffer = data[1:]
                self.tty.cpos = len(self.tty.ibuffer)
                self.tty.draw_prompt()
            elif data[0] == chr(249):
                self.tty.live_notification = True if data[1] == chr(1) else False
            elif data[0] == chr(248):
                if data[1] == chr(1):
                    self.tty.ban_ip('.'.join([str(ord(x)) for x in data[2:]]))
                elif data[1] == chr(2):
                    self.tty.unban_ip('.'.join([str(ord(x)) for x in data[2:]]))
                elif data[1] == chr(3):
                    self.tty.get_ban_list()
            elif data[0] == chr(247):
                self.tty.handle_disco(ord(data[1]))
                self.handle_close()
            elif data[0] == chr(246):
                self.tty.away_mode = True
            elif data[0] == chr(245):
                if data[1] == chr(1):
                    self.tty.on_authok()
                elif data[1] == chr(2):
                    if hasattr(self.tty, 'on_authfail'):
                        self.tty.on_authfail()
                elif data[1] == chr(3):
                    self.tty.on_denied()
                elif data[1] == chr(4):
                    if hasattr(self.tty, 'on_complete'):
                        self.tty.on_complete()
            elif data[0] == chr(244):
                self.tty.raw_mode = True if data[1] == chr(1) else False
            elif data[0] == chr(243):
                if data[1] == chr(1):
                    self.tty.enable_mouse()
                else:
                    self.tty.disable_mouse()
            else:
                log.error('Invalid op code from engine: %s' % ord(data[0]))
    def process(self, data):
        if self.connected:
            self.push(chr(255)+data+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def ctype(self, data):
        if self.connected:
            self.push(chr(254)+data+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def ctrl(self, data):
        if self.connected:
            self.push(chr(253)+data+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def request(self, op):
        if self.connected:
            self.push(chr(252)+chr(op)+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def authenticate(self, username, password):
        if self.connected:
            self.push(chr(251)+str(username)+chr(255)+str(hashlib.md5(password).hexdigest())+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def connhost(self, ip_addr):
        if self.connected:
            self.push(chr(250)+chr(1)+str(ip_addr)+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def mouse(self, but, col, row):
        if self.connected:
            self.push(chr(249)+chr(but)+chr(col)+chr(row)+chr(255)+chr(0))
        else:
            self.__tty.handle_close()
    def log_info(self, message, type='info'):
        log.critical(message)

class VMConnector(asynchat.async_chat):
    def __init__(self, tty, ip_addr):
        asynchat.async_chat.__init__(self)
        self.__tty = tty
        self.__ip_addr = ip_addr
        #self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        #self.connect('vm6502')
        if ip_addr == 'VMSTATS':
            self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.connect('vm6502')
        else:
            self.__http = hosts(self, 'get_vm', self.ip_addr)
        self.set_terminator(chr(255)+chr(0))
        self.ibuffer = ''
        self.endpoint = ip_addr
    def http_callback(self, result):
        try:
            del self.__http
        except:
            pass
        if result[0] == 'get_vm':
            if result[1] == 'ERR':
                log.error('Unknown connector for %s' % self.__ip_addr)
                if hasattr(self.__tty, 'is_tty'):
                    self.__tty.vm_result('NOHOST')
                else:
                    self.__tty.vm_result('NOHOST', self.__ip_addr)
                return
            log.info('VM Connector: %s' % result[1])
            try:
                if ':' in result[1]:
                    self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
                    addr = result[1].split(':')
                    self.connect((addr[0], int(addr[1])))
                else:
                    self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.connect(result[1])
            except socket.error:
                log.critical('Unable to contact VM daemon!')
                self.__tty.vm_result('NOHOST')
                return
        elif result[0] == 'make_host':
            if result[1] == 'ERR':
                log.error('Error attempting to create host: %s' % self.__ip_addr)
                self.__tty.vm_result('MKERR')
            elif result[1] == 'OK':
                log.info('Host has been created: %s' % self.__ip_addr)
                self.__tty.vm_result('MKHOST')
    @property
    def ip_addr(self):
        return self.__ip_addr
    def handle_connect(self):
        if self.__ip_addr == 'VMSTATS':
            self.push(chr(254)+'VMSTATS'+chr(255)+chr(0))
            return
        tty = chr(1) if hasattr(self.__tty, 'is_tty') else chr(2)
        self.push(chr(255)+tty+self.__ip_addr+chr(255)+chr(0))
    def handle_close(self):
        if hasattr(self.__tty, 'is_tty'):
            self.__tty.csi('0m')
            try:
                self.__tty.csi(self.__tty.ic.colour)
            except:
                pass
            self.__tty = None
        log.info('VM Hypervisor closed connection to %s' % self.__ip_addr)
        self.close()
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        data = self.ibuffer
        self.ibuffer = ''
        if data[0] == chr(254):
            if hasattr(self.__tty, 'is_tty'):
                self.__tty.stdout(data[1:])
                self.__tty.show_prompt(data[1:].split('\n')[-1])
        elif data[0] == chr(253):
            if hasattr(self.__tty, 'is_tty'):
                self.__tty.vm_result(data[1:])
            else:
                self.__tty.vm_result(data[1:], self.__ip_addr)
        elif data[0] == chr(252):
            if hasattr(self.__tty, 'is_vm'):
                self.__tty.netin(data[1:], self.__ip_addr)
        elif data[0] == chr(251):
            if hasattr(self.__tty, 'is_tty'):
                bitset = ord(data[1])
                if (bitset & 0x10) == 0x10:
                    self.__tty.echo(True)
                else:
                    self.__tty.echo(False)
                if (bitset & 0x20) == 0x20:
                    self.__tty.set_raw(True)
                else:
                    self.__tty.set_raw(False)
                if (bitset & 0x40) == 0x40:
                    self.__tty.set_mouse(True)
                else:
                    self.__tty.set_mouse(False)
        elif data[0] == chr(250):
            self.__tty.exec_result(self.__ip_addr, ord(data[1]), ord(data[2]), ord(data[3]))
    def vm_ctrl(self, code):
        if self.connected:
            self.push(chr(255)+chr(code)+chr(255)+chr(0))
        else:
            if self.__tty is not None:
                self.__tty.vm_result('TERM')
            self.handle_close()
    def vm_boot(self):
        log.debug('Sending VM boot control command.')
        self.vm_ctrl(1)
    def vm_shutdown(self):
        log.debug('Sending VM shutdown control command.')
        self.vm_ctrl(2)
    def vm_provision(self, template):
        log.debug('Sending VM provision code.')
        if self.connected:
            self.push(chr(253)+str(template)+chr(255)+chr(0))
        else:
            if self.__tty is not None:
                self.__tty.vm_result('TERM')
            self.handle_close()
    def vm_tty(self):
        log.debug('Requesting VM TTY.')
        self.vm_ctrl(3)
    def vm_stdin(self, data):
        log.debug('VM STDIN: %s' % data)
        if self.connected:
            self.push(chr(252)+str(data)+chr(255)+chr(0))
        else:
            if self.__tty is not None:
                self.__tty.vm_result('TERM')
            self.handle_close()
    def vm_netconn(self, port, from_ip):
        log.debug('Requesting VM port access to %s' % port)
        if self.connected:
            self.push(chr(255)+chr(5)+chr(port)+str(from_ip)+chr(255)+chr(0))
        else:
            if self.__tty is not None:
                self.__tty.vm_result('TERM')
            self.handle_close()
    def vm_netin(self, data):
        log.debug('VM NETIN: %s' % data)
        if self.connected:
            self.push(chr(251)+str(data)+chr(255)+chr(0))
        else:
            if self.__tty is not None:
                self.__tty.vm_result('TERM')
            self.handle_close()
    def vm_mkhost(self):
        log.debug('Host creation requested for %s' % self.__ip_addr)
        self.__http = hosts(self, 'make_host', self.ip_addr, self.connector)
        #self.vm_ctrl(4)
    def vm_hostdata(self):
        log.debug('Host metadata requested for %s' % self.__ip_addr)
        if self.connected:
            self.push(chr(254)+'HOSTDATA'+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_interrupt(self):
        log.debug('VM Interrupt requested for %s' % self.__ip_addr)
        self.vm_ctrl(6)
    def vm_nmi(self):
        log.debug('VM NMI requested for %s' % self.__ip_addr)
        self.vm_ctrl(7)
    def vm_debug(self):
        log.info('VM CPU Debug info requested for %s' % self.__ip_addr)
        self.vm_ctrl(8)
    def vm_hex(self, hexcode):
        log.debug('Hex code request for %s' % self.__ip_addr)
        if self.connected:
            self.push(chr(250)+chr(2)+str(hexcode)+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_hex_hostfs(self, fname, hexcode):
        log.debug('Hex code request for %s with filename %s' % (self.__ip_addr, fname))
        if self.connected:
            self.push(chr(250)+chr(3)+chr(len(fname))+str(fname)+str(hexcode)+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_attach(self, storage):
        log.debug('VM Attach requested for %s using storage %s' % (self.__ip_addr, storage))
        if self.connected:
            self.push(chr(249)+chr(1)+str(storage)+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_detach(self, storage):
        log.debug('VM Detach requested for %s using storage %s' % (self.__ip_addr, storage))
        if self.connected:
            self.push(chr(249)+chr(2)+str(storage)+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_attachments(self):
        if self.connected:
            self.push(chr(249)+chr(3)+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_mouse(self, but, col, row):
        if self.connected:
            self.push(chr(248)+but+col+row+chr(255)+chr(0))
        else:
            self.handle_close()
    def vm_exec(self, addr, sparam, np1, np2):
        if self.connected:
            lo = addr & 0xff
            hi = (addr >> 8) & 0xff
            self.push(chr(247)+chr(lo)+chr(hi)+chr(np1)+chr(np2)+str(sparam)+chr(255)+chr(0))
        else:
            self.handle_close()
    def log_info(self, message, type='info'):
        log.critical(message)
    def alert_tty(self):
        self.handle_close()

class VMChannel(asynchat.async_chat):
    def __init__(self, channel):
        asynchat.async_chat.__init__(self, channel)
        self.set_terminator(chr(255)+chr(0))
        self.ibuffer = ''
        self.__tty = None
        self.__ip_addr = None
        self.__close_handled = False
        self.is_vm = True
    @property
    def tty(self):
        return self.__tty
    @property
    def ip_addr(self):
        return self.__ip_addr
    def send_result(self, data):
        self.push(chr(253)+str(data)+chr(255)+chr(0))
    def stdout(self, data):
        if self.__tty:
            self.push(chr(254)+str(data)+chr(255)+chr(0))
    def netout(self, data):
        self.push(chr(252)+str(data)+chr(255)+chr(0))
    def transmit(self, data):
        self.stdout(str(data)+'\r\n')
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        data = self.ibuffer
        self.ibuffer = ''
        if self.__ip_addr is None and data[0] == chr(255):
            if data[1] == chr(1):
                self.__tty = True
            elif data[1] == chr(2):
                self.__tty = False
            else:
                log.error('Invalid TTY request packet!')
                self.close()
            self.__ip_addr = data[2:]
            log.debug('VM Request to %s' % self.__ip_addr)
            host_dir = get_host_dir(self.__ip_addr)
            if not os.path.exists(host_dir):
                self.send_result('NOHOST')
                return
            if not os.path.exists('%s/%s' % (host_dir, self.__ip_addr)):
                os.mkdir('%s/%s' % (host_dir, self.__ip_addr))
            self.host_dir = '%s/%s' % (host_dir, self.__ip_addr)
            self.allocate()
        elif self.__ip_addr is not None and data[0] == chr(255):
            if data[1] == chr(1):
                log.debug('VM Boot/IPL requested for %s' % self.__ip_addr)
                self.ipl()
            elif data[1] == chr(2):
                log.debug('VM Shutdown requested for %s' % self.__ip_addr)
                self.halt()
            elif data[1] == chr(3):
                log.debug('VM TTY requested.')
                self.request_tty()
            elif data[1] == chr(4):
                log.debug('VM mkhost requested.')
                self.mkhost()
            elif data[1] == chr(5):
                log.debug('Requested connection to network port %s from %s' % (ord(data[2]), data[3:]))
                self.netconn(ord(data[2]), data[3:])
            elif data[1] == chr(6):
                log.debug('Hardware interrupt received.')
                self.brk()
        elif self.__ip_addr is None and data[0] == chr(254):
            self.__tty = True
            if data[1:] == 'VMSTATS':
                log.debug('VM stats requested.')
                vm_count = 0
                for c in asyncore.socket_map.values():
                    if c.connected:
                        vm_count+=1
                status = open('/proc/%s/status' % os.getpid(),'r').read()
                rssi = status.index('VmRSS:')
                rss = status[rssi:status.index('\n',rssi)]
                self.send_result(chr(vm_count-1)+rss)
        elif self.__ip_addr is not None and data[0] == chr(254):
            self.__tty = True
            if data[1:] == 'HOSTDATA':
                log.debug('Host data requested.')
                self.send_result(pickle.dumps({'key':'value'}))
        elif self.__ip_addr is not None and data[0] == chr(253):
            log.debug('VM Provision with template %s' % data[1:])
            self.prov(data[1:])
        elif self.__ip_addr is not None and data[0] == chr(252):
            log.debug('VM STDIN: %s' % data[1:])
            self.stdin(data[1:])
        elif self.__ip_addr is not None and data[0] == chr(251):
            log.debug('VM NETIN: %s' % data[1:])
            self.netin(data[1:])
    def handle_close(self):
        if self.__close_handled:
            return
        self.__close_handled = True
        log.debug('VM connection closed to %s' % self.__ip_addr)
        self.close()
    def allocate(self):
        self.send_result('OFFLINE')
    def ipl(self):
        self.send_result('IPL')
    def halt(self):
        self.send_result('HALT')
    def request_tty(self):
        self.stdout('Shell> ')
    def mkhost(self):
        self.send_result('MKHOST')
    def netconn(self, port):
        self.send_result('NETOK')
    def brk(self):
        self.send_result('HALT')
    def prov(self, tmpl):
        self.send_result('PROVOK')
    def stdin(self, data):
        if data == 'exit\n':
            self.send_result('HALT')
            return
        self.stdout('?SYNTAX ERROR\r\nShell> ')
    def netin(self, data):
        pass
    def log_info(self, message, type='info'):
        log.critical(message)


BAN_LIST = []

class FEChannel(asynchat.async_chat):
    version = 'Version not set.'
    def __init__(self, sock, addr):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        self.state = 'init'
        self.ctype = 'None'
        self.ibuffer = ''
        self.init()
        self.game = GameConnector(self, self.state)
    def init(self):
        pass # Override me!
    def send_payload(self, data):
        pass
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def handle_close(self):
        log.info('Closing connection from %s' % self.addr)
        if self.game and self.game.connected and not self.game.closing:
            self.game.close()
        self.close()
    def draw_prompt(self):
        buf = '*'*len(self.ibuffer) if self.mask else self.ibuffer
        self.push('\r'+chr(27)+'[K'+self.prompt+buf)
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
    def transmit(self, data):
        self.push(data+self.terminator)
    def set_prompt(self, data):
        pass
    def process_esc(self, esc):
        if esc == 'A':
            return self.game.ctrl('UP')
        elif esc == 'B':
            return self.game.ctrl('DN')
        elif esc == 'C':
            self.esc_right()
            return True
        elif esc == 'D':
            self.esc_left()
            return True
        elif esc == 'F':
            self.tty.cpos = len(self.ibuffer)
        elif esc == 'H':
            self.cpos = 0
            self.csi('%sD' % len(self.ibuffer))
            return True
        elif esc == 'P':
            log.debug('F1')
            pass # F1 pressed.
        elif esc == 'Q':
            pass # F2
        elif esc == 'R':
            pass # F3
        elif esc == 'S':
            pass # F4
        elif esc == '15~':
            pass # F5
        elif esc == '17~':
            pass # F6
        elif esc == '18~':
            pass # F7
        elif esc == '19~':
            pass # F8
        elif esc == '20~':
            pass # F9
        elif esc == '21~':
            pass # F10
        elif esc == '23~':
            pass # F11
        elif esc == '24~':
            pass # F12
        elif len(esc) == 0:
            log.debug('ESC pressed.')
        elif esc[-1] == 'R':
            self.tsize = tuple([int(i) for i in esc[:-1].split(';')])
            log.debug('Rows: %s, Cols: %s' % self.tsize)
        elif esc[0] == 'M':
            but = ord(esc[1])-32
            col = ord(esc[2])-32
            row = ord(esc[3])-32
            log.debug('Mouse: %s, %s, %s' % (but, col, row))
        else:
            log.warning('Escape code Unhandled: %s' % esc)
            return
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
    def log_info(self, message, type='info'):
        log.critical(message)
