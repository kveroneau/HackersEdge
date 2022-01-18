from plugio import HEDevice
import logging
from game_engine.exceptions import VMHalt, VMReset
from game_engine.databases import cc65, ca65
from game_engine.settings import CC65_ROOT

log = logging.getLogger('HEAPI')

hexchrs = '0123456789ABCDEF'

class HEAPI(HEDevice):
    """ This device is the official Hacker's Edge API. """
    def out_0xf2(self, value):
        if value == 0x78:
            raise VMHalt
        elif value == 0x79:
            raise VMReset
    def in_0x30(self):
        return 0xa9
    def in_0x31(self):
        return 0x78
    def in_0x32(self):
        return 0x8d
    def in_0x33(self):
        return 0xf2
    def in_0x34(self):
        return 0xff
    def in_0xf2(self):
        api = self.mem.get_io(0xf2)
        handler = getattr(self, 'api_%s' % hex(api), None)
        if handler:
            return handler()
        return 0xff
    def api_0x30(self):
        cmd = self.mem.getstring(self.get_word(0xf0))
        log.debug('HE Internal Monitor API: %s' % cmd)
        i = 0
        chex = ''
        faddr = 0x0
        daddr = 0x0
        while i < len(cmd):
            c = cmd[i].upper()
            i+=1
            if c in hexchrs:
                chex+=c
            elif c == '.':
                if chex != '':
                    self.mem.set_word(0xf3, int(chex,16))
                    chex = ''
                faddr = self.get_word(0xf3)
            elif c == ' ':
                if faddr > 0x0:
                    fmt = '0000'+hex(faddr)[2:]
                    self.mem.term_write('%s: ' % fmt[-4:])
                    for addr in range(faddr, int(chex,16)+1):
                        value = '00'+hex(self.mem.get(addr))[2:]
                        self.mem.term_write('%s ' % value[-2:])
                    self.set_word(0xf3, int(chex,16)+1)
                    self.mem.term_write('\n')
                    faddr = 0x0
                    chex = ''
                elif daddr > 0x0:
                    self.mem.set(daddr, int(chex,16))
                    daddr+=1
                    self.set_word(0xf3, int(chex,16))
                else:
                    fmt = '0000'+chex
                    value = '00'+hex(self.mem.get(int(chex,16)))[2:]
                    self.mem.term_write('%s: %s\n' % (fmt[-4:], value[-2:]))
                    self.set_word(0xf3, int(chex,16))
                    chex = ''
            elif c == ':':
                if chex != '':
                    self.set_word(0xf3, int(chex,16))
                    chex = ''
                daddr = self.get_word(0xf3)
            elif c == 'R':
                return 0x40
            else:
                return 0xff
        if chex != '':
            if faddr > 0x0:
                fmt = '0000'+hex(faddr)[2:]
                self.mem.term_write('%s: ' % fmt[-4:])
                for addr in range(faddr, int(chex,16)+1):
                    value = '00'+hex(self.mem.get(addr))[2:]
                    self.mem.term_write('%s ' % value[-2:])
                self.set_word(0xf3, int(chex,16)+1)
                self.mem.term_write('\n')
            elif daddr > 0x0:
                fmt = '0000'+hex(daddr)[2:]
                value = '00'+hex(self.mem.get(int(chex,16)))[2:]
                self.mem.term_write('%s: %s\n' % (fmt[-4:], value[-2:]))
                self.mem.set(daddr, int(chex,16))
            else:
                fmt = '0000'+chex
                value = '00'+hex(self.mem.get(int(chex,16)))[2:]
                self.mem.term_write('%s: %s\n' % (fmt[-4:], value[-2:]))
                self.set_word(0xf3, int(chex,16))
        self.stdflush = True
        return 0x0
    def api_0x40(self):
        addr = self.get_word(0xf0)
        dest = self.get_word(0xf3)
        ip_addr = self.mem.getstring(addr)
        log.debug('HE Internal aotn API: %s' % ip_addr)
        self.mem.seek(dest)
        self.mem.write(''.join([chr(int(c)) for c in ip_addr.split('.')]))
        return 0x0
    def api_0x41(self):
        addr = self.get_word(0xf0)
        dest = self.get_word(0xf3)
        self.mem.seek(addr)
        self.mem.setstring(dest, '.'.join([str(ord(c)) for c in list(self.mem.read(4))]))
        return 0x0
    def api_0x31(self):
        addr = self.get_word(0xf0)
        size = self.get_word(0xf3)
        log.debug('HE Internal hexdump API: %s' % hex(addr))
        out = ''
        for addr in range(addr,addr+size):
            b = ''
            out += ' %4s' % hex(ord(b))
    def call_compiler(self, func):
        addr = self.get_word(0xf0)
        size = self.get_word(0xf3)
        log.info('call_compiler [%s:%s]' % (hex(addr), hex(size)))
        self.mem.seek(addr)
        data = self.mem.read(size)
        open('%s/workspace/prog.s' % CC65_ROOT, 'w').write(data)
        rt = func()
        if rt is None:
            log.error('Redis queue timed out!  Is cc65d running?')
            return 0xff
        if rt:
            self.mem.seek(addr)
            data = open('%s/workspace/prog.bin' % CC65_ROOT, 'rb').read()
            self.mem.write(data)
            self.set_word(0xf3, len(data))
            return 0x0
        else:
            self.mem.term_write(open('%s/workspace/prog.log' % CC65_ROOT,'r').read())
            return 0x1
    def api_0x20(self):
        log.debug('CA65 being called.')
        return self.call_compiler(ca65)
    def api_0x21(self):
        log.debug('CC65 being called.')
        return self.call_compiler(cc65)
