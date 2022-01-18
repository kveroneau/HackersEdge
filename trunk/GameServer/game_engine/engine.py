import asyncore, asynchat, socket, logging, time, hashlib, shlex, settings, os
from datetime import datetime
from databases import site_ping, get_user, get_last_login
from connector import VMConnector
from sessions import notify_sessions, player_count, is_connected
from utils import valid_data
from ooc import OOC
from ic import IC
from exceptions import SwitchHost
import cPickle as pickle

log = logging.getLogger('Engine')

BAN_LIST = []

HONEYPOT_USERS = ('root', 'admin', 'administrator', 'pi', 'help', 'new', 'ls', 'guest', 'delphi', 'pot',)

__uptime = time.time()

def uptime():
    from datetime import timedelta
    return str(timedelta(seconds=time.time()-__uptime))

class EngineProtocol(asynchat.async_chat):
    version = "Hacker's Edge Engine v1.4.8 $Rev: 298 $"
    def __init__(self, channel):
        asynchat.async_chat.__init__(self, channel)
        self.is_tty = True
        self.state = 'init'
        self.http_state = None
        self.set_terminator(chr(255)+chr(0))
        self.username = None
        self.ctype = None
        self.udata = {'staff':False}
        self.sid = 'GUEST'
        self.ip_addr = None
        self.ibuffer = ''
        self.prompt = None
        self.__vm = None
        self.connect_time = datetime.isoformat(datetime.now())
        self.live_notification = True
        self.away_mode = False
        self.raw_mode = False
        self.mouse = False
        self.abuse_count = 0
        self.__close_handled = False
    def __setattr__(self, name, value):
        if name == 'hpos':
            if self.state in ('shell', 'ic'):
                if value > len(self.history)-1:
                    value = len(self.history)
                    self.set_buffer('')
                elif value < 0:
                    value = 0
                else:
                    log.debug('History: %s' % self.history[value])
                    self.set_buffer(self.history[value])
            if self.state == 'ic':
                self.ic.hpos = value
        else:
            self.__dict__[name] = value
    def transmit(self, data):
        if data == '':
            data = ' '
        self.push(chr(255)+str(data)+chr(255)+chr(0))
    def stdout(self, data):
        self.push(chr(255)+chr(1)+str(data)+chr(255)+chr(0))
    def set_prompt(self, data):
        self.push(chr(254)+str(data)+chr(255)+chr(0))
    def show_prompt(self, prompt=None):
        if prompt is not None:
            self.prompt = prompt
        self.set_prompt(self.prompt)
    def csi(self, data):
        if self.connected:
            self.push(chr(253)+data+chr(255)+chr(0))
    def notify(self, data):
        self.push(chr(252)+str(data)+chr(255)+chr(0))
    def ban_ip(self, ip):
        if ip not in BAN_LIST:
            BAN_LIST.append(ip)
        self.push(chr(248)+chr(1)+''.join([chr(int(x)) for x in ip.split('.')])+chr(255)+chr(0))
    def unban_ip(self, ip):
        if ip in BAN_LIST:
            BAN_LIST.remove(ip)
        self.push(chr(248)+chr(2)+''.join([chr(int(x)) for x in ip.split('.')])+chr(255)+chr(0))
    def get_ban_list(self):
        self.transmit(', '.join(BAN_LIST))
    def disco(self, reason):
        self.push(chr(247)+chr(reason)+chr(255)+chr(0))
    def echo(self, state):
        value = chr(1) if state else chr(0)
        self.push(chr(251)+value+chr(255)+chr(0))
    def set_buffer(self, data):
        self.push(chr(250)+str(data)+chr(255)+chr(0))
    def live_notifications(self, state):
        value = chr(1) if state else chr(0)
        self.push(chr(249)+value+chr(255)+chr(0))
    def set_away_mode(self):
        self.away_mode = True
        self.push(chr(246)+chr(255)+chr(0))
    def send_status(self, code):
        self.push(chr(245)+chr(code)+chr(255)+chr(0))
    def set_raw(self, state):
        self.raw_mode = state
        rs = chr(1 if state else 2)
        self.push(chr(244)+rs+chr(255)+chr(0))
    def set_mouse(self, state):
        self.mouse = state
        rs = chr(1 if state else 2)
        self.push(chr(243)+rs+chr(255)+chr(0))
    @property
    def history(self):
        if self.state == 'ic':
            return self.ic.history
        return []
    @property
    def hpos(self):
        if self.state == 'ic':
            return self.ic.hpos
        return 0
    def tab_completion(self, ibuf):
        if len(ibuf) == 0:
            return []
        if ibuf[0] in ('+', '@'):
            if hasattr(self, 'ooc'):
                return self.ooc.tab_completion(ibuf)
            return []
        elif self.state == 'ic':
            return self.ic.tab_completion(ibuf)
        return []
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        data = self.ibuffer
        self.ibuffer = ''
        if data[0] == chr(255):
            self.away_mode = False
            handler = getattr(self, 'do_%s' % self.state, None)
            if handler:
                handler(data[1:])
        elif data[0] == chr(254):
            self.ctype = data[1:]
            log.debug('Updated ctype: %s' % self.ctype)
        elif data[0] == chr(253):
            if data[1:] == 'UP':
                if self.state == 'ic':
                    self.hpos-=1
            elif data[1:] == 'DN':
                if self.state == 'ic':
                    self.hpos+=1
            elif data[1] == 't':
                ibuf = data[2:]
                log.debug('Tab data: %s' % ibuf)
                data = self.tab_completion(ibuf)
                if len(data) == 1:
                    if ' ' in ibuf:
                        ibuf = ibuf.split(' ')[0]+' '+data[0]
                    else:
                        ibuf = data[0]+' '
                    self.set_buffer(ibuf)
                elif len(data) == 0:
                    return
                else:
                    self.stdout('\r'+chr(27)+'[K')
                    self.transmit('\t'.join(data))
                    self.set_buffer(ibuf)
            elif data[1] == 'C':
                if self.state == 'vmtty':
                    if self.__vm is not None:
                        self.__vm.vm_interrupt()
                elif self.state == 'ooctty':
                    self.ooc.brk_vm()
                elif self.state == 'login':
                    self.transmit('^C')
                    self.username = 'delphi'
                    self.start_honeypot('pi', False)
                elif self.state == 'honeypot':
                    self.handle_close()
                elif self.state == 'hexinput':
                    self.state = 'ic'
                    self.show_prompt()
            elif self.state == 'login' and data[1] == 'Z':
                self.transmit('^Z')
                self.username = 'pot'
                self.start_honeypot('admin')
            elif data[1] == 'D' or data[1] == 'Z':
                if self.state == 'vmtty':
                    if self.__vm is not None:
                        self.__vm.handle_close()
                        self.__vm = None
                        if self.raw_mode:
                            self.set_raw(False)
                        self.echo(False)
                        self.state = 'ic'
                        self.show_prompt(self.ic.get_prompt())
                elif self.state == 'ooctty':
                    self.ooc.kill_vm()
                    if self.raw_mode:
                        self.set_raw(False)
                    self.echo(False)
                    self.state = 'ic'
                    self.show_prompt(self.ic.get_prompt())
                elif self.state == 'hexinput':
                    self.state = 'ic'
                    self.show_prompt()
                else:
                    self.handle_close()
            elif data[1] == 'F':
                log.debug('Function key %s pressed.' % data[2:])
                if self.state == 'vmtty':
                    if self.__vm is not None:
                        if data[2:] == '6':
                            if self.ooc.designer:
                                self.__vm.vm_debug()
                            else:
                                self.__vm.vm_nmi()
                        else:
                            log.debug('Sending VM function key.')
                            self.__vm.vm_stdin(chr(0)+chr(int(data[2:])))
                elif self.state == 'ic':
                    try:
                        self.ic.do_macro(data[2:])
                    except SwitchHost, e:
                        if self.__vm is not None:
                            self.__vm.handle_close()
                        self.__vm = VMConnector(self, str(e))
                if settings.DEBUG and data[2:] == '6':
                    log.debug('Providing engine debugging info...')
                    log.info('Current state: %s' % self.state)
                    log.info('Username: %s' % self.username)
                    log.info('Udata: %s' % self.udata)
                    log.info('SID: %s' % self.sid)
                    log.info('IP_Addr: %s' % self.ip_addr)
                    log.info('Prompt: %s' % self.prompt)
                    if self.state == 'ic':
                        log.info('OOC SID: %s' % self.ooc.sid)
                        log.info('OOC Admin: %s' % self.ooc.admin)
                        log.info('OOC Staff: %s' % self.ooc.staff)
                        log.info('OOC Designer: %s' % self.ooc.designer)
            else:
                log.debug('Control code: %s' % data[1:])
        elif data[0] == chr(252):
            if data[1] == chr(1):
                if settings.SHOW_VERSIONS:
                    self.transmit(self.version)
                self.transmit(open('banner.txt', 'r').read().replace('\n', '\r\n'))
                self.csi('31m')
                self.transmit("Time since last Hacker's Edge server restart: %s" % uptime())
                count = player_count()
                if count > 0:
                    self.transmit('There are currently %s player(s) connected.' % count)
                self.csi('32m')
        elif data[0] == chr(251):
            self.username, self.__password = data[1:].split(chr(255))
            self.__http = get_user(self, self.username)
        elif data[0] == chr(250):
            if hasattr(self, 'ic'):
                if data[1] == chr(1):
                    log.info('API Request to host %s' % str(data[2:]))
                    if data[2:] not in self.ic.host_list:
                        self.send_status(3)
                        return
                    if self.__vm is not None:
                        self.__vm.handle_close()
                    self.state = 'hexinput'
                    self.ic.hexcode = [str(data[2:])]
        elif data[0] == chr(249):
            if self.mouse:
                if self.state == 'vmtty':
                    if self.__vm is not None:
                        self.__vm.vm_mouse(data[1], data[2], data[3])
        else:
            log.warning('Invalid op code from front-end: %s' % ord(data[0]))
    def do_init(self, data):
        self.ctype, self.ip_addr, self.state = data.split(chr(255))
        log.info('New connection from %s' % self.ip_addr)
        if self.ip_addr in BAN_LIST:
            self.ban_ip(self.ip_addr)
            log.info('Banning IP in global ban list: %s' % self.ip_addr)
            self.handle_close()
            return
        if self.ctype in ('Telnet', 'Web',):
            try:
                self.__http = site_ping(self)
                self.state = 'http_init'
            except:
                self.disco(1)
                self.state = 'null'
                return
    def do_auth(self, data):
        self.username, api_key = data.split(chr(0))
        log.info('Remote AUTH requested for %s' % self.username)
        try:
            if not os.path.exists('players/%s' % self.username):
                raise
            self.ic = IC(self.username, self)
            if not self.ic.chk_apikey(api_key):
                raise
            self.state = 'authok'
            self.send_status(1)
            self.state = 'null'
        except:
            self.state = 'authfail'
            self.send_status(2)
            self.handle_close()
    def http_init(self):
        if settings.SHOW_VERSIONS:
            self.transmit(self.version)
        self.transmit(open('banner.txt', 'r').read().replace('\n', '\r\n'))
        self.csi('31m')
        self.transmit("Time since last Hacker's Edge server restart: %s" % uptime())
        count = player_count()
        if count > 0:
            self.transmit('There are currently %s player(s) connected.' % count)
        self.csi('32m')
        self.login(self.login_syslogin, 'hackersedge login: ')
    def login(self, callback, prompt='Login: ', attempts=3):
        self.show_prompt(prompt)
        self.state = 'login'
        self.cb_login = callback
        self.attempts = attempts
    def do_login(self, data):
        if not self.username:
            if data == '':
                self.show_prompt()
                return
            if not valid_data.match(data):
                if data.startswith('USER '):
                    self.ctype = 'IRC'
                    self.transmit('Welcome %s!' % data.split(':')[1])
                    self.username = data.split(' ')[1]
                    log.debug('Detected connection from IRC client for user %s' % self.username)
                    self.set_prompt('Password: ')
                    self.echo(True)
                    self.__http = get_user(self, self.username)
                    return
                if data.startswith(chr(2)):
                    log.debug('Detected MacTelnet.')
                    self.ctype = 'MacTelnet'
                    self.username = data[13:]
                    log.debug('User sign-in attempt: %s' % self.username)
                    self.set_prompt('Password: ')
                    self.echo(True)
                    self.__http = get_user(self, self.username)
                    return
                if len(data) > 50:
                    log.critical('Buffer overflow attempt by %s' % self.ip_addr)
                    self.transmit(' * Buffer overflow attempt!  You have been temporarily banned.')
                    self.ban_ip(self.ip_addr)
                    self.handle_close()
                    return
                if data.startswith('GET'):
                    log.critical('Blocking potential HTTP bot: %s' % self.ip_addr)
                    self.ban_ip(self.ip_addr)
                    self.handle_close()
                    return
                log.warning('Characters: %s' % ','.join([str(ord(c)) for c in data]))
                if self.abuse_count > 5:
                    self.transmit(' * You have been temporarily banned!')
                    self.ban_ip(self.ip_addr)
                    return
                self.transmit('Please only input lowercase alphanumeric characters!')
                self.abuse_count+=1
                self.show_prompt()
                return
            if data.lower() in ('help', 'new', 'create',):
                self.transmit(' ** Please refer to the website for this...')
                if data.lower() in ('new', 'create',):
                    self.transmit(' * Character accounts are created on your character page.')
                    self.transmit(' * You will need to first create a website account, then')
                    self.transmit(' * Request access to the closed beta to create a character.')
                    self.transmit(' * Once you have a character, you can come back here.')
                self.show_prompt()
                return
            log.info('User sign-in attempt: %s' % data)
            self.username = data
            self.set_prompt('Password: ')
            self.echo(True)
            self.__http = get_user(self, self.username)
        else:
            self.echo(False)
            self.cb_login(data)
    def login_syslogin(self, data):
        if not hasattr(self, 'udata'):
            self.udata = {'password':'None'}
        if self.udata == False:
            self.udata = {'password':'None'}
        if self.username.lower() in HONEYPOT_USERS:
            log.info('HoneyPot user detected: %s' % self.username)
            self.udata = None
            #self.username = None
            #self.show_prompt()
            self.start_honeypot(self.username.lower())
        elif hashlib.md5(data).hexdigest() == self.udata['password'] or settings.DEBUG:
            if is_connected(self.udata['username']):
                if not self.udata['staff']:
                    self.transmit(' ** You are already logged in from another locaton.')
                    self.handle_close()
                    return
            if settings.MAINTENANCE_MODE and not self.udata['staff']:
                self.transmit(" *** Hacker's Edge is currently undergoing routine system maintenance.")
                self.handle_close()
                return
            self.sid = self.udata['username']
            self.ooc = OOC(self.username, self)
            self.transmit(open('motd.txt', 'r').read().replace('\n', '\r\n'))
            self.__http = get_last_login(self, self.username)
            self.state = 'http'
            """
            msgs = check_mail('%s:%s' % (self.udata['mailhost'], self.username))
            if msgs > 0:
                self.notify('You have %s new message(s).' % msgs)
            """
            return
        else:
            self.udata = None
            self.username = None
            self.transmit('Invalid username and/or password.')
            self.attempts -=1
            if self.attempts < 2:
                self.transmit('Have you created a character in your account?')
            if self.attempts < 1:
                self.transmit('Excessive logins attempted, disconnecting...')
                self.handle_close()
                return
            self.show_prompt()
    def do_ic(self, data):
        try:
            cmd = shlex.split(data)
        except ValueError, e:
            self.transmit(' ** %s' % e)
            data = ''
        if data == '':
            pass
        elif data == '@exit' or data == '@exit ':
            self.handle_close()
        elif data[0] == '+':
            self.ooc.plus_cmd(*cmd)
        elif data[0] == '@':
            self.ooc.sys_cmd(*cmd)
        else:
            self.ic.history.append(data)
            self.ic.hpos = len(self.ic.history)
            try:
                self.ic.handle_command(*cmd)
            except SwitchHost, e:
                if self.__vm is not None:
                    self.__vm.handle_close()
                self.__vm = VMConnector(self, str(e))
        if self.state == 'ic':
            self.show_prompt()
    def do_vmtty(self, data):
        if not self.raw_mode:
            if len(data) > 0 and data[0] == '+':
                try:
                    cmd = shlex.split(data)
                except ValueError, e:
                    self.transmit(' ** %s' % e)
                    data = ''
                self.ooc.plus_cmd(*cmd)
                self.show_prompt()
                return
            data+='\n'
        self.__vm.vm_stdin(data)
    def do_ooctty(self, data):
        if not self.raw_mode:
            data+='\n'
        self.ooc.vm_stdin(data)
    def do_hexinput(self, data):
        self.ic.hexcode.append(data)
        if data == ':00000001FF':
            self.state = 'hex_import'
            self.transmit(' * Importing HexCode into %s, please wait...' % self.ic.hexcode[0])
            if self.__vm is not None:
                self.__vm.handle_close()
            self.__vm = VMConnector(self, self.ic.hexcode[0])
    def start_honeypot(self, username, banner=True):
        if username in ('root', 'pi',):
            if banner:
                self.transmit('Last login: Thu Mar 31 22:03:05 2016')
            prompt = '%s@raspberrypi ~ $ ' % self.username
        elif username in ('admin', 'administrator', 'guest',):
            prompt = 'C:/users/%s/My Code/Hacker\'s Edge>' % self.username
        elif username == 'ls':
            self.transmit('Documents  Downloads    Desktop    Music  Pictures  Videos')
            self.transmit('Public     HackersEdge  Templates  BankAccounts.txt')
            self.transmit('Last login: Thu Mar 31 22:03:05 2016')
            prompt = 'hp@cthulhu ~ $ '
        self.cmdcount = 0
        self.state = 'honeypot'
        self.show_prompt(prompt)
    def do_honeypot(self, data):
        self.cmdcount+=1
        if data == 'exit' or data == 'logout':
            self.handle_close()
        if data.lower() in ('ls', 'dir',):
            self.transmit('?SYNTAX ERROR')
        elif data.lower() in ('whoami', 'who', 'w',):
            self.transmit(self.username)
        elif data.lower() in ('su', 'sudo',):
            self.transmit('BAD COMMAND OR FILE FUNCTION')
        elif data != '':
            if self.username.lower() in ('root', 'pi', 'delphi'):
                self.transmit('%s: command not found' % data.split(' ')[0])
            elif self.username.lower() in ('admin', 'administrator', 'pot', 'guest',):
                self.transmit('BAD COMMAND OR FILENAME')
            else:
                self.transmit('?SYNTAX ERROR')
        if data != '':
            log.info('HoneyPot: %s' % data)
        if self.cmdcount == 4:
            self.transmit('  *** Welcome to the Hacker\'s Edge Honey pot! ***  ')
            self.transmit('https://en.wikipedia.org/wiki/Honeypot_%28computing%29')
            self.transmit('\r\nIf you wish to play the game, please create a character account:')
            self.transmit('http://www.hackers-edge.com/accounts/Characters/')
            self.show_prompt('HoneyPot> ')
        else:
            self.show_prompt()
    def vm_result(self, result):
        log.debug('VM Result code: %s' % result)
        if self.state == 'vm_attach':
            if result == 'ONLINE' or result == 'OFFLINE':
                self.__vm.vm_attach(self.ic.storage)
                return
        elif self.state == 'vm_detach':
            if result == 'ONLINE' or result == 'OFFLINE':
                self.__vm.vm_detach(self.ic.storage)
                return
        elif self.state == 'vm_attachments':
            if result == 'ONLINE' or result == 'OFFLINE':
                self.__vm.vm_attachments()
                return
            elif result == 'NOBLKDEV':
                self.transmit(' * Host does not have a block device controller installed.')
            else:
                self.transmit(' * Connected storage:')
                for storage in pickle.loads(result):
                    if storage.startswith('hosts/'):
                        self.transmit('Internal Storage device')
                    elif storage.startswith('players/'):
                        self.transmit('Floppy Disk: %s' % storage.split('/')[-1])
                    else:
                        self.transmit('Removable: %s' % storage)
        if result == 'TERM':
            pass
        elif result == 'ONLINE':
            if self.state == 'vm_boot':
                self.transmit(' * Host is already started.')
            elif self.state == 'vm_halt':
                self.transmit(' * Shutting down host...')
                self.__vm.vm_shutdown()
                return
            elif self.state == 'vm_tty':
                self.__vm.vm_tty()
                self.state = 'vmtty'
                return
            elif self.state == 'vm_install':
                self.transmit(' * Please shutdown the host before proceeding.')
            elif self.state == 'hex_import':
                self.__vm.vm_hex('\n'.join(self.ic.hexcode[1:]))
                return
            elif self.state == 'vm_attach':
                self.__vm.vm_attach(self.ic.storage)
                return
            elif self.state == 'vm_detach':
                self.__vm.vm_detach(self.ic.storage)
                return
        elif result == 'OFFLINE':
            if self.state == 'vm_boot':
                self.transmit(' * Booting host, please wait...')
                self.__vm.vm_boot()
                return
            elif self.state == 'vm_halt':
                self.transmit(' * Host has already been turned off.')
            elif self.state == 'vm_tty':
                self.transmit(' * Host offline, attempting to boot...')
                self.__vm.vm_boot()
                return
            elif self.state == 'vm_install':
                self.__vm.vm_provision('DEFAULT')
                return
            elif self.state == 'hex_import':
                self.transmit(' * Host needs to be running in order to import into memory!')
                self.send_status(2)
            elif self.state == 'vm_attach':
                self.__vm.vm_attach(self.ic.storage)
                return
            elif self.state == 'vm_detach':
                self.__vm.vm_detach(self.ic.storage)
                return
        elif result == 'IPL':
            if self.state == 'vm_boot':
                self.transmit(' * VM has been booted, connecting to TTY...')
                self.__vm.vm_tty()
                self.state = 'vmtty'
                return
            elif self.state == 'vm_tty':
                self.transmit(' * Connecting to TTY...')
                self.__vm.vm_tty()
                self.state = 'vmtty'
                return
        elif result == 'BOOTFAIL':
            self.transmit(' ** Host boot failure.')
        elif result == 'HALT':
            self.transmit(' ** VM has been shutdown.')
        elif result == 'PROVOK':
            if self.state == 'vm_install':
                self.transmit(' * Host has been reinstalled successfully!')
            else:
                self.transmit(' * Host has been configured successfully, attempting to boot...')
                self.__vm.vm_boot()
                return
        elif result == 'PROVERR':
            log.error('Error configuring player host %s' % self.__vm.ip_addr)
            self.transmit(' * There was a problem configuring your host!')
        elif result == 'EXCPT':
            self.transmit(' * There was an error during program execution.')
        elif result == 'NOHOST':
            log.critical('Host allocation issue occurred in IC!')
            self.transmit(' * There was a problem allocating your host!')
            self.__vm = None
            self.state = 'ic'
            self.show_prompt(self.ic.get_prompt())
            return
        elif result == 'HEXOK':
            self.transmit(' * Intel Hex provided has been imported into memory.')
            self.send_status(4)
        elif result == 'HEXFAIL':
            self.transmit(' * There was an error while trying to import the Intel Hex.')
            self.send_status(2)
        elif result == 'ATTACHOK':
            self.transmit(' * Storage device attached.')
            self.ic.remove_storage(self.ic.storage)
            del self.ic.storage
        elif result == 'ATTACHER':
            self.transmit(' * Failed to attach storage device.')
            del self.ic.storage
        elif result == 'DETACHOK':
            self.transmit(' * Storage device detached.')
            self.ic.add_storage(self.ic.storage)
            del self.ic.storage
        elif result == 'DETACHER':
            self.transmit(' * Failed to detach storage device.')
            del self.ic.storage
        self.__vm.handle_close()
        self.__vm = None
        if self.raw_mode:
            self.set_raw(False)
        self.echo(False)
        self.state = 'ic'
        self.show_prompt(self.ic.get_prompt())
    def http_callback(self, result):
        try:
            del self.__http
        except:
            pass
        if self.state == 'http_init':
            if result[0] == 'pong':
                self.http_init()
            else:
                self.disco(1)
                self.state = 'null'
        elif result[0] == 'udata':
            self.udata = pickle.loads(result[1])
            if isinstance(self.udata, dict):
                log.debug('Got udata for: %s' % self.udata['username'])
        elif result[0] == 'last_login':
            last_login = pickle.loads(result[1])
            self.transmit('Last Login: %s' % last_login)
            self.ic = IC(self.username, self)
            self.state = 'ic'
            self.show_prompt(self.ic.get_prompt())
        else:
            self.transmit('You should never see this!')
            log.critical('Invalid HTTP Callback result: %s' % result[0])
            self.state = 'ic'
            self.show_prompt()
    def handle_close(self):
        if self.__close_handled:
            return
        self.__close_handled = True
        if self.__vm is not None:
            self.__vm.close()
            self.__vm = None
        if hasattr(self, 'ic'):
            self.ic.save_history()
        if hasattr(self, 'ooc'):
            self.ooc.kill_vm()
        if self.connected:
            if hasattr(self, 'ooc'):
                del self.ooc
                notify_sessions('%s disconnected.' % self.sid, self.sid)
            if self.ip_addr is not None:
                log.info('[%s]Closing connection from %s' % (len(asyncore.socket_map), self.ip_addr))
            self.close()
    def log_info(self, message, type='info'):
        log.critical(message)

class EngineServer(asyncore.dispatcher):
    """ This is the main telnet server class, the class which listens for incoming connections. """
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        if ':' in settings.ENGINE_SERVER:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            addr = settings.ENGINE_SERVER.split(':')
            self.bind((addr[0], int(addr[1])))
        else:
            self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.bind(settings.ENGINE_SERVER)
        self.listen(5)
        log.info("Listening on UNIX domain socket.")
    def handle_accept(self):
        channel, addr = self.accept()
        c = EngineProtocol(channel)
    def log_info(self, message, type='info'):
        log.critical(message)
