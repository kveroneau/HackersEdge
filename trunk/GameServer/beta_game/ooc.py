import logging, os, hashlib, threading, asyncore
from sessions import SHM, notify_sessions, clean_sessions, hypervisor
from utils import Shell, get_xp, get_balance, hecmd, ipv4
from chat import channels
from databases import get_host, set_host, forum, SUPERUSERS, hosts
from hostops import setup_dns, copy_file, get_file
from settings import SHOW_VERSIONS, DEBUG
from exceptions import SwitchState

log = logging.getLogger('OOC')

class OOC(Shell):
    version = 'HackerOOC v0.7.2 $Revision: 195 $'
    def __init__(self, username, engine):
        self.username, self.engine = username, engine
        if SHOW_VERSIONS:
            self.transmit(self.version)
        udata = SHM[username]
        self.sid = udata['username']
        self.admin = udata['admin']
        self.staff = udata['staff']
        self.designer = udata['designer']
        self.channels = ['public']
        self.cmdset = None
        if self.admin:
            notify_sessions('[%s] Game creator logged on.' % self.sid, self.sid)
        elif self.designer:
            notify_sessions('[%s] Game mission designer logged on.' % self.sid, self.sid)
        elif self.staff:
            notify_sessions('[%s] Game moderator logged on.' % self.sid, self.sid)
        else:
            notify_sessions('[%s] Player logged on.' % self.sid, self.sid)
        channels['public'].join(self.sid)
    def __del__(self):
        log.debug('Removing OOC for %s' % self.sid)
        for channel in self.channels:
            channels[channel].leave(self.sid)
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
        self.engine.tty.transmit(data)
    def plus_cmd(self, *cmdline):
        self.state = 'shell'
        try:
            if not self.parse_cmd('plus', True, *cmdline):
                self.transmit(' ** Use +help to understand the OOC commands.')
        except:
            if DEBUG:
                raise
            self.transmit(' ** Unable to execute OOC command.')
            log.critical('Exception while running: %s' % ' '.join(cmdline))
    def sys_cmd(self, *cmdline):
        self.state = 'shell'
        try:
            if not self.parse_cmd('sys', True, *cmdline):
                self.transmit(' ** Use @help to understand the OOC system commands.')
        except:
            if DEBUG:
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
        for opid,s in SHM.sessions.items():
            try:
                idle = '<Away>' if s.away_mode else ''
                self.transmit('{0:<20} {1}\t{2}\t{3}'.format(opid,s.game.connect_time,s.ctype,idle))
            except:
                pass
    @hecmd('<user> <message>', 2)
    def plus_page(self, args):
        """ Sends a private message to another player who is online. """
        if SHM.sessions.has_key(args[0]):
            SHM.sessions[args[0]].notify('[%s] %s' % (self.sid, args[1]))
        else:
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
    sys_notice.admin = True
    def sys_blockip(self, args):
        """ Adds an IP address into the blocklist """
        SHM.blocklist.append(args[0])
    sys_blockip.admin = True
    def sys_unblockip(self, args):
        """ Removes an IP address from the blocklist """
        if args[0] in SHM.blocklist:
            SHM.blocklist.remove(args[0])
    sys_unblockip.admin = True
    def sys_blocklist(self, args):
        """ Displays the current list of blocked IP addresses """
        self.columnize(SHM.blocklist)
    sys_blocklist.admin = True
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
        udata = SHM[self.username]
        self.transmit('Home host: %s' % udata['ip_addr'])
        self.transmit('Mail host: %s' % udata['mailhost'])
        self.transmit('Bank host: %s' % udata['bank'])
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
    @hecmd('<ip addr>',1, staff=True)
    def sys_mkhost(self, args):
        """ Creates a new host """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter in a valid IP address.')
            return
        host = get_host(args[0])
        if host != False:
            self.transmit(' ** This host already exists.')
            return
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
    @hecmd('<ip addr>', 1, staff=True)
    def sys_pushsys(self, args):
        """ Pushes latest system files over to a host """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        host = get_host(args[0])
        if not host:
            self.transmit(' ** The IP address provided is not valid.')
            return
        self.transmit('Copying over system files...')
        for f in ['BOOT.SYS','KERNEL.SYS','FILEIO.SYS','NETDRV.SYS']:
            copy_file('96.164.6.147:%s' % f, args[0])
        self.transmit('System files were copied successfully.')
    def sys_heshutdown(self, args):
        """ Shuts down every host in the game """
        if not SHM.MAINTENANCE_MODE:
            self.transmit(' ** Please initiate maintenance mode first!')
            return
        log.critical('Shut down of HENet by %s' % self.username)
        self.transmit('Shutting down entire game network, please wait...')
        for ip_addr in hosts.host_list():
            self.transmit('Shutting down %s...' % ip_addr)
            host = get_host(ip_addr)
            if host['online']:
                host['online'] = False
                set_host(ip_addr, host)
            else:
                self.transmit(' ** Host was never online.')
        self.transmit('Operation complete!')
    sys_heshutdown.admin = True
    @hecmd('<ip addr>', 1, staff=True)
    def sys_online(self, args):
        """ Forces a host online regardless of it's settings """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        host = get_host(args[0])
        if not host:
            self.transmit(' ** The IP address provided is not valid.')
            return
        host['online'] = True
        set_host(args[0], host)
    @hecmd('<ip addr>', 1, staff=True)
    def sys_boot(self, args):
        """ Boots up a host using the BOOT.SYS system file """
        if not ipv4.match(args[0]):
            self.transmit(' ** Enter a valid IP address.')
            return
        host = get_host(args[0])
        if not host:
            self.transmit(' ** The IP address provided is not valid.')
            return
        if host['online']:
            self.transmit(' ** The host is already online.')
            return
        if 'BOOT.SYS' not in host['files']:
            self.transmit(' ** Missing system files.')
            return
        self.transmit('Booting host...')
        sid = 'ooc-%s' % self.username
        hypervisor.allocate(sid, False)
        hypervisor.switch_host(sid, args[0])
        hypervisor.reboot(sid)
        try:
            hypervisor.execute(sid)
            hypervisor.wait(sid)
            self.transmit(hypervisor.stdout(sid))
            hypervisor.destroy(sid)
        except:
            self.transmit(' ** Unable to boot the host.')
    @hecmd('<ip addr> <file>', 2, staff=True)
    def sys_pushfile(self, args):
        """ Pushes a single file to a host. """
        ip_addr = SHM[self.username]['host']
        host_data = get_host(ip_addr)
        if args[1] not in host_data['files']:
            self.transmit(' ** The file does not exist on current host.')
            return
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
        copy_file('96.164.6.147:%s' % args[1], args[0])
        self.transmit('Operation complete.')
    @hecmd('<ip addr> <binfile>', 2, staff=True)
    def sys_exec(self, args):
        """ Executes a binary on a remote host. """
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
        if args[1] not in host['files']:
            self.transmit(' ** Binary file does not exist on remote host.')
            return
        self.transmit('Attempting to execute binary image...')
        sid = 'ooc-%s' % self.username
        hypervisor.allocate(sid, False)
        hypervisor.switch_host(sid, args[0])
        try:
            fname = get_file('%s:%s' % (args[0], args[1]))
            hypervisor.load(sid, fname)
            hypervisor.set_param(sid)
            hypervisor.execute(sid)
            hypervisor.wait(sid)
            self.transmit(hypervisor.stdout(sid))
        except:
            self.transmit(' ** Unable to execute binary image.')
        hypervisor.destroy(sid)
    @hecmd('[attr] [value]', admin=True)
    def sys_host(self, args):
        """ Sets or displays host specific attributes """
        ip_addr = SHM[self.username]['host']
        host_data = get_host(ip_addr)
        if len(args) == 0:
            for data in host_data.items():
                self.transmit('%s = %s' % data)
        elif len(args) == 1:
            try:
                del host_data[args[0]]
                set_host(ip_addr, host_data)
                self.transmit(' ** Attribute removed.')
            except:
                self.transmit(' ** Attribute not found.')
        elif len(args) == 2:
            if args[1] == 'true':
                host_data[args[0]] = True
            elif args[1] == 'false':
                host_data[args[0]] = False
            else:
                host_data[args[0]] = args[1]
            set_host(ip_addr, host_data)
            self.transmit(' ** Attribute updated.')
    @hecmd('[ip] <username> <perms>', staff=True)
    def sys_grant(self, args):
        """ Grant access rights on a host """
        if len(args) == 2:
            ip_addr = SHM[self.username]['host']
            user, perms = args
        elif len(args) == 3:
            ip_addr = args[0]
            if not ipv4.match(ip_addr):
                self.transmit(' ** Enter a valid IP address.')
                return
            user, perms = args[1:]
        try:
            host_data = get_host(ip_addr)
            if not self.admin:
                for u in SUPERUSERS:
                    if u in host_data['acl'].keys() and host_data['acl'][u] == 'RWF':
                        self.transmit(' ** You do not have access to update grants on %s.' % ip_addr)
                        return
            host_data['acl'][user] = perms
            set_host(ip_addr, host_data)
            self.transmit(' ** %s has been granted access.' % user)
        except:
            self.transmit(' ** There was a problem granting the perms.')
    @hecmd('[username]', admin=True)
    def sys_mkmail(self, args):
        """ Enables mail on the current host """
        ip_addr = SHM[self.username]['host']
        host_data = get_host(ip_addr)
        mail_dir = '%s/%s/mail' % (host_data['host_dir'], ip_addr)
        if len(args) == 1:
            try:
                open('%s/%s.new' % (mail_dir, args[0]), 'w').write('')
                open('%s/%s' % (mail_dir, args[0]), 'w').write('')
                host_data['mailboxes'].append(args[0])
                set_host(ip_addr, host_data)
                self.transmit(' ** Mailbox has been created.')
            except:
                self.transmit(' ** An error occured while creating the mailbox')
            return
        try:
            os.mkdir(mail_dir)
            host_data['mailboxes'] = []
            set_host(ip_addr, host_data)
            self.transmit(' ** Host has been enabled for mail.')
        except:
            self.transmit(' ** Host is already enabled for mail.')
    @hecmd('<dnsfile>', 1, staff=True)
    def sys_mkdns(self, args):
        """ Creates an in-game DNS server """
        ip_addr = SHM[self.username]['host']
        if setup_dns(ip_addr, args[0]):
            self.transmit(' ** DNS Server has been configured.')
    def sys_mkbank(self, args):
        """ Creates an in-game bank """
        ip_addr = SHM[self.username]['host']
        host_data = get_host(ip_addr)
        
    sys_mkbank.admin = True
    def plus_stats(self, args):
        """ Displays your character stats """
        udata = SHM[self.username]
        self.transmit('Experience Points: %s' % get_xp(self.username))
        self.transmit('Credits: %s' % get_balance(udata['bank'], self.username))
    @hecmd('[topic]')
    def plus_bboard(self, args):
        """ Access the Hacker's Edge forum """
        if len(args) == 0:
            topics = forum.topic_list()
            for topic in topics:
                self.transmit('Title: %s' % topic['title'])
                self.transmit('%s' % topic['description'].replace('\n', '\r\n'))
                self.transmit('To view type: +bboard %s' % topic['slug'])
                self.transmit('='*80)
        elif len(args) == 1:
            threads = forum.thread_list(args[0])
            if threads == False:
                self.transmit(' ** Topic does not exist.')
                return
            for thread in threads:
                self.transmit('Subject: %s' % thread['subject'])
                self.transmit('Started by: %s' % thread['started_by'])
                self.transmit('Started on: %20s Last Updated: %20s' % (thread['started_on'], thread['last_updated']))
                self.transmit('To view type: +thread %s' % thread['pk'])
                self.transmit('='*80)
        else:
            self.transmit('Usage: +bboard [topic]')
    @hecmd('<thread id>', 1)
    def plus_thread(self, args):
        """ View a thread from the Hacker's Edge forum """
        try:
            pk = int(args[0])
        except:
            self.transmit(' ** Please enter in the thread\'s ID.')
            return
        posts = forum.post_list(pk)
        if posts == False:
            self.transmit(' ** Thread does not exist.')
            return
        for post in posts:
            self.transmit('Subject: %s' % post['subject'])
            self.transmit('Posted by: %s' % post['username'])
            self.transmit('Posted on: %s' % post['posted'])
            self.transmit('%s' % post['body'].replace('\n', '\r\n'))
            self.transmit('='*80)
    @hecmd('<thread id>', 1)
    def plus_reply(self, args):
        """ Post a reply on an existing thread """
        try:
            pk = int(args[0])
        except:
            self.transmit(' ** Please enter in the thread\s ID.')
            return
        self.transmit('Write your reply and terminate with a period on a line by itself.')
        udata = SHM[self.username]
        udata['compose_msg'] = 'Reply has been posted.'
        udata['compose_cb'] = self.cb_reply
        udata['thread_pk'] = pk
        raise SwitchState('compose|')
    def cb_reply(self, data):
        udata = SHM[self.username]
        body = data.replace('\n', '\n\n')+"    =================\n    Posted in-game."
        r = forum.post_reply(udata['thread_pk'], self.sid, body)
        if r == False:
            self.transmit(' ** There was an error posting the reply.')
        del udata['thread_pk']
    @hecmd('[trigger] [action] [arg]', staff=True)
    def sys_trigger(self, args):
        ip_addr = SHM[self.username]['host']
        host_data = get_host(ip_addr)
        if len(args) == 0:
            if not host_data.has_key('triggers'):
                self.transmit(' ** Host has no triggers assigned.')
                return
            for trigger in host_data['triggers'].items():
                self.transmit('%s=%s' % trigger)
        elif len(args) == 1:
            if not host_data.has_key('triggers'):
                self.transmit(' ** Host has no triggers assigned.')
                return
            if host_data['triggers'].has_key(args[0]):
                del host_data['triggers'][args[0]]
                set_host(ip_addr, host_data)
                self.transmit(' ** Trigger removed.')
        elif len(args) > 1:
            if not host_data.has_key('triggers'):
                host_data['triggers'] = {}
            arg = []
            if len(args) > 2:
                arg = args[2:]
            host_data['triggers'][args[0]] = {'action':args[1], 'args':arg}
            set_host(ip_addr, host_data)
            self.transmit(' ** Trigger has been set.')
    @hecmd('<string>', 1, admin=True)
    def sys_md5(self, args):
        self.transmit(hashlib.md5(args[0]).hexdigest())
    def plus_notify(self, args):
        """ Toggle live notifications """
        if SHM.sessions[self.sid].live_notification:
            SHM.sessions[self.sid].live_notification = False
            self.transmit(' * Live notifications turned off.')
        else:
            SHM.sessions[self.sid].live_notification = True
            self.transmit(' * Live notifications turned on.')
    def sys_stats(self, args):
        """ Provides server stats. """
        self.transmit('Telnet logins: %s' % SHM.total_telnet)
        self.transmit('Web logins: %s' % SHM.total_web)
        self.transmit('Current sessions: %s' % ', '.join(SHM.sessions.keys()))
        self.transmit('Current udata: %s' % SHM.list_udata())
        self.transmit('SHM data: %s' % ', '.join(dir(SHM)))
        self.transmit('Current routes: %s' % ', '.join(SHM.connhost.keys()))
        self.transmit('VM Count: %s/%s' % (hypervisor.running_vms, len(hypervisor.vms)))
        self.transmit('Threads: %s' % threading.active_count())
        self.transmit('VM Hosts: %s' % ', '.join(hypervisor.hosts.keys()))
        self.transmit('ASyncore channels: %s' % len(asyncore.socket_map))
        for channel in asyncore.socket_map.items():
            self.transmit('%s: %s' % channel)
    sys_stats.admin = True
    @hecmd('<username>', 1, admin=True)
    def sysx_su(self, args):
        """ Switch to another user, and act as if you are them. """
        self.state = 'SU:%s' % args[0]
    @hecmd('<character>', 1, admin=True)
    def sys_udata(self, args):
        """ Displays a character's udata in SHM. """
        udata = SHM[args[0]]
        self.transmit('%s' % udata)
    def plus_idle(self, args):
        """ Sets idle mode when in a telnet client. """
        if SHM.sessions[self.sid].ctype in ('Telnet', 'MacTelnet'):
            log.info('Idle enabled by %s' % self.username)
            SHM.sessions[self.sid].away_mode = True
            self.transmit(' * Idle mode enabled.')
        else:
            self.transmit(' * This command can only be in a Telnet session.')
    def sys_maintenance(self, args):
        """ Puts Hacker's Edge into Maintenance mode. """
        if SHM.MAINTENANCE_MODE:
            log.info('Maintenance mode turned off by %s' % self.username)
            SHM.MAINTENANCE_MODE = False
            self.transmit(' * Maintenance mode turned off.')
            return
        log.critical('Maintenance mode enabled by %s' % self.username)
        SHM.MAINTENANCE_MODE = True
        self.transmit(' * Turning maintenance mode on, kicking users...')
        SHM.kick_all(self.transmit)
        self.transmit(' * Maintenance mode enabled.')
    sys_maintenance.admin = True
    @hecmd('<username> <reason>', 2, staff=True)
    def sys_kick(self, args):
        """ Kicks a user off the server. """
        log.critical('KICK %s "%s" by %s' % (args[0], args[1], self.username))
        if args[0] in SHM.sessions.keys():
            if args[0] == 'kveroneau':
                SHM.sessions['kveroneau'].notify(' ** %s attempted to kick you!' % self.sid)
                self.transmit(' ** Access denied to kicking %s.' % args[0])
                self.transmit(' ** Your moderator rights have been revoked.')
                self.staff = False
                SHM.blocklist.append(SHM.sessions[self.sid].ip_addr)
                return
            SHM.blocklist.append(SHM.sessions[args[0]].ip_addr)
            SHM.sessions[args[0]].transmit(' ** You have been kicked: %s' % args[1])
            SHM.sessions[args[0]].close_when_done()
            self.transmit(' * User has been kicked from game server.')
            self.sys_clean([])
        else:
            self.transmit(' * User is not logged in.')
    def sys_clean(self, args):
        """ Manually performs various server cleaning operations. """
        self.transmit(' * Killing VMs...')
        hypervisor.killall()
        self.transmit(' * Cleaning sessions...')
        clean_sessions()
    sys_clean.admin = True
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
