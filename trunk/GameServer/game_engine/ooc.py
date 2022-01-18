import logging, os, threading, asyncore, settings, pickle, StringIO, mmap, zipfile, hashlib
from sessions import notify_sessions, kick_all, connected_users, vm_list
from utils import Shell, hecmd, ipv4, valid_data
from chat import channels
from databases import get_host, hosts
from connector import VMConnector
from economy import economy
from exceptions import EngineError
from ConfigParser import SafeConfigParser
from intelhex import IntelHex

log = logging.getLogger('OOC')

class OOC(Shell):
    version = 'HackerOOC v1.3.2 $Rev: 325 $'
    def __init__(self, username, engine):
        self.is_tty = True
        self.username, self.engine = username, engine
        if settings.SHOW_VERSIONS:
            self.transmit(self.version)
            self.transmit(economy.version)
        self.sid = self.engine.udata['username']
        self.admin = self.engine.udata['admin']
        self.staff = self.engine.udata['staff']
        self.designer = self.engine.udata['designer']
        self.channels = ['public']
        self.cmdset = None
        if self.admin:
            notify_sessions('[%s] Game creator logged on.' % self.sid, self.sid)
            # TODO: Add HomeCU notification for logins.
        elif self.staff:
            notify_sessions('[%s] Game moderator logged on.' % self.sid, self.sid)
        elif self.designer:
            notify_sessions('[%s] Game mission designer logged on.' % self.sid, self.sid)
        else:
            notify_sessions('[%s] Player logged on.' % self.sid, self.sid)
        channels['public'].join(self.sid)
        self.__vm = None
        economy.cache_xp(username)
    def __del__(self):
        log.debug('Removing OOC for %s' % self.sid)
        for channel in self.channels:
            channels[channel].leave(self.sid)
    def kill_vm(self):
        if self.__vm is not None:
            self.__vm.handle_close()
            self.__vm = None
    def brk_vm(self):
        if self.__vm is not None:
            self.__vm.vm_interrupt()
    def tab_completion(self, ibuf):
        if self.cmdset is None:
            self.cmdset = []
            for cmd in dir(self):
                if cmd.startswith('plus_'):
                    func = getattr(self, cmd)
                    if func.__doc__ is None:
                        continue
                    admin = getattr(func, 'admin', False)
                    staff = getattr(func, 'staff', False)
                    designer = getattr(func, 'designer', False)
                    if admin and not self.admin:
                        continue
                    if staff and not self.staff:
                        continue
                    if designer and not self.designer:
                        continue
                    self.cmdset.append('+'+cmd[5:])
                elif cmd.startswith('sys_'):
                    func = getattr(self, cmd)
                    if func.__doc__ is None:
                        continue
                    admin = getattr(func, 'admin', False)
                    staff = getattr(func, 'staff', False)
                    designer = getattr(func, 'designer', False)
                    if admin and not self.admin:
                        continue
                    if staff and not self.staff:
                        continue
                    if designer and not self.designer:
                        continue
                    self.cmdset.append('@'+cmd[4:])
        result = []
        if ' ' not in ibuf:
            for cmd in self.cmdset:
                if cmd.startswith(ibuf):
                    result.append(cmd)
        return result
    def transmit(self, data):
        self.engine.transmit(data)
    def stdout(self, data):
        self.engine.stdout(data)
    def csi(self, data):
        self.engine.csi(data)
    def set_prompt(self, data):
        self.engine.set_prompt(data)
    def show_prompt(self, data):
        self.engine.show_prompt(data)
    def echo(self, state):
        self.engine.echo(state)
    def set_raw(self, state):
        self.engine.set_raw(state)
    def set_mouse(self, state):
        self.engine.set_mouse(state)
    def prov_hex(self, description, hexcode, block):
        sfile = 'storage/%s' % self.__prov.get('storage', 'name')
        self.transmit(' * Loading Intel Hex formatted %s...' % description)
        try:
            sio = StringIO.StringIO(hexcode)
            h = IntelHex(sio)
            self.tty.transmit(' * Checking segments used...')
            segs = h.segments()
            if len(segs) == 1:
                segrange = segs[0]
                self.transmit(' * %s starting address is %s' % (description, hex(segrange[0])))
                size = segrange[1]-segrange[0]
                self.transmit(' * Total %s size is %s' % (description, hex(size)))
                f = open(sfile, 'r+b')
                f.seek(block*256)
                for addr in h.addresses():
                    f.write(chr(h[addr]))
                f.close()
            else:
                self.transmit(' * Multi-segment Intel Hex is not supported for flat binary files.')
        except:
            raise
    def prov_get(self, section, option, last=False):
        if self.__prov.has_option(section, option):
            self.__provmode = option
            self.__http = hosts(self, 'get_file', self.__prov.get(section, option))
            return True
        if last:
            self.engine.state = 'ic'
        return False
    def http_callback(self, result):
        del self.__http
        if result[0] == 'get_host':
            self.engine.state = 'ic'
            host = pickle.loads(result[1])
            self.transmit('Host data: %s' % host)
        elif result[0] == 'get_template':
            if result[1] == 'ERR':
                self.transmit(' * Template requested not found.')
            elif self.engine.state == 'ooc_mkos':
                self.transmit(' * Generating storage disk from template...')
                fp = StringIO.StringIO(result[1])
                self.__prov = SafeConfigParser()
                self.__prov.readfp(fp, 'storage.ini')
                fp.close()
                del fp
                if self.__prov.has_section('storage'):
                    sfile = 'storage/%s' % self.__prov.get('storage', 'name')
                    size = self.__prov.getint('storage', 'size')*1024
                    open(sfile, 'w+b').write('\x00'*size)
                    if self.__prov.has_option('storage', 'hexfile'):
                        hexfile = self.__prov.get('storage', 'hexfile')
                        self.transmit(' * Provisioning RAW storage device using hex file %s...' % hexfile)
                        self.__http = hosts(self, 'get_file', hexfile)
                        return
                    elif self.__prov.has_option('storage', 'bootloader'):
                        hexfile = self.__prov.get('storage', 'bootloader')
                        self.transmit(' * Importing bootloader from Intel Hex...')
                        self.__http = hosts(self, 'get_file', hexfile)
                    else:
                        self.transmit(' * Hexfile not provided in storage template.')
                else:
                    self.transmit(' * Template has no storage section.')
            else:
                self.transmit(result[1])
            self.engine.state = 'ic'
        elif result[0] == 'get_file':
            if result[1] == 'ERR':
                self.transmit(' * Requested provisioner file not found.')
                self.engine.state = 'ic'
            else:
                if self.__prov.has_option('storage', 'hexfile'):
                    sfile = 'storage/%s' % self.__prov.get('storage', 'name')
                    try:
                        sio = StringIO.StringIO(result[1])
                        h = IntelHex(sio)
                        f = open(sfile, 'r+b')
                        m = mmap(f.fileno(), 0)
                        for addr in h.addresses():
                            m[addr] = chr(h[addr])
                        m.close()
                        f.close()
                    except:
                        raise
                elif self.__prov.has_option('storage', 'bootloader'):
                    self.prov_hex('Bootloader', result[1], 0)
                    if self.__prov.has_option('filesystem', 'fstype'):
                        if self.__prov.get('filesystem', 'fstype') == 'hardcoded':
                            pass
                self.engine.state = 'ic'
        elif result[0] == 'make_available':
            log.debug('Made host available in pool')
            return
        elif result[0] == 'set_designer':
            log.debug('Mission designer associated with host')
            return
        elif result[0] == 'host_pool':
            self.engine.state = 'ic'
            self.transmit('Available hosts to @prov:')
            self.transmit('\r\n'.join(result[1].split('|')))
        self.engine.show_prompt()
    def vm_result(self, data):
        if self.engine.state == 'vmstats':
            self.engine.state = 'ic'
            self.transmit('VM6502 Count: %s' % ord(data[0]))
            self.transmit('VM6502 Memory: %s' % data[1:])
            self.__vm.handle_close()
            self.__vm = None
        elif self.engine.state == 'vmhostdata':
            if data == 'ONLINE' or data == 'OFFLINE':
                self.__vm.vm_hostdata()
                return
            self.engine.state = 'ic'
            hd = pickle.loads(data)
            for k,v in hd.items():
                self.transmit('%s: %s' % (k,str(v)))
            self.__vm.handle_close()
            self.__vm = None
        elif self.engine.state == 'vm_boot':
            if data == 'ONLINE':
                self.transmit(' * Host is already booted up.')
            elif data == 'OFFLINE':
                self.transmit(' * Host not booted yet.')
                self.__vm.vm_boot()
                return
            elif data == 'NOHOST':
                self.transmit(' * Host does not exist.')
            elif data == 'IPL':
                self.transmit(' * IPL was completed successfully.')
                self.__vm.vm_tty()
                self.engine.state = 'ooctty'
                return
            elif data == 'BOOTFAIL':
                self.transmit(' * Host boot failed...')
            elif data == 'PROVOK':
                self.transmit(' * Provision was successful!')
                self.__vm.vm_boot()
                return
            elif data == 'PROVERR':
                self.transmit(' * There was a problem while configuring your host.')
            elif data == 'EXCPT':
                self.transmit(' * The processor throw an exception.')
            else:
                self.transmit(' * Invalid VM result: %s' % data)
            self.engine.state = 'ic'
            self.__vm.handle_close()
            self.__vm = None
        elif self.engine.state == 'vm_halt':
            if data == 'ONLINE':
                self.transmit(' * Host booted, attempting shutdown...')
                self.__vm.vm_shutdown()
                return
            elif data == 'OFFLINE':
                self.transmit(' * Host is already shutdown.')
                self.__vm.handle_close()
                self.__vm = None
            elif data == 'NOHOST':
                self.transmit(' * Host does not exist.')
                self.__vm.handle_close()
                self.__vm = None
            elif data == 'HALT':
                self.transmit(' * Host shutdown successfully.')
                self.__vm.handle_close()
                self.__vm = None
            self.engine.state = 'ic'
        elif self.engine.state == 'vm_prov':
            if data == 'ONLINE':
                self.transmit(' * Host is online, please halt the host first!')
                self.__vm.handle_close()
                self.__vm = None
            elif data == 'OFFLINE':
                self.transmit(' * Host offline, starting provision process...')
                self.__vm.vm_provision(self.prov_tmpl)
                return
            elif data == 'NOHOST':
                self.transmit(' * Host does not exist.')
                #self.__vm.handle_close()
                self.__vm = None
            elif data == 'PROVOK':
                self.transmit(' * Provisioning was successful!')
                self.__vm.handle_close()
                self.__http = hosts(self, 'set_designer', str(self.__vm.ip_addr), str(self.sid))
                host_list = list(self.engine.ic.host_list)
                if self.__vm.ip_addr not in host_list:
                    host_list.append(self.__vm.ip_addr)
                    self.engine.ic.host_list = host_list
                self.__vm = None
            elif data == 'PROVERR':
                self.transmit(' * Error with provisioning!')
                self.__vm.handle_close()
                self.__vm = None
            elif data == 'EXCPT':
                self.transmit(' * The processor throw an exception.')
                self.__vm.handle_close()
                self.__vm = None
            self.engine.state = 'ic'
        elif self.engine.state == 'vm_mkhost':
            if data == 'ONLINE' or data == 'OFFLINE':
                self.transmit(' * Host already exists.')
                self.__vm.handle_close()
                self.__vm = None
            elif data == 'NOHOST':
                self.transmit(' * Creating host...')
                self.__vm.vm_mkhost()
                return
            elif data == 'MKHOST':
                self.transmit(' * Host has been created.')
                #self.__vm.handle_close()
                self.__http = hosts(self, 'make_available', self.__vm.ip_addr)
                self.__vm = None
            elif data == 'MKERR':
                self.transmit(' * There was a problem with host creation.')
                #self.__vm.handle_close()
                self.__vm = None
            self.engine.state = 'ic'
        elif self.engine.state == 'ooctty':
            if data == 'HALT':
                self.transmit(' ** VM has been shutdown.')
                self.__vm.handle_close()
                self.__vm = None
                self.engine.state = 'ic'
            else:
                log.error('Got unhandled result for ooctty: %s' % data)
        elif self.engine.state == 'vm_exec':
            log.debug('Arrived with result %s' % data)
            if data == 'ONLINE':
                self.__vm.vm_exec(int(self.__vm.params[0], 16), self.__vm.params[1], int(self.__vm.params[2]), int(self.__vm.params[3]))
                return
            elif data == 'OFFLINE':
                self.transmit(' * Host is not online, cannot proceed.')
                self.__vm.handle_close()
                self.__vm = None
                self.engine.state = 'ic'
            elif data == 'EXECOK':
                self.transmit(' * Sent EXEC request, awaiting response...')
                return
            elif data == 'EXECER':
                self.transmit(' * Unable to perform EXEC request on this host.')
                self.transmit(' * Please check that interrupts are enabled and the vector is set.')
                self.__vm.handle_close()
                self.__vm = None
                self.engine.state = 'ic'
        self.engine.show_prompt(self.engine.ic.get_prompt())
    def exec_result(self, ip_addr, regA, regX, regY):
        log.debug('EXEC Result for %s [%s,%s,%s]' % (ip_addr, regA, regX, regY))
        self.transmit('Remote Execution results:')
        self.transmit('A=%s X=%s Y=%s' % (hex(regA), hex(regX), hex(regY)))
        self.__vm.handle_close()
        self.__vm = None
        self.engine.state = 'ic'
        self.engine.show_prompt()
    def vm_stdin(self, data):
        self.__vm.vm_stdin(data)
    def plus_cmd(self, *cmdline):
        self.state = 'shell'
        try:
            if not self.parse_cmd('plus', True, *cmdline):
                self.transmit(' ** Use +help to understand the OOC commands.')
        except EngineError, e:
            self.transmit(' ** %s' % str(e))
        except:
            if settings.DEBUG:
                raise
            self.transmit(' ** Unable to execute OOC command.')
            log.critical('Exception while running: %s' % ' '.join(cmdline))
    def sys_cmd(self, *cmdline):
        self.state = 'shell'
        try:
            if not self.parse_cmd('sys', True, *cmdline):
                self.transmit(' ** Use @help to understand the OOC system commands.')
        except EngineError, e:
            self.transmit(' ** %s' % str(e))
        except:
            if settings.DEBUG:
                raise
            self.transmit(' ** Unable to execute OOC command.')
            log.critical('Exception while running: %s' % ' '.join(cmdline))
    def plus_help(self, args):
        self.show_help('plus', '+')
    def sys_help(self, args):
        self.show_help('sys', '@')
    def sys_exit(self, args):
        """ Exits the Hacker's Edge network returning to reality """
        pass # Handled by main code.
    def plus_who(self, args):
        """ Display who is currently playing Hacker's Edge online """
        for s in asyncore.socket_map.values():
            if s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
                if s.state != 'login':
                    try:
                        idle = '<Away>' if s.away_mode else ''
                        self.transmit('{0:<20} {1}\t{2}\t{3}'.format(s.sid,s.connect_time,s.ctype,idle))
                    except:
                        pass
                elif self.staff:
                    try:
                        idle = '<Away>' if s.away_mode else ''
                        self.transmit('{0:<20} {1}\t{2}\t{3}'.format(s.sid,s.connect_time,s.ctype,idle))
                    except:
                        pass
        if self.staff:
            self.transmit(' * Non-connected players:')
            for s in asyncore.socket_map.values():
                if not s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
                    try:
                        self.transmit('{0:<20} {1}\t{2}\t{3}'.format(s.sid,s.connect_time,s.ctype))
                    except:
                        self.transmit('Data error...')
                        s.close()
    @hecmd('<user> <message>', 2)
    def plus_page(self, args):
        """ Sends a private message to another player who is online. """
        found = False
        for s in asyncore.socket_map.values():
            if s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
                found = True
                s.notify('[%s] %s' % (self.sid, args[1]))
                break
        if not found:
            self.transmit('The user "%s" is not online.' % args[0])
    def sys_mem(self, args):
        """ Display the current server memory usage for Hacker's Edge """
        status = open('/proc/%s/status' % os.getpid(),'r').read()
        rssi = status.index('VmRSS:')
        rss = status[rssi:status.index('\n',rssi)]
        self.transmit('%s' % rss)
    sys_mem.admin = True
    def sys_notice(self, args):
        """ Send a system notice to all online users """
        notify_sessions('NOTICE: %s' % args[0], self.sid)
    sys_notice.staff = True
    def sys_blockip(self, args):
        """ Adds an IP address into the blocklist """
        self.engine.ban_ip(args[0])
    sys_blockip.admin = True
    def sys_unblockip(self, args):
        """ Removes an IP address from the blocklist """
        self.engine.unban_ip(args[0])
    sys_unblockip.staff = True
    def sys_blocklist(self, args):
        """ Displays the current list of blocked IP addresses """
        self.engine.get_ban_list()
    sys_blocklist.staff = True
    def sys_pid(self, args):
        """ Displays server's PID. """
        self.transmit('%s' % os.getpid())
    sys_pid.admin = True
    def sys_whoami(self, args):
        """ Displays your user information. """
        self.transmit('Real username: %s' % self.sid)
        self.transmit('Character logged in as: %s' % self.username)
        if self.admin:
            self.transmit('You have SuperUser access rights.')
        elif self.staff:
            self.transmit('You have moderator access rights.')
        elif self.designer:
            self.transmit('You have mission designer access rights.')
        self.transmit('Home host: %s' % self.engine.udata['ip_addr'])
        self.transmit('Mail host: %s' % self.engine.udata['mailhost'])
        self.transmit('Bank host: %s' % self.engine.udata['bank'])
    def sys_chan(self, args):
        """ Chat channel management command """
        if len(args) == 0:
            for name, chan in channels.items():
                self.transmit(' %15s   %s' % (name, chan.description))
            self.transmit('')
            self.transmit('Use @chan join <channel> to join a channel.')
            self.transmit('Use @chan leave <channel> to leave a channel.')
            self.transmit('Use @chan list <channel> to view users in channel.')
        elif len(args) == 1:
            self.transmit('You are part of the following channels:')
            self.transmit(', '.join(self.channels))
        elif len(args) == 2:
            if args[0] == 'join':
                if args[1] in self.channels:
                    self.transmit(' ** You are already part of this channel.')
                    return
                if channels.has_key(args[1]):
                    channels[args[1]].join(self.sid)
                    self.channels.append(args[1])
                else:
                    self.transmit(' ** The channel "%s" does not exist.' % args[1])
            elif args[0] == 'leave':
                if args[1] in self.channels:
                    channels[args[1]].leave(self.sid)
                    self.channels.remove(args[1])
                else:
                    self.transmit(' ** You cannot leave a channel you are not part of.')
            elif args[0] == 'list':
                if channels.has_key(args[1]):
                    self.transmit('The following users are in "%s":' % args[1])
                    self.transmit(', '.join(channels[args[1]].users))
                else:
                    self.transmit(' ** The channel "%s" does not exist.' % args[1])
        else:
            self.transmit(' ** Inappropriate amount of arguments.')
    @hecmd('<chat message>', 1)
    def plus_p(self, args):
        """ Say something in the "Public" chat channel """
        if 'public' not in self.channels:
            self.transmit(' ** You need to join the public channel before you can chat.')
            return
        channels['public'].say(args[0], self.sid)
    @hecmd('<chat message>', 1)
    def plus_k(self, args):
        """ Say something in the "kernel" chat channel """
        if 'kernel' not in self.channels:
            self.transmit(' ** You need to join the kernel channel before you can chat.')
            return
        channels['kernel'].say(args[0], self.sid)
    @hecmd('<chat message>', 1)
    def plusx_i(self, args):
        """ Say something in the "IRC" chat channel """
        if 'irc' not in self.channels:
            self.transmit(' ** You need to join the IRC channel before you can chat.')
            return
        channels['irc'].say(args[0], self.sid)
    @hecmd('<chat message>', 1)
    def plusx_g(self, args):
        """ Say something in the "Gopher" chat channel """
        if 'gopher' not in self.channels:
            self.transmit(' ** You need to join the IRC channel before you can chat.')
            return
        channels['gopher'].say(args[0], self.sid)
    @hecmd('<chat message>', 1)
    def plusx_s(self, args):
        """ Say something in the "SDF" chat channel """
        if 'sdf' not in self.channels:
            self.transmit(' ** You need to join the IRC channel before you can chat.')
            return
        channels['sdf'].say(args[0], self.sid)
    def sys_log(self, args):
        """ Displays the RAW server log """
        if len(args) == 0:
            self.transmit(open('server.log','r').read().replace('\n','\r\n'))
        else:
            for line in open('server.log','r').readlines():
                if args[0] in line:
                    self.transmit(line.replace('\n', ''))
    sys_log.admin = True
    def sys_vmlog(self, args):
        """ Displays the 65c02 VM log file """
        if len(args) == 0:
            self.transmit(open('vm6502.log','r').read().replace('\n','\r\n'))
        else:
            for line in open('vm6502.log','r').readlines():
                if args[0] in line:
                    self.transmit(line.replace('\n', ''))
    sys_vmlog.designer = True        
    @hecmd('<ip addr> <connector>',2, admin=True)
    def sys_mkhost(self, args):
        """ Creates a new host """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter in a valid IP address.')
            return
        self.engine.state = 'vm_mkhost'
        self.__vm = VMConnector(self, args[0])
        self.__vm.connector = args[1]
        """
        if not self.admin:
            allow = False
            this = get_host(SHM[self.username]['host'])
            if this.has_key('netmod') and this['netmod'] == self.username:
                sn1 = '.'.join(args[0].split('.')[:3])
                sn2 = '.'.join(SHM[self.username]['host'].split('.')[:3])
                if sn1 == sn2:
                    allow = True
            if not allow:
                self.transmit(' ** You are not the in-game moderator of this network.')
                return
        data = {'files':[],
                'acl':{self.username:'RWF'},
                'online':True,
                'netmod':self.username}
        if not set_host(args[0], data):
            self.transmit(' ** There was an error setting up the host.')
            return
        self.transmit('Copying over system files...')
        for f in ['BOOT.SYS','KERNEL.SYS','FILEIO.SYS','NETDRV.SYS']:
            copy_file('96.164.6.147:%s' % f, args[0])
        self.transmit('The host was successfully created.')
        """
    @hecmd('<ip addr>', 1, staff=True)
    def sys_boot(self, args):
        """ Boots up a host """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        self.transmit('Booting host...')
        self.engine.state = 'vm_boot'
        self.__vm = VMConnector(self, args[0])
    @hecmd('<ip addr>', 1, staff=True)
    def sys_halt(self, args):
        """ Shuts down a host """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        self.transmit('Shutting down host...')
        self.engine.state = 'vm_halt'
        self.__vm = VMConnector(self, args[0])
    @hecmd('<ip addr> <file>', 2, staff=True)
    def sysx_pushfile(self, args):
        """ Pushes a single file to a host. """
        #ip_addr = SHM[self.username]['host']
        #host_data = get_host(ip_addr)
        #if args[1] not in host_data['files']:
        #    self.transmit(' ** The file does not exist on current host.')
        #    return
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        host = get_host(args[0])
        if not host:
            self.transmit(' ** The IP address provided is not valid.')
            return
        if not host['online']:
            self.transmit(' ** The host is not online.')
            return
        self.transmit('Pushing %s to %s...' % (args[1], args[0]))
        #copy_file('96.164.6.147:%s' % args[1], args[0])
        self.transmit('Operation complete.')
    @hecmd('<ip addr>', 1, staff=True)
    def sys_host(self, args):
        """ Views host metadata for debugging purposes. """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        self.engine.state = 'vmhostdata'
        self.__vm = VMConnector(self, args[0])
    def plus_stats(self, args):
        """ Displays your character stats """
        self.transmit('Experience Points: %s' % economy[self.username])
        #self.transmit('Credits: %s' % get_balance(udata['bank'], self.username))
    def plus_notify(self, args):
        """ Toggle live notifications """
        if self.engine.live_notification:
            self.engine.live_notifications(False)
            self.engine.live_notification = False
            self.transmit(' * Live notifications turned off.')
        else:
            self.engine.live_notifications(True)
            self.engine.live_notification = True
            self.transmit(' * Live notifications turned on.')
    def plus_away(self, args):
        """ Sets AFK/Away mode """
        self.engine.set_away_mode()
        self.transmit(' * Away mode has been enabled, your terminal will beep on notifications.')
    def sys_stats(self, args):
        """ Provides server stats. """
        vms = vm_list()
        self.transmit('Current sessions: %s' % ', '.join(connected_users()))
        self.transmit('VM Count: %s' % len(vms))
        self.transmit('Threads: %s' % threading.active_count())
        self.transmit('VM Hosts: %s' % ', '.join(vms))
        self.transmit('ASyncore channels: %s' % len(asyncore.socket_map))
        for channel in asyncore.socket_map.items():
            self.transmit('%s: %s' % channel)
        self.engine.state = 'vmstats'
        if self.__vm is not None:
            self.__vm.handle_close()
        self.__vm = VMConnector(self, 'VMSTATS')
    sys_stats.admin = True
    """
    def plus_idle(self, args):
        "" Sets idle mode when in a telnet client. ""
        if SHM.sessions[self.sid].ctype in ('Telnet', 'MacTelnet'):
            log.info('Idle enabled by %s' % self.username)
            SHM.sessions[self.sid].away_mode = True
            self.transmit(' * Idle mode enabled.')
        else:
            self.transmit(' * This command can only be in a Telnet session.')
    """
    def sys_maintenance(self, args):
        """ Puts Hacker's Edge into Maintenance mode. """
        if settings.MAINTENANCE_MODE:
            log.info('Maintenance mode turned off by %s' % self.username)
            settings.MAINTENANCE_MODE = False
            self.transmit(' * Maintenance mode turned off.')
            return
        log.critical('Maintenance mode enabled by %s' % self.username)
        settings.MAINTENANCE_MODE = True
        self.transmit(' * Turning maintenance mode on, kicking users...')
        kick_all()
        self.transmit(' * Maintenance mode enabled.')
    sys_maintenance.admin = True
    @hecmd('<username> <reason>', 2, staff=True)
    def sys_kick(self, args):
        """ Kicks a user off the server. """
        log.critical('KICK %s "%s" by %s' % (args[0], args[1], self.username))
        found = False
        for s in asyncore.socket_map.values():
            if s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
                try:
                    if s.sid == args[0]:
                        if args[0] == 'kveroneau':
                            s.notify(' ** %s attempted to kick you!' % self.sid)
                            self.transmit(' ** Access denied to kicking %s.' % args[0])
                            self.transmit(' ** Your moderator rights have been revoked.')
                            self.staff = False
                            self.engine.ban_ip(self.engine.ip_addr)
                            return
                        self.engine.ban_ip(s.ip_addr)
                        s.transmit(' ** You have been kicked: %s' % args[1])
                        s.handle_close()
                        self.transmit(' * User has been kicked from game server.')
                        found = True
                except:
                    pass
        if not found:
            self.transmit(' * User is not logged in.')
    @hecmd('<niceness>', 1, admin=True)
    def sys_nice(self, args):
        """ Change the nice level of the GameServer process. """
        try:
            r=os.nice(int(args[0]))
            self.transmit(' * New nice level: %s' % r)
        except:
            self.transmit(' * An error occured while attempting to set nice level.')
    def sys_terminate(self, args):
        """ Shuts down the Hacker's Edge game server. """
        asyncore.close_all()
    sys_terminate.admin = True
    def sys_stopserver(self, args):
        """ Stops the Hacker's Edge game servers from taking new connections. """
        for channel in asyncore.socket_map.values():
            if channel.accepting:
                channel.close()
    sys_stopserver.admin = True
    @hecmd('<template>', 1, designer=True)
    def sys_template(self, args):
        """ Display a host template from the mission designer. """
        self.__http = hosts(self, 'get_template', args[0])
        self.engine.state = 'http'
    @hecmd('<ip addr> <template>', 2, designer=True)
    def sys_prov(self, args):
        """ Provision a specific host with a template """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        self.transmit('Provisoning host...')
        self.engine.state = 'vm_prov'
        self.prov_tmpl = args[1]
        self.__vm = VMConnector(self, args[0])
    def sys_hostpool(self, args):
        """ Provides a list of available hosts for mission designers to provision. """
        self.__http = hosts(self, 'host_pool')
        self.engine.state = 'http'
    sys_hostpool.designer = True
    @hecmd('<player>', 1, staff=True)
    def sys_gamedata(self, args):
        """ Reads internal gamedata for a specific player """
        if args[0] == 'list':
            for d in os.listdir('players/'):
                self.transmit(d)
            return
        fname = 'players/%s/gamedata' % args[0]
        if os.path.exists(fname):
            data = pickle.loads(open(fname, 'r').read())
            for item in data.items():
                self.transmit('%s: %s' % item)
        else:
            self.transmit('* Player gamedata not found.')
    @hecmd('<player> <host>', 2, admin=True)
    def sys_assign(self, args):
        """ Assign a host to a specific player """
        if args[0] == 'me':
            host_list = list(self.engine.ic.host_list)
            if args[1] not in host_list:
                host_list.append(args[1])
                self.engine.ic.host_list = host_list
                self.transmit(' * Host added.')
        else:
            fname = 'players/%s/gamedata' % args[0]
            if os.path.exists(fname):
                data = pickle.loads(open(fname, 'r').read())
                if args[1] not in data['host_list']:
                    data['host_list'].append(args[1])
                    open(fname, 'w').write(pickle.dumps(data))
                    self.transmit(' * Host added.')
            else:
                self.transmit(' * Player does not exist.')
    @hecmd('<player> <host>', 2, admin=True)
    def sys_unassign(self, args):
        """ Unassigns a host from a specific player """
        if args[0] == 'me':
            host_list = list(self.engine.ic.host_list)
            if args[1] in host_list:
                host_list.remove(args[1])
                self.engine.ic.host_list = host_list
                self.transmit(' * Host removed.')
        else:
            fname = 'players/%s/gamedata' % args[0]
            if os.path.exists(fname):
                data = pickle.loads(open(fname, 'r').read())
                if args[1] in data['host_list']:
                    data['host_list'].remove(args[1])
                    open(fname, 'w').write(pickle.dumps(data))
                    self.transmit(' * Host removed.')
            else:
                self.transmit(' * Player does not exist.')
    def sys_become_staff(self, args):
        """ Lower access to staff level """
        self.admin = False
        self.staff = True
    sys_become_staff.admin = True
    def sys_become_designer(self, args):
        """ Lower access to designer level """
        self.admin = False
        self.staff = False
        self.designer = True
    sys_become_designer.staff = True
    def sys_become_normal(self, args):
        """ Lower access to player level """
        self.admin = False
        self.staff = False
        self.designer = False
    sys_become_normal.designer = True
    @hecmd('[regen]')
    def sys_apikey(self, args):
        """ Shows or regenerates an API key """
        if len(args) > 0:
            if args[0] != 'regen':
                self.transmit(' * Invalid parameter.')
                return
            self.engine.ic.show_apikey(True)
        else:
            self.engine.ic.show_apikey(False)
    @hecmd('<name>', 1, designer=True)
    def sys_mkdisk(self, args):
        """ Creates a large disk suitable for OS installation media """
        if not valid_data.match(args[0]):
            self.transmit(' * The storage name should only contain alpha-numeric characters.')
            return
        if not os.path.exists('players/%s/storage' % self.username):
            os.mkdir('players/%s/storage' % self.username)            
        self.transmit(' * Creating new storage device of 32k in size...')
        dfile = 'players/%s/storage/%s' % (self.username, args[0])
        open(dfile, 'w+b').write('\x00'*32768)
        self.engine.ic.add_storage(dfile, True)
        self.transmit(' * Disk has been created successfully.')
    @hecmd('<player> <storage>', 2, staff=True)
    def sys_give(self, args):
        """ Gives a player access to a specific global storage media """
        if not os.path.exists('storage/%s' % args[1]):
            self.transmit(' ** Storage does not exist.')
        elif args[0] == 'me':
            self.engine.ic.add_storage(args[1])
            self.transmit(' * Storage added.')
        else:
            fname = 'players/%s/gamedata' % args[0]
            if os.path.exists(fname):
                data = pickle.loads(open(fname, 'r').read())
                if args[1] not in data['storage']:
                    data['storage'].append(args[1])
                    open(fname, 'w').write(pickle.dumps(data))
                    self.transmit(' * Storage added.')
            else:
                self.transmit(' * Player does not exist.')
    @hecmd('<service>', 1, admin=True)
    def sys_start(self, args):
        """ Starts a game service """
        if args[0] == 'economy':
            economy.start()
            self.transmit(' * Economy started.')
    @hecmd('<service>', 1, admin=True)
    def sys_stop(self, args):
        """ Stops a game service """
        if args[0] == 'economy':
            economy.stop()
            self.transmit(' * Economy stopped.')
    @hecmd('<host> <addr> "<sparam>" <np1> <np2>', 5, admin=True)
    def sys_exec(self, args):
        """ Use the VM Exec command to run code """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        self.transmit('Sending request to host...')
        self.engine.state = 'vm_exec'
        self.__vm = VMConnector(self, args[0])
        self.__vm.params = args[1:]
    @hecmd('<host> <imagename>', 2, staff=True)
    def sys_mkosimage(self, args):
        """ Generates an OS image from a HostFS to use in a Host Template """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        if not valid_data.match(args[1]):
            self.transmit(' ** Please use only alphanumeric characters for the osimage.')
            return
        if os.path.exists('osimages/%s.img' % args[1]):
            self.transmit(' ** This osimage already exists, please choose a new name.')
            return
        host = args[0]
        host_dir = 'hosts/%s/%s/files' % ('.'.join(host.split('.')[:2]), host)
        if not os.path.exists(host_dir):
            self.transmit(' ** Selected host does not have a HostFS device!')
            return
        try:
            idx = open('%s/idx' % host_dir, 'rb').read().split(chr(255))
        except:
            self.transmit(' ** Selected host does not have any files!')
            return
        self.transmit(' * Generating OSImage %s.img from host %s...' % (args[1], host))
        zf = zipfile.ZipFile('osimages/%s.img' % args[1], 'w')
        for fname in idx:
            if fname == '':
                continue
            self.transmit(' * Writing %s...' % fname)
            hname = '%s/%s' % (host_dir, hashlib.md5(fname).hexdigest())
            zf.write(hname, fname)
        zf.close()
        self.transmit(' * Process complete!')
    """
    @hecmd('<template>', 1, designer=True)
    def sys_mkos(self, args):
        "" Generate an OS boot disc from a template ""
        self.__http = hosts(self, 'get_template', args[0])
        self.engine.state = 'ooc_mkos'
    """
