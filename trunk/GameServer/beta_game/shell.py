import logging
from utils import Shell, ipv4, hecmd
from sessions import SHM
from databases import get_host, set_host
from exceptions import ShellError, SwitchShell, CompileError, ExecuteBin, SwitchState
from asm import Assembler
import hostops, mailops, shlex, hashlib, datetime
from settings import SHOW_VERSIONS

log = logging.getLogger('HackerShell')

ATTR_LIST = ['autorun', 'hide', 'logging', 'dns', 'hostname']

class RescueShell(Shell):
    intro = 'RescueShell v0.3'
    host = 'rescue'
    route = []
    def __init__(self, username, engine):
        self.username, self.engine = username, engine
        self.history = []
        self.state = 'shell'
    def transmit(self, data):
        self.engine.transmit(data)
    def get_prompt(self):
        return '%s$ ' % self.username
    def handle_command(self, *cmd):
        if not self.parse_cmd('cmd', False, *cmd):
            self.transmit(' ** Bad command: %s' % cmd[0])
        return self.state
    def cmd_help(self, args):
        self.show_help('cmd')
    def cmd_exit(self, args):
        """ Dummy command, use OOC exit  """
        self.transmit(' *** Use Out-of-character exit command to exit.')
    def cmd_format(self, args):
        """ Reformats the entire host """
        self.transmit('Formatting host...')
        ip_addr = SHM[self.username]['host']
        hd = hostops.get_host(ip_addr)
        hd['files'] = []
        for attr in ATTR_LIST:
            if hd.has_key(attr):
                del hd[attr]
        hd['acl'] = {self.username: 'RWF'}
        hostops.set_host(ip_addr, hd)
        self.transmit('File System has been formatted.')
        self.transmit('Copying over system files...')
        for f in ['BOOT.SYS','KERNEL.SYS','FILEIO.SYS','NETDRV.SYS']:
            hostops.copy_file('96.164.6.147:%s' % f, ip_addr)
        self.transmit('System files copied successfully!')
        self.transmit('Please log out and log back in to boot into host.')

class HackerShell(Shell):
    intro = 'HackerShell v0.8 $Revision: 190 $'
    ACL = {
        'ls': 'R',
        'cat': 'R',
        'rm': 'W',
        'rcp': 'R',
        'halt': 'F',
        'mkfs': 'F',
        'acl': 'F',
        'iptables': 'F',
        'attr': 'F',
        'reboot': 'F',
        'create': 'W',
        'asm': 'W',
        'hexdump': 'R',
        'editor': 'RW',
    }
    def __init__(self, username, engine):
        self.udata = SHM[username]
        self.host = self.udata['host']
        self.route = self.udata['route']
        self.username = username
        self.engine = engine
        self.host_data = get_host(self.host)
        self.state = 'shell'
        self.get_acl()
        try:
            self.history = hostops.open_file('%s:hsh_history' % self.host, 'r').read().split('\n')
        except:
            self.history = []
        self.hpos = len(self.history)
        self.cmdset = None
    def transmit(self, data):
        self.engine.tty.transmit(data)
    def save_history(self):
        hostops.open_file('%s:hsh_history' % self.host, 'w').write('\n'.join(self.history))
    def tab_completion(self, ibuf):
        if self.cmdset is None:
            self.cmdset = []
            for cmd in dir(self):
                if cmd.startswith('cmd_'):
                    self.cmdset.append(cmd[4:])
        result = []
        if ' ' not in ibuf:
            for cmd in self.cmdset:
                if cmd.startswith(ibuf):
                    result.append(cmd)
            if 'R' in self.host_acl:
                for binf in self.host_data['files']:
                    if binf.endswith('.bin') and binf.startswith(ibuf):
                        result.append(binf)
        else:
            cmd = ibuf.split(' ')
            if 'R' in self.host_acl:
                if cmd[0] in ('cat', 'rcp', 'hexdump'):
                    for f in self.host_data['files']:
                        if f.startswith(cmd[1]):
                            result.append(f)
            if 'W' in self.host_acl:
                if cmd[0] == 'asm':
                    for asmf in self.host_data['files']:
                        if asmf.endswith('.asm') and asmf.startswith(cmd[1]):
                            result.append(asmf)
                elif cmd[0] in ('rm', 'editor'):
                    for f in self.host_data['files']:
                        if f.startswith(cmd[1]):
                            result.append(f)                                    
        return result
    def get_prompt(self):
        try:
            hostname = self.host_data['hostname']
        except:
            hostname = self.host
        return '%s@%s> ' % (self.username, hostname)
    def runscript(self, fname, arg=''):
        log.info('runscript %s %s' % (fname, arg))
        f = hostops.open_file('%s:%s' % (self.host,fname), 'r')
        uuid = hashlib.md5('%s' % datetime.datetime.now()).hexdigest()
        if len(self.route) > 0:
            remote = self.route[-1]
            home = self.route[0]
        else:
            remote = ''
            home = self.host
        for cmd in f.readlines():
            cmd = cmd.replace('$v', arg).replace('$uuid', uuid).replace('$remote', remote).replace('$home', home)
            try:
                self.handle_command(*shlex.split(cmd))
            except ValueError, e:
                raise ShellError(str(e))
        f.close()
    def handle_command(self, *cmd):
        self.state = 'shell'
        if len(cmd) == 0:
            return
        log.info('[%s] %s' % (self.username,' '.join(cmd)))
        if self.ACL.has_key(cmd[0]):
            if self.ACL[cmd[0]] not in self.host_acl:
                raise ShellError('Permission denied.')
        cmd = list(cmd)
        if '%s.bin' % cmd[0] in self.host_data['files']:
            cmd[0] = '%s.bin' % cmd[0]
        ext = cmd[0][-4:]
        if ext == '.hsh':
            self.transmit(' ** hsh scripts are soon to be deprecated!')
            try:
                self.runscript(cmd[0], cmd[1])
            except:
                self.runscript(cmd[0], '')
            self.logit('%s ran the script "%s"' % (self.username, cmd[0]))
        elif ext == '.bin':
            raise ExecuteBin('%s:%s' % (self.host,cmd[0]))
        if not self.parse_cmd('cmd', False, *cmd):
            self.transmit(' ** Bad command: %s' % cmd[0])
        return self.state
    def validate_host(self, host):
        if ipv4.match(host):
            return host
        if 'dns' in self.host_data:
            ip_addr = hostops.query_dns(self.host_data['dns'], host)
            if ip_addr is not False:
                return ip_addr
        raise ShellError('Unknown hostname or DNS Error.')
    def get_host(self, ip_addr):
        data = get_host(ip_addr)
        if not data:
            raise ShellError('No route to host.')
        if not data['online']:
            raise ShellError('No route to host.')
        return data
    def get_acl(self):
        if self.username in self.host_data['acl']:
            self.host_acl = self.host_data['acl'][self.username]
        elif 'other' in self.host_data['acl']:
            self.host_acl = self.host_data['acl']['other']
        else:
            self.host_acl = ''
    def check_access(self, ip_addr, host):
        if self.username in host['acl']:
            return
        if 'other' in host['acl']:
            return
        self.logit('Connection refused from %s@%s' % (self.username, self.host), ip_addr, host)
        raise ShellError('Access denied to remote host.')
    def log_enabled(self, data=None):
        try:
            if data is None:
                return self.host_data['logging']
            return data['logging']
        except:
            return False
    def logit(self, msg, ip_addr=None, data=None):
        if self.log_enabled(data):
            if ip_addr is None:
                ip_addr = self.host
            hostops.logit(ip_addr, msg)
    def handle_trigger(self, trigger, action, args):
        handler = getattr(self, 'evt_%s' % action, None)
        if handler:
            handler(trigger, *args)
    def cmd_help(self, args):
        self.show_help('cmd')
    def cmd_exit(self, args):
        """ Logs off the currently connected host. """
        old_host = self.host
        try:
            self.host = self.route.pop()
            SHM.disconnect(old_host, self.host)
            self.logit('Disconnected %s' % self.host, old_host)
        except IndexError:
            self.save_history()
            raise SwitchState('disconnect')
        self.host_data = get_host(self.host)
        self.get_acl()
        self.engine.switch_host(self.host)
        log.info('Disconnect from %s' % old_host)
        self.transmit('Disconnected from host %s.' % old_host)
    def cmd_logoff(self, args):
        """ Logs off the currently connected host. """
        self.cmd_exit(args)
    @hecmd('<ip address>', 1)
    def cmd_rlogin(self, args):
        """ Connect to another host via IP Address. """
        log.info('Try to connect to %s' % args[0])
        ip_addr = self.validate_host(args[0])
        self.transmit('Trying %s...' % ip_addr)
        data = self.get_host(ip_addr)
        #self.check_access(ip_addr, data)
        self.logit('Connection accepted from %s@%s' % (self.username, self.host), ip_addr, data)
        SHM.connected(ip_addr, self.host)
        self.host_data = data
        self.get_acl()
        self.route.append(self.host)
        self.host = ip_addr
        self.udata['host'] = ip_addr
        self.engine.switch_host(ip_addr)
        self.transmit('Connected to %s.' % self.host)
        log.info('Connected to %s' % self.host)
        if data.has_key('triggers'):
            if data['triggers'].has_key('connect'):
                self.handle_trigger('connect', **data['triggers']['connect'])
        if 'autorun' in self.host_data:
            autorun = self.host_data['autorun']
            if autorun['type'] == 'script':
                log.info('Running autorun: %s' % autorun['filename'])
                self.runscript(autorun['filename'])
    def cmd_route(self, args):
        """ Display your current route. """
        data = 'Gateway -> '
        for host in self.route:
            data +='%s -> ' % host
        data +=self.host
        self.transmit(data)
    def cmd_ifconfig(self, args):
        """ Display the IP Address of the currently connected system. """
        self.transmit(self.host)
    def cmd_ls(self, args):
        """ List files available on currently connected system. """
        self.host_data = get_host(self.host)
        self.columnize(self.host_data['files'])
        if self.host_data.has_key('mailboxes'):
            self.columnize(self.host_data['mailboxes'])
    @hecmd('<filename>', 1)
    def cmd_cat(self, args):
        """ Reads a file from the connected system's file system. """
        f = hostops.open_file('%s:%s' % (self.host, args[0]), 'r')
        self.transmit(f.read().replace('\n','\r\n'))
        f.close()
    @hecmd('<filename>', 1)
    def cmd_rm(self, args):
        """ Deletes a file from the connected system's file system. """
        hostops.delete_file('%s:%s' % (self.host, args[0]))
    @hecmd('<file> <remote ip>', 2)
    def cmd_rcp(self, args):
        """ Copy a file from this system to another system you have access to. """
        log.info('Copy file: %s:%s to %s' % (self.host, args[0], args[1]))
        try:
            if args[0] not in self.host_data['files']:
                raise
        except:
            raise ShellError('File not found.')
        ip_addr = self.validate_host(args[1])
        self.transmit('Trying %s...' % ip_addr)
        remote = self.get_host(ip_addr)
        """
        rt = self.chk_firewall(ip_addr, remote, ACTION_LIST['COPY'])
        if rt == 128:
            self.stdout.write('Connection refused.\n')
            self.logit('Firewall blocked cpfile command from %s' % self.host, remote, ip_addr)
            return False
        """
        try:
            acl = remote['acl'][self.username]
        except:
            acl = ''
        try:
            if acl == '':
                acl = remote['acl']['other']
            if 'W' not in acl:
                raise
            if args[0] in remote['files']:
                self.transmit('File already exists on remote system.')
                return
        except:
            self.logit('Copy file %s to host by %s@%s denied.' % (args[0], self.username, self.host), ip_addr, remote)
            raise ShellError('Access denied to remote host.')
        if not hostops.copy_file('%s:%s' % (self.host, args[0]), ip_addr):
            raise ShellError('There was an error during the copy process.')
        self.transmit('The copy operation was successful.')
        self.logit('%s copied file to %s' % (self.username, args[1]))
        self.logit('%s@%s copied %s to this host' % (self.username, self.host, args[0]), ip_addr, remote)
    def cmd_halt(self, args):
        """ Powers of the currently connected system and disconnects. """
        self.transmit('Shutting down system...')
        self.host_data['online'] = False
        set_host(self.host, self.host_data)
        self.cmd_exit([])
    def cmd_mkfs(self, args):
        """ Format a file system on the currently connected system. """
        log.info('Format of %s requested.' % self.host)
        self.host_data['files'] = []
        if len(args) == 2:
            if args[0] == '--kernel':
                self.host_data['files'].append(args[1])
        for attr in ATTR_LIST:
            if self.host_data.has_key(attr):
                del self.host_data[attr]
        self.host_data['acl'] = {self.username: 'RWF'}
        hostops.set_host(self.host, self.host_data)
        self.transmit('File System has been formatted.')
    @hecmd('[user] [perms]')
    def cmd_acl(self, args):
        """ Update the ACL list of the currently connected system. """
        acls = self.host_data['acl']
        if len(args) == 2:
            acls[args[0]] = args[1]
            self.host_data['acl'] = acls
            hostops.set_host(self.host, self.host_data)
            self.get_acl()
            self.logit('%s added %s to the ACL with permissions "%s"' % (self.username, args[0], args[1]))
        elif len(args) == 1:
            try:
                del acls[args[0]]
                self.host_data['acl'] = acls
                hostops.set_host(self.host, self.host_data)
                self.get_acl()
                self.logit('%s removed %s from ACL table' % (self.username, args[0]))
            except:
                self.transmit('User does not exist.')
        else:
            for k,v in acls.items():
                self.transmit('%s = %s' % (k,v))
            self.logit('%s viewed the current ACL table' % self.username)
    def cmdx_iptables(self, args):
        """ View the currently connected system's firewall. """
        pass
    @hecmd('[attribute] [value]')
    def cmd_attr(self, args):
        """ Display or set specific attributes on this host. """
        if len(args) > 0 and args[0] in ATTR_LIST:
            if len(args) == 1:
                try:
                    if args[0] == 'autorun':
                        self.transmit('Autorun: %s' % self.host_data['autorun']['filename'])
                    else:
                        self.transmit('%s: %s' % (args[0], self.host_data[args[0]]))
                except:
                    self.transmit('Attribute not set.')
            elif len(args) == 2:
                if args[0] == 'autorun':
                    autorun = {'type':'script', 'filename':args[1]}
                    self.host_data['autorun'] = autorun
                elif args[0] == 'hide':
                    if args[1] in self.host_data['files']:
                        self.host_data['files'].remove(args[1])
                        if 'hide' not in self.host_data:
                            self.host_data['hide'] = []
                        self.host_data['hide'].append(args[1])
                elif args[0] == 'logging':
                    self.host_data['logging'] = True if args[1] == 'on' else False
                else:
                    self.host_data[args[0]] = args[1]
                hostops.set_host(self.host, self.host_data)
                self.transmit('Attribute set.')
        else:
            self.transmit('Unknown Attribute.')
    @hecmd('<remote host>', 1)
    def cmd_finger(self, args):
        """ Queries a remote host. """
        ip_addr = self.validate_host(args[0])
        remote = self.get_host(ip_addr)
        try:
            self.transmit('Found Hostname: %s' % remote['hostname'])
        except:
            pass
        self.transmit('Trying %s...' % ip_addr)
        """
        rt = self.chk_firewall(ip_addr, remote, ACTION_LIST['QUERY'])
        if rt == 64:
            self.stdout.write('\nConnection refused to QUERY service.\n')
            self.logit('Firewall blocked QUERY attempt from %s' % self.host, data, ip_addr)
            return False
        """
        self.transmit('Connected to remote QUERY service on %s.' % ip_addr)
        self.transmit('Remote users:')
        self.columnize(remote['acl'].keys())
        self.logit('%s QUERIED this host' % self.host, ip_addr, remote)
    @hecmd('<remote host>', 1)
    def cmdx_nmap(self, args):
        """ Query a remote host for open ports. """
        ip_addr = self.validate_host(args[0])
        data = self.get_host(ip_addr)
        self.transmit('Probing %s...' % ip_addr)
        """
        for k,v in ACTION_LIST.iteritems():
            self.stdout.write('%s...' % k)
            rt = self.chk_firewall(ip_addr, data, v)
            self.stdout.write('%s\n' % rt)
        """
    def cmd_whoami(self, args):
        """ Displays your user specific information on the console. """
        self.transmit('LOGNAME=%s' % self.username)
        self.transmit('HOST=%s' % self.host)
        self.transmit('GATEWAY=%s' % self.udata['ip_addr'])
        self.transmit('MAILHOST=%s' % self.udata['mailhost'])
        self.transmit('BANK=%s' % self.udata['bank'])
    def cmd_reboot(self, args):
        """ Reboot the currently connected host. """
        raise ExecuteBin('%s:BOOT.SYS' % self.host)
    def cmd_mail(self, args):
        """ Connects to mail on localhost. """
        mbox = mailops.get_mbox('%s:%s' % (self.host, self.username))
        if mbox is None:
            #self.transmit("The currently connected host doesn't support mail.")
            #self.transmit('To read and/or send mail, please connect to a supported host.')
            #self.transmit('Your default mailbox is currently: %s' % self.udata['mailhost'])
            #return
            self.cmd_rlogin([self.udata['mailhost']])
        raise SwitchShell('HackerMail')
    @hecmd('"<string>"', 1)
    def cmd_echo(self, args):
        self.transmit(args[0])
    @hecmd('<filename>', 1)
    def cmd_create(self, args):
        """ Creates a new text file on this host. """
        self.transmit('Write your text-file and terminate with a period on a line by itself.')
        self.udata['compose_msg'] = 'File has been created.'
        self.udata['compose_cb'] = self.cb_create
        self.udata['fname'] = '%s:%s' % (self.host, args[0])
        raise SwitchState('compose')
    def cb_create(self, data):
        f = hostops.open_file(self.udata['fname'], 'w')
        f.write(data)
        f.close()
        del self.udata['fname']
        self.host_data = get_host(self.host)
    @hecmd('<filename>', 1)
    def cmd_editor(self, args):
        """ Creates or edits an existing file. """
        self.udata['editor_cb'] = self.cb_create
        self.udata['fname'] = '%s:%s' % (self.host, args[0])
        raise SwitchState('editor')
    def cmd_conntrack(self, args):
        """ Shows the connection tracker, displaying connected hosts. """
        if SHM.connhost.has_key(self.host):
            for host in SHM.connhost[self.host]:
                self.transmit(host)
    @hecmd('<hostname>', 1)
    def cmd_nslookup(self, args):
        """ Looks up a hostname via Name Server lookup """
        if not self.host_data.has_key('dns'):
            raise ShellError('This host does not have a DNS server configured!')
        self.transmit('Querying %s...' % self.host_data['dns'])
        ip_addr = self.validate_host(args[0])
        self.transmit('IP Address: %s' % ip_addr)
    def evt_echo(self, trigger, message):
        self.transmit('%s - %s' % (trigger, message))
    @hecmd('<filename>', 1)
    def cmd_asm(self, args):
        """ 65c02 Assembler """
        if args[0] in self.host_data['files']:
            try:
                lines = open(hostops.get_file('%s:%s' % (self.host, args[0])), 'r').read().split('\n')
                inc = []
                for l in range(0,len(lines)-1):
                    if lines[l].upper().startswith('.INC'):
                        inc.append(l)
                offset = 1
                for i in inc:
                    offset-=1
                    #self.transmit('INC Line: %s' % lines[i+offset])
                    fname = lines[i+offset][5:]
                    if fname == args[0]:
                        self.transmit(' ** Cannot import %s into itself!' % fname)
                        return
                    inc_lines = open(hostops.get_file('%s:%s' % (self.host, fname)), 'r').read().split('\n')
                    del lines[i+offset]
                    for line in inc_lines:
                        lines.insert(i+offset,line)
                        offset+=1
                #self.transmit('\r\n'.join(lines))
                #self.transmit('Total includes: %s' % len(inc))
                #return
                asm = Assembler(lines)
                if SHOW_VERSIONS:
                    self.transmit(asm.version)
                self.transmit('Assembling...')
                asm.assemble()
                if asm.outfile is None:
                    binf = '%s.bin' % args[0][:-4]
                else:
                    binf = asm.outfile
                asm.savebin(hostops.get_file('%s:%s' % (self.host, binf), create=True))
                if asm.result != '':
                    self.transmit(asm.result)
                else:
                    self.transmit('No result...')
            except CompileError, e:
                self.transmit('Compile Error: %s' % e)
            self.host_data = get_host(self.host)
    @hecmd('<filename>', 1)
    def cmd_hexdump(self, args):
        """ Hex dumps a file """
        if args[0] in self.host_data['files']:
            out = ''
            bc = 0
            data = hostops.open_file('%s:%s' % (self.host, args[0]), 'r').read()
            for b in data:
                bc +=1
                out += ' %4s' % hex(ord(b))
                if bc > 16:
                    self.transmit(out)
                    out, bc = '', 0
            if out != '':
                self.transmit(out)
    def cmd_clear(self, args):
        """ Clears the screen and homes the cursor """
        #self.engine.tty.csi('37;44m')
        self.engine.tty.csi('H')
        self.engine.tty.csi('2J')
