from utils import Shell, hecmd
from databases import get_host, set_host
from sessions import SHM, hypervisor
from settings import SHOW_VERSIONS
from exceptions import SwitchHost, ShellError
from hostops import copy_file
import logging, os, sys, pickle

log = logging.getLogger('IC')

HELP_FILES = os.listdir('help')

class ICData(object):
    def __init__(self, fname):
        self.fname = fname
        if os.path.exists(fname):
            self.__ic_data = pickle.loads(open(fname, 'r').read())
        else:
            self.__ic_data = {'new': True}
    def __getitem__(self, item):
        try:
            return self.__ic_data[item]
        except:
            return False
    def __setitem__(self, item, value):
        self.__ic_data[item] = value
        open(self.fname, 'w').write(pickle.dumps(self.__ic_data))
        log.info('Saved IC Data.')
    def __delitem__(self, item):
        try:
            del self.__ic_data[item]
        except:
            pass
    def save(self):
        open(self.fname, 'w').write(pickle.dumps(self.__ic_data))
        log.info('Saved IC Data.')        

class IC(Shell):
    version = 'HackerIC v0.3.2 $Revision: 197 $'
    def __init__(self, username, engine):
        self.username, self.engine = username, engine
        if SHOW_VERSIONS:
            self.transmit(self.version)
        self.udata = SHM[username]
        if not os.path.exists('players/%s' % self.username):
            os.mkdir('players/%s' % self.username)
        self.__ic_data = ICData('players/%s/gamedata' % self.username)
        self.host = 'ic'
        try:
            self.history = open('players/%s/ic_history' % self.username).read().split('\n')
        except:
            self.history = []
        self.hpos = len(self.history)
        self.cmdset = None
        if self.__ic_data['new']:
            self.transmit("Welcome to Hacker's Edge!  I see this is your first time connecting")
            self.transmit('as %s.  How exciting!' % self.username)
            self.transmit('This text will soon be replaced with a tutorial system in the future.')
            self.transmit('For now, you should try using the "manual" command to learn more')
            self.transmit("about your new shiny Hacker's Edge PC!\r\n")
            del self.__ic_data['new']
            self.colour = '0m'
            self.host_list = [self.engine.udata['ip_addr']]
            self.__ic_data['storage'] = os.listdir('storage')
    @property
    def colour(self):
        return self.__ic_data['colour']
    @colour.setter
    def colour(self, value):
        self.__ic_data['colour'] = value
    @property
    def host_list(self):
        return self.__ic_data['host_list']
    @host_list.setter
    def host_list(self, value):
        self.__ic_data['host_list'] = value
    def transmit(self, data):
        self.engine.tty.transmit(data)
    def save_history(self):
        open('players/%s/ic_history' % self.username, 'w').write('\n'.join(self.history))
    def get_prompt(self):
        self.engine.tty.csi(self.colour)
        return '%s%% ' % self.username
    def check_host(self, args):
        if args[0] not in self.host_list:
            raise ShellError('You do not possess direct access to that host.')
        host = get_host(args[0])
        if not host:
            raise ShellError('The IP address provided is not valid.')
    def handle_command(self, *cmd):
        log.info('[%s] %s' % (self.username,' '.join(cmd)))
        try:
            if not self.parse_cmd('cmd', False, *cmd):
                self.transmit(' ** Use help to understand the IC commands.')
        except ShellError, e:
            self.transmit(' ** %s' % e)
        except SwitchHost:
            raise
        except:
            self.transmit(' ** Unable to execute IC command.')
            log.critical('Exception while running: [%s]%s' % (sys.exc_info()[1],' '.join(cmd)))
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
        else:
            cmd = ibuf.split(' ')
            if cmd[0] in ('boot', 'shutdown', 'connect', 'install', 'attachments', 'attach', 'detach'):
                for host in self.host_list:
                    if host.startswith(cmd[1]):
                        result.append(host)
            elif cmd[0] == 'manual':
                for doc in HELP_FILES:
                    if doc.startswith(cmd[1]):
                        result.append(doc)
            elif cmd[0] == 'colour':
                for colour in ('green', 'white', 'cyan', 'red', 'reset'):
                    if colour.startswith(cmd[1]):
                        result.append(colour)
            if len(cmd) == 2:
                if cmd[1] in ('attach', 'detach'):
                    for blkdev in self.__ic_data['storage']:
                        if blkdev.startswith(cmd[2]):
                            result.append(blkdev)
        return result
    def cmd_help(self, args):
        self.show_help('cmd')
    def cmd_hosts(self, args):
        """ List hosts under your direct control """
        self.transmit('\r\n'.join(self.host_list))
    @hecmd('<host>', 1, checker='host')
    def cmd_boot(self, args):
        """ Boot a selected host """
        host = get_host(args[0])
        if host['online']:
            raise ShellError('The host is already online.')
        if 'BOOT.SYS' not in host['files']:
            raise ShellError(' ** Missing system files.')
        self.transmit('Booting host...')
        sid = 'ic-%s' % self.username
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
    @hecmd('<host>', 1, checker='host')
    def cmd_shutdown(self, args):
        """ Shuts down a selected host """
        host = get_host(args[0])
        if not host['online']:
            self.transmit(' ** The host is already offline.')
            return
        host['online'] = False
        set_host(args[0], host)
        self.transmit('Operation complete.')
    @hecmd('<host>', 1, checker='host')
    def cmd_connect(self, args):
        """ Connects to a selected host """
        raise SwitchHost(args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_install(self, args):
        """ Install system files onto selected host """
        self.transmit('Installing system files...')
        for f in ['BOOT.SYS','KERNEL.SYS','FILEIO.SYS','NETDRV.SYS']:
            copy_file('96.164.6.147:%s' % f, args[0])
        self.transmit('System files were installed successfully.')
    @hecmd('[document]')
    def cmd_manual(self, args):
        """ Read the various manuals which came with your Hacker's Edge PC """
        if len(args) == 0:
            self.transmit('You see the following guides next to your PC:')
            self.transmit('=============================================')
            self.transmit('\r\n'.join(HELP_FILES))
            return
        if args[0] in HELP_FILES:
            self.transmit('%s' % args[0].upper())
            self.transmit('=============================================')
            self.transmit(open('help/%s' % args[0], 'r').read().replace('\n','\r\n'))
        else:
            log.info('%s attempted to access help file: %s' % (self.username, args[0]))
            self.transmit(' ** Help file could not be found.')
    def cmd_clear(self, args):
        """ Clears your terminal and homes the cursor """
        self.engine.tty.csi('H')
        self.engine.tty.csi('2J')
    @hecmd('<colorname>', 1)
    def cmd_colour(self, args):
        """ Changes your terminal color to make it easier to use """
        if args[0] == 'green':
            self.colour = '32m'
        elif args[0] == 'white':
            self.colour = '37m'
        elif args[0] == 'cyan':
            self.colour = '36m'
        elif args[0] == 'red':
            self.colour = '31m'
        elif args[0] == 'reset':
            self.colour = '0m'
        else:
            self.transmit('Please choose one of the following colornames:')
            self.transmit('green  white  cyan  red  reset')
            return
        self.engine.tty.csi(self.colour)
    def cmd_history(self, args):
        """ Displays your IC command history """
        if len(args) == 1 and args[0] == 'clear':
            self.history = []
            self.transmit('IC Command history cleared.')
            return
        self.transmit('\r\n'.join(self.history))
    def cmdx_append(self, args):
        """ Example on how to append a new host to the list for ICData to save it correctly. """
        self.host_list+=[args[0]]
    def cmd_storage(self, args):
        """ Displays your currently available block devices you can attach to a host. """
        self.transmit('\r\n'.join(self.__ic_data['storage']))
    @hecmd('<host> <storage>', 2, checker='host')
    def cmd_attach(self, args):
        """ Attach a block device to a host under your direct control. """
        if args[1] not in self.__ic_data['storage']:
            self.transmit(' ** Block device not available.')
            return
        self.transmit('Attaching block device to host...')
        hypervisor.attach(args[0], 'storage/%s' % args[1])
        self.__ic_data['storage'].remove(args[1])
        self.__ic_data.save()
    @hecmd('<host>', 1, checker='host')
    def cmd_attachments(self, args):
        """ View block devices attached to a specific host. """
        host = hypervisor.get_host(args[0])
        if host.has_key('storage'):
            self.transmit('\r\n'.join([s.split('/')[-1] for s in host['storage']]))
        else:
            self.transmit('No block devices attached to this host.')
    @hecmd('<host> <storage>', 2, checker='host')
    def cmd_detach(self, args):
        """ Detach a block device from a specific host. """
        self.transmit('Removing block device from host...')
        if hypervisor.detach(args[0], 'storage/' % args[1]):
            self.__ic_data['storage']+=[args[1]]
        else:
            self.transmit('The specified block device is not attached to this host.')
