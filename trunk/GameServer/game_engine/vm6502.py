from databases import hosts, get_host_dir
from exceptions import VMError, CompileError, VMNoData, VMFlush, VMNetData, VMHalt, VMReset, VMTermBit
from connector import VMConnector
from ConfigParser import SafeConfigParser
from asm6502 import Assembler
import cStringIO as StringIO
import cPickle as pickle
from devices.memory import Memory
from devices.terminal import Terminal
from devices.rom import BootROM
from devices.heapi import HEAPI
from devices.misc import RTC
from devices.nic import NetworkCard
from devices.blockdev import StorageController
from intelhex import IntelHex
from devices.cffa1 import CFFA1Controller
from devices.hostfs import HostFS
from settings import DEBUG
import mmap, logging, os, binascii, struct, time, asyncore, asynchat, socket, hashlib

log = logging.getLogger('HackerVM')

cpu_state = struct.Struct('>BBBBIBI')

DEVICES = {
    'terminal': Terminal,
    'bootrom': BootROM,
    'heapi': HEAPI,
    'rtc': RTC,
    'nic': NetworkCard,
    'blkdev': StorageController,
    'cffa1': CFFA1Controller,
    'hostfs': HostFS,
}

if DEBUG:
    from devices.debugfs import DebugFS
    DEVICES['debugfs'] = DebugFS

STORAGE_DEVICES = ('blkdev', 'cffa1',)

DEFAULT_DEVICES = ('terminal', 'bootrom', 'heapi', 'rtc', 'nic', 'blkdev',)

class CPU(object):
    version = 'HackerVM v1.9 $Rev: 325 $'
    def __init__(self, ip_addr, tty=None):
        self.ip_addr = ip_addr
        self.__socks = {}
        self.is_vm = True
        self.vm_state = None
        self.__from_ip = None
        if tty is not None:
            self.__socks['tty'] = tty
        self.__running = False
        self.finished = False
        self.__http = None
        self.__intr = []
        self.__exec = False
        host_dir = get_host_dir(ip_addr)
        if not os.path.exists(host_dir):
            log.error('Attempting to create host in invalid network: %s' % ip_addr)
            self.mem = None
            if tty:
                tty.send_result('NOHOST')
            return
        try:
            os.mkdir('%s/%s' % (host_dir, ip_addr))
            log.debug('Created host directory: %s/%s' % (host_dir, ip_addr))
        except OSError:
            pass
        memory = '%s/%s/memory' % (host_dir, ip_addr)
        try:
            self.__file = open(memory, 'r+b')
        except IOError:
            log.info('Setting up new VM for %s' % ip_addr)
            self.__file = open(memory, 'w+b')
            self.__file.write('\x00'*(0xffff+1))
            self.__file.close()
            self.__file = open(memory, 'r+b')
        self.mem = Memory(self.__file.fileno(), 0xffff, ip_addr)
        self.reset()
        self.get_host()
        if tty:
            tty.transmit(self.version)
    @property
    def tty(self):
        if not self.__socks.has_key('tty'):
            return None
        return self.__socks['tty']
    @property
    def running(self):
        return self.__running
    @running.setter
    def running(self, value):
        if self.mem.host is None:
            value = False
        self.__running = value
        if value:
            self.finished = False
        else:
            self.finished = True
    def start(self):
        self.running = True
    def reset(self):
        log.debug('CPU Reset initiated.')
        self.regA, self.regX, self.regY, self.regP = 0,0,0,0
        self.pc, self.sp, self.ss = 0,0xff,0x100
        self.running = False
    def ipl(self):
        if not self.mem.host.has_key('bootaddr'):
            return False
        self.clear_memory()
        if self.tty is not None:
            self.tty.termbit(0)
        self.mem.set_word(0xf0, 0xe000)
        self.mem.ipl_devices()
        self.mem.resume_devices()
        self.pc = self.mem.host['bootaddr']
        self.mem.set_word(0xfffc, self.mem.host['bootaddr'])
        self.mem.host['online'] = True
        self.mem.host['boottime'] = int(time.time())
        isr = (self.mem.io_page << 8)+0x30
        self.mem.set_word(0xfffa, isr)
        self.mem.set_word(0xfffe, isr)
        self.set_host()
        return True
    def shutdown(self):
        if self.tty is not None:
            self.tty.transmit(' * Host is being shutdown...')
        self.mem.suspend_devices()
        self.running = False
        self.mem.host['online'] = False
        for cname, sock in self.__socks.items():
            if cname != 'tty':
                #sock.send_result('HALT')
                sock.handle_close()
                del self.__socks[cname]
        self.set_host()
    def suspend(self):
        self.mem.suspend_devices()
        self.running = False
        self.save_state()
    def provision(self, template):
        if template == 'DEFAULT':
            template = self.mem.host['template']
        else:
            self.mem.host['template'] = template
        self.tty.transmit(' * Provisioning with template %s...' % template)
        self.tty.transmit(Assembler.version)
        self.__http = hosts(self, 'get_template', str(template))
    def mkhost(self):
        if self.mem is None:
            return False
        if self.mem.host is not None:
            return False
        self.mem.host = {'online': False, 'vm': 'vm6502'}
        self.set_host()
        return True
    def attach(self, storage):
        self.mem.host['storage'].append(storage)
    def detach(self, storage):
        self.mem.host['storage'].remove(storage)
    def set_tty(self, tty):
        if tty is not None:
            if self.tty is not None:
                self.tty.send_result('NEWTTY')
            self.__socks['tty'] = tty
            self.tty.transmit(self.version)
        else:
            self.tty.send_result('NOTTY')
            del self.__socks['tty']
    def stdin(self, data):
        if self.tty is None:
            return
        self.mem.input(data)
        self.running = True
    def netconn(self, port, from_ip):
        self.__from_ip = from_ip
        log.debug('Network request to port %s.' % port)
        nettbl = self.host['nettbl']
        idx = 0
        for entry in nettbl:
            if entry['type'] == 1 and entry['port'] == port:
                conn = {'ip_addr':from_ip, 'port':port}
                self.host['nettbl'][idx]['contbl'].append(conn)
                self.set_host()
                self.mem.set_io(0x71, idx)
                self.interrupt(entry['addr'])
                return True
            idx+=1
        return False
    def netin(self, data, ip_addr=None):
        log.debug('Network data received from %s: %s' % (ip_addr, data))
        nettbl = self.host['nettbl']
        idx = 0
        for entry in nettbl:
            if entry['type'] == 2 and entry['ip_addr'] == ip_addr:
                self.mem.netin(ip_addr, data)
                self.mem.set_io(0x71, idx)
                self.interrupt(entry['addr'])
            elif entry['type'] == 1 and ip_addr == None:
                self.mem.netin('svr', data)
                idx = 0
                for conn in entry['contbl']:
                    if conn['ip_addr'] == self.__from_ip:
                        self.mem.set_io(0x71, idx)
                    idx+=1
                self.interrupt(entry['addr'])
            idx+=1
    def netclose(self):
        if self.__from_ip is not None:
            log.debug('Closing network connection from %s' % self.__from_ip)
            nettbl = self.host['nettbl']
            idx = 0
            for entry in nettbl:
                if entry['type'] == 1:
                    idx2 = 0
                    for conn in entry['contbl']:
                        if conn['ip_addr'] == self.__from_ip:
                            del self.host['nettbl'][idx]['contbl'][idx2]
                        idx2+=1
                idx+=1
            self.mem.update_netseg()
    def interrupt(self, addr):
        if (self.regP & 0x04) == 0x0:
            self.__intr.insert(0, addr)
            self.regP &= ~0x10
            self.running = True
    def brk(self):
        self.interrupt(self.mem.host['isr'])
    def nmi(self):
        self.push((self.pc >> 8) & 0xff)
        self.push((self.pc & 0xff))
        self.push(self.regP)
        self.pc = self.mem.get_word(0xfffa)
        self.running = True
    def hex_import(self, hexcode):
        sio = StringIO.StringIO(hexcode)
        h = IntelHex(sio)
        for addr in h.addresses():
            self.mem.set(addr, h[addr])
        del h
        sio.close()
        del sio
        return True
    def hex_hostfs(self, fname, hexcode):
        if 'hostfs' not in self.mem.host['devices']:
            return False
        sio = StringIO.StringIO(hexcode)
        h = IntelHex(sio)
        host_dir = '%s/%s/files' % (get_host_dir(self.ip_addr), self.ip_addr)
        flist = open('%s/idx' % host_dir, 'rb').read().split(chr(255))
        if fname not in flist:
            flist.append(fname)
            open('%s/idx' % host_dir, 'rb').write(chr(255).join(flist))
        fname = '%s/%s' % (host_dir, hashlib.md5(fname).hexdigest())
        f = open(fname, 'wb')
        for addr in h.addresses():
            f.write(h[addr])
        f.close()
        del h
        sio.close()
        del sio
        return True
    def mouse(self, but, col, row):
        self.mem.set_io(0xd9, but)
        self.mem.set_io(0xda, col)
        self.mem.set_io(0xdb, row)
        irq_addr = (self.mem.io_page << 8)+0xdd
        self.interrupt(self.mem.get_word(irq_addr))
    def execute(self, addr, sparam, np1, np2):
        log.info('Engine remote execution code at address %s' % hex(addr))
        if (self.regP & 0x04) == 0x04:
            return False
        ptr = self.mem.get_word(0x7e)
        if ptr < 0x200:
            return False
        self.mem.set(ptr, np1)
        self.mem.set(ptr+1, np2)
        self.mem.set(ptr+2, len(sparam))
        self.mem.setstring(ptr+3, sparam)
        self.interrupt(self.mem.get_word(addr))
        self.__exec = True
        return True
    def debug_info(self):
        if self.tty:
            self.tty.transmit('\n%s-    A=%s X=%s Y=%s P=%s S=%s\n' % (hex(self.pc)[2:], hex(self.regA)[2:], hex(self.regX)[2:], hex(self.regY)[2:], hex(self.regP)[2:], hex(self.sp)[2:]))
    def set_host(self):
        self.mem.set_host()
    def get_host(self):
        if self.__http is not None:
            log.warning('Previous AsyncHTTP did not finish, not getting host: %s' % self.ip_addr)
            return
        self.__http = hosts(self, 'get_host', self.ip_addr)
    @property
    def host(self):
        return self.mem.host
    def prov_asm(self, description, asmcode, **kwargs):
        mode = kwargs.pop('mode')
        self.tty.transmit(' * Assembling %s...' % description)
        try:
            asm = Assembler(asmcode.split('\r\n'))
            asm.assemble()
            if mode == 'BIOS':
                if self.mem.host.has_key('romaddr'):
                    del self.mem.host['romaddr']
                    del self.mem.host['romsize']
                asm.savebin('%s/%s/bios' % (get_host_dir(self.ip_addr), self.ip_addr))
                self.tty.transmit(asm.result)
            elif mode == 'BLKDEV':
                dev = int(kwargs.pop('dev'))
                blk = int(kwargs.pop('blk'))
                if self.mem.blkdev[0].fstype == 'hardcoded':
                    if asm.outfile is None:
                        asm.outfile = self.__prov.get('file%s' % self.__curfile, 'asm').split('.')[0]
                    self.mem.blkdev[0].writefile(asm.outfile, asm.get_header()+asm.get_cseg())
                else:
                    self.mem.blkdev[dev].writeblock(blk, asm.get_header()+asm.get_cseg())
                    if 'ds' in kwargs.keys():
                        ds = int(kwargs.pop('ds'))
                        self.mem.blkdev[dev].writeblock(ds, asm.get_dseg())
                self.tty.transmit(asm.result)
            del asm
        except CompileError, e:
            self.tty.transmit(' * %s' % e)
            self.tty.send_result('PROVERR')
    def prov_hex(self, description, hexcode):
        self.tty.transmit(' * Loading Intel Hex formatted %s...' % description)
        try:
            sio = StringIO.StringIO(hexcode)
            h = IntelHex(sio)
            self.tty.transmit(' * Checking segments used...')
            segs = h.segments()
            if len(segs) == 1:
                segrange = segs[0]
                self.tty.transmit(' * %s starting address is %s' % (description, hex(segrange[0])))
                self.mem.host['romaddr'] = segrange[0]
                romsize = segrange[1]-segrange[0]
                self.tty.transmit(' * Total %s size is %s' % (description, hex(romsize)))
                self.mem.host['romsize'] = romsize
                biosfile = '%s/%s/bios' % (get_host_dir(self.ip_addr), self.ip_addr)
                if os.path.exists(biosfile):
                    os.unlink(biosfile)
                f = open(biosfile, 'wb')
                for addr in h.addresses():
                    f.write(chr(h[addr]))
                f.close()
            else:
                self.tty.transmit(' * Multi-segment Intel Hex support coming soon!')
                raise
            del h
            sio.close()
            del sio
        except:
            del h
            sio.close()
            del sio
            self.tty.transmit(' * Intel Hex import failed.')
            self.tty.send_result('PROVERR')
    def prov_get(self, section, option, last=False):
        if self.__prov.has_option(section, option):
            self.__provmode = option
            self.__http = hosts(self, 'get_file', self.__prov.get(section, option))
            return True
        if last:
            if self.mem.host.has_key('new'):
                del self.mem.host['new']
            for dev in self.mem.host['devices']:
                self.mem.attach_device(DEVICES[dev])
            self.mem.resume_devices()
            self.tty.send_result('PROVOK')
        return False
    def http_callback(self, result):
        if result[0] == 'get_host':
            if result[1] == 'ERR':
                self.tty.send_result('NOHOST')
                self.__http = None
                return
            self.mem.host = pickle.loads(result[1])
            if self.mem.host.has_key('new') and not self.mem.host['online']:
                log.info('New host detected %s, attempting to provision...' % self.ip_addr)
                self.tty.transmit(' * Provisioning with template %s...' % self.mem.host['template'])
                self.tty.transmit(Assembler.version)
                self.__http = hosts(self, 'get_template', str(self.mem.host['template']))
                return
            if not self.mem.host.has_key('devices'):
                self.mem.host['devices'] = list(DEFAULT_DEVICES)
                self.set_host()
            if self.mem.host.has_key('iopage'):
                self.mem.io_page = self.mem.host['iopage']
            for dev in self.mem.host['devices']:
                self.mem.attach_device(DEVICES[dev])
            try:
                self.mem.update_netseg()
            except:
                pass
            if self.mem.host['online']:
                self.load_state()
                self.tty.send_result('ONLINE')
            else:
                self.tty.send_result('OFFLINE')
        elif result[0] == 'get_template':
            log.debug('get_template returned.')
            if result[1] == 'ERR':
                self.tty.send_result('PROVERR')
            else:
                fp = StringIO.StringIO(result[1])
                self.__prov = SafeConfigParser()
                self.__prov.readfp(fp, 'host.ini')
                fp.close()
                del fp
                try:
                    storage_dev = None
                    bios = self.__prov.get('machine', 'bios')
                    self.tty.transmit('BIOS: %s' % bios)
                    bootaddr = str(self.__prov.get('machine', 'bootaddr'))
                    if bootaddr[0] == '$':
                        self.mem.host['bootaddr'] = int(bootaddr[1:], 16)
                    else:
                        self.mem.host['bootaddr'] = int(bootaddr)
                    if self.__prov.has_option('machine', 'devices'):
                        devices = self.__prov.get('machine', 'devices')
                        devices = devices.replace(' ','')
                        devices = devices.split(',')
                        for dev in devices:
                            if dev not in DEVICES.keys():
                                raise
                            if dev in STORAGE_DEVICES:
                                storage_dev = dev
                        self.mem.host['devices'] = devices
                    else:
                        self.mem.host['devices'] = list(DEFAULT_DEVICES)
                        storage_dev = 'blkdev'
                    if self.__prov.has_option('machine', 'iopage'):
                        self.mem.host['iopage'] = int(self.__prov.get('machine', 'iopage')[1:], 16)
                    else:
                        self.mem.host['iopage'] = 0xff
                    if self.__prov.has_section('storage'):
                        if 'hostfs' in devices:
                            if self.__prov.has_option('storage', 'hostfs'):
                                osimage = self.__prov.get('storage', 'hostfs')
                                self.tty.transmit(' * Installing OS image from %s...' % osimage)
                                hfs = HostFS(self.mem)
                                if not hfs.reinstall(osimage):
                                    self.tty.transmit(' * Failed to install OS image!')
                                    raise
                            else:
                                self.tty.transmit(' * HostFS configured in empty state.')
                        elif storage_dev is None:
                            self.tty.transmit(' * Storage device not available!')
                            raise
                        else:
                            sfile = '%s/%s/storage' % (get_host_dir(self.ip_addr), self.ip_addr)
                            self.mem.host['storage'] = [sfile]
                            size = self.__prov.getint('storage', 'size')*1024
                            open(sfile, 'w+b').write('\x00'*size)
                            self.tty.transmit(' * Starting storage device %s...' % storage_dev)
                            self.mem.attach_device(DEVICES[storage_dev])
                            self.mem.open_storage()
                            self.mem.blkdev[0].fstype = None
                    if bios.endswith('.hex'):
                        self.__provmode = 'hexbios'
                    elif bios.endswith('.asm'):
                        self.__provmode = 'bios'
                    else:
                        self.tty.transmit(' * BIOS source file unknown.')
                        self.tty.send_result('PROVERR')
                        return
                    self.__http = hosts(self, 'get_file', bios)
                    return
                except:
                    if DEBUG:
                        raise
                    self.tty.send_result('PROVERR')
        elif result[0] == 'get_file':
            log.debug('get_file returned.')
            if result[1] == 'ERR':
                self.tty.send_result('PROVERR')
            elif self.__provmode == 'bios':
                self.prov_asm('ROM/BIOS', result[1], mode='BIOS')
                if self.prov_get('storage', 'bootloader', True):
                    return
            elif self.__provmode == 'hexbios':
                self.prov_hex('ROM/BIOS', result[1])
                if self.prov_get('storage', 'hexfile'):
                    return
                if self.prov_get('storage', 'bootloader', True):
                    return
            elif self.__provmode == 'bootloader':
                self.prov_asm('Bootloader', result[1], mode='BLKDEV', dev=0, blk=0)
                if self.__prov.has_option('filesystem', 'fstype'):
                    if self.__prov.get('filesystem', 'fstype') == 'hardcoded':
                        try:
                            self.mem.blkdev[0].format_header()
                        except:
                            log.error('Error creating fs header data!')
                            self.tty.send_result('PROVERR')
                            return
                        self.mem.blkdev[0].fstype = 'hardcoded'
                        self.__curfile = 1
                        if self.prov_get('file1', 'asm'):
                            return
                        elif self.prov_get('file1', 'text', True):
                            return
                    return
                if self.prov_get('filesystem', 'mkfs', True):
                    return
            elif self.__provmode == 'mkfs':
                self.mem.blkdev[0].fstype = 'mkfs'
                blk = self.__prov.getint('filesystem', 'superblock')
                self.prov_asm('mkfs', result[1], mode='BLKDEV', dev=0, blk=blk)
                self.__curfile = 1
                if self.prov_get('file1', 'asm'):
                    return
                elif self.prov_get('file1', 'text', True):
                    return
            elif self.__provmode == 'asm':
                try:
                    blk = self.__prov.getint('file%s' % self.__curfile, 'block')
                except:
                    blk = 0
                description = self.__prov.get('file%s' % self.__curfile, 'description')
                self.prov_asm(description, result[1], mode='BLKDEV', dev=0, blk=blk)
                self.__curfile+=1
                if self.prov_get('file%s' % self.__curfile, 'asm'):
                    return
                elif self.prov_get('file%s' % self.__curfile, 'text', True):
                    return
            elif self.__provmode == 'text':
                description = self.__prov.get('file%s' % self.__curfile, 'description')
                self.tty.transmit(' * Storing %s...' % description)
                if self.mem.blkdev[0].fstype == 'hardcoded':
                    self.mem.blkdev[0].writefile(self.__prov.get('file%s' % self.__curfile, 'text'), result[1])
                else:
                    blk = self.__prov.getint('file%s' % self.__curfile, 'block')
                    self.mem.blkdev[0].writeblock(blk, result[1])
                self.__curfile+=1
                if self.prov_get('file%s' % self.__curfile, 'asm'):
                    return
                elif self.prov_get('file%s' % self.__curfile, 'text', True):
                    return
            elif self.__provmode == 'hexfile':
                self.tty.transmit(' * Provisioning block storage using hex file...')
                try:
                    sio = StringIO.StringIO(result[1])
                    h = IntelHex(sio)
                    for addr in h.addresses():
                        self.mem.blkdev[0].blkdev[addr] = chr(h[addr])
                    del h
                    sio.close()
                    del sio
                except:
                    raise
                self.prov_get('NA', 'NA', True)
            else:
                log.critical('Unhandled provision mode: %s' % self.__provmode)
                self.tty.transmit(' * Unknown provisioning mode!')
                self.tty.send_result('PROVERR')
                return
        else:
            log.critical('http_callback got %s!' % result[0])                
        self.__http = None
    def vm_result(self, result, ip_addr=None):
        log.debug('VM Result code for %s: %s' % (ip_addr, result))
        if ip_addr not in self.__socks.keys():
            return
        if result == 'TERM':
            del self.mem.host['nettbl'][self.__socks[ip_addr].idx]
            del self.__socks[ip_addr]
            self.set_host()
            self.running = True
        elif result == 'ONLINE':
            if self.__socks[ip_addr].state == 'netconn':
                self.__socks[ip_addr].vm_netconn(self.__socks[ip_addr].port, self.ip_addr)
                self.mem.set_io(0x75, 0x0)
                #self.running = True
        elif result == 'OFFLINE':
            if self.__socks[ip_addr].state == 'netconn':
                del self.mem.host['nettbl'][self.__socks[ip_addr].idx]
                self.__socks[ip_addr].handle_close()
                del self.__socks[ip_addr]
                self.set_host()
                self.mem.set_io(0x75, 0xff)
                self.running = True
        elif result == 'NETOK':
            self.mem.set_io(0x75, 0x0)
            self.running = True
        elif result == 'NETFAIL' or result == 'NOHOST':
            del self.mem.host['nettbl'][self.__socks[ip_addr].idx]
            self.__socks[ip_addr].handle_close()
            del self.__socks[ip_addr]
            self.set_host()
            self.mem.set_io(0x75, 0xff)
            self.running = True
        elif result == 'HALT':
            del self.mem.host['nettbl'][self.__socks[ip_addr].idx]
            self.__socks[ip_addr].handle_close()
            del self.__socks[ip_addr]
            self.set_host()
            self.mem.set_io(0x75, 0xff)
            self.running = True
    def save_state(self):
        log.debug('Saving CPU State for %s...' % self.ip_addr)
        if self.mem.host is not None:
            self.mem.host['cpu_state'] = binascii.b2a_hex(cpu_state.pack(self.regA, self.regX, self.regY, self.regP, self.pc, self.sp, self.ss))
            self.set_host()
    def load_state(self):
        log.debug('Loading CPU State for %s...' % self.ip_addr)
        if self.mem.host is None:
            return False
        if self.mem.host.has_key('cpu_state'):
            data = binascii.a2b_hex(self.mem.host['cpu_state'])
            self.regA, self.regX, self.regY, self.regP, self.pc, self.sp, self.ss = cpu_state.unpack(data)
        self.mem.resume_devices()
        if self.tty is not None:
            self.tty.termbit(self.mem.get_io(0xdc))
        return True
    def clear_memory(self):
        self.running = False
        log.debug('Clearing out host memory: %s' % self.ip_addr)
        self.mem.close()
        self.__file.close()
        memory = '%s/%s/memory' % (get_host_dir(self.ip_addr), self.ip_addr)
        self.__file = open(memory, 'w+b')
        self.__file.write('\x00'*(0xffff+1))
        self.__file.close()
        self.__file = open(memory, 'r+b')
        self.mem.mem = mmap.mmap(self.__file.fileno(), 0)
        self.reset()
    def __del__(self):
        if self.mem is None:
            return
        self.mem.close()
        self.__file.close()
    def set_nv_flags(self, value):
        if value:
            self.regP &= 0xfd
        else:
            self.regP |= 0x02
        if value & 0x80:
            self.regP |= 0x80
        else:
            self.regP &= 0x7f
    def set_carry0(self, value):
        self.regP = (self.regP & 0xfe) | (value & 1)
    def set_carry7(self, value):
        self.regP = (self.regP & 0xfe) | ((value >> 7) & 1)
    def BIT(self, value):
        if value & 0x80:
            self.regP |= 0x80
        else:
            self.regP &= 0x7f
        if value & 0x40:
            self.regP |= 0x40
        else:
            self.regP &= 0x40
        if self.regA & value:
            self.regP &= 0xfd
        else:
            self.regP |= 0x02
    def CLC(self):
        self.regP &= 0xfe
    def SEC(self):
        self.regP |= 1
    def CLV(self):
        self.regP &= 0xbf
    def set_overflow(self):
        self.regP |= 0x40
    def DEC(self, addr):
        value = self.mem.get(addr)
        value-=1
        value &= 0xff
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def INC(self, addr):
        value = self.mem.get(addr)
        value+=1
        value &= 0xff
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def overflow(self):
        return self.regP & 0x40
    def dec_mode(self):
        return self.regP & 8
    def carry(self):
        return self.regP & 1
    def negative(self):
        return self.regP & 0x80
    def zero(self):
        return self.regP & 0x02
    def compare(self, reg, value):
        if reg >= value:
            self.SEC()
        else:
            self.CLC()
        value = reg-value
        self.set_nv_flags(value)
    def test_sbc(self, value):
        if (self.regA ^ value) & 0x80:
            self.set_overflow()
        else:
            self.CLV()
        if self.dec_mode():
            tmp = 0xf + (self.regA & 0xf) - (value & 0xf) + self.carry()
            if tmp < 0x10:
                w = 0
                tmp -= 6
            else:
                w = 0x10
                tmp -= 0x10
            w += 0xf0 + (self.regA & 0xf0) - (value & 0xf0)
            if w < 0x100:
                self.CLC()
                if self.overflow() and w < 0x80:
                    self.CLV()
                w -= 0x60
            else:
                self.SEC()
                if self.overflow() and w >= 0x180:
                    self.CLV()
            w += tmp
        else:
            w = 0xff + self.regA - value + self.carry()
            if w < 0x100:
                self.CLC()
                if self.overflow() and w < 0x80:
                    self.CLV()
            else:
                self.SEC()
                if self.overflow() and w >= 0x180:
                    self.CLV()
        self.regA = w & 0xff
        self.set_nv_flags(self.regA)
    def test_adc(self, value):
        if (self.regA ^ value) & 0x80:
            self.CLV()
        else:
            self.set_overflow()
        if self.dec_mode():
            tmp = (self.regA & 0xf) + (value & 0xf) + self.carry()
            if tmp >= 10:
                tmp = 0x10 | ((tmp + 6) & 0xf)
            tmp += (self.regA & 0xf0) + (value & 0xf0)
            if tmp >= 160:
                self.SEC()
                if self.overflow() and tmp >= 0x180:
                    self.CLV()
                tmp += 0x60
            else:
                self.CLC()
                if self.overflow() and tmp < 0x80:
                    self.CLV()
        else:
            tmp = self.regA + value + self.carry()
            if tmp >= 0x100:
                self.SEC()
                if self.overflow() and tmp >= 0x180:
                    self.CLV()
            else:
                self.CLC()
                if self.overflow() and tmp < 0x80:
                    self.CLV()
        self.regA = tmp & 0xff
        self.set_nv_flags(self.regA)
    def fetch(self):
        self.pc+=1
        return self.mem.get(self.pc-1)
    def fetch16(self):
        self.pc+=2
        return self.mem.get_word(self.pc-2)
    def push(self, value):
        self.mem.set((self.sp & 0xff) + self.ss, value & 0xff)
        self.sp-=1
        if self.sp < 0:
            self.sp = 0xff
    def pop(self):
        self.sp+=1
        if self.sp > 0xff:
            self.sp = 0
        return self.mem.get(self.sp + self.ss)
    def branch(self, offset):
        if offset > 0x7f:
            self.pc = (self.pc - (0x100 - offset))
        else:
            self.pc = (self.pc + offset)
    def op_0x0(self):
        caddr = self.pc + 1
        self.push((caddr >> 8) & 0xff)
        self.push((caddr & 0xff))
        self.push(self.regP)
        self.regP |= 0x10
        self.regP &= 0xf7
        self.pc = self.mem.host['isr']
    def op_0x1(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.regA |= value
        self.set_nv_flags(self.regA)
    def op_0x4(self):
        addr = self.fetch()
        value = self.mem.get(addr)
        self.BIT(value)
        value = value & self.regA
        self.mem.set(addr, value)
    def op_0x5(self):
        zp = self.fetch()
        self.regA |= self.mem.get(zp)
        self.set_nv_flags(self.regA)
    def op_0x6(self):
        zp = self.fetch()
        value = self.mem.get(zp)
        self.set_carry7(value)
        value = value << 1
        self.mem.set(zp, value)
        self.set_nv_flags(value)
    def op_0x8(self):
        self.push(self.regP | 0x30)
    def op_0x9(self):
        self.regA |= self.fetch()
        self.set_nv_flags(self.regA)
    def op_0xa(self):
        self.set_carry7(self.regA)
        self.regA = (self.regA << 1) & 0xff
        self.set_nv_flags(self.regA)
    def op_0xc(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.BIT(value)
        value = value & self.regA
        self.mem.set(addr, value)
    def op_0xd(self):
        self.regA |= self.mem.get(self.fetch16())
        self.set_nv_flags(self.regA)
    def op_0xe(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x10(self):
        offset = self.fetch()
        if not self.negative():
            self.branch(offset)
    def op_0x11(self):
        zp = self.fetch()
        value = self.mem.get_word(zp) + self.regY
        self.regA |= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x12(self):
        zp = self.fetch()
        value = self.mem.get_word(zp)
        self.regA |= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x14(self):
        addr = self.fetch()
        value = self.mem.get(addr)
        self.BIT(value)
        value = value & (self.regA ^ 0xff)
        self.mem.set(addr, value)
    def op_0x15(self):
        addr = (self.fetch() + self.regX) & 0xff
        self.regA |= self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0x16(self):
        addr = (self.fetch() + self.regX) & 0xff
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x18(self):
        self.CLC()
    def op_0x19(self):
        addr = self.fetch16() + self.regY
        self.regA |= self.mem.get(addr)
    def op_0x1a(self):
        self.regA = (self.regA + 1) & 0xff
        self.set_nv_flags(self.regA)
    def op_0x1c(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.BIT(value)
        value = value & (self.regA ^ 0xff)
        self.mem.set(addr, value)
    def op_0x1d(self):
        addr = self.fetch16() + self.regX
        self.regA |= self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0x1e(self):
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x20(self):
        addr = self.fetch16()
        caddr = self.pc - 1
        self.push((caddr >> 8) & 0xff)
        self.push((caddr & 0xff))
        self.pc = addr
    def op_0x21(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.regA &= value
        self.set_nv_flags(self.regA)
    def op_0x24(self):
        zp = self.fetch()
        value = self.mem.get(zp)
        self.BIT(value)
    def op_0x25(self):
        zp = self.fetch()
        self.regA &= self.mem.get(zp)
        self.set_nv_flags(self.regA)
    def op_0x26(self):
        sf = self.carry()
        addr = self.fetch()
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        value |= sf
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x28(self):
        self.regP = self.pop() | 0x30
    def op_0x29(self):
        self.regA &= self.fetch()
        self.set_nv_flags(self.regA)
    def op_0x2a(self):
        sf = self.carry()
        self.set_carry7(self.regA)
        self.regA = (self.regA << 1) & 0xff
        self.regA |= sf
        self.set_nv_flags(self.regA)
    def op_0x2c(self):
        value = self.mem.get(self.fetch16())
        self.BIT(value)
    def op_0x2d(self):
        value = self.mem.get(self.fetch16())
        self.regA &= value
        self.set_nv_flags(self.regA)
    def op_0x2e(self):
        sf = self.carry()
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        value |= sf
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x30(self):
        offset = self.fetch()
        if self.negative():
            self.branch(offset)
    def op_0x31(self):
        zp = self.fetch()
        value = self.mem.get_word(zp) + self.regY
        self.regA &= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x32(self):
        zp = self.fetch()
        value = self.mem.get_word(zp)
        self.regA &= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x34(self):
        zp = self.fetch() + self.regX
        value = self.mem.get(zp)
        self.BIT(value)
    def op_0x35(self):
        addr = (self.fetch() + self.regX) & 0xff
        self.regA &= self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0x36(self):
        sf = self.carry()
        addr = (self.fetch() + self.regX) & 0xff
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        value |= sf
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x38(self):
        self.SEC()
    def op_0x39(self):
        addr = self.fetch16() + self.regY
        value = self.mem.get(addr)
        self.regA &= value
        self.set_nv_flags(self.regA)
    def op_0x3a(self):
        self.regA = (self.regA - 1) & 0xff
        self.set_nv_flags(self.regA)
    def op_0x3c(self):
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.BIT(value)
    def op_0x3d(self):
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.regA &= value
        self.set_nv_flags(self.regA)
    def op_0x3e(self):
        sf = self.carry()
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.set_carry7(value)
        value = value << 1
        value |= sf
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x3f(self):
        addr = self.mem.get_word(self.fetch16())
        caddr = self.pc - 1
        self.push((caddr >> 8) & 0xff)
        self.push((caddr & 0xff))
        self.pc = addr
    def op_0x40(self):
        self.regP = self.pop() | 0x30
        self.pc = self.pop() | (self.pop() << 8)
        if self.__exec:
            self.running = False
            self.__exec = False
            self.tty.exec_result(self.regA, self.regX, self.regY)
    def op_0x41(self):
        zp = (self.fetch() + self.regX) & 0xff
        value = self.mem.get_word(zp)
        self.regA ^= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x45(self):
        addr = self.fetch() & 0xff
        value = self.mem.get(addr)
        self.regA ^= value
        self.set_nv_flags(self.regA)
    def op_0x46(self):
        addr = self.fetch() & 0xff
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x48(self):
        self.push(self.regA)
    def op_0x49(self):
        self.regA ^= self.fetch()
        self.set_nv_flags(self.regA)
    def op_0x4a(self):
        self.set_carry0(self.regA)
        self.regA = self.regA >> 1
        self.set_nv_flags(self.regA)
    def op_0x4c(self):
        self.pc = self.fetch16()
    def op_0x4d(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.regA ^= value
        self.set_nv_flags(self.regA)
    def op_0x4e(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x50(self):
        offset = self.fetch()
        if not self.overflow():
            self.branch(offset)
    def op_0x51(self):
        zp = self.fetch()
        value = self.mem.get_word(zp) + self.regY
        self.regA ^= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x52(self):
        zp = self.fetch()
        value = self.mem.get_word(zp)
        self.regA ^= self.mem.get(value)
        self.set_nv_flags(self.regA)
    def op_0x55(self):
        addr = (self.fetch() + self.regX) & 0xff
        self.regA ^= self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0x56(self):
        addr = (self.fetch() + self.regX) & 0xff
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x58(self):
        self.regP &= ~0x04
    def op_0x59(self):
        addr = self.fetch16() + self.regY
        value = self.mem.get(addr)
        self.regA ^= value
        self.set_nv_flags(self.regA)
    def op_0x5a(self):
        self.push(self.regY)
    def op_0x5d(self):
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.regA ^= value
        self.set_nv_flags(self.regA)
    def op_0x5e(self):
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x60(self):
        self.pc = (self.pop() | (self.pop() << 8)) + 1
    def op_0x61(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.test_adc(value)
    def op_0x64(self):
        self.mem.set(self.fetch(), 0x0)
    def op_0x65(self):
        addr = self.fetch()
        value = self.mem.get(addr)
        self.test_adc(value)
    def op_0x66(self):
        sf = self.carry()
        addr = self.fetch()
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        if sf:
            value |= 0x80
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x68(self):
        self.regA = self.pop()
        self.set_nv_flags(self.regA)
    def op_0x69(self):
        value = self.fetch()
        self.test_adc(value)
    def op_0x6a(self):
        sf = self.carry()
        self.set_carry0(self.regA)
        self.regA = self.regA >> 1
        if sf:
            self.regA |= 0x80
        self.set_nv_flags(self.regA)
    def op_0x6c(self):
        self.pc = self.mem.get_word(self.fetch16())
    def op_0x6d(self):
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.test_adc(value)
    def op_0x6e(self):
        sf = self.carry()
        addr = self.fetch16()
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        if sf:
            value |= 0x80
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x70(self):
        offset = self.fetch()
        if self.overflow():
            self.branch(offset)
    def op_0x71(self):
        zp = self.fetch()
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr+self.regY)
        self.test_adc(value)
    def op_0x72(self):
        zp = self.fetch()
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.test_adc(value)
    def op_0x74(self):
        addr = self.fetch() + self.regX
        self.mem.set(addr, 0x0)
    def op_0x75(self):
        addr = (self.fetch() + self.regX) & 0xff
        value = self.mem.get(addr)
        self.test_adc(value)
    def op_0x76(self):
        sf = self.carry()
        addr = (self.fetch() + self.regX) & 0xff
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        if sf:
            value |= 0x80
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x78(self):
        self.regP |= 0x04
    def op_0x79(self):
        addr = self.fetch16()
        value = self.mem.get(addr + self.regY)
        self.test_adc(value)
    def op_0x7a(self):
        self.regY = self.pop()
        self.set_nv_flags(self.regY)
    def op_0x7c(self):
        self.pc = self.mem.get_word(self.fetch16() + self.regX)
    def op_0x7d(self):
        addr = self.fetch16()
        value = self.mem.get(addr + self.regX)
        self.test_adc(value)
    def op_0x7e(self):
        sf = self.carry()
        addr = self.fetch16() + self.regX
        value = self.mem.get(addr)
        self.set_carry0(value)
        value = value >> 1
        if sf:
            value |= 0x80
        self.mem.set(addr, value)
        self.set_nv_flags(value)
    def op_0x80(self):
        offset = self.fetch()
        self.branch(offset)
    def op_0x81(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        self.mem.set(addr, self.regA)
    def op_0x84(self):
        self.mem.set(self.fetch(), self.regY)
    def op_0x85(self):
        self.mem.set(self.fetch(), self.regA)
    def op_0x86(self):
        self.mem.set(self.fetch(), self.regX)
    def op_0x88(self):
        self.regY = (self.regY - 1) & 0xff
        self.set_nv_flags(self.regY)
    def op_0x89(self):
        value = self.fetch()
        self.BIT(value)
    def op_0x8a(self):
        self.regA = self.regX & 0xff
        self.set_nv_flags(self.regA)
    def op_0x8c(self):
        self.mem.set(self.fetch16(), self.regY)
    def op_0x8d(self):
        self.mem.set(self.fetch16(), self.regA)
    def op_0x8e(self):
        self.mem.set(self.fetch16(), self.regX)
    def op_0x90(self):
        offset = self.fetch()
        if not self.carry():
            self.branch(offset)
    def op_0x91(self):
        zp = self.fetch()
        addr = self.mem.get_word(zp) + self.regY
        self.mem.set(addr, self.regA)
    def op_0x92(self):
        zp = self.fetch()
        addr = self.mem.get_word(zp)
        self.mem.set(addr, self.regA)
    def op_0x94(self):
        self.mem.set((self.fetch() + self.regX) & 0xff, self.regY)
    def op_0x95(self):
        self.mem.set((self.fetch() + self.regX) & 0xff, self.regA)
    def op_0x96(self):
        self.mem.set((self.fetch() + self.regY) & 0xff, self.regX)
    def op_0x98(self):
        self.regA = self.regY & 0xff
        self.set_nv_flags(self.regA)
    def op_0x99(self):
        self.mem.set(self.fetch16() + self.regY, self.regA)
    def op_0x9a(self):
        self.sp = self.regX & 0xff
    def op_0x9c(self):
        self.mem.set(self.fetch16(), 0x0)
    def op_0x9d(self):
        self.mem.set(self.fetch16() + self.regX, self.regA)
    def op_0x9e(self):
        self.mem.set(self.fetch16() +  self.regX, 0x0)
    def op_0xa0(self):
        self.regY = self.fetch()
        self.set_nv_flags(self.regY)
    def op_0xa1(self):
        zp = (self.fetch() + self.regX) & 0xff
        self.regA = self.mem.get(self.mem.get_word(zp))
        self.set_nv_flags(self.regA)
    def op_0xa2(self):
        self.regX = self.fetch()
        self.set_nv_flags(self.regX)
    def op_0xa4(self):
        self.regY = self.mem.get(self.fetch())
        self.set_nv_flags(self.regY)
    def op_0xa5(self):
        self.regA = self.mem.get(self.fetch())
        self.set_nv_flags(self.regA)
    def op_0xa6(self):
        self.regX = self.mem.get(self.fetch())
        self.set_nv_flags(self.regX)
    def op_0xa8(self):
        self.regY = self.regA & 0xff
        self.set_nv_flags(self.regY)
    def op_0xa9(self):
        self.regA = self.fetch()
        self.set_nv_flags(self.regA)
    def op_0xaa(self):
        self.regX = self.regA & 0xff
        self.set_nv_flags(self.regX)
    def op_0xac(self):
        self.regY = self.mem.get(self.fetch16())
        self.set_nv_flags(self.regY)
    def op_0xad(self):
        self.regA = self.mem.get(self.fetch16())
        self.set_nv_flags(self.regA)
    def op_0xae(self):
        self.regX = self.mem.get(self.fetch16())
        self.set_nv_flags(self.regX)
    def op_0xb0(self):
        offset = self.fetch()
        if self.carry():
            self.branch(offset)
    def op_0xb1(self):
        addr = self.mem.get_word(self.fetch()) + self.regY
        self.regA = self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0xb2(self):
        addr = self.mem.get_word(self.fetch())
        self.regA = self.mem.get(addr)
        self.set_nv_flags(self.regA)
    def op_0xb4(self):
        self.regY = self.mem.get((self.fetch() + self.regX) & 0xff)
        self.set_nv_flags(self.regY)
    def op_0xb5(self):
        self.regA = self.mem.get((self.fetch() + self.regX) & 0xff)
        self.set_nv_flags(self.regA)
    def op_0xb6(self):
        self.regX = self.mem.get((self.fetch() + self.regY) & 0xff)
        self.set_nv_flags(self.regX)
    def op_0xb8(self):
        self.CLV()
    def op_0xb9(self):
        self.regA = self.mem.get(self.fetch16() + self.regY)
        self.set_nv_flags(self.regA)
    def op_0xba(self):
        self.regX = self.sp & 0xff
        self.set_nv_flags(self.regX)
    def op_0xbc(self):
        self.regY = self.mem.get(self.fetch16() + self.regX)
        self.set_nv_flags(self.regY)
    def op_0xbd(self):
        self.regA = self.mem.get(self.fetch16() + self.regX)
        self.set_nv_flags(self.regA)
    def op_0xbe(self):
        self.regX = self.mem.get(self.fetch16() + self.regY)
        self.set_nv_flags(self.regX)
    def op_0xc0(self):
        self.compare(self.regY, self.fetch())
    def op_0xc1(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.compare(self.regA, value)
    def op_0xc4(self):
        self.compare(self.regY, self.mem.get(self.fetch()))
    def op_0xc5(self):
        self.compare(self.regA, self.mem.get(self.fetch()))
    def op_0xc6(self):
        self.DEC(self.fetch())
    def op_0xc8(self):
        self.regY = (self.regY + 1) & 0xff
        self.set_nv_flags(self.regY)
    def op_0xc9(self):
        self.compare(self.regA, self.fetch())
    def op_0xca(self):
        self.regX = (self.regX -1) & 0xff
        self.set_nv_flags(self.regX)
    def op_0xcc(self):
        self.compare(self.regY, self.mem.get(self.fetch16()))
    def op_0xcd(self):
        self.compare(self.regA, self.mem.get(self.fetch16()))
    def op_0xce(self):
        self.DEC(self.fetch16())
    def op_0xd0(self):
        offset = self.fetch()
        if not self.zero():
            self.branch(offset)
    def op_0xd1(self):
        addr = self.mem.get_word(self.fetch()) + self.regY
        value = self.mem.get(addr)
        self.compare(self.regA, value)
    def op_0xd2(self):
        addr = self.mem.get_word(self.fetch())
        value = self.mem.get(addr)
        self.compare(self.regA, value)
    def op_0xd5(self):
        value = self.mem.get((self.fetch() + self.regX) & 0xff)
        self.compare(self.regA, value)
    def op_0xd6(self):
        self.DEC((self.fetch() + self.regX) & 0xff)
    def op_0xd8(self):
        self.regP &= 0xf7
    def op_0xd9(self):
        value = self.mem.get(self.fetch16() + self.regY)
        self.compare(self.regA, value)
    def op_0xda(self):
        self.push(self.regX)
    def op_0xdd(self):
        value = self.mem.get(self.fetch16() + self.regX)
        self.compare(self.regA, value)
    def op_0xde(self):
        self.DEC(self.fetch16() + self.regX)
    def op_0xe0(self):
        self.compare(self.regX, self.fetch())
    def op_0xe1(self):
        zp = (self.fetch() + self.regX) & 0xff
        addr = self.mem.get_word(zp)
        value = self.mem.get(addr)
        self.test_sbc(value)
    def op_0xe4(self):
        self.compare(self.regX, self.mem.get(self.fetch()))
    def op_0xe5(self):
        self.test_sbc(self.mem.get(self.fetch()))
    def op_0xe6(self):
        self.INC(self.fetch())
    def op_0xe8(self):
        self.regX = (self.regX + 1) & 0xff
        self.set_nv_flags(self.regX)
    def op_0xe9(self):
        self.test_sbc(self.fetch())
    def op_0xea(self):
        pass
    def op_0xeb(self):
        pass
    def op_0xec(self):
        self.compare(self.regX, self.mem.get(self.fetch16()))
    def op_0xed(self):
        self.test_sbc(self.mem.get(self.fetch16()))
    def op_0xee(self):
        self.INC(self.fetch16())
    def op_0xf0(self):
        offset = self.fetch()
        if self.zero():
            self.branch(offset)
    def op_0xf1(self):
        self.test_sbc(self.mem.get(self.mem.get_word(self.fetch())) + self.regY)
    def op_0xf2(self):
        self.test_sbc(self.mem.get(self.mem.get_word(self.fetch())))
    def op_0xf5(self):
        addr = (self.fetch() + self.regX) & 0xff
        self.test_sbc(self.mem.get(addr))
    def op_0xf6(self):
        self.INC((self.fetch() + self.regX) & 0xff)
    def op_0xf8(self):
        self.regP |= 8
    def op_0xf9(self):
        self.test_sbc(self.mem.get(self.fetch16() + self.regY))
    def op_0xfa(self):
        self.regX = self.pop()
        self.set_nv_flags(self.regX)
    def op_0xfd(self):
        self.test_sbc(self.mem.get(self.fetch16() + self.regX))
    def op_0xfe(self):
        self.INC(self.fetch16() + self.regX)
    def process_op(self):
        if len(self.__intr) > 0 and (self.regP & 0x04) == 0x0:
            addr = self.__intr.pop()
            log.debug('External interrupt to address %s' % hex(addr))
            self.push((self.pc >> 8) & 0xff)
            self.push((self.pc & 0xff))
            self.push(self.regP)
            self.pc = addr
        op = hex(self.fetch())
        try:
            getattr(self, 'op_%s' % op)()
        except VMNoData:
            self.pc-=3
            self.running = False
        except VMNetData, e:
            log.debug('VM Network data processing: %s' % e)
            op, idx = str(e).split(':')
            if op == 'CONN':
                idx = int(idx)
                try:
                    ip_addr = self.mem.host['nettbl'][idx]['ip_addr']
                    port = self.mem.host['nettbl'][idx]['port']
                    log.debug('Net connection to %s:%s' % (ip_addr, port))
                    self.__socks[ip_addr] = VMConnector(self, ip_addr)
                    self.__socks[ip_addr].state = 'netconn'
                    self.__socks[ip_addr].port = port
                    self.__socks[ip_addr].idx = idx
                    self.running = False
                except:
                    log.critical('Unable to create network connection.')
                    if ip_addr in self.__socks.keys():
                        self.__socks[ip_addr].handle_close()
                        del self.__socks[ip_addr]
                    self.mem.mem[0xff75] = chr(1)
            elif op == 'SEND':
                idx = int(idx)
                data = self.mem.netout
                log.debug('Sending %s to host...' % data)
                try:
                    ip_addr = self.mem.host['nettbl'][idx]['ip_addr']
                    self.__socks[ip_addr].state = 'netsend'
                    self.__socks[ip_addr].vm_netin(data)
                    self.__socks[ip_addr].idx = idx
                    self.mem.mem[0xff75] = chr(0)
                except:
                    log.critical('Unable to send network data.')
                    self.mem.mem[0xff75] = chr(1)
            elif op == 'DISC':
                log.debug('Disconnecting from host: %s' % idx)
                self.vm_state = None
                self.__socks[idx].handle_close()
                del self.__socks[idx]
            elif op == 'SRV':
                log.debug('Sending data from server to client %s.' % self.__from_ip)
                data = self.mem.netout
                self.tty.netout(data)
                self.mem.mem[0xff75] = chr(0)
        except VMHalt:
            log.debug('VMHalt API called.')
            self.running = False
            self.shutdown()
            self.tty.send_result('HALT')
        except VMReset:
            log.debug('VMReset API called.')
            if self.tty is not None:
                self.tty.transmit(' * Host is being reset...')
            self.running = False
            self.mem.host['online'] = False
            self.ipl()
            self.running = True
        except VMTermBit:
            log.debug('Terminal bit set request.')
            if self.tty is not None:
                self.tty.termbit(self.mem.get_io(0xdc))
        except AttributeError:
            log.debug('Invalid op code: %s at %s' % (op, hex(self.pc)))
            if DEBUG:
                raise VMError('Invalid op code: %s' % op)

def vmfunc(func):
    def wrapped_f(self, ip_addr, *args):
        if ip_addr not in self.vms.keys():
            return False
        method = func(self)
        if method is None:
            return
        try:
            return getattr(self.vms[ip_addr], method)(*args)
        except:
            return False
    return wrapped_f

class VMManager(object):
    def __init__(self):
        self.vms = {}
        self.vm_count = {}
        self.running_vms = 0
    def allocate(self, ip_addr, tty=None):
        if ip_addr in self.vms.keys():
            log.debug('Trying to allocate already allocated VM %s' % ip_addr)
            self.vm_count[ip_addr]+=1
            if tty:
                self.vms[ip_addr].set_tty(tty)
            return True
        self.vms[ip_addr] = CPU(ip_addr, tty)
        self.vm_count[ip_addr] = 1
        return False
    def destroy(self, ip_addr, tty=False):
        if ip_addr not in self.vms.keys():
            log.debug('Trying to destroy non-existent VM %s' % ip_addr)
            return
        self.vms[ip_addr].netclose()
        self.vm_count[ip_addr]-=1
        if self.vm_count[ip_addr] < 1:
            log.info('Destroying VM %s' % ip_addr)
            try:
                self.vms[ip_addr].suspend()
            except:
                log.critical('Unable to suspend %s' % ip_addr)
            del self.vm_count[ip_addr]
            del self.vms[ip_addr]
        else:
            if tty:
                self.vms[ip_addr].set_tty(None)
    @vmfunc
    def boot(self):
        return 'ipl'
    @vmfunc
    def mkhost(self):
        return 'mkhost'
    @vmfunc
    def shutdown(self):
        return 'shutdown'
    @vmfunc
    def provision(self):
        return 'provision'
    @vmfunc
    def tty(self):
        return 'start'
    @vmfunc
    def stdin(self):
        return 'stdin'
    @vmfunc
    def netconn(self):
        return 'netconn'
    @vmfunc
    def netin(self):
        return 'netin'
    @vmfunc
    def brk(self):
        return 'brk'
    @vmfunc
    def nmi(self):
        return 'nmi'
    @vmfunc
    def hex_import(self):
        return 'hex_import'
    @vmfunc
    def hex_hostfs(self):
        return 'hex_hostfs'
    @vmfunc
    def attach(self):
        return 'attach'
    @vmfunc
    def detach(self):
        return 'detach'
    @vmfunc
    def mouse(self):
        return 'mouse'
    @vmfunc
    def execute(self):
        return 'execute'
    @vmfunc
    def debug_info(self):
        return 'debug_info'
    @property
    def timeout(self):
        return 30.0 if self.running_vms == 0 else 0
    def vmloop(self):
        self.running_vms = 0
        for vm in self.vms.values():
            if vm.running:
                self.running_vms+=1
                try:
                    vm.process_op()
                    if not vm.running:
                        vm.tty.stdout(vm.mem.stdout)
                    elif vm.mem.stdflush:
                        vm.mem.reset_stdflush()
                        vm.tty.stdout(vm.mem.stdout)
                except VMFlush:
                    vm.tty.stdout(vm.mem.stdout)
                except VMError, e:
                    vm.running = False
                    vm.tty.transmit(' * %s' % e)
                    vm.tty.send_result('EXCPT')
                except NotImplemented, e:
                    vm.tty.transmit(' * NotImplemented: %s' % e)
                except:
                    raise # For now

hypervisor = VMManager()

class VMChannel(asynchat.async_chat):
    def __init__(self, channel):
        asynchat.async_chat.__init__(self, channel)
        self.set_terminator(chr(255)+chr(0))
        self.ibuffer = ''
        self.__tty = None
        self.__ip_addr = None
    def send_result(self, data):
        self.push(chr(253)+str(data)+chr(255)+chr(0))
    def stdout(self, data):
        if self.__tty:
            self.push(chr(254)+str(data)+chr(255)+chr(0))
    def netout(self, data):
        self.push(chr(252)+str(data)+chr(255)+chr(0))
    def termbit(self, data):
        self.push(chr(251)+chr(data)+chr(255)+chr(0))
    def exec_result(self, regA, regX, regY):
        self.push(chr(250)+chr(regA)+chr(regX)+chr(regY)+chr(255)+chr(0))
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
            log.info('VM Request to %s' % self.__ip_addr)
            if hypervisor.allocate(self.__ip_addr, self):
                self.send_result('ONLINE')
        elif self.__ip_addr is not None and data[0] == chr(255):
            if data[1] == chr(1):
                log.debug('VM Boot/IPL requested for %s' % self.__ip_addr)
                if hypervisor.boot(self.__ip_addr):
                    self.send_result('IPL')
                else:
                    self.send_result('BOOTFAIL')
            elif data[1] == chr(2):
                log.debug('VM Shutdown requested for %s' % self.__ip_addr)
                hypervisor.shutdown(self.__ip_addr)
                self.send_result('HALT')
            elif data[1] == chr(3):
                log.debug('VM TTY requested.')
                hypervisor.tty(self.__ip_addr)
            elif data[1] == chr(4):
                log.debug('VM mkhost requested.')
                if hypervisor.mkhost(self.__ip_addr):
                    self.send_result('MKHOST')
                else:
                    self.send_result('MKERR')
            elif data[1] == chr(5):
                log.debug('Requested connection to network port %s' % ord(data[2]))
                if hypervisor.netconn(self.__ip_addr, ord(data[2]), data[3:]):
                    self.send_result('NETOK')
                else:
                    self.send_result('NETFAIL')
                    self.handle_close()
            elif data[1] == chr(6):
                log.debug('VM Interrupt requested for %s' % self.__ip_addr)
                hypervisor.brk(self.__ip_addr)
            elif data[1] == chr(7):
                log.debug('VM NMI requested for %s' % self.__ip_addr)
                hypervisor.nmi(self.__ip_addr)
            elif data[1] == chr(8):
                log.info('VM Debug CPU info requested for %s' % self.__ip_addr)
                hypervisor.debug_info(self.__ip_addr)
        elif self.__ip_addr is None and data[0] == chr(254):
            self.__tty = True
            if data[1:] == 'VMSTATS':
                log.debug('VM stats requested.')
                vm_count = 0
                for c in asyncore.socket_map.values():
                    if c.connected:
                        vm_count+=1
                if len(hypervisor.vms) != vm_count-1:
                    vm_count = len(hypervisor.vms)
                status = open('/proc/%s/status' % os.getpid(),'r').read()
                rssi = status.index('VmRSS:')
                rss = status[rssi:status.index('\n',rssi)]
                self.send_result(chr((vm_count-1) & 0xff)+rss)
        elif self.__ip_addr is not None and data[0] == chr(254):
            self.__tty = True
            if data[1:] == 'HOSTDATA':
                log.debug('Host data requested.')
                self.send_result(pickle.dumps(hypervisor.vms[self.__ip_addr].mem.host))
        elif self.__ip_addr is not None and data[0] == chr(253):
            log.debug('VM Provision with template %s' % data[1:])
            hypervisor.provision(self.__ip_addr, data[1:])
        elif self.__ip_addr is not None and data[0] == chr(252):
            log.debug('VM STDIN: %s' % data[1:])
            hypervisor.stdin(self.__ip_addr, data[1:])
        elif self.__ip_addr is not None and data[0] == chr(251):
            log.debug('VM NETIN: %s' % data[1:])
            hypervisor.netin(self.__ip_addr, data[1:])
        elif self.__ip_addr is not None and data[0] == chr(250):
            log.debug('RAW Host Memory operation requested for %s' % self.__ip_addr)
            if data[1] == chr(1):
                pass # Future API for Memory read operation.
            elif data[1] == chr(2):
                if hypervisor.hex_import(self.__ip_addr, data[2:]):
                    self.send_result('HEXOK')
                else:
                    self.send_result('HEXFAIL')
            elif data[1] == chr(3):
                sz = 3+ord(data[2])
                fname = data[3:sz]
                if hypervisor.hex_hostfs(self.__ip_addr, fname, data[sz:]):
                    self.send_result('HEXOK')
                else:
                    self.send_result('HEXFAIL')
        elif self.__ip_addr is not None and data[0] == chr(249):
            log.debug('Storage attachment requested for %s' % self.__ip_addr)
            if data[1] == chr(1):
                if hypervisor.attach(self.__ip_addr, data[2:]):
                    self.send_result('ATTACHOK')
                else:
                    self.send_result('ATTACHER')
            elif data[1] == chr(2):
                if hypervisor.detach(self.__ip_addr, data[2:]):
                    self.send_result('DETACHOK')
                else:
                    self.send_result('DETACHER')
            elif data[1] == chr(3):
                try:
                    self.send_result(pickle.dumps(hypervisor.vms[self.__ip_addr].mem.host['storage']))
                except:
                    self.send_result('NOBLKDEV')
        elif self.__ip_addr is not None and data[0] == chr(248):
            log.debug('Mouse input interrupt for %s' % self.__ip_addr)
            hypervisor.mouse(self.__ip_addr, ord(data[1]), ord(data[2]), ord(data[3]))
        elif self.__ip_addr is not None and data[0] == chr(247):
            addr = ord(data[1])+(ord(data[2]) << 8)
            log.debug('Game Engine remote execution request for %s' % self.__ip_addr)
            if hypervisor.execute(self.__ip_addr, addr, str(data[5:]),ord(data[3]), ord(data[4])):
                self.send_result('EXECOK')
            else:
                self.send_result('EXECER')
    def handle_close(self):
        log.info('VM connection closed to %s' % self.__ip_addr)
        hypervisor.destroy(self.__ip_addr, self.__tty)
        self.close()
    def alert_tty(self):
        self.transmit(' * VM daemon shutting down...')
        self.send_result('TERM')
        self.handle_close()
    def log_info(self, message, type='info'):
        log.critical(message)

class VMServer(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.bind('vm6502')
        self.listen(5)
        log.info("Listening on UNIX domain socket.")
    def handle_accept(self):
        channel, addr = self.accept()
        VMChannel(channel)
    def log_info(self, message, type='info'):
        log.critical(message)
    def alert_tty(self):
        self.close()

def event_loop():
    hypervisor.vmloop()
