import mmap, logging
from game_engine.databases import hosts
from game_engine.exceptions import VMError
import cPickle as pickle

log = logging.getLogger('MemoryDev')

class Memory(object):
    def __init__(self, fileno, size, ip_addr):
        self.mem = mmap.mmap(fileno, 0)
        self.mem.resize(size+1)
        self.ip_addr = ip_addr
        self.host = None
        self.__http = None
        self.__set_host = False
        self.__io_page = 0xff
        self.__ioset = {}
        self.__ioget = {}
        self.__exposed = {}
        self.__iomap = {}
        self.__devices = []
    @property
    def io_page(self):
        return self.__io_page
    @io_page.setter
    def io_page(self, value):
        if self.__io_page == 0xff:
            if value > 0xff:
                value = value >> 8
            self.__io_page = value
        else:
            raise VMError('Attempt to set IO page at invalid time!')
    def attach_device(self, device):
        dev = device(self)
        for addr in dev.io_in:
            self.__ioget[addr] = dev
        for addr in dev.io_out:
            self.__ioset[addr] = dev
        for func in dev.exposed:
            self.__exposed[func] = dev
        if dev.io_addr is not None:
            if isinstance(dev.io_addr, (list, tuple,)):
                for addr in dev.io_addr:
                    self.__iomap[addr] = dev
            else:
                self.__iomap[dev.io_addr] = dev
        self.__devices.append(dev)
    def ipl_devices(self):
        for dev in self.__devices:
            dev.ipl()
    def resume_devices(self):
        for dev in self.__devices:
            dev.resume()
    def suspend_devices(self):
        for dev in self.__devices:
            dev.suspend()
            dev.close()
    def __getattr__(self, attr):
        if attr in self.__exposed.keys():
            return getattr(self.__exposed[attr], attr)
        raise AttributeError('Attribute not found: %s' % attr)
    def reset_stdflush(self):
        self.__exposed['stdflush'].stdflush = False 
    def flush(self):
        self.mem.flush()
    def close(self):
        self.mem.flush()
        self.mem.close()
    def set_host(self):
        if self.__http is not None:
            self.__set_host = True
            return
        self.__http = hosts(self, 'set_host', self.ip_addr, pickle.dumps(self.host))
        try:
            self.update_netseg()
        except:
            pass
    def http_callback(self, result):
        self.__http = None
        if result[0] == 'get_host':
            log.critical('Invalid callback from get_host!')
        elif result[0] == 'set_host':
            log.debug('Set host: %s' % self.ip_addr)
            if self.__set_host:
                self.__set_host = False
                self.set_host()
    def set_io(self, addr, value):
        if addr > 0xff:
            ioaddr = addr & 0xff
            if ioaddr in self.__ioset.keys():
                rt = getattr(self.__ioset[ioaddr], 'out_%s' % hex(ioaddr))(value)
                if rt is not None:
                    value = rt
        else:
            addr = (self.__io_page << 8)+addr
        self.mem[addr] = chr(value & 0xff)
    def get_io(self, addr):
        if addr > 0xff:
            ioaddr = addr & 0xff
            if ioaddr in self.__ioget.keys():
                return getattr(self.__ioget[ioaddr], 'in_%s' % hex(ioaddr))()
        else:
            addr = (self.__io_page << 8)+addr
        return ord(self.mem[addr])
    def set(self, addr, value):
        page = addr >> 8
        if page in self.__iomap.keys():
            self.__iomap[page].set(addr, value)
        elif addr > 0xfff9:
            if addr == 0xfffa:
                word = value + (self.get(0xfffb) << 8)
                self.host['nmi'] = word
                self.set_host()
            elif addr == 0xfffb:
                word = self.get(0xfffa) + (value << 8)
                self.host['nmi'] = word
                self.set_host()
            elif addr == 0xfffe:
                word = value + (self.get(0xffff) << 8)
                self.host['isr'] = word
                self.set_host()
            elif addr == 0xffff:
                word = self.get(0xfffe) + (value << 8)
                self.host['isr'] = word
                self.set_host()
            self.mem[addr & 0xffff] = chr(value & 0xff)
        elif page == self.__io_page:
            self.set_io(addr, value)
        else:
            self.mem[addr & 0xffff] = chr(value & 0xff)
    def set_word(self, addr, value):
        self.set(addr, value & 0xff)
        self.set(addr+1, (value >> 8) & 0xff)
    def get(self, addr):
        page = addr >> 8
        if page in self.__iomap.keys():
            try:
                return self.__iomap[page].get(addr)
            except IndexError:
                return 0x0
        elif page == self.__io_page:
            return self.get_io(addr)
        else:
            return ord(self.mem[addr & 0xffff])
    def get_word(self, addr):
        return self.get(addr)+(self.get(addr+1) << 8)
    def seek(self, addr):
        self.mem.seek(addr & 0xffff)
    def write(self, data):
        self.mem.write(data)
    def read(self, size):
        return self.mem.read(size)
    def getstring(self, addr):
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
