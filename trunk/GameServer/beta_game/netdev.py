import threading, logging

log = logging.getLogger('Networking')

VERSION = 'HackerNET v0.1 $Revision: 190 $'

class NetworkManager(threading.Thread):
    """ This thread will manage network connections between VMs. """
    def __init__(self):
        threading.Thread.__init__(self)
        self.finish = threading.Event()
        self.net_lock = threading.Lock()
        self.net_queue = {}
    def sendto(self, ip_addr, data):
        with self.net_lock:
            if ip_addr not in self.net_queue.keys():
                self.net_queue[ip_addr] = ''
            self.net_queue[ip_addr]+=data
    def recv(self, ip_addr):
        with self.net_lock:
            if ip_addr not in self.net_queue.keys():
                return ''
            data = self.net_queue[ip_addr]
            self.net_queue[ip_addr] = ''
        return data
    def cancel(self):
        log.info('NetworkManager cancelled.')
        self.finish.set()
    def run(self):
        log.info('VM Networking started, and ready.')
        while not self.finish.is_set():
            pass

network = NetworkManager()
