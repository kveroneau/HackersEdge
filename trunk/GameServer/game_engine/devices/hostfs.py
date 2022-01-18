from plugio import HEDevice
import logging, os, hashlib, zipfile, subprocess

log = logging.getLogger('HostFS')

class HostFS(HEDevice):
    """ Classic file system which uses the server's file system to store files. """
    io_addr = (0x90, 0x91,)
    cffa1 = False
    def init(self):
        self.file_dir = '%s/files' % self.host_dir
        if not os.path.exists(self.file_dir):
            log.info('Creating HostFS directory: %s' % self.file_dir)
            os.mkdir(self.file_dir)
            open('%s/%s' % (self.file_dir, 'idx'), 'wb').write('')
        self.zp = ''
        self.__api = 0x0
        self.errormsg = 'Error not available.\n'
    def resume(self):
        if (self.mem.get_io(0x8f) & 0x20) == 0x20:
            self.cffa1 = True
            self.__api = self.mem.get(0x9100)
        else:
            self.cffa1 = False
    def read_idx(self):
        idx = open('%s/%s' % (self.file_dir, 'idx'), 'rb').read()
        if idx == '':
            return []
        return idx.split(chr(255))
    def write_idx(self, flist):
        idx = chr(255).join(flist)
        open('%s/%s' % (self.file_dir, 'idx'), 'wb').write(idx)
    def reinstall(self, osimage):
        if not os.path.exists('osimages/%s.img' % osimage):
            return False
        zf = zipfile.ZipFile('osimages/%s.img' % osimage, 'r')
        flist = list(zf.namelist())
        for fname in flist:
            hname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
            open(hname, 'wb').write(zf.open(fname, 'r').read())
        zf.close()
        self.write_idx(flist)
        return True
    def out_0x82(self, value):
        dev = self.mem.get_io(0x8a)
        if dev != 0:
            return 0x1
        memaddr = self.mem.get_io(0x84) << 8
        fblk = self.mem.get_io(0x83) -1
        fname = self.mem.getstring(self.get_word(0x80))
        log.debug('[%s]Filename to use: %s' % (value, fname))
        if value == 1:
            if fname not in self.read_idx():
                return 0x1
            self.mem.seek(memaddr)
            fname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
            f = open(fname, 'rb')
            if fblk == -1:
                data = f.read()
            else:
                f.seek(fblk*256)
                data = f.read(256)
            f.close()
            self.mem.write(data)
            self.set_word(0x85, len(data))
            return 0x0
        elif value == 2:
            self.mem.seek(memaddr)
            sz = self.get_word(0x85)
            flist = self.read_idx()
            hname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
            if fblk == -1:
                if fname in flist:
                    os.unlink(hname)
                else:
                    flist.append(fname)
                    self.write_idx(flist)
                open(hname, 'wb').write(self.mem.read(sz))
            else:
                if fname not in flist:
                    return 0x1
                f = open(hname, 'wb')
                f.seek(fblk*256)
                f.write(self.mem.read(sz))
                f.close()
            return 0x0
        elif value == 3:
            if fname not in self.read_idx():
                return 0x1
            fname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
            stat = os.stat(fname)
            self.set_word(0x85, stat.st_size)
            return 0x0
        elif value == 4:
            flist = self.read_idx()
            if fname in flist:
                os.unlink('%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest()))
                flist.remove(fname)
                self.write_idx(flist)
                return 0x0
            return 0x1
        elif value == 5:
            flist = self.read_idx()
            if len(flist) == 0:
                return 0x1
            self.mem.set(memaddr, len(flist))
            memaddr+=1
            for fname in flist:
                self.mem.setstring(memaddr, fname)
                memaddr+=len(fname)+1
            self.set_word(0x85, memaddr-self.get_word(0x83))
            return 0x0
        elif value == 6:
            for fname in os.listdir(self.file_dir):
                os.unlink('%s/%s' % (self.file_dir, fname))
            open('%s/%s' % (self.file_dir, 'idx'), 'wb').write('')
            return 0x0
        elif value == 0x80:
            if fname not in self.read_idx():
                return 0x1
            hname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
            try:
                stdout = subprocess.Popen(['/usr/bin/hexdump', '-C', hname], stdout=subprocess.PIPE).communicate()[0]
            except:
                return 0x2
            self.mem.term_write(stdout)
            return 0x0
    def out_0x8f(self, value):
        log.info('8f: %s' % value)
        if (value & 0x20) == 0x20:
            self.cffa1 = True
            self.mem.set(0xAFDC, 0xCF)
            self.mem.set(0xAFDD, 0xFA)
        else:
            self.cffa1 = False
            self.mem.set(0xAFDC, 0x0)
            self.mem.set(0xAFDD, 0x0)
    def get_dest(self):
        return self.mem.get_word(0x00)
    def get_filename(self):
        return self.mem.getstring(self.mem.get_word(0x02)+1)
    def get(self, addr):
        if not self.cffa1:
            return ord(self.mem.mem[addr])
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
                flist = self.read_idx()
                hname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
                if fname in flist:
                    os.unlink(hname)
                else:
                    flist.append(fname)
                    self.write_idx(flist)
                open(hname, 'wb').write(self.mem.read(fsize))
            elif self.__api == 0x22:
                dest = self.get_dest()
                fname = self.get_filename()
                if fname not in self.read_idx():
                    self.errormsg = 'File not found.\n'
                    return 0x38
                log.debug('Loading file: %s into %s' % (fname, hex(dest)))
                self.mem.seek(dest)
                fname = '%s/%s' % (self.file_dir, hashlib.md5(fname).hexdigest())
                data = open(fname, 'rb').read()
                self.mem.write(data)
                self.mem.set_word(0x09, len(data))
            elif self.__api == 0x2e:
                self.errormsg = 'Use HostFS API to format.\n'
                return 0x38                
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
        return 0x0
    def set(self, addr, value):
        if not self.cffa1:
            self.mem.mem[addr] = chr(value)
            return
        if addr == 0x9100:
            self.__api = value
