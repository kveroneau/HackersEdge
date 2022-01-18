import logging, shlex, gc, hashlib, threading, urllib, hostops
from datetime import datetime
from sessions import SHM, close_session, ban_session, uptime, player_count, hypervisor
from utils import valid_data, valid_ascii, setup_rank, setup_bank, post2discord
from ooc import OOC
from shell import HackerShell
from databases import userdb
from exceptions import ShellError, SwitchShell, ExecuteBin, CloseSession, VMError, SwitchState, SwitchHost
from mailapp import HackerMail
from mailops import check_mail, send_mail
from settings import SHOW_VERSIONS, DEBUG
from ic import IC

log = logging.getLogger('HackersEdge')

HONEYPOT_USERS = ('root', 'admin', 'administrator', 'pi', 'help', 'new', 'ls', 'guest', 'delphi', 'pot',)

class HackersEdge(object):
    version = "Hacker's Edge Engine v0.11.3 $Revision: 203 $"
    def __init__(self, sid, tty):
        self.sid = sid
        self.tty = tty
        self.state = 'login'
        self.route = []
        self.host = None
        self.connect_time = datetime.isoformat(datetime.now())
        self.username = None
        self.prompt = None
        self.shell = None
        self.compose_data = ''
    def set_prompt(self, prompt):
        self.tty.set_prompt(prompt)
    def transmit(self, data):
        self.tty.transmit(data)
    def echo(self, state):
        self.tty.echo(state)
    def close(self):
        raise CloseSession
    def notify(self, data):
        self.tty.notify(data)
    def on_connect(self):
        try:
            userdb.ping()
        except:
            raise CloseSession("Hacker's Edge is currently offline, please try back later.")
        if SHOW_VERSIONS:
            self.transmit(self.version)
        self.transmit(open('banner.txt', 'r').read().replace('\n', '\r\n'))
        self.tty.csi('31m')
        self.transmit("Time since last Hacker's Edge server restart: %s" % uptime())
        count = player_count()
        if count > 0:
            self.transmit('There are currently %s player(s) connected.' % count)
        self.tty.csi('32m')
        #self.tty.enable_mouse()
        self.login(self.login_syslogin, 'hackersedge login: ')
    def on_disconnect(self):
        log.info('on_disconnect for %s' % self.username)
        close_session(self.sid)
        if self.shell:
            del self.shell
        self.ic.save_history()
        del self.ic
        del self.ooc
        raise CloseSession('Good-bye, please play again!')
    def cbreak(self):
        self.transmit('^C')
        log.info('%s pressed control-C.' % self.username)
        if self.state == 'login':
            self.username = 'delphi'
            self.start_honeypot('pi', False)
            return
            close_session(self.sid)
            raise CloseSession
        elif self.state == 'honeypot':
            close_session(self.sid)
            raise CloseSession
        elif self.state == 'vm':
            hypervisor.kill(self.sid)
        else:
            self.show_prompt()
    def suspend(self):
        self.transmit('^Z')
        log.info('%s pressed control-Z.' % self.username)
        if self.state == 'login':
            self.username = 'pot'
            self.start_honeypot('admin')
            return
            self.transmit(open('server.log','r').read().replace('\n', '\r\n'))
            close_session(self.sid)
            raise CloseSession
        elif self.state == 'honeypot':
            close_session(self.sid)
            raise CloseSession
        elif self.state == 'vm':
            pass
        else:
            self.switch_state('ic', self.ic.get_prompt())
    def eof(self):
        log.info('%s pressed control-D.' % self.username)
        if self.state == 'login':
            close_session(self.sid)
            raise CloseSession
        elif self.state == 'compose':
            self.do_compose('.')
        elif self.state == 'shell':
            self.do_shell('exit')
        elif self.state == 'honeypot':
            raise CloseSession
        elif self.state == 'ic':
            self.on_disconnect()
    @property
    def history(self):
        if self.state == 'shell':
            return self.shell.history
        elif self.state == 'ic':
            return self.ic.history
        return []
    @property
    def hpos(self):
        if self.state == 'shell':
            return self.shell.hpos
        elif self.state == 'ic':
            return self.ic.hpos
        return 0
    @hpos.setter
    def hpos(self, value):
        if self.state in ('shell', 'ic'):
            if value > len(self.history)-1:
                value = len(self.history)
                self.tty.ibuffer = ''
            elif value < 0:
                value = 0
            else:
                self.tty.ibuffer = self.history[value]
            self.tty.cpos = len(self.tty.ibuffer)
        if self.state == 'shell':
            self.shell.hpos = value
        elif self.state == 'ic':
            self.ic.hpos = value
    def tab_completion(self, ibuf):
        if len(ibuf) == 0:
            return []
        if ibuf[0] in ('+', '@'):
            return self.ooc.tab_completion(ibuf)
        elif self.state == 'shell':
            return self.shell.tab_completion(ibuf)
        elif self.state == 'ic':
            return self.ic.tab_completion(ibuf)
        return []
    def esc_up(self):
        if self.state in ('shell', 'ic'):
            self.hpos -=1
    def esc_down(self):
        if self.state in ('shell','ic'):
            self.hpos +=1
    def esc_right(self):
        if self.tty.cpos < len(self.tty.ibuffer):
            self.tty.csi('C')
            self.tty.cpos+=1
    def esc_left(self):
        if self.tty.cpos > 0:
            self.tty.csi('D')
            self.tty.cpos-=1
    def process_esc(self, esc):
        if esc == 'A':
            return self.esc_up()
        elif esc == 'B':
            return self.esc_down()
        elif esc == 'C':
            self.esc_right()
            return True
        elif esc == 'D':
            self.esc_left()
            return True
        elif esc == 'F':
            self.tty.cpos = len(self.tty.ibuffer)
        elif esc == 'H':
            self.tty.cpos = 0
            self.tty.csi('%sD' % len(self.tty.ibuffer))
            return True
        elif esc == 'P':
            log.info('F1')
            pass # F1 pressed.
        elif esc == 'Q':
            pass # F2
        elif esc == 'R':
            pass # F3
        elif esc == 'S':
            if DEBUG:
                self.transmit('DEBUG info:')
                self.transmit('Current state: %s' % self.state)
                self.transmit('Shell set: %s' % ('Yes' if self.shell else 'No'))
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
            log.info('ESC pressed.')
        elif esc[-1] == 'R':
            self.tsize = tuple([int(i) for i in esc[:-1].split(';')])
            log.info('Rows: %s, Cols: %s' % self.tsize)
        elif esc[0] == 'M':
            but = ord(esc[1])-32
            col = ord(esc[2])-32
            row = ord(esc[3])-32
            log.info('Mouse: %s, %s, %s' % (ord(esc[1])-32, ord(esc[2])-32, ord(esc[3])-32))
            hypervisor.mousein(self.sid, but, row, col)
        else:
            log.info('Escape code Unhandled: %s' % esc)
            return
    def show_prompt(self, prompt=None):
        self.tty.pure_raw_mode(False)
        if prompt is not None:
            self.prompt = prompt
        if self.shell:
            self.tty.set_prompt(self.shell.get_prompt())
        else:
            self.tty.set_prompt(self.prompt)
    def switch_state(self, state, prompt):
        self.state = state
        if self.shell:
            self.shell.save_history()
            del self.shell
            self.shell = None
        self.show_prompt(prompt)
    def switch_shell(self, klass):
        self.state = 'shell'
        if self.shell:
            SHM[self.username] = self.shell.udata
            self.shell.save_history()
            log.debug('Shell references: %s' % gc.get_referrers([self.shell]))
            del self.shell
        self.shell = klass(self.username, self)
        if SHOW_VERSIONS:
            self.transmit(self.shell.intro)
        self.show_prompt(self.shell.get_prompt())
    def switch_host(self, ip_addr):
        hypervisor.switch_host(self.sid, ip_addr)
    def connect_host(self, ip_addr):
        self.udata['host'] = ip_addr
        self.udata['route'] = []
        hypervisor.allocate(self.sid)
        self.switch_host(ip_addr)
        hd = hypervisor.host_data(self.sid)
        if hd.has_key('new'):
            log.info('First-time connect to this host: %s' % ip_addr)
            self.transmit('Initializing host...')
            if not hostops.setup_user(self.username, ip_addr, self.udata['mailhost']):
                log.critical('Error setting up user: %s' % self.username)
                self.transmit('There was a slight problem allocating your host on the network...')
                self.transmit("Hacker's Edge will contact you when the issue is resolved.")
                self.switch_state('ic', self.ic.get_prompt())
                return
            hd = hypervisor.host_data(self.sid)
            try:
                setup_rank(self.username)
                setup_bank(self.udata['bank'], self.username)
            except:
                log.critical('Unable to configure user rank and bank.')
            send_mail('chronoboy@96.164.6.6','%s@%s' % (self.username, self.udata['mailhost']), "Welcome to Hacker's Edge %s!" % self.username, 'Congratulations %s, on finding out how to read your email!\n\nYou can give me some feedback by replying back to this, just type "reply".\n' % self.username)
            del hd['new']
            hypervisor.set_host(self.sid)
            self.transmit('Your host has been allocated successfully, connecting...')
        if not hd['online']:
            self.transmit('Host is offline, attempting to boot...')
            if not hypervisor.reboot(self.sid):
                self.transmit('Error booting host, missing system files.')
                self.transmit("Please consult your Hacker's Edge user guide.")
                self.switch_state('ic', self.ic.get_prompt())
                return
            self.shell = HackerShell(self.username, self)
            hypervisor.execute(self.sid)
            self.state = 'vm'
            self.tty.set_prompt('')
        else:
            self.switch_shell(HackerShell)
    def process(self, data):
        if self.state is None:
            return
        try:
            handler = getattr(self, 'do_%s' % self.state, None)
            if handler:
                handler(data)
        except CloseSession:
            raise
        except SwitchState, e:
            self.switch_state(*str(e).split('|'))
        except SwitchHost, e:
            self.connect_host(str(e))
        except:
            import traceback, sys
            send_mail('traceback@%s' % self.state, 'chronoboy@96.164.6.6', '%s: %s' % (sys.exc_info()[0], sys.exc_info()[1]), '\n'.join(traceback.format_tb(sys.exc_info()[2])))
            if self.state == 'editor':
                self.exit_editor('An unknown error occurred, exiting to IC Shell...')
            else:
                self.transmit("An unknown error occurred, exiting to IC shell...")
            log.critical('An error occurred: (%s) %s' % (sys.exc_info()[0], sys.exc_info()[1]))
            if self.shell:
                SHM[self.username] = self.shell.udata
                log.debug('Shell references: %s' % gc.get_referrers([self.shell]))
                del self.shell
                self.shell = None
            self.switch_state('ic', self.ic.get_prompt())
    def login(self, callback, prompt='Login: ', attempts=3):
        self.show_prompt(prompt)
        self.state = 'login'
        self.cb_login = callback
        self.attempts = attempts
    def check_attempts(self):
        pass
    def do_bugfix(self, data):
        self.tty.set_terminator('\r\n')
        self.on_connect()
    def do_login(self, data):
        if not self.username:
            if data == '':
                return
            if not valid_data.match(data):
                if data.startswith('USER '):
                    self.tty.ctype = 'IRC'
                    self.transmit('Welcome %s!' % data.split(':')[1])
                    self.username = data.split(' ')[1]
                    log.info('Detected connection from IRC client for user %s' % self.username)
                    self.tty.set_prompt('Password: ')
                    self.echo(True)
                    return
                if data.startswith(chr(2)):
                    self.tty.ctype = 'MacTelnet'
                    self.username = data[13:]
                    log.info('User sign-in attempt: %s' % self.username)
                    self.tty.set_prompt('Password: ')
                    self.echo(True)
                    return
                if len(data) > 50:
                    log.critical('Buffer overflow attempt by %s' % self.tty.ip_addr)
                    ban_session(self.sid)
                    raise CloseSession('Buffer overflow attempted!')
                if data.startswith('GET'):
                    log.critical('Blocking potential HTTP bot: %s' % self.tty.ip_addr)
                    ban_session(self.sid)
                    raise CloseSession("This isn't an HTTP Server!")
                log.info('Characters: %s' % ','.join([str(ord(c)) for c in data]))
                self.transmit('Please only input alphanumeric characters!')
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
            self.tty.set_prompt('Password: ')
            self.echo(True)
        else:
            self.echo(False)
            self.cb_login(data)
    def login_syslogin(self, data):
        try:
            udata = userdb.get_user(self.username)
            if udata == False:
                udata = {'password':'None'}
                if DEBUG:
                    raise CloseSession('Invalid username in DEBUG mode.')
        except:
            udata = {'password':'None'}
            if DEBUG:
                raise CloseSession('Invalid username in DEBUG mode.')
        if self.username.lower() in HONEYPOT_USERS:
            log.info('HoneyPot user detected: %s' % self.username)
            self.start_honeypot(self.username.lower())
        elif hashlib.md5(data).hexdigest() == udata['password'] or DEBUG:
            if SHM.sessions.has_key(udata['username']):
                if not udata['staff']:
                    SHM.sessions[udata['username']].notify(' ** Attempted login from another location.')
                    self.transmit(' ** You are already logged in from another location.')
                    raise CloseSession(' ** Please disconnect your other character and try again.')
                SHM.sessions[udata['username']].close()
            #self.tty.disable_mouse()
            if SHM.MAINTENANCE_MODE and not udata['staff']:
                self.transmit(" *** Hacker's Edge is currently undergoing routine system maintenance.")
                raise CloseSession(' *** Please try to connect at a later time.')
            post2discord("%s has just logged into Hacker's Edge." % udata['username'])
            self.tty.pure_raw_mode(True)
            SHM[self.username] = udata
            self.udata = udata
            SHM[self.username]['route'] = []
            SHM[self.username]['host'] = udata['ip_addr']
            SHM.update_session(self.sid, udata['username'])
            self.sid = udata['username']
            self.ooc = OOC(self.username, self)
            self.transmit(open('motd.txt', 'r').read().replace('\n', '\r\n'))
            last_login = userdb.get_last_login(self.username)
            self.transmit('Last Login: %s' % last_login)
            msgs = check_mail('%s:%s' % (self.udata['mailhost'], self.username))
            if msgs > 0:
                self.notify('You have %s new message(s).' % msgs)
            self.ic = IC(self.username, self)
            self.switch_state('ic', self.ic.get_prompt())
            return
        else:
            self.username = None
            self.transmit('Invalid username and/or password.')
            self.attempts -=1
            if self.attempts < 2:
                self.transmit('Have you created a character in your account?')
            if self.attempts < 1:
                self.transmit('Excessive logins attempted, disconnecting...')
                #ban_session(self.sid)
                self.tty.close_when_done()
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
        elif data == '@exit':
            self.on_disconnect()
        elif data[0] == '+':
            self.ooc.plus_cmd(*cmd)
        elif data[0] == '@':
            self.ooc.sys_cmd(*cmd)
        else:
            self.ic.history.append(data)
            self.ic.hpos = len(self.ic.history)
            self.ic.handle_command(*cmd)
        self.show_prompt()
    def do_shell(self, data):
        try:
            cmd = shlex.split(data)
        except ValueError, e:
            self.transmit(' ** %s' % e)
            data = ''
        if data == '':
            pass
        elif data == '@exit':
            for host in self.shell.route:
                self.shell.cmd_exit([])
            self.on_disconnect()
        elif data[0] == '+':
            self.ooc.plus_cmd(*cmd)
        elif data[0] == '@':
            self.ooc.sys_cmd(*cmd)
        else:
            try:
                # TODO: This can call a VM address to process actual shell command.
                self.shell.history.append(data)
                self.shell.hpos = len(self.shell.history)
                self.shell.handle_command(*cmd)
            except ShellError, e:
                self.transmit(' ** %s' % e)
            except SwitchShell, e:
                klass = globals()[str(e)]
                self.switch_shell(klass)
                return
            except SwitchState, e:
                self.state = str(e)
            except IOError, e:
                self.transmit('%s' % e)
            except ExecuteBin, e:
                if str(e).endswith('BOOT.SYS'):
                    #self.state = None
                    #self.tty.pure_raw_mode(True)
                    self.transmit('Rebooting...')
                    if not hypervisor.reboot(self.sid):
                        self.transmit('Error booting host, missing system files.')
                        self.transmit("Please consult your Hacker's Edge user guide.")
                        self.switch_state('ic', self.ic.get_prompt())
                        return
                    hypervisor.execute(self.sid)
                    self.state = 'vm'
                    self.tty.set_prompt('')
                    return
                try:
                    fname = hostops.get_file(str(e))
                except:
                    self.transmit('File not found.')
                    self.show_prompt()
                    return
                try:
                    hypervisor.load(self.sid, fname)
                    if len(cmd) == 2:
                        hypervisor.set_param(self.sid, cmd[1])
                    else:
                        hypervisor.set_param(self.sid)
                    hypervisor.execute(self.sid)
                    self.state = 'vm'
                    self.tty.set_prompt('')
                except VMError, e:
                    self.transmit(' ** %s' % e)
                except:
                    raise
            except:
                import traceback, sys
                send_mail('traceback@%s' % self.shell.host, 'chronoboy@96.164.6.6', '%s: %s' % (sys.exc_info()[0], sys.exc_info()[1]), '\n'.join(traceback.format_tb(sys.exc_info()[2])))
                self.transmit("An unknown error occurred, restarting shell...")
                log.critical('An error occurred: (%s) %s' % (sys.exc_info()[0], sys.exc_info()[1]))
                if self.shell.host != 'rescue':
                    self.switch_shell(HackerShell)
                return
        if self.state == 'shell':
            self.show_prompt()
        elif self.state == 'disconnect':
            if self.shell:
                SHM[self.username] = self.shell.udata
                log.debug('Shell references: %s' % gc.get_referrers([self.shell]))
                del self.shell
                self.shell = None
            self.switch_state('ic', self.ic.get_prompt())
        elif self.state == 'compose':
            self.tty.set_prompt('')
        elif self.state == 'editor':
            self.show_editor()
    def do_disconnect(self, data):
        if len(data) > 0 and data[0] == 'y':
            close_session(self.sid)
            del self.ooc
            raise CloseSession
        else:
            self.switch_shell(HackerShell)
    def do_compose(self, data):
        if data == '.':
            self.udata['compose_cb'](self.compose_data)
            self.compose_data = ''
            if self.udata['compose_msg']:
                self.transmit(self.udata['compose_msg'])
            del self.udata['compose_msg']
            del self.udata['compose_cb']
            if self.shell:
                self.state = 'shell'
                self.show_prompt()
            else:
                self.switch_state('ic', self.ic.get_prompt())
            return
        self.compose_data+='%s\n' % data
        self.tty.accept_input = True
    def start_honeypot(self, username, banner=True):
        self.tty.disable_mouse()
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
        self.switch_state('honeypot', prompt)
    def do_honeypot(self, data):
        self.cmdcount+=1
        if data == 'exit' or data == 'logout':
            raise CloseSession
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
    def update_editor(self, new_line):
        if new_line < 0:
            return
        if new_line > len(self.edit_buffer)-1:
            self.edit_buffer.append('')
        if new_line > self.tty.tsize[0]-3:
            #self.tty.esc('D')
            return
        self.edit_line = new_line
        if self.edit_col > len(self.edit_buffer[self.edit_line]):
            self.edit_col = len(self.edit_buffer[self.edit_line])
        self.tty.csi('25;1H')
        self.tty.csi('31;47m')
        self.tty.csi('Kcpos: %s, line: %s, lines: %s' % (self.edit_col, self.edit_line, len(self.edit_buffer)))
        self.tty.csi('37;44m')
    def show_editor(self):
        log.debug('Editor started.')
        self.tty.raw_mode = True
        self.tty.accept_input = True
        self.tty.csi('37;44m')
        self.tty.csi('H')
        self.tty.csi('2J')
        self.tty.csi('30;41m')
        self.tty.csi('K')
        self.transmit('HackerEdit | %s | ESC: Exit without saving | Ctrl-D: Save and exit' % self.udata['fname'].split(':')[1])
        self.tty.csi('37;44m')
        self.tty.csi('2;%sr' % str(self.tty.tsize[0]-1))
        self.tty.csi('B')
        self.edit_buffer = []
        self.edit_line = 0
        self.edit_col = 0
        fname = hostops.get_file(self.udata['fname'], True)
        if hostops.exists(fname):
            self.edit_buffer = open(fname, 'r').read().split('\n')
            for line in self.edit_buffer:
                self.transmit(line)
                self.edit_line+=1
                if self.edit_line>self.tty.tsize[0]:
                    break
            self.edit_line = 0
            self.tty.csi('%s;%sH' % (self.edit_line+2, self.edit_col+1))
        else:
            self.edit_buffer.append('')
        self.tty.enable_mouse()
    def exit_editor(self, message):
        self.tty.disable_mouse()
        self.tty.csi('r')
        self.tty.csi('32;40m')
        self.tty.csi('H')
        self.tty.csi('J')
        self.tty.raw_mode = False
        self.transmit(message)
        self.state = 'shell'
        if 'error' not in message:
            self.show_prompt()
    def do_editor(self, data):
        if data == chr(4):
            self.udata['editor_cb']('\n'.join(self.edit_buffer))
            self.exit_editor('Data has been saved.')
            return
        elif len(data) == 0:
            if self.edit_line < len(self.edit_buffer)-1:
                log.debug('Inserting new line...')
                self.edit_buffer.insert(self.edit_line+1, '')
                l = self.edit_line+1
                for line in self.edit_buffer[self.edit_line+1:]:
                    self.tty.csi('K')
                    self.transmit(line)
                    l+=1
                    if l > self.tty.tsize[0]:
                        break
                self.tty.accept_input = True
            self.update_editor(self.edit_line+1)
            self.tty.csi('%s;%sH' % (self.edit_line+2, self.edit_col+1))
        elif data[0] == chr(27):
            if len(data) == 1:
                self.exit_editor('Data not saved.')
                return
            elif data[2] == 'H':
                self.edit_col = 0
            elif data[2] == 'F':
                self.edit_col = len(self.edit_buffer[self.edit_line])
            elif data[2] == 'A':
                self.update_editor(self.edit_line-1)
            elif data[2] == 'B':
                self.update_editor(self.edit_line+1)
            elif data[2] == 'C':
                self.edit_col+=1
            elif data[2] == 'D':
                self.edit_col-=1
            elif data[2] == 'M':
                if ord(data[3])-32 == 3:
                    log.debug('%s, %s' % (ord(data[5])-32, ord(data[4])-32))
                    self.edit_col = ord(data[4])-33
                    new_line = ord(data[5])-34
                    if new_line > len(self.edit_buffer)-1:
                        new_line = len(self.edit_buffer)
                    self.update_editor(new_line)
                    log.debug('%s,%s' % (self.edit_line, self.edit_col))
                else:
                    log.debug('%s' % ord(data[3]))
            else:
                log.debug('ESC key: %s' % data[2])
            if self.edit_col < 0:
                self.edit_col = 0
            elif self.edit_col > len(self.edit_buffer[self.edit_line]):
                self.edit_col = len(self.edit_buffer[self.edit_line])
            self.tty.csi('%s;%sH' % (self.edit_line+2, self.edit_col+1))
        elif data == chr(127) or data == chr(8):
            if self.edit_col < len(self.edit_buffer[self.edit_line]) and self.edit_col > 0:
                b = list(self.edit_buffer[self.edit_line])
                del b[self.edit_col-1]
                self.edit_buffer[self.edit_line] = ''.join(b)
            elif self.edit_col == 0:
                self.edit_buffer[self.edit_line-1]+=self.edit_buffer[self.edit_line]
                del self.edit_buffer[self.edit_line]
                l = self.edit_line
                for line in self.edit_buffer[self.edit_line:]:
                    self.tty.csi('K')
                    self.transmit(line)
                    l+=1
                    if l > self.tty.tsize[0]:
                        break
                self.edit_line -=1
                self.edit_col = len(self.edit_buffer[self.edit_line])
            else:
                self.edit_buffer[self.edit_line] = self.edit_buffer[self.edit_line][:-1]
                self.tty.csi('2K')
            self.edit_col -=1
            self.tty.csi('%s;1H' % str(self.edit_line+2))
            self.transmit(self.edit_buffer[self.edit_line])
            self.tty.csi('%s;%sH' % (self.edit_line+2, self.edit_col+1))
        elif valid_ascii.match(data) is not None:
            if self.edit_col == len(self.edit_buffer[self.edit_line]):
                self.edit_buffer[self.edit_line] += data
            else:
                b = list(self.edit_buffer[self.edit_line])
                b.insert(self.edit_col, data)
                self.edit_buffer[self.edit_line] = ''.join(b)
            #self.csi('%sC' % len(data))
            self.edit_col +=len(data)
            self.tty.csi('%s;1H' % str(self.edit_line+2))
            self.transmit(self.edit_buffer[self.edit_line])
            self.tty.csi('%s;%sH' % (self.edit_line+2, self.edit_col+1))
        else:
            log.debug('Editor key pressed: %s' % ord(data[0]))
    def do_vm(self, data):
        self.tty.prompt = ''
        hypervisor.stdin(self.sid, data+'\n')
        log.info('Hypervisor STDIN: %s' % data)
