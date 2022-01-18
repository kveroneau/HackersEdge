from plugio import HEDevice
import logging, os, subprocess

log = logging.getLogger('DebugFS')

DEBUGFS_PATH = '/tmp/debugfs'

class DebugFS(HEDevice):
    """ This is a special debug-only virtual device which provides direct access to the server file system """
    def init(self):
        if not os.path.exists(DEBUGFS_PATH):
            log.debug('DebugFS initialized under %s' % DEBUGFS_PATH)
            os.mkdir(DEBUGFS_PATH)
    def out_0x82(self, value):
        dev = self.mem.get_io(0x8a)
        if dev != 0:
            return 0x1
        memaddr = self.mem.get_io(0x84) << 8
        fblk = self.mem.get_io(0x83) - 1
        fname = '%s/%s' % (DEBUGFS_PATH, self.mem.getstring(self.get_word(0x80)))
        log.debug('[%s]Filename to use: %s' % (value, fname))
        if value == 1:
            if not os.path.exists(fname) or fname.endswith('/'):
                return 0x1
            self.mem.seek(memaddr)
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
            if fname.endswith('/'):
                return 0x1
            self.mem.seek(memaddr)
            sz = self.get_word(0x85)
            if fblk == -1:
                if os.path.exists(fname):
                    os.unlink(fname)
                open(fname, 'wb').write(self.mem.read(sz))
            else:
                f = open(fname, 'wb')
                f.seek(fblk*256)
                f.write(self.mem.read(sz))
                f.close()
            return 0x0
        elif value == 3:
            if not os.path.exists(fname) or fname.endswith('/'):
                return 0x1
            stat = os.stat(fname)
            self.set_word(0x85, stat.st_size)
            return 0x0
        elif value == 4:
            if fname.endswith('/'):
                return 0x1
            if os.path.exists(fname):
                os.unlink(fname)            
                return 0x0
            return 0x1
        elif value == 5:
            flist = os.listdir(DEBUGFS_PATH)
            if flist is None:
                return 0x1
            self.mem.set(memaddr, len(flist))
            memaddr+=1
            for fname in flist:
                self.mem.setstring(memaddr, fname)
                memaddr+=len(fname)+1
            self.set_word(0x85, memaddr-self.get_word(0x83))
            return 0x0
        elif value == 6:
            for fname in os.listdir(DEBUGFS_PATH):
                os.unlink('%s/%s' % (DEBUGFS_PATH, fname))
            return 0x0
        elif value == 0x80:
            if not os.path.exists(fname):
                return 0x1
            try:
                stdout = subprocess.Popen(['/usr/bin/hexdump', '-C', fname], stdout=subprocess.PIPE).communicate()[0]
            except:
                return 0x2
            self.mem.term_write(stdout)
            return 0x0
