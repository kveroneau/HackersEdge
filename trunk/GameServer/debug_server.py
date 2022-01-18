#from gevent.monkey import patch_all
#patch_all()

ENABLE_VM = False

import asyncore, logging, sys, signal, os, traceback
from game_engine.engine import EngineServer
from game_engine.telnet import TelnetServer
from game_engine.websocket import WebServer
from game_engine.economy import economy
if ENABLE_VM:
    from game_engine.vm6502 import VMServer, hypervisor

log = logging.getLogger('DebugServer')

def main():
    logging.basicConfig(filename=None, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG)
    sys.stdout.write(chr(27)+']2;GameServer'+chr(7))
    sys.stdout.flush()

    def handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, handler)
    
    engined = EngineServer()
    log.info('Engined server started.')
    telnetd = TelnetServer(('0.0.0.0', 1337))
    log.info('Telnetd server started.')
    wsd = WebServer(('127.0.0.1', 4080))
    log.info('Wsd server started.')
    if ENABLE_VM:
        vm6502d = VMServer()
        log.info('vm6502d server started.')
    economy.start()
    running = True
    log.debug('Async socket_map: %s' % len(asyncore.socket_map))
    while running:
        try:
            if ENABLE_VM:
                asyncore.loop(timeout=hypervisor.timeout, use_poll=True, count=1)
                hypervisor.vmloop()
            else:
                asyncore.loop(use_poll=True, count=1)
            if len(asyncore.socket_map) == 0:
                log.info('Finished handling all requests, terminating...')
                running = False
        except KeyboardInterrupt:
            log.info('Requested server termination.')
            if ENABLE_VM:
                vm6502d.close()
            engined.close()
            telnetd.close()
            wsd.close()
            for s in asyncore.socket_map.values():
                s.close()
        except:
            log.critical('Server exception occurred: [%s]%s' % (sys.exc_info()[0],sys.exc_info()[1]))
            open('stacktrace.log', 'w').write('\n'.join(traceback.format_tb(sys.exc_info()[2])))
    log.info('Server shutdown complete.')
    if ENABLE_VM:
        os.unlink('vm6502')
    os.unlink('engine')

if __name__ == '__main__':
    main()
