import asyncore, logging, sys, signal, os, traceback
from game_engine.engine import EngineServer

log = logging.getLogger('Engined')

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-l', '--log', dest='logfile', help='Output server log to this file.')
    parser.add_option('-d', '--daemon', action='store_true', dest='daemon', default=False, help='Run server in daemon mode.')
    parser.add_option('-D', '--debug', action='store_true', dest='debug', default=False, help='Enable DEBUG log level.')
    options, args = parser.parse_args()
    logging.basicConfig(filename=options.logfile, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG if options.debug else logging.INFO)
    
    if options.daemon:
        pid = os.fork()
        if pid > 0:
            sys.stdout.write("Forked process: %d\n" % pid)
            open('engined.pid', 'w').write(str(pid))
            sys.exit(0)
        null = open(os.devnull, 'r+')
        sys.stdout = null
        sys.stderr = null
        os.nice(10)
    else:
        sys.stdout.write(chr(27)+']2;Engined'+chr(7))
        sys.stdout.flush()

    def handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, handler)
    
    engined = EngineServer()
    log.info('Engined server started.')
    running = True
    while running:
        try:
            asyncore.loop(use_poll=True, count=1)
            if len(asyncore.socket_map) == 0:
                log.info('Finished handling all requests, terminating...')
                running = False
        except KeyboardInterrupt:
            log.info('Requested server termination.')
            engined.close()
            for channel in asyncore.socket_map.values():
                channel.handle_close()
        except:
            log.critical('Server exception occurred: [%s]%s' % (sys.exc_info()[0],sys.exc_info()[1]))
            open('stacktrace.log', 'w').write('\n'.join(traceback.format_tb(sys.exc_info()[2])))
    log.info('Server shutdown complete.')
    os.unlink('engine')

if __name__ == '__main__':
    main()
