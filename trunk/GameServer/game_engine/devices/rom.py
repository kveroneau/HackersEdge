from plugio import HEDevice
import mmap, logging

log = logging.getLogger('ROM')

class ROM(HEDevice):
    """ This device is a ROM chip, read-only memory. """
    rom_file = None
    enabled = True
    def ipl(self):
        self.mem.set_io(0x1a, 0x20)
    def resume(self):
        if self.rom_file is None:
            raise ValueError('No ROM file was specified in the ROM Class!')
        try:
            fh = self.fopen(self.rom_file)
            self.__mem = mmap.mmap(fh.fileno(), 0)
            if (self.mem.get_io(0x1a) & 0x20) == 0x20:
                self.enabled = True
            else:
                self.enabled = False
        except:
            pass # Usually means that a machine isn't provisioned yet.
    def suspend(self):
        try:
            self.__mem.close()
            del self.__mem
        except:
            pass
    def get(self, addr):
        if self.enabled:
            return ord(self.__mem[addr-self.baseaddr])
        else:
            return ord(self.mem.mem[addr])
    def set(self, addr, value):
        if self.enabled:
            return
        else:
            self.mem.mem[addr] = chr(value)
    def out_0x1a(self, value):
        if (value & 0x20) == 0x20:
            self.enabled = True
        else:
            self.enabled = False

class BootROM(ROM):
    """ This device is the ROM-BIOS chip, code which is executed when a host first boots up. """
    rom_file = 'bios'
    def init(self):
        if self.mem.host.has_key('romaddr'):
            rompg = self.mem.host['romaddr'] >> 8
            romsize = (self.mem.host['romsize'] >> 8)+rompg
            log.debug('ROM %s:%s' % (rompg, romsize))
            self.io_addr = []
            for pg in range(rompg, romsize+1):
                self.io_addr.append(pg)
            self.baseaddr = self.mem.host['romaddr']
        elif self.mem.host.has_key('bootaddr'):
            self.io_addr = self.mem.host['bootaddr'] >> 8
            self.baseaddr = self.mem.host['bootaddr']
