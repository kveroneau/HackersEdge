import asyncore, logging, sys, signal, os, traceback, socket
from beta_game.sessions import Idler, EventThread, hypervisor
from beta_game.telnet import TelnetServer
from beta_game.http import WebServer
from beta_game.ftp import FTPServer

log = logging.getLogger('BetaServer')

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-l', '--log', dest='logfile', help='Output server log to this file.')
    parser.add_option('-p', '--port', type='int', dest='port', default=1337, help='The port to use for the Telnet server.')
    parser.add_option('--http', type='int', dest='wsport', default=1338, help='The port to use for the websockets HTTP server.')
    parser.add_option('-d', '--daemon', action='store_true', dest='daemon', default=False, help='Run server in daemon mode.')
    parser.add_option('-D', '--debug', action='store_true', dest='debug', default=False, help='Enable DEBUG log level.')
    options, args = parser.parse_args()
    logging.basicConfig(filename=options.logfile, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG if options.debug else logging.INFO)

    if options.daemon:
        pid = os.fork()
        if pid > 0:
            sys.stdout.write("Forked process: %d\n" % pid)
            sys.exit(0)
        null = open(os.devnull, 'r+')
        sys.stdout = null
        sys.stderr = null
        os.nice(10)
    else:
        sys.stdout.write(chr(27)+']2;GameServer'+chr(7))
        sys.stdout.flush()

    def handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, handler)
    

    s = TelnetServer(('0.0.0.0', options.port))
    w = WebServer(('127.0.0.1', options.wsport))
    f = FTPServer()
    idler = Idler()
    events = EventThread()
    idler.start()
    events.start()
    hypervisor.start()
    log.info("Hacker's Edge server started.")
    running = True
    while running:
        try:
            asyncore.loop(use_poll=True, count=1)
            if len(asyncore.socket_map) == 0:
                log.info('Finished handling all requests, terminating...')
                running = False
            else:
                state = open('state','r').read()
                if state == 'HEALTH':
                    open('health.log', 'w').write('Socket map: %s' % len(asyncore.socket_map))
                elif state == 'TERM':
                    open('state', 'w').write('OK')
                    log.info('Requested termination...')
                    s.close()
                    w.close()
                    f.close()
                for v in asyncore.socket_map.values():
                    if hasattr(v, 'ctype'):
                        v.notify('Health check.')
        except KeyboardInterrupt:
            log.info('Requested server termination...')
            s.close()
            w.close()
            f.close()
        except socket.error:
            log.critical('Server socket error, terminating...')
            running = False
        except:
            log.critical('Server exception occurred: [%s]%s' % (sys.exc_info()[0],sys.exc_info()[1]))
            open('stacktrace.log', 'w').write('\n'.join(traceback.format_tb(sys.exc_info()[2])))
    hypervisor.cancel()
    events.cancel()
    idler.cancel()
    log.info('Shutting down threads...')
    idler.join()

if __name__ == '__main__':
    main()
