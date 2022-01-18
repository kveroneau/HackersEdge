#!/usr/bin/env python

import asyncore, asynchat, socket, sys, ConfigParser, os
try:
    from intelhex import IntelHex
except ImportError:
    IntelHex = None

try:
    cfg = ConfigParser.ConfigParser()
    cfg.read('he.ini')
    if not cfg.has_option('auth', 'username'):
        raise
    if not cfg.has_option('auth', 'apikey'):
        raise
except:
    sys.stderr.write(' * HE.INI file misconfigured.\n\n')
    sys.exit(2)

class BridgeClient(asynchat.async_chat):
    def __init__(self, ip_addr, hex_file=None, bin_file=None):
        asynchat.async_chat.__init__(self)
        self.ip_addr = ip_addr
        self.hex_file, self.bin_file = hex_file, bin_file
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.state = 'init'
        self.connect(('node1', 4356))
        self.set_terminator(chr(255))
        self.ibuffer = ''
    def transmit(self, data):
        self.push(data+chr(255))
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def found_terminator(self):
        if self.ibuffer[0] == 'P':
            sys.stdout.write(self.ibuffer[1:]+'\n')
        elif self.ibuffer[0] == 'F':
            sys.stderr.write(' * Operation failed.\n')
        elif self.ibuffer[0] == '@':
            self.transmit('H'+str(self.ip_addr))
            for line in open(self.hex_file, 'r').read().split('\n'):
                self.transmit('D'+line)
        else:
            sys.stderr.write(' * Invalid OpCode from server: %s\n' % self.ibuffer)
            self.close()
        self.ibuffer = ''
    def handle_connect(self):
        self.transmit(str(cfg.get('auth', 'username'))+chr(0)+str(cfg.get('auth', 'apikey')))

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-H', '--host', dest='host', help='Host which to upload the Intel Hex into.')
    parser.add_option('-f', '--file', dest='hex_file', help='Hex file which you want to upload.')
    options, args = parser.parse_args()
    if not options.host:
        sys.stderr.write(' * Please provide host!\n')
        sys.exit(4)
    if not options.hex_file:
        sys.stderr.write(' * Please provide hex file!\n')
        sys.exit(4)
    if not os.path.exists(options.hex_file):
        sys.stderr.write(' * Hex file does not exist!')
        sys.exit(3)
    bc = BridgeClient(options.host, hex_file=options.hex_file)
    asyncore.loop()
