from plugio import HEDevice
import logging

log = logging.getLogger('PCSlots')

class SlotDevice(object):
    """ Base class for slotted card devices, all slot cards should extend this class """
    def __init__(self):
        log.debug('Initializing slot device %s...' % self.__class__.__name__)

class EmptySlot(SlotDevice):
    pass

class SlotInterface(HEDevice):
    """ This device manages player interchangable slotted card on the motherboard """
    io_addr = 0xb00
    def init(self):
        self.slots = {}
        for slot in range(0,8):
            self.slots[slot] = EmptySlot
    def resume(self):
        if 'slots' not in self.mem.host.keys():
            return
