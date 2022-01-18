from databases import get_host, set_host
from exceptions import VMError, VMNoData, VMFlush, ExecuteBin, SessionCtrl, VMNetData
import hostops, mmap, logging, threading, os, random, hashlib, binascii, struct, time
import cStringIO as StringIO
from Crypto.Cipher import Blowfish
from netdev import network

log = logging.getLogger('HackerVM')

cpu_state = struct.Struct('>BBBBIBI')

class BlockDevice(object):
    def __init__(self, fname):
        self.__f = open(fname, 'r+b')
        self.blkdev = mmap.mmap(self.__f.fileno(), 0)
        self.__readonly = True if fname.startswith('storage/') else False
        log.info('Mapped block device %s as readonly = %s' % (fname, self.__readonly))
    def close(self):
        self.blkdev.flush()
        self.blkdev.close()
        self.__f.close()
    def readblock(self, blk):
        self.blkdev.seek(blk*256)
        return self.blkdev.read(256)
    def writeblock(self, blk, data):
        if self.__readonly:
            raise VMError('Attempting to write to a read-only device.')
        self.blkdev.seek(blk*256)
        self.blkdev.write(data)
    def clearblock(self, blk):
        self.writeblock(blk, '\x00'*256)
    def __getitem__(self, blk):
        return self.readblock(blk)
    def __setitem__(self, blk, data):
        self.writeblock(blk, data)
    def __delitem__(self, blk):
        self.clearblock(blk)

class Memory(object):
    def __init__(self, fileno, size, ip_addr):
        self.mem = mmap.mmap(fileno, 0)
        self.mem.resize(size+1)
        self.__stdout = StringIO.StringIO()
        self.__stdin_lck = threading.Lock()
        self.__stdin = []
        self.__netout = StringIO.StringIO()
        self.__netin_lck = threading.Lock()
        self.__netin = {}
        self.__remote_ip = None
        self.fname = None
        self.ip_addr = ip_addr
        self.blkdev = []
        self.host = get_host(ip_addr)
        if self.host.has_key('storage'):
            for fname in self.host['storage']:
                self.blkdev.append(BlockDevice(fname))
    def __del__(self):
        while len(self.blkdev) > 0:
            blk = self.blkdev.pop()
            blk.close()
            del blk
    def flush(self):
        self.mem.flush()
    def close(self):
        self.mem.flush()
        self.mem.close()
    def set_host(self):
        set_host(self.ip_addr, self.host)
        self.update_netseg()
    def get_host(self):
        self.host = get_host(self.ip_addr)
        self.update_netseg()
    def enable_mouse(self):
        raise SessionCtrl('M:1')
    def disable_mouse(self):
        raise SessionCtrl('M:0')
    def __file_getio(self, ctrl, seek, page, value):
            if ctrl == 1:
                f = hostops.open_file(self.fname, 'w+b')
                f.seek(page+seek)
                seek+=1
                if seek>255:
                    seek=0
                    page+=1
                    if page>255:
                        page=0
                    self.mem[0xff85] = chr(page)
                self.mem[0xff83] = chr(seek)
                f.write(chr(value))
                f.close()
            elif ctrl == 2:
                f = hostops.open_file(self.fname, 'w+b')
                f.seek(page+seek)
                page+=1
                if page>255:
                    page=255
                self.mem[0xff85] = chr(page)
                self.seek(value << 8)
                f.write(self.read(0xff))
                f.close()
            elif ctrl == 3:
                f = hostops.open_file(self.fname, 'r+b')
                f.seek(page+seek)
                page+=1
                if page>255:
                    page=255
                self.mem[0xff85] = chr(page)
                self.seek(value << 8)
                self.write(f.read(0xff))
                f.close()
            elif ctrl == 4:
                raise ExecuteBin('%s#%s' % (self.fname, value))
            elif ctrl == 5:
                hd = get_host(self.ip_addr)
                try:
                    fname = hd['files'][value]
                except:
                    raise VMError('Invalid file index: %s' % value)
                self.setstring(self.get_word(self.get_word(0xff80)), fname)
    def __net_setio(self, ctrl):
        if ctrl == 1:
            svr = {'type':1}
            svr['addr'] = self.get_word(0xff72)
            svr['port'] = self.get(0xff74)
            svr['contbl'] = []
            for e in self.host['nettbl']:
                if e['type'] == 1 and e['port'] == svr['port']:
                    raise ValueError('Port in-use.')
            idx = len(self.host['nettbl'])
            self.host['nettbl'].append(svr)
            self.set_host()
            self.update_netseg()
            self.mem[0xff71] = chr(idx)
            self.mem[0xff75] = chr(0)
        elif ctrl == 2:
            cli = {'type':2}
            cli['ip_addr'] = self.getip(self.get_word(0xff76))
            cli['port'] = self.get(0xff74)
            idx = len(self.host['nettbl'])
            self.host['nettbl'].append(cli)
            self.set_host()
            self.update_netseg()
            self.mem[0xff71] = chr(idx)
            self.mem[0xff75] = chr(0)
            raise VMNetData('CONN:%s' % idx)
        elif ctrl == 3:
            idx = ord(self.mem[0xff71])
            if idx > len(self.host['nettbl']):
                self.mem[0xff75] = chr(len(self.host['nettbl']))
                return
            entry = self.host['nettbl'][idx]
            if entry['type'] == 1:
                self.set_word(0xff72, entry['addr'])
                self.set(0xff74, entry['port'])
            elif entry['type'] == 2:
                pass
        elif ctrl == 4:
            idx = ord(self.mem[0xff71])
            if idx > len(self.host['nettbl']):
                self.mem[0xff75] = chr(len(self.host['nettbl']))
                return
            entry = self.host['nettbl'][idx]
            if entry['type'] == 1:
                del self.host['nettbl'][idx]
                self.set_host()
                self.update_netseg()
                self.mem[0xff71] = chr(0)
                self.mem[0xff75] = chr(0)
            elif entry['type'] == 2:
                del self.host['nettbl'][idx]
                self.set_host()
                self.update_netseg()
                self.mem[0xff71] = chr(0)
                self.mem[0xff75] = chr(0)
        elif ctrl == 5:
            idx = ord(self.mem[0xff71])
            if idx > len(self.host['nettbl']):
                self.mem[0xff75] = chr(len(self.host['nettbl']))
                return
            network.sendto(self.host['nettbl'][idx]['ip_addr'], self.netout)
            #raise VMNetData('SEND:%s' % idx)
    def set_io(self, addr, value):
        if addr == 0x20:
            api = value >> 4
            if api == 0x1:
                value = value & 0xf
                page = ord(self.mem[0xff21])
                self.seek(page << 8)
                data = self.read(256)
                target = self.get_word(self.get(ord(self.mem[0xff22])))
                result = ''
                if value == 0x0:
                    result = hashlib.md5(data).digest()
                elif value == 0x1:
                    result = hashlib.sha1(data).digest()
                elif value == 0x2:
                    result = hashlib.sha256(data).digest()
                elif value == 0x3:
                    result = hashlib.sha512(data).digest()
                elif value == 0xf:
                    result = struct.pack('i',binascii.crc32(data))
                self.seek(target)
                self.write(result)
            elif api == 0x7:
                value = value & 0xf
                page = ord(self.mem[0xff21])
                self.seek(page << 8)
                data = self.read(256)
                key_addr = self.get_word(self.get(ord(self.mem[0xff22])))
                self.seek(key_addr)
                if value == 0x4:
                    key = self.read(16)
                    data = Blowfish.new(key).encrypt(data)
                elif value == 0x5:
                    key = self.read(32)
                    data = Blowfish.new(key).encrypt(data)
                elif value == 0x8:
                    key = self.read(16)
                    data = Blowfish.new(key).decrypt(data)
                elif value == 0x9:
                    key = self.read(32)
                    data = Blowfish.new(key).decrypt(data)
                self.seek(page << 8)
                self.write(data)
        elif addr == 0x21:
            self.mem[0xff21] = chr(value)
        elif addr == 0x22:
            self.mem[0xff22] = chr(value)
        elif addr == 0x70:
            self.mem[0xff70] = chr(value)
            if value > 1:
                seg = value << 8
                self.setip(seg, self.ip_addr)
                self.mem[seg+4] = chr(0)
                self.host['netseg'] = seg
                self.host['nettbl'] = []
                self.set_host()
            else:
                if self.host.has_key('netseg'):
                    del self.host['nettbl']
                    del self.host['netseg']
                    self.set_host()
        elif addr == 0x71:
            self.mem[0xff71] = chr(value)
        elif addr == 0x72:
            self.mem[0xff72] = chr(value)
        elif addr == 0x73:
            self.mem[0xff73] = chr(value)
        elif addr == 0x74:
            self.mem[0xff74] = chr(value)
        elif addr == 0x75:
            try:
                self.__net_setio(value)
            except VMNetData:
                raise
            except:
                self.mem[0xff75] = chr(0xff)
        elif addr == 0x76:
            self.mem[0xff76] = chr(value)
        elif addr == 0x77:
            self.mem[0xff77] = chr(value)
        elif addr == 0x78:
            self.__netout.write(chr(value))
        elif addr == 0x80:
            self.mem[0xff80] = chr(value)
        elif addr == 0x81:
            self.mem[0xff81] = chr(value)
        elif addr == 0x82:
            self.fname = '%s:%s' % (self.ip_addr, self.getstring(self.get_word(self.get_word(0xff80))))
            self.mem[0xff82] = chr(value)
        elif addr == 0x83:
            self.mem[0xff83] = chr(value)
        elif addr == 0x84:
            if self.fname is None:
                self.mem[0xff86] = chr(2)
            ctrl = ord(self.mem[0xff82])
            seek = ord(self.mem[0xff83])
            page = ord(self.mem[0xff85]) << 8
            result = 0x0
            try:
                self.__file_getio(ctrl, seek, page, value)
            except IOError:
                result = 0x1
            self.mem[0xff86] = chr(result)
        elif addr == 0x85:
            self.mem[0xff85] = chr(value)
        elif addr == 0x8a:
            self.mem[0xff8a] = chr(value)
        elif addr == 0x8b:
            self.mem[0xff8b] = chr(value)
        elif addr == 0x8c:
            self.mem[0xff8c] = chr(value)
        elif addr == 0x8d:
            self.mem[0xff8d] = chr(value)
        elif addr == 0x8e:
            dev = ord(self.mem[0xff8a])
            if dev > len(self.blkdev)-1:
                self.mem[0xff8e] = 0x1
            mempage = ord(self.mem[0xff8b])
            blk = self.get_word(0xff8c)
            self.seek(mempage << 8)
            if value == 1:
                self.mem.write(self.blkdev[dev][blk])
                self.mem[0xff8e] = 0x0
            elif value == 2:
                try:
                    self.blkdev[dev][blk] = self.mem.read(256)
                    self.mem[0xff8e] = 0x0
                except VMError:
                    self.mem[0xff8e] = 0xff
        elif addr == 0xd0:
            self.__stdout.write(chr(value))
        elif addr == 0xd1:
            self.__stdout.write(str(value))
        elif addr == 0xd2:
            self.__stdout.write(hex(value))
        elif addr == 0xd3:
            if chr(value) == 'm':
                fg, bg = str(ord(self.mem[0xffd4])), str(ord(self.mem[0xffd5]))
                self.__stdout.write(chr(27)+'[%s;%sm' % (fg,bg))
            elif value == 0x00:
                raise VMFlush
            else:
                self.__stdout.write(chr(27)+'['+chr(value))
        elif addr == 0xd4:
            self.__stdout.write(chr(27)+'[%sm' % str(value))
            self.mem[0xffd4] = chr(value)
        elif addr == 0xd5:
            fg = str(ord(self.mem[0xffd4]))
            self.__stdout.write(chr(27)+'[%s;%sm' % (fg,str(value)))
            self.mem[0xffd5] = chr(value)
        elif addr == 0xd6:
            col = str(ord(self.mem[0xffd7]))
            self.__stdout.write(chr(27)+'[%s;%sH' % (str(value),col))
            self.mem[0xffd6] = chr(value)
        elif addr == 0xd7:
            row = str(ord(self.mem[0xffd6]))
            self.__stdout.write(chr(27)+'[%s;%sH' % (row,str(value)))
            self.mem[0xffd7] = chr(value)
        elif addr == 0xdb:
            self.mem[0xffdb] = chr(value)
        elif addr == 0xdc:
            self.mem[0xffdc] = chr(value)
            if value == 0:
                self.disable_mouse()
            else:
                self.enable_mouse()
        elif addr == 0xdd:
            self.mem[0xffdd] = chr(value)
        elif addr == 0xde:
            self.mem[0xffde] = chr(value)
        elif addr == 0xdf:
            self.mem[0xffdf] = chr(value)
        elif addr == 0xfe:
            word = value + (self.get_io(0xff) << 8)
            self.host['isr'] = word
            self.set_host()
            self.mem[0xfffe] = chr(value)
        elif addr == 0xff:
            word = self.get_io(0xfe) + (value << 8)
            self.host['isr'] = word
            self.set_host()
            self.mem[0xffff] = chr(value)
    def get_io(self, addr):
        if addr == 0x20:
            return random.randint(ord(self.mem[0xff21]),ord(self.mem[0xff22]))
        elif addr == 0x21:
            return ord(self.mem[0xff21])
        elif addr == 0x22:
            return ord(self.mem[0xff22])
        elif addr == 0x27:
            return int(time.time()) & 0xff
        elif addr == 0x28:
            return (int(time.time()) & 0xff00) >> 8
        elif addr == 0x29:
            return (int(time.time()) & 0xff0000) >> 16
        elif addr == 0x2a:
            return (int(time.time()) & 0xff000000) >> 24
        elif addr == 0x70:
            return ord(self.mem[0xff70])
        elif addr == 0x71:
            return ord(self.mem[0xff71])
        elif addr == 0x72:
            return ord(self.mem[0xff72])
        elif addr == 0x73:
            return ord(self.mem[0xff73])
        elif addr == 0x74:
            return ord(self.mem[0xff74])
        elif addr == 0x75:
            return ord(self.mem[0xff75])
        elif addr == 0x76:
            return ord(self.mem[0xff76])
        elif addr == 0x77:
            return ord(self.mem[0xff77])
        elif addr == 0x78:
            idx = ord(self.mem[0xff71])
            if idx > len(self.host['nettbl']):
                self.mem[0xff75] = chr(len(self.host['nettbl']))
                return
            entry = self.host['nettbl'][idx]
            if not entry.has_key('ip_addr'):
                return 0x0
            with self.__netin_lck:
                self.__netin[entry['ip_addr']].reverse()
                try:
                    value = ord(self.__netin[entry['ip_addr']].pop())
                except IndexError:
                    return 0x0
                self.__netin[entry['ip_addr']].reverse()
            return value
        elif addr == 0x80:
            return ord(self.mem[0xff80])
        elif addr == 0x81:
            return ord(self.mem[0xff81])
        elif addr == 0x82:
            return ord(self.mem[0xff82])
        elif addr == 0x83:
            return ord(self.mem[0xff83])
        elif addr == 0x84:
            ctrl = ord(self.mem[0xff82])
            seek = ord(self.mem[0xff83])
            page = ord(self.mem[0xff85]) << 8
            if ctrl == 1:
                f = hostops.open_file(self.fname, 'r+b')
                f.seek(page+seek)
                seek+=1
                if seek>255:
                    seek=0
                    page+=1
                    if page>255:
                        page=0
                    self.mem[0xff85] = chr(page)
                self.mem[0xff83] = chr(seek)
                try:
                    value = ord(f.read(1))
                except:
                    value = 0x0
                f.close()
                return value
            elif ctrl == 5:
                hd = get_host(self.ip_addr)
                return len(hd['files'])
        elif addr == 0x85:
            return ord(self.mem[0xff85])
        elif addr == 0x86:
            return ord(self.mem[0xff86])
        elif addr == 0x8a:
            return ord(self.mem[0xff8a])
        elif addr == 0x8b:
            return ord(self.mem[0xff8b])
        elif addr == 0x8c:
            return ord(self.mem[0xff8c])
        elif addr == 0x8d:
            return ord(self.mem[0xff8d])
        elif addr == 0x8e:
            return ord(self.mem[0xff8e])
        elif addr == 0xd4:
            return ord(self.mem[0xffd4])
        elif addr == 0xd5:
            return ord(self.mem[0xffd5])
        elif addr == 0xdb:
            return ord(self.mem[0xffdb])
        elif addr == 0xdc:
            return ord(self.mem[0xffdc])
        elif addr == 0xdd:
            return ord(self.mem[0xffdd])
        elif addr == 0xde:
            return ord(self.mem[0xffde])
        elif addr == 0xdf:
            return ord(self.mem[0xffdf])
        elif addr == 0xe0:
            with self.__stdin_lck:
                self.__stdin.reverse()
                try:
                    value = ord(self.__stdin.pop())
                except IndexError:
                    raise VMNoData
                self.__stdin.reverse()
            return value
        elif addr == 0xfe:
            return ord(self.mem[0xfffe])
        elif addr == 0xff:
            return ord(self.mem[0xffff])
        return 0x0
    def set(self, addr, value):
        if addr >= 0xff00:
            self.set_io(addr & 0xff, value)
        else:
            self.mem[addr & 0xffff] = chr(value & 0xff)
    def set_word(self, addr, value):
        self.set(addr, value & 0xff)
        self.set(addr+1, (value >> 8) & 0xff)
    def get(self, addr):
        if addr >= 0xff00:
            return self.get_io(addr & 0xff)
        return ord(self.mem[addr & 0xffff])
    def get_word(self, addr):
        return self.get(addr)+(self.get(addr+1) << 8)
    def seek(self, addr):
        self.mem.seek(addr & 0xffff)
    def write(self, data):
        self.mem.write(data)
    def read(self, size):
        return self.mem.read(size)
    @property
    def stdout(self):
        value = self.__stdout.getvalue()
        self.__stdout.seek(0)
        self.__stdout.truncate()
        return value.replace('\n', '\r\n')
    def input(self, data):
        with self.__stdin_lck:
            self.__stdin.extend(list(data))
    @property
    def netout(self):
        value = self.__netout.getvalue()
        self.__netout.seek(0)
        self.__netout.truncate()
        return value
    def netin(self, from_ip, data):
        with self.__netin_lck:
            if from_ip not in self.__netin.keys():
                self.__netin[from_ip] = []
            self.__netin[from_ip].extend(list(data))
    def getstring(self, addr):
        #print hex(addr)
        buf = ''
        while True:
            b=self.get(addr)
            if b == 0:
                break
            buf+=chr(b)
            addr+=1
        return buf
    def setstring(self, addr, data):
        self.mem.seek(addr)
        self.mem.write(data+chr(0))
    def getip(self, addr):
        self.mem.seek(addr)
        return '.'.join([str(ord(c)) for c in list(self.mem.read(4))])
    def setip(self, addr, ip_addr):
        self.mem.seek(addr)
        self.mem.write(''.join([chr(int(c)) for c in ip_addr.split('.')]))
    def update_netseg(self):
        if not self.host.has_key('netseg'):
            return # Ignore the requested update.
        seg = self.host['netseg']
        self.setip(seg, self.ip_addr)
        nettbl = self.host['nettbl']
        self.seek(seg+4)
        self.write(chr(len(nettbl)))
        seg+=5
        for entry in nettbl:
            self.set(seg, entry['type'])
            seg+=1
            if entry['type'] == 1:
                self.set_word(seg, entry['addr'])
                self.set(seg+2, entry['port'])
                self.set(seg+3, len(entry['contbl']))
                seg+=4
                for conn in entry['contbl']:
                    self.setip(seg, conn['ip_addr'])
                    self.set(seg+4, conn['port'])
                    seg+=5
            elif entry['type'] == 2:
                self.setip(seg, entry['ip_addr'])
                self.set(seg+4, entry['port'])
                seg+=5

class CPU(object):
    version = 'HackerVM v0.10.1 $Rev: 193 $'
    def __init__(self, tty=True):
        self.mem = None
        self.tty = tty
        self.__running = False
        self.finished = threading.Event()
        self.reset()
        self.__file = None
        self.__intr = []
    @property
    def running(self):
        return self.__running
    @running.setter
    def running(self, value):
        self.__running = value
        if value:
            self.finished.clear()
        else:
            self.finished.set()
    def reset(self):
        log.debug('CPU Reset initiated.')
        self.regA, self.regX, self.regY, self.regP = 0,0,0,0
        self.pc, self.sp, self.ss = 0,0xff,0x100
        self.running = False
    def ipl(self):
        self.clear_memory()
        self.reset()
        self.mem.set_word(0xf0, 0xe000)
        self.get_host()
        if 'BOOT.SYS' not in self.mem.host['files']:
            self.mem.host['online'] = False
            self.set_host()
            return False
        fname = hostops.get_file('%s:BOOT.SYS' % self.ip_addr)
        self.load(fname, 0x800)
        self.pc = 0x800
        self.mem.host['online'] = True
        self.mem.host['boottime'] = int(time.time())
        self.set_host()
        return True
    def interrupt(self, addr):
        self.__intr.insert(0, addr)
    def set_host(self):
        self.mem.set_host()
    def get_host(self):
        self.mem.get_host()
    @property
    def host(self):
        return self.mem.host
    def switch_host(self, ip_addr):
        log.info('Switching to host %s' % ip_addr)
        if self.__file is not None:
            self.save_state()
            self.mem.close()
            self.__file.close()
        self.ip_addr = ip_addr
        host = get_host(ip_addr)
        memory = '%s/%s/memory' % (host['host_dir'], ip_addr)
        try:
            self.__file = open(memory, 'r+b')
        except IOError:
            log.info('Setting up new VM for %s' % ip_addr)
            self.__file = open(memory, 'w+b')
            self.__file.write('\x00'*(0xffff+1))
            self.__file.close()
            self.__file = open(memory, 'r+b')
        self.mem = Memory(self.__file.fileno(), 0xffff, ip_addr)
        self.load_state()
    def save_state(self):
        self.get_host()
        log.info('Saving CPU State for %s...' % self.ip_addr)
        self.mem.host['cpu_state'] = binascii.b2a_hex(cpu_state.pack(self.regA, self.regX, self.regY, self.regP, self.pc, self.sp, self.ss))
        self.set_host()
    def load_state(self):
        log.info('Loading CPU State for %s...' % self.ip_addr)
        self.mem.get_host()
        if self.mem.host.has_key('cpu_state'):
            data = binascii.a2b_hex(self.mem.host['cpu_state'])
            self.regA, self.regX, self.regY, self.regP, self.pc, self.sp, self.ss = cpu_state.unpack(data)
    def clear_memory(self):
        self.running = False
        log.info('Clearing out host memory: %s' % self.ip_addr)
        self.mem.close()
        self.__file.close()
        memory = '%s/%s/memory' % (self.host['host_dir'], self.ip_addr)
        self.__file = open(memory, 'w+b')
        self.__file.write('\x00'*(0xffff+1))
        self.__file.close()
        self.__file = open(memory, 'r+b')
        self.mem = Memory(self.__file.fileno(), 0xffff, self.ip_addr)
        self.mem.ip_addr = self.ip_addr
        self.reset()
    def __del__(self):
        #log.info('Destroying VM for %s' % self.ip_addr)
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
            raise VMError('Stackoverflow!')
    def pop(self):
        self.sp+=1
        if self.sp > self.ss:
            raise VMError('Stackoverflow!')
        return self.mem.get(self.sp + self.ss)
    def branch(self, offset):
        if offset > 0x7f:
            self.pc = (self.pc - (0x100 - offset))
        else:
            self.pc = (self.pc + offset)
    def op_0x0(self):
        #caddr = self.pc + 1
        #self.push((caddr >> 8) & 0xff)
        #self.push((caddr & 0xff))
        #self.push(self.regP)
        #self.regP |= 0x10
        #self.pc = self.mem.get_word(0xfffe)
        self.running = False
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
        self.pc = self.fetch16() + self.regX
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
    def load(self, fname, addr=0x800):
        self.mem.seek(addr)
        with open(fname, 'rb') as f:
            bintyp = f.read(1)
            if bintyp not in (chr(0xfe),chr(0xff)):
                raise VMError('Invalid binary format.')
            if bintyp == chr(0xfe):
                addr = ord(f.read(1)) << 8
                self.mem.seek(addr)
                self.mem.write(f.read())
                self.pc = addr
                return
            if f.read(1) != chr(0):
                raise VMError('Binary version mismatch.')
            ab = ord(f.read(1))
            if ab > 0:
                absptr = []
                for x in range(0,ab):
                    absptr.append(ord(f.read(1)))
            dsize = ord(f.read(1))
            dseg = self.mem.get_word(0xf0)
            self.mem.set(0xf2, dsize)
            self.mem.seek(dseg)
            self.mem.write(f.read(dsize))
            self.mem.seek(addr)
            self.mem.write(f.read())
            if ab > 0:
                pg = addr >> 8
                for ab in absptr:
                    self.mem.set(ab+addr+1, pg)
                    #ptr = self.mem.get_word(ab+addr)
                    #self.mem.set_word(ab+addr, ptr+addr)
    def set_param(self, param=None):
        if param is None:
            self.mem.set(0xf4, 0)
            return
        try:
            if param[0] == '$':
                v = int(param[1:], 16)
            else:
                v = int(param)
            self.mem.set(0xf4, 1)
            self.mem.set_word(0xf5, v)
        except:
            self.mem.set(0xf4, 2)
            self.mem.set_word(0xf5, 0xf000)
            self.mem.seek(0xf000)
            self.mem.write(param+chr(0))
    def process_op(self):
        if len(self.__intr) > 0:
            addr = self.__intr.pop()
            self.push((self.pc >> 8) & 0xff)
            self.push((self.pc & 0xff))
            self.push(self.regP)
            self.pc = addr
        op = hex(self.fetch())
        try:
            getattr(self, 'op_%s' % op)()
        except VMNoData:
            self.pc-=3
            raise
        except ExecuteBin, e:
            fname, addr = str(e).split('#')
            addr = int(addr) << 8
            fname = hostops.get_file(fname)
            if not os.path.exists(fname):
                raise IOError('File not found: %s' % str(e).split('#')[0].split(':')[1])
            self.load(fname, addr)
        except AttributeError:
            raise VMError('Invalid op code: %s' % op)
    def run(self, fname, reloc=False):
        self.load(fname, reloc)
        self.running = True
        while self.running:
            self.process_op()
    def step(self):
        self.running = True
        while self.running:
            buf = 'PC: %s, A: %s, X: %s, Y: %s, ' % (self.pc, self.regA, self.regX, self.regY)
            op = hex(self.fetch())
            nxt = self.mem.get(self.pc)
            nxt16 = self.mem.get_word(self.pc)
            buf+= 'Op: %s, B: %s, W: %s' % (op, nxt, nxt16)
            print buf
            x = raw_input('* ')
            if x == 'q':
                self.running = False
            else:
                getattr(self, 'op_%s' % op)()
