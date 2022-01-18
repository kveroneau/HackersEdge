from plugio import HEDevice
import logging, StringIO
from game_engine.exceptions import VMNoData, VMTermBit

log = logging.getLogger('TerminalDev')

class Terminal(HEDevice):
    """ This is a generic Terminal I/O device. """
    exposed = ['stdout', 'input', 'stdflush', 'term_write']
    def init(self):
        self.__stdout = StringIO.StringIO()
        self.stdflush = False
        self.__stdin = []
    def resume(self):
        fg, bg = str(self.mem.get_io(0xd4)), str(self.mem.get_io(0xd5))
        if int(bg) > 0:
            self.__stdout.write(chr(27)+'[%s;%sm' % (fg,bg))
        elif int(fg) > 0:
            self.__stdout.write(chr(27)+'[%sm' % fg)
    @property
    def stdout(self):
        value = self.__stdout.getvalue()
        self.__stdout.seek(0)
        self.__stdout.truncate()
        for clean in (chr(255), chr(0),):
            value=value.replace(clean, '')
        return value.replace('\n', '\r\n')
    def input(self, data):
        if data == '':
            self.__stdin.append('\n')
        else:
            if (self.mem.get_io(0xdc) & 0x80) == 0x80:
                v = int(data[:-1])
                data = [chr(v & 0xff)]
                if v > 255:
                    data.append(chr(v >> 8))
                data.append('\n')
            self.__stdin.extend(list(data))
    def term_write(self, data):
        self.__stdout.write(data)
        self.stdflush = True
    def out_0xd0(self, value):
        self.__stdout.write(chr(value))
        if value == 0xa:
            self.stdflush = True
    def out_0xd1(self, value):
        self.__stdout.write(str(value))
    def out_0xd2(self, value):
        self.__stdout.write(hex(value))
    def out_0xd3(self, value):
        if chr(value) == 'm':
            fg, bg = str(self.mem.get_io(0xd4)), str(self.mem.get_io(0xd5))
            self.__stdout.write(chr(27)+'[%s;%sm' % (fg,bg))
        elif value == 0x00:
            self.stdflush = True
        else:
            self.__stdout.write(chr(27)+'['+chr(value))
    def out_0xd4(self, value):
        self.__stdout.write(chr(27)+'[%sm' % str(value))
    def out_0xd5(self, value):
        fg = str(self.mem.get_io(0xd4))
        self.__stdout.write(chr(27)+'[%s;%sm' % (fg,str(value)))
    def out_0xd6(self, value):
        col = str(self.mem.get_io(0xd7))
        self.__stdout.write(chr(27)+'[%s;%sH' % (str(value),col))
    def out_0xd7(self, value):
        row = str(self.mem.get_io(0xd6))
        self.__stdout.write(chr(27)+'[%s;%sH' % (row,str(value)))
    def out_0xdc(self, value):
        self.mem.set_io(0xdc, value)
        raise VMTermBit
    def in_0xe0(self):
        self.__stdin.reverse()
        try:
            value = ord(self.__stdin.pop())
        except IndexError:
            raise VMNoData
        self.__stdin.reverse()
        return value
