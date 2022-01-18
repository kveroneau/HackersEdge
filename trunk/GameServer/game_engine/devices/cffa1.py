import logging
from plugio import HEDevice
from blockdev import BlockDevice

log = logging.getLogger('CFFA1')

class CFFA1Controller(HEDevice):
    exposed = ['open_storage', 'blkdev']
    io_addr = (0x90, 0x91,)
    def init(self):
        self.blkdev = []
        self.zp = ''
        self.__api = 0x0
        self.errormsg = 'Error not available.\n'
    def resume(self):
        self.open_storage()
    def suspend(self):
        while len(self.blkdev) > 0:
            blk = self.blkdev.pop()
            blk.close()
            del blk
    def open_storage(self):
        if len(self.blkdev) > 0:
            return
        if not self.mem.host.has_key('storage'):
            return
        for storage in self.mem.host['storage']:
            self.blkdev.append(BlockDevice(storage))
        self.mem.set(0xAFDC, 0xCF)
        self.mem.set(0xAFDD, 0xFA)
        #self.mem.set_word(0xAFDC, 0xFACF)
    def get_dest(self):
        return self.mem.get_word(0x00)
    def get_filename(self):
        return self.mem.getstring(self.mem.get_word(0x02)+1)
    def get(self, addr):
        log.debug('Access firmware address %s' % hex(addr))
        if addr == 0x9006:
            return 0x60 # RTS, CFFA1 Menu not implemented.
        elif addr == 0x9009:
            return 0x60 # RTS, CFFA1 Block Driver not implemented.
        elif addr == 0x900c:
            return 0x8e
        elif addr == 0x900d:
            return 0x00
        elif addr == 0x900e:
            return 0x91
        elif addr == 0x900f:
            if self.__api == 0x04:
                self.mem.term_write(self.errormsg)
                return 0x60
            elif self.__api == 0x20:
                dest = self.get_dest()
                fname = self.get_filename()
                fsize = self.mem.get_word(0x09)
                log.debug('Saving file: %s from %s with size %s' % (fname, hex(dest), fsize))
                self.mem.seek(dest)
                data = self.mem.read(fsize)
                self.blkdev[0].read_header()
                try:
                    self.blkdev[0].writefile(fname, data)
                except:
                    self.errormsg = 'Drive not formatted.\nPlease run CALL $FEFD to format.\n'
                    return 0x38
            elif self.__api == 0x22:
                dest = self.get_dest()
                fname = self.get_filename()
                log.debug('Loading file: %s into %s' % (fname, hex(dest)))
                self.mem.seek(dest)
                self.blkdev[0].read_header()
                e = self.blkdev[0].findfile(fname)
                if e is None:
                    self.errormsg = 'File not found.\n'
                    return 0x38
                self.mem.set_word(0x09, e[1])
                self.blkdev[0].blkdev.seek(e[0][1]*256)
                self.mem.write(self.blkdev[0].blkdev.read(e[1]))
            elif self.__api == 0x2e:
                self.blkdev[0].format_header()
            else:
                self.errormsg = 'CFFA1 API not implemented.\n'
                return 0x38
            return 0x18
        elif addr == 0x9010:
            return 0x60
        elif addr == 0x9140:
            self.mem.seek(0)
            self.zp = self.mem.read(256)
            return 0x60 # RTS, we are done here.
        elif addr == 0x9135:
            self.mem.seek(0)
            self.mem.write(self.zp)
            self.zp = ''
            return 0x60 # RTS, we are done here.
    def set(self, addr, value):
        if addr == 0x9100:
            self.__api = value
