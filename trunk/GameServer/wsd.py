import asyncore, logging, sys, signal, os, traceback
from game_engine.websocket import WebServer

log = logging.getLogger('WebSocketd')

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-l', '--log', dest='logfile', help='Output server log to this file.')
    parser.add_option('-p', '--port', type='int', dest='port', default=1338, help='The port to use for the Telnet server.')
    parser.add_option('-d', '--daemon', action='store_true', dest='daemon', default=False, help='Run server in daemon mode.')
    parser.add_option('-D', '--debug', action='store_true', dest='debug', default=False, help='Enable DEBUG log level.')
    options, args = parser.parse_args()
    logging.basicConfig(filename=options.logfile, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG if options.debug else logging.INFO)
    
    if options.daemon:
        pid = os.fork()
        if pid > 0:
            sys.stdout.write("Forked process: %d\n" % pid)
            open('wsd.pid', 'w').write(str(pid))
            sys.exit(0)
        null = open(os.devnull, 'r+')
        sys.stdout = null
        sys.stderr = null
        os.nice(10)
    else:
        sys.stdout.write(chr(27)+']2;WebSocketd'+chr(7))
        sys.stdout.flush()

    def handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, handler)
    
    wsd = WebServer(('127.0.0.1', options.port))
    log.info('WebSocketd server started.')
    running = True
    while running:
        try:
            asyncore.loop(use_poll=True, count=1)
            if len(asyncore.socket_map) == 0:
                log.info('Finished handling all requests, terminating...')
                running = False
        except KeyboardInterrupt:
            log.info('Requested server termination.')
            wsd.close()
        except:
            log.critical('Server exception occurred: [%s]%s' % (sys.exc_info()[0],sys.exc_info()[1]))
            open('stacktrace.log', 'w').write('\n'.join(traceback.format_tb(sys.exc_info()[2])))
    log.info('Server shutdown complete.')

if __name__ == '__main__':
    main()
