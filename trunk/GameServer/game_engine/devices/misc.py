from plugio import HEDevice
import time, hashlib, struct, binascii, random

class RTC(HEDevice):
    """ This is the real-time clock chip. """
    def in_0x27(self):
        return int(time.time()) & 0xff
    def in_0x28(self):
        return (int(time.time()) & 0xff00) >> 8
    def in_0x29(self):
        return (int(time.time()) & 0xff0000) >> 16
    def in_0x2a(self):
        return (int(time.time()) & 0xff000000) >> 24

class HashChip(HEDevice):
    """ Chip provides hashing routines. """
    def out_0x20(self, value):
        api = value >> 4
        if api == 0x1:
            value = value & 0xf
            page = self.mem.get_io(0x21)
            self.mem.seek(page << 8)
            data = self.mem.read(256)
            target = self.mem.get_word(self.mem.get_io(0x22))
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
            self.mem.seek(target)
            self.mem.write(result)
    def in_0x20(self):
        return random.randint(self.mem.get_io(0x21),self.mem.get_io(0x22))
