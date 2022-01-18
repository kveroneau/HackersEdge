import logging
from game_engine.databases import get_host_dir

log = logging.getLogger('HEDevice')

class HEDevice(object):
    """ This is the base class to define a Hacker's Edge device """
    exposed = []
    io_addr = None
    def __init__(self, mem):
        log.debug('Initializing device %s...' % self.__class__.__name__)
        self.mem = mem
        self.__handles = []
        self.io_in, self.io_out = [], []
        in_pre = 'in_'
        out_pre = 'out_'
        for prt in dir(self.__class__):
            if prt[:len(in_pre)] == in_pre:
                self.io_in.append(int(prt[len(in_pre):], 16))
            elif prt[:len(out_pre)] == out_pre:
                self.io_out.append(int(prt[len(out_pre):], 16))
        self.init()
    def get_word(self, addr):
        return self.mem.get_io(addr)+(self.mem.get_io(addr+1) << 8)
    def set_word(self, addr, value):
        self.mem.set_io(addr, value & 0xff)
        self.mem.set_io(addr+1, (value >> 8) & 0xff)
    @property
    def ip_addr(self):
        """ Returns the IP address from the CPU Memory class instance. """
        return self.mem.ip_addr
    @property
    def host_dir(self):
        """ Returns the host's private data directory, where memory and other devices can store persistent data. """
        return '%s/%s' % (get_host_dir(self.mem.ip_addr), self.mem.ip_addr)
    def fopen(self, fname):
        """ Returns a file handle to a private host data file. """
        fh = open('%s/%s/%s' % (get_host_dir(self.mem.ip_addr), self.mem.ip_addr, fname), 'r+b')
        self.__handles.append(fh)
        return fh
    def close(self):
        """ Called from Memory manager to close any opened assets before removing the instance. """
        for fh in self.__handles:
            if not fh.closed:
                fh.close()
    def cycle(self):
        """ If this is overridden, it is called on every CPU cycle so that the device can do something. """
        pass
    def init(self):
        """ Called immediately after the class is initialized. """
        pass
    def ipl(self):
        """ Called when the CPU is reset and in IPL mode, called once per boot. """
        pass
    def resume(self):
        """ If this is overridden, it is called when the CPU is resumed from a suspended state. """
        pass
    def suspend(self):
        """ If this is overridden, it is called just before the CPU is suspended. """
        pass
    def get(self, addr):
        """ This gets called by the Memory managed when a memory get request is done in the allocated memory space. """
        pass
    def set(self, addr, value):
        """ This gets called by the Memory managed when a memory set request is done in the allocated memory space. """
        pass
