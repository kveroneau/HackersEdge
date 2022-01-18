from plugio import HEDevice
from game_engine.exceptions import VMNetData
import logging, StringIO

log = logging.getLogger('NIC')

class NetworkCard(HEDevice):
    """ This is a network card interface device. """
    exposed = ['netout', 'netin', 'update_netseg']
    def init(self):
        self.__netout = StringIO.StringIO()
        self.__netin = {}
    @property
    def netout(self):
        value = self.__netout.getvalue()
        self.__netout.seek(0)
        self.__netout.truncate()
        return value
    def netin(self, from_ip, data):
        if from_ip not in self.__netin.keys():
            self.__netin[from_ip] = []
        self.__netin[from_ip].extend(list(data))
    def getip(self, addr):
        self.mem.seek(addr)
        return '.'.join([str(ord(c)) for c in list(self.mem.read(4))])
    def setip(self, addr, ip_addr):
        self.mem.seek(addr)
        self.mem.write(''.join([chr(int(c)) for c in ip_addr.split('.')]))
    def update_netseg(self):
        if not self.mem.host.has_key('netseg'):
            return # Ignore the requested update.
        seg = self.mem.host['netseg']
        self.setip(seg, self.ip_addr)
        nettbl = self.mem.host['nettbl']
        self.mem.seek(seg+4)
        self.mem.write(chr(len(nettbl)))
        seg+=5
        for entry in nettbl:
            self.mem.set(seg, entry['type'])
            seg+=1
            if entry['type'] == 1:
                self.mem.set_word(seg, entry['addr'])
                self.mem.set(seg+2, entry['port'])
                self.mem.set(seg+3, len(entry['contbl']))
                seg+=4
                for conn in entry['contbl']:
                    self.setip(seg, conn['ip_addr'])
                    self.mem.set(seg+4, conn['port'])
                    seg+=5
            elif entry['type'] == 2:
                self.setip(seg, entry['ip_addr'])
                self.mem.set(seg+4, entry['port'])
                self.mem.set_word(seg+5, entry['addr'])
                seg+=7
    def __net_setio(self, ctrl):
        if ctrl == 1:
            svr = {'type':1}
            svr['addr'] = self.get_word(0x72)
            svr['port'] = self.mem.get_io(0x74)
            svr['contbl'] = []
            for e in self.mem.host['nettbl']:
                if e['type'] == 1 and e['port'] == svr['port']:
                    raise ValueError('Port in-use.')
            idx = len(self.mem.host['nettbl'])
            self.mem.host['nettbl'].append(svr)
            self.mem.set_host()
            self.mem.set_io(0x71, idx)
            return 0x0
        elif ctrl == 2:
            cli = {'type':2}
            cli['ip_addr'] = self.getip(self.get_word(0x76))
            cli['port'] = self.mem.get_io(0x74)
            cli['addr'] = self.get_word(0x72)
            idx = len(self.mem.host['nettbl'])
            self.mem.host['nettbl'].append(cli)
            self.mem.set_host()
            self.mem.set_io(0x71, idx)
            self.mem.set_io(0x75, 0)
            raise VMNetData('CONN:%s' % idx)
        elif ctrl == 3:
            idx = self.mem.get_io(0x71)
            if idx > len(self.mem.host['nettbl']):
                return len(self.mem.host['nettbl'])
            entry = self.mem.host['nettbl'][idx]
            if entry['type'] == 1:
                self.set_word(0x72, entry['addr'])
                self.mem.set_io(0x74, entry['port'])
                return 0x0
            elif entry['type'] == 2:
                pass
        elif ctrl == 4:
            idx = self.mem.get_io(0x71)
            if idx > len(self.mem.host['nettbl']):
                return len(self.mem.host['nettbl'])
            entry = self.mem.host['nettbl'][idx]
            if entry['type'] == 1:
                del self.mem.host['nettbl'][idx]
                self.mem.set_host()
                self.mem.set_io(0x71, 0)
                return 0x0
            elif entry['type'] == 2:
                ip_addr = str(self.mem.host['nettbl'][idx]['ip_addr'])
                del self.mem.host['nettbl'][idx]
                self.mem.set_host()
                self.mem.set_io(0x71, 0)
                self.mem.set_io(0x75, 0)
                raise VMNetData('DISC:%s' % ip_addr)
        elif ctrl == 5:
            idx = self.mem.get_io(0x71)
            if idx > len(self.mem.host['nettbl']):
                self.mem.set_io(0x75, len(self.mem.host['nettbl']))
                return
            raise VMNetData('SEND:%s' % idx)
        elif ctrl == 6:
            idx = self.mem.get_io(0x71)
            raise VMNetData('SRV:%s' % idx)
    def out_0x70(self, value):
        if value > 1:
            seg = value << 8
            self.setip(seg, self.ip_addr)
            self.mem.set(seg+4, 0)
            self.mem.host['netseg'] = seg
            self.mem.host['nettbl'] = []
            self.mem.set_host()
        else:
            if self.mem.host.has_key('netseg'):
                del self.mem.host['nettbl']
                del self.mem.host['netseg']
                self.mem.set_host()
    def out_0x75(self, value):
        try:
            return self.__net_setio(value)
        except VMNetData:
            raise
        except:
            return 0xff
    def out_0x78(self, value):
        self.__netout.write(chr(value))
    def in_0x78(self):
        idx = self.mem.get_io(0x71)
        if idx > len(self.mem.host['nettbl']):
            self.mem.set_io(0x75, len(self.host['nettbl']))
            return
        entry = self.mem.host['nettbl'][idx]
        if not entry.has_key('ip_addr'):
            return 0x0
        self.__netin[entry['ip_addr']].reverse()
        try:
            value = ord(self.__netin[entry['ip_addr']].pop())
        except IndexError:
            return 0x0
        self.__netin[entry['ip_addr']].reverse()
        return value
