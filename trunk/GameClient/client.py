import asynchat, asyncore, socket, threading, time, sys
import vgaconsole, pygame

class TelnetClient(asynchat.async_chat):
    def __init__(self, console):
        asynchat.async_chat.__init__(self)
        self.console = console
        self.set_terminator(None)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        console.stdio.write('Connecting to Hacker\'s Edge...')
    def handle_connect(self):
        self.console.stdio.write('connected!\n')
    def handle_close(self):
        self.console.stdio.write('Disconnected.\n')
        self.close()
    def transmit(self, data):
        self.push(data+'\r\n')
    def process_iac(self, iac):
        if iac[2] == chr(1):
            if iac[1] == chr(251):
                self.console.mask_input = '*'
            elif iac[1] == chr(252):
                self.console.mask_input = None            
    def collect_incoming_data(self, data):
        if chr(255) in data:
            iac = data.index(chr(255))
            self.process_iac(data[iac:iac+3])
            if iac == 0:
                data = data[3:]
            else:
                data = data[:iac]+data[iac+3:]
        self.console.stdio.write(data.replace('\r\n', '\n'))

class ConsoleApp(vgaconsole.VGAConsole):
    cursor_klass = vgaconsole.AnimatedCursor
    def init(self):
        self.set_color(2,0)
        self.telnet = TelnetClient(self)
        self.ctrl_time = time.time()
    def parse(self):
        self.stdio.write('\n')
        line = self.stdio.read()
        self.telnet.transmit(line)
    def cbreak(self):
        if not self.ctrl_time > time.time()-1:
            self.ctrl_time = time.time()
            self.stdio.write('^C')
            self.stdio.ibuffer = ''
            self.telnet.push(chr(255)+chr(244)+chr(255)+chr(253)+chr(6))
    def suspend(self):
        if not self.ctrl_time > time.time()-1:
            self.ctrl_time = time.time()
            self.stdio.write('^Z')
            self.stdio.ibuffer = ''
            self.telnet.push(chr(255)+chr(237)+chr(255)+chr(253)+chr(6))

def main():
    pygame.display.init()
    screen = pygame.display.set_mode((640,400),0,8)
    pygame.display.set_caption("Hacker's Edge")
    vga = ConsoleApp(screen)
    vga.init()
    vga.draw()
    pygame.display.update()
    try:
        vga.telnet.connect(('localhost', 1337))
        client_thread = threading.Thread(target=asyncore.loop, kwargs={'timeout':1})
        client_thread.start()
    except socket.gaierror, e:
        vga.stdio.write('failed!\n%s' % e)
    ctrl = False
    while True:
        vgaconsole.clock.tick(30)
        events = pygame.event.get()
        for e in events:
            if e.type == vgaconsole.QUIT:
                vga.telnet.close()
                client_thread.join()
                pygame.quit()
                sys.exit()
            if vga.telnet.connected:
                if e.type == vgaconsole.KEYDOWN and e.key == 13:
                    vga.parse()
                elif e.type == vgaconsole.KEYDOWN and (e.key == vgaconsole.K_LCTRL or e.key == vgaconsole.K_RCTRL):
                    ctrl = True
                elif e.type == vgaconsole.KEYUP and (e.key == vgaconsole.K_LCTRL or e.key == vgaconsole.K_RCTRL):
                    ctrl = False
                else:
                    if ctrl:
                        if e.key == vgaconsole.K_c:
                            vga.cbreak()
                        elif e.key == vgaconsole.K_z:
                            vga.suspend()
                    else:
                        vga.handle_event(e)
        try:
            vga.draw()
        except:
            print sys.exc_info()
            pass
        pygame.display.update()

if __name__ == '__main__':
    main()
