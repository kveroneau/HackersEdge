import mmap, logging, struct, math, os
from game_engine.exceptions import VMError
from plugio import HEDevice

log = logging.getLogger('BlockDEV')

hdr = struct.Struct('>BBBBB')
entry = struct.Struct('<12sBBB')

class BlockDevice(object):
    def __init__(self, fname):
        if not fname.startswith('hosts/') and not fname.startswith('players/'):
            fname='storage/%s' % fname
        self.__blocks = os.path.getsize(fname)/256
        self.__f = open(fname, 'r+b')
        self.blkdev = mmap.mmap(self.__f.fileno(), 0)
        self.__readonly = True if fname.startswith('storage/') else False
        log.debug('Mapped block device %s as readonly = %s' % (fname, self.__readonly))
    @property
    def blocks(self):
        return self.__blocks/256
    def read_header(self):
        self.blkdev.seek(256)
        self.__hdr = hdr.unpack(self.blkdev.read(hdr.size))
    def close(self):
        self.blkdev.flush()
        self.blkdev.close()
        self.__f.close()
    def __update_header(self, *new_hdr):
        pointer = self.blkdev.tell()
        self.writeblock(1, hdr.pack(*new_hdr))
        self.blkdev.flush()
        self.blkdev.seek(pointer)
        self.__hdr = tuple(new_hdr)
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
    def format_header(self):
        log.debug('Formating header...')
        self.writeblock(1, hdr.pack(0,(len(self.blkdev)/256)-2,2,0,0))
        self.blkdev.flush()
        self.blkdev.seek(0)
        self.read_header()
    def findfile(self, fname):
        self.blkdev.seek(261)
        if self.__hdr[0] == 0:
            return None
        for i in range(0,self.__hdr[0]):
            e = entry.unpack(self.blkdev.read(entry.size))
            if e[0].rstrip('\x00') == fname:
                total = (e[2]*256-256)+e[3]
                log.info("Start: %s, Size: %s, Last Block: %s, Total: %s" % (e[1], e[2], e[3], total))
                return e, total
        return None
    def writefile(self, fname, data):
        if self.__readonly:
            raise VMError('Attempting to write to a read-only device.')
        blocks = 1 if len(data) < 256 else int(math.ceil(len(data)/256.0))
        final_bytes = len(data) if len(data) < 256 else len(data)-(256*blocks-256)
        log.debug("%s will require %s blocks." % (fname, blocks))
        e = self.findfile(fname)
        if e is None:
            e = (fname, self.__hdr[2], blocks, final_bytes)
            nextblk = self.__hdr[2] + blocks
            free = self.__hdr[1] - blocks
            entries = self.__hdr[0] + 1
            log.debug(str(e))
            self.blkdev.write(entry.pack(*e))
            self.__update_header(entries, free, nextblk, 0, 0)
            self.blkdev.seek(e[1]*256)
            self.blkdev.write(data)
            self.blkdev.flush()
        else:
            self.deletefile(fname)
            self.writefile(fname, data)
    def readfile(self, fname):
        e = self.findfile(fname)
        if e is None:
            return None
        self.blkdev.seek(e[0][1]*256)
        return self.blkdev.read(e[1])
    def catalog(self):
        file_list = []
        log.debug("Entries: %s, Free blocks: %s, Next block: %s" % (self.__hdr[0], self.__hdr[1], self.__hdr[2]))
        if self.__hdr[0] == 0:
            return None
        self.blkdev.seek(261)
        for i in range(0,self.__hdr[0]):
            e = entry.unpack(self.blkdev.read(entry.size))
            log.debug("%12s %s %s %s" % e)
            file_list.append(e[0])
    def deletefile(self, fname):
        if self.__readonly:
            raise VMError('Attempting to write to a read-only device.')
        files = []
        inode = None
        self.blkdev.seek(261)
        for i in range(0,self.__hdr[0]):
            e = entry.unpack(self.blkdev.read(entry.size))
            if e[0].rstrip('\x00') == fname:
                inode = i
            files.append(e)
        if self.__hdr[0]-1 == inode:
            nextblk = self.__hdr[2] - e[2]
            free = self.__hdr[1] + e[2]
            entries = self.__hdr[0] - 1
            self.__update_header(entries, free, nextblk, 0, 0)
            return
        else:
            e = files[inode]
            blocks = 0
            start = files[inode+1][1]
            log.debug('Start block to move: %s' % start)
            self.blkdev.seek(261+(inode*entry.size))
            for i in range(inode+1, self.__hdr[0]):
                f = list(files[i])
                f[1]-=e[2]
                self.blkdev.write(entry.pack(*f))
                log.debug('Start: %s, Size: %s, Last Block: %s' % (f[1], f[2], f[3]))
                blocks+=files[i][2]
            nextblk = self.__hdr[2] - e[2]
            free = self.__hdr[1] + e[2]
            entries = self.__hdr[0] - 1
            self.__update_header(entries, free, nextblk, 0, 0)
            log.debug('Blocks to move: %s' % blocks)
            self.blkdev.seek(start*256)
            data = self.blkdev.read(blocks*256)
            self.blkdev.seek((start-e[2])*256)
            log.debug('Dest: %s' % ((start-e[2])*256))
            self.blkdev.write(data)

class StorageController(HEDevice):
    """ This is a storage controller, that we attach block devices to. """
    exposed = ['open_storage', 'blkdev']
    def init(self):
        self.blkdev = []
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
    def out_0x82(self, value):
        dev = self.mem.get_io(0x8a)
        if dev > len(self.blkdev)-1:
            return 0x1
        memaddr = self.get_word(0x83)
        fname = self.mem.getstring(self.get_word(0x80))
        log.debug('[%s]Filename to use: %s' % (value, fname))
        if value == 1:
            self.mem.seek(memaddr)
            self.blkdev[dev].read_header()
            data = self.blkdev[dev].readfile(fname)
            if data is None:
                return 0x1
            self.mem.write(data)
            return 0x0
        elif value == 2:
            self.mem.seek(memaddr)
            self.blkdev[dev].read_header()
            sz = self.get_word(0x85)
            try:
                self.blkdev[dev].writefile(fname, self.mem.read(sz))
                return 0x0
            except VMError:
                return 0xff
        elif value == 3:
            self.blkdev[dev].read_header()
            e = self.blkdev[dev].findfile(fname)
            if e is None:
                return 0x1
            self.set_word(0x85, e[1])
            self.mem.set_io(0x8c, e[0][1])
            return 0x0
        elif value == 4:
            self.blkdev[dev].deletefile(fname)
            return 0x0
        elif value == 5:
            flist = self.blkdev[dev].catalog()
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
            self.blkdev[dev].clearblock(0)
            self.blkdev[dev].clearblock(1)
            self.blkdev[dev].format_header()
            return 0x0
    def out_0x8e(self, value):
        dev = self.mem.get_io(0x8a)
        if dev > len(self.blkdev)-1:
            return 0x1
        if value == 0x10:
            return self.blkdev[dev].blocks
        mempage = self.mem.get_io(0x8b)
        blk = self.get_word(0x8c)
        self.mem.seek(mempage << 8)
        if value == 1:
            self.mem.write(self.blkdev[dev][blk])
            log.debug('Read block %s:%s into page %s' % (dev, blk, mempage))
            return 0x0
        elif value == 2:
            try:
                log.debug('Write page %s into block %s:%s' % (mempage, dev, blk))
                self.blkdev[dev][blk] = self.mem.read(256)
                return 0x0
            except VMError:
                return 0xff
        elif value == 0xff:
            return 0x0
