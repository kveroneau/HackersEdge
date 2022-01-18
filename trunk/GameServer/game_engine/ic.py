from utils import Shell, hecmd
from settings import SHOW_VERSIONS
from exceptions import SwitchHost, ShellError
from databases import get_host_dir
import logging, os, sys, pickle, uuid, subprocess

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
        log.debug('Saved IC Data.')
    def __delitem__(self, item):
        try:
            del self.__ic_data[item]
        except:
            pass
    def save(self):
        open(self.fname, 'w').write(pickle.dumps(self.__ic_data))
        log.debug('Saved IC Data.')        

class IC(Shell):
    version = 'HackerIC v1.3.1 $Rev: 319 $'
    def __init__(self, username, engine):
        self.username, self.engine = username, engine
        if SHOW_VERSIONS:
            self.transmit(self.version)
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
    def __del__(self):
        log.debug('Removing IC for %s' % self.username)
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
    def chk_apikey(self, api_key):
        if self.__ic_data['api_key'] == False:
            return False
        if self.__ic_data['api_key'] == api_key:
            return True
        return False
    def show_apikey(self, regen=False):
        if regen:
            self.__ic_data['api_key'] = False
        if self.__ic_data['api_key'] == False:
            self.__ic_data['api_key'] = str(uuid.uuid4())
        self.transmit(' * API Key: %s' % self.__ic_data['api_key'])
    def transmit(self, data):
        self.engine.transmit(data)
    def save_history(self):
        open('players/%s/ic_history' % self.username, 'w').write('\n'.join(self.history))
    def get_prompt(self):
        self.engine.csi(self.colour)
        return '%s%% ' % self.username
    def check_host(self, args):
        if args[0] not in self.host_list:
            raise ShellError('You do not possess direct access to that host.')
    def do_macro(self, fkey):
        cmd = self.__ic_data[fkey]
        if cmd is False:
            return
        self.transmit('%s' % cmd)
        self.handle_command(*cmd.split(' '))
    def add_storage(self, storage, raw=False):
        if not raw:
            if storage.startswith('players/'):
                if '/disks/' in storage:
                    storage = storage.split('/')[-1]
        if storage not in self.__ic_data['storage']:
            self.__ic_data['storage']+=[storage]
    def remove_storage(self, storage):
        if storage.startswith('players/'):
            if '/disks/' in storage:
                storage = storage.split('/')[-1]
        if storage in self.__ic_data['storage']:
            self.__ic_data['storage'].remove(storage)
            self.__ic_data.save()
    def handle_command(self, *cmd):
        log.debug('[%s] %s' % (self.username,' '.join(cmd)))
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
            if cmd[0] in ('boot', 'shutdown', 'connect', 'reinstall', 'attachments', 'attach', 'detach', 'import', 'memdump',):
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
        self.engine.state = 'vm_boot'
        raise SwitchHost(args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_shutdown(self, args):
        """ Shuts down a selected host """
        self.engine.state = 'vm_halt'
        raise SwitchHost(args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_connect(self, args):
        """ Connects to a selected host """
        self.engine.state = 'vm_tty'
        raise SwitchHost(args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_reinstall(self, args):
        """ Install system files onto selected host """
        self.engine.state = 'vm_install'
        self.transmit('Reinstalling system files...')
        raise SwitchHost(args[0])
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
            log.warning('%s attempted to access help file: %s' % (self.username, args[0]))
            self.transmit(' ** Help file could not be found.')
    def cmd_clear(self, args):
        """ Clears your terminal and homes the cursor """
        self.engine.csi('H')
        self.engine.csi('2J')
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
        self.engine.csi(self.colour)
    def cmd_history(self, args):
        """ Displays your IC command history """
        if len(args) == 1 and args[0] == 'clear':
            self.history = []
            self.transmit('IC Command history cleared.')
            return
        self.transmit('\r\n'.join(self.history))
    @hecmd('<fkey> "<IC command>"', 2)
    def cmd_macro(self, args):
        """ Sets a function key to a macro """
        try:
            fkey = int(args[0])
            if fkey < 1 or fkey > 12:
                raise ValueError('Function key can only be between 1 and 12!')
        except ValueError, e:
            self.transmit(' ** %s' % str(e))
            return
        self.__ic_data[args[0]] = args[1]
        self.transmit('Macro for F%s has been configured.' % args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_import(self, args):
        """ Imports Intel Hex into a running hosts memory """
        self.transmit('Paste your Intel Hex assembled code below...')
        self.engine.state = 'hexinput'
        self.hexcode = [args[0]]
        self.engine.set_prompt('')
    def cmdx_append(self, args):
        """ Example on how to append a new host to the list for ICData to save it correctly. """
        self.host_list+=[args[0]]
    def cmd_storage(self, args):
        """ Displays your currently available block devices you can attach to a host """
        for storage in self.__ic_data['storage']:
            if storage.startswith('players/'):
                self.transmit('Special disk: %s' % storage.split('/')[-1])
            else:
                self.transmit(storage)
    @hecmd('<host> <storage>', 2, checker='host')
    def cmd_attach(self, args):
        """ Attach a block device to a host under your direct control """
        if args[1] not in self.__ic_data['storage']:
            st = 'players/%s/storage/%s' % (self.username, args[1])
            if st not in self.__ic_data['storage']:
                self.transmit(' ** Block device not available.')
                return
        else:
            st = args[1]
        self.transmit('Attaching block device to host...')
        self.engine.state = 'vm_attach'
        if args[1][0:5] == 'disk.':
            self.storage = 'players/%s/disks/%s' % (self.username, st)
        else:
            self.storage = st
        raise SwitchHost(args[0])
    @hecmd('<host>', 1, checker='host')
    def cmd_attachments(self, args):
        """ View block devices attached to a specific host """
        self.engine.state = 'vm_attachments'
        raise SwitchHost(args[0])
    @hecmd('<host> <storage>', 2, checker='host')
    def cmd_detach(self, args):
        """ Detach a block device from a specific host """
        self.transmit('Removing block device from host...')
        self.engine.state = 'vm_detach'
        if args[1][0:5] == 'disk.':
            self.storage = 'players/%s/disks/%s' % (self.username, args[1])
        elif os.path.exists('players/%s/storage/%s' % (self.username, args[1])):
            self.storage = 'players/%s/storage/%s' % (self.username, args[1])
        else:
            self.storage = args[1]
        raise SwitchHost(args[0])
    def cmd_buydisk(self, args):
        """ Purchase a floppy disk from the hardware store """
        self.transmit(' * Purchasing floppy disk from hardware store...')
        if not os.path.exists('players/%s/disks' % self.username):
            os.mkdir('players/%s/disks' % self.username)
            self.__ic_data['diskidx'] = 0
        if self.__ic_data['diskidx'] > 4:
            self.transmit(' * The store appears to be fresh out of floppy disks.')
            return
        self.__ic_data['diskidx']+=1
        dfile = 'players/%s/disks/disk.%s' % (self.username, self.__ic_data['diskidx'])
        open(dfile, 'w+b').write('\x00'*8192)
        self.__ic_data['storage']+=['disk.%s' % self.__ic_data['diskidx']]
        self.transmit(' * Disk %s has been purchased.' % self.__ic_data['diskidx'])
    @hecmd('<host>', 1, checker='host')
    def cmd_memdump(self, args):
        """ Dumps the memory of a host you have in your inventory """
        memfile = '%s/%s/memory' % (get_host_dir(args[0]), args[0])
        if os.path.exists(memfile):
            try:
                stdout = subprocess.Popen(['/usr/bin/hexdump', '-C', memfile], stdout=subprocess.PIPE).communicate()[0]
            except:
                stdout = ' * An error occurred!'
            self.transmit(stdout.replace('\n', '\r\n'))
        else:
            self.transmit(' * Host memory currently unavailable.')
