import threading, time, logging, sys
from settings import SHOW_VERSIONS
from vm import CPU
from exceptions import VMError, VMNoData, VMFlush, SessionCtrl, VMNetData
from utils import send_traceback
from databases import get_host, set_host
import asynchat

log = logging.getLogger('Sessions')

VERSION = 'HackerSessions v0.10.3 $Revision: 195 $'

class asynclock(asynchat.async_chat):
    def __init__(self, sock=None, map=None):
        asynchat.async_chat.__init__(self, sock, map)
        self.__push_lock = threading.Lock()
        self.__read_lock = threading.Lock()
    def initiate_send(self):
        with self.__push_lock:
            asynchat.async_chat.initiate_send(self)
    def handle_read(self):
        with self.__read_lock:
            asynchat.async_chat.handle_read(self)

class SharedMemory(object):
    def __init__(self):
        self.__lock = threading.Lock()
        self.__udata = {}
    def __setattr__(self, name, value):
        if name == '_SharedMemory__lock':
            self.__dict__['_SharedMemory__lock'] = value
            return
        with self.__lock:
            super(SharedMemory, self).__setattr__(name, value)
    def __setitem__(self, key, value):
        with self.__lock:
            self.__udata[key] = value
    def __getitem__(self, key):
        with self.__lock:
            value = self.__udata[key]
        return value
    def clean_udata(self):
        with self.__lock:
            for udata in self.__udata.keys():
                sid = self.__udata[udata]['username']
                if not self.sessions.has_key(sid):
                    log.info('Clearing udata: %s' % udata)
                    host, route = self.__udata[udata]['host'], self.__udata[udata]['route']
                    del self.__udata[udata]
                    for h in route:
                        old_host = host
                        host = route.pop()
                        self.disconnect(old_host, host)
    def del_udata(self, username):
        with self.__lock:
            if username in self.__udata.keys():
                del self.__udata[username]
    def kick_all(self, transmit):
        with self.__lock:
            for udata in self.__udata.keys():
                if not self.__udata[udata]['staff']:
                    s = SHM.sessions[self.__udata[udata]['username']]
                    try:
                        if s.connected:
                            transmit('Kicking %s...' % self.__udata[udata]['username'])
                            s.transmit(" *** Hacker's Edge Game Server going into maintenance mode. ***")
                            s.close_when_done()
                    except:
                        raise
        self.clean_udata()
    def list_udata(self):
        with self.__lock:
            value = ', '.join(self.__udata.keys())
        return value
    def add_session(self, channel):
        if SHOW_VERSIONS:
            channel.transmit(VERSION)
        sid = str(time.time())
        with self.__lock:
            self.sessions[sid] = channel
        return sid
    def del_session(self, sid):
        with self.__lock:
            try:
                del self.sessions[sid]
            except:
                pass
    def update_session(self, sid, username):
        log.info('Upgrading session for: %s' % username)
        with self.__lock:
            try:
                self.sessions[username] = self.sessions[sid]
                del self.sessions[sid]
            except:
                log.critical('Problem with session upgrade: %s' % sys.exc_info()[1])
    def connected(self, to_host, from_host):
        with self.__lock:
            if not self.connhost.has_key(to_host):
                self.connhost[to_host] = []
            self.connhost[to_host].append(from_host)
    def disconnect(self, from_host, to_host):
        with self.__lock:
            try:
                self.connhost[from_host].remove(to_host)
            except:
                log.error('Could not remove %s from connhost[%s]' % (to_host, from_host))
    def push_event(self, event):
        with self.__lock:
            self.events.insert(0, event)
    def get_events(self):
        with self.__lock:
            events = self.events
        self.events = []
        return events

SHM = SharedMemory()
SHM.uptime = time.time()
SHM.total_telnet = SHM.total_web = 0
SHM.sessions = {}
SHM.blocklist = []
SHM.connhost = {}
SHM.events = []
SHM.MAINTENANCE_MODE = True

def notify_sessions(message, me):
    for sid, s in SHM.sessions.items():
        if sid != me and s.connected:
            s.notify(message)

def clean_sessions():
    for opid,s in SHM.sessions.items():
        if not s.connected:
            notify_sessions('[%s] Player logged out.' % opid, opid)
            try:
                s.game.on_disconnect()
            except:
                pass
            try:
                hypervisor.destroy(opid)
                SHM.del_session(opid)
            except:
                pass

def ban_session(sid):
    ip_addr = SHM.sessions[sid].ip_addr
    log.info('[%s] Banning session: %s' % (ip_addr, sid))
    SHM.blocklist.append(ip_addr)
    SHM.del_session(sid)
    clean_sessions()

def close_session(sid):
    log.info("Disconnect by: %s" % sid)
    try:
        if SHM.sessions[sid].game.state != 'login':
            notify_sessions('[%s] Player logged out.' % sid, sid)
    except:
        pass
    try:
        SHM.del_session(sid)
    except:
        pass
    hypervisor.destroy(sid)
    clean_sessions()

def uptime():
    from datetime import timedelta
    return str(timedelta(seconds=time.time()-SHM.uptime))

def player_count():
    return len(SHM.sessions)-1

class Idler(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.finish = threading.Event()
    def cancel(self):
        log.info('Idler cancelled.')
        self.finish.set()
    def run(self):
        while not self.finish.is_set():
            self.finish.wait(60.0*30)
            if not self.finish.is_set():
                clean_sessions()
                for sid,s in SHM.sessions.items():
                    if not s.away_mode and not s.last_seen > time.time()-300:
                        log.info('Disconnecting: %s' % s.ip_addr)
                        notify_sessions('[%s] Player logged out.' % sid, sid)
                        s.transmit('Disconnecting...')
                        hypervisor.destroy(sid)
                        s.close()
                SHM.clean_udata()

class EventThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.finish = threading.Event()
    def cancel(self):
        log.info('EventThread cancelled.')
        self.finish.set()
    def run(self):
        while not self.finish.is_set():
            self.finish.wait(60.0)
            if not self.finish.is_set():
                events = SHM.get_events()
                for evt in events:
                    handler = getattr(self, 'evt_%s' % evt['action'], None)
                    if handler:
                        handler(*evt['args'])
    def evt_hello(self, sid):
        SHM.sessions[sid].notify('Hello from the EventThread!')

class VMManager(threading.Thread):
    """ This thread will manage the VM allocations. """
    def __init__(self):
        threading.Thread.__init__(self)
        self.finish = threading.Event()
        self.process = threading.Event()
        self.vms = {}
        self.hosts = {}
        self.vms_lock = threading.Lock()
    def cancel(self):
        log.info('VMManager cancelled.')
        self.finish.set()
        self.process.set()
    def allocate(self, session, tty=True):
        with self.vms_lock:
            self.vms[session] = CPU(tty)
        if tty and SHOW_VERSIONS:
            SHM.sessions[session].transmit(CPU.version)
    def get_vm(self, ip_addr, tty=False):
        with self.vms_lock:
            if ip_addr in self.hosts.keys():
                sid = self.hosts[ip_addr]
            else:
                sid = 'tmp-%s' % str(time.time())
                self.vms[sid] = CPU(tty)
                self.vms[sid].switch_host(ip_addr)
                self.hosts[ip_addr] = sid
        return sid
    def destroy(self, session):
        log.info('Removing VM for %s' % session)
        with self.vms_lock:
            if session in self.hosts.values():
                del self.hosts[self.vms[session].ip_addr]
            if self.vms.has_key(session):
                self.vms[session].save_state()
                del self.vms[session]
    def switch_host(self, session, ip_addr):
        if session in self.hosts.values():
            try:
                del self.hosts[self.vms[session].ip_addr]
            except:
                pass
        self.vms[session].switch_host(ip_addr)
        self.hosts[ip_addr] = session
    def host_data(self, session):
        with self.vms_lock:
            self.vms[session].get_host()
            return self.vms[session].host
    def set_host(self, session):
        with self.vms_lock:
            self.vms[session].set_host()
    def get_host(self, ip_addr):
        with self.vms_lock:
            if ip_addr in self.hosts.keys():
                sid = self.hosts[ip_addr]
            else:
                return get_host(ip_addr)
        return self.host_data(sid)
    def attach(self, ip_addr, blkdev):
        with self.vms_lock:
            if ip_addr in self.hosts.keys():
                sid = self.hosts[ip_addr]
                host = self.host_data(sid)
                if not host.has_key('storage'):
                    host['storage'] = []
                host['storage'].append(blkdev)
                self.set_host(sid)
            else:
                host = get_host(ip_addr)
                if not host.has_key('storage'):
                    host['storage'] = []
                host['storage'].append(blkdev)
                set_host(ip_addr, host)
    def detach(self, ip_addr, blkdev):
        with self.vms_lock:
            if ip_addr in self.hosts.keys():
                sid = self.hosts[ip_addr]
                host = self.host_data(sid)
                try:
                    host['storage'].remove(blkdev)
                except:
                    return False
                self.set_host(sid)
            else:
                host = get_host(ip_addr)
                try:
                    host['storage'].remove(blkdev)
                except:
                    return False
                set_host(ip_addr, host)
        return True
    def reboot(self, session):
        log.info('Rebooting VM for %s' % session)
        with self.vms_lock:
            self.vms[session].running = False
            rt = self.vms[session].ipl()
        return rt
    def load(self, session, fname, addr=0x800):
        with self.vms_lock:
            if self.vms.has_key(session):
                self.vms[session].pc = addr
                self.vms[session].load(fname, addr)
    def set_pc(self, session, addr):
        with self.vms_lock:
            self.vms[session].pc = addr
    def set_byte(self, session, addr, value):
        with self.vms_lock:
            self.vms[session].mem.set(addr, value)
    def set_word(self, session, addr, value):
        with self.vms_lock:
            self.vms[session].mem.set_word(addr, value)
    def set_page(self, session, page, data):
        with self.vms_lock:
            self.vms[session].mem.seek((page >> 8) << 8)
            self.vms[session].mem.write(data)
    def get_byte(self, session, addr):
        with self.vms_lock:
            value = self.vms[session].mem.get(addr)
        return value
    def get_word(self, session, addr):
        with self.vms_lock:
            value = self.vms[session].mem.get_word(addr)
        return value
    def get_page(self, session, page):
        with self.vms_lock:
            self.vms[session].mem.seek((page >> 8) << 8)
            return self.vms[session].mem.read(256)
    def set_param(self, session, param=None):
        with self.vms_lock:
            if self.vms.has_key(session):
                self.vms[session].set_param(param)
    def execute(self, session):
        with self.vms_lock:
            self.vms[session].running = True
        self.process.set()
    def exec_isr(self, session, addr):
        with self.vms_lock:
            self.vms[session].interrupt(addr)
            self.vms[session].running = True
        self.process.set()
    def wait(self, session):
        self.vms[session].finished.wait()
    def interrupt(self, session):
        r = self.vms[session].regP & 0x04
        if r == 0:
            return False
        hd = self.host_data(session)
        isr = hd.get('isr', None)
        if isr is None:
            return False
        with self.vms_lock:
            self.vms[session].interrupt(isr)
        self.process.set()
    def kill(self, session):
        with self.vms_lock:
            if self.vms.has_key(session):
                self.vms[session].running = False
                self.__stop_vm(session, self.vms[session])
        self.process.set()
        log.info('VM Killed: %s' % session)
    def killall(self):
        with self.vms_lock:
            for sid, vm in self.vms.items():
                if vm.running:
                    vm.running = False
                    self.__stop_vm(sid, vm)
                    log.info('VM Killed: %s' % sid)
    def __stop_vm(self, sid, vm):
        #vm.reset() # For the time being, we need to reset the CPU...
        if vm.tty:
            prompt = SHM.sessions[sid].game.prompt
            SHM.sessions[sid].prompt = prompt
            SHM.sessions[sid].stdout(vm.mem.stdout)
            SHM.sessions[sid].game.show_prompt()
            SHM.sessions[sid].game.state = 'shell'
    def stdin(self, session, data):
        with self.vms_lock:
            self.vms[session].mem.input(data)
            self.vms[session].running = True
        self.process.set()
    def stdout(self, session):
        with self.vms_lock:
            data = self.vms[session].mem.stdout
        return data
    def mousein(self, session, but, row, col):
        self.set_byte(session, 0xffdd, but)
        self.set_byte(session, 0xffde, row)
        self.set_byte(session, 0xffdf, col)
        addr = self.get_word(session, 0xffdb)
        with self.vms_lock:
            self.vms[session].interrupt(addr)
            self.vms[session].running = True
        self.process.set()
    @property
    def running_vms(self):
        running = 0
        with self.vms_lock:
            for vm in self.vms.values():
                if vm.running:
                    running+=1
        return running
    def run(self):
        log.info('VM Hypervisor started, and ready.')
        while not self.finish.is_set():
            self.process.wait()
            self.process.clear()
            #log.info('VM Processing has begun...')
            with self.vms_lock:
                for sid, vm in self.vms.items():
                    if vm.running:
                        try:
                            vm.process_op()
                        except VMFlush:
                            if vm.tty:
                                SHM.sessions[sid].stdout(vm.mem.stdout)
                        except VMNoData:
                            if vm.tty:
                                stdout = vm.mem.stdout
                                SHM.sessions[sid].prompt = stdout.split('\n')[-1]
                                SHM.sessions[sid].stdout(stdout)
                            else:
                                log.critical('Attempting to obtain input without TTY!')
                            vm.running = False
                            log.info('VMNoData, gathering standard input...')
                            continue
                        except IOError, e:
                            vm.running = False
                            if vm.tty:
                                SHM.sessions[sid].stdout('%s\r\n' % str(e))
                        except VMError, e:
                            vm.running = False
                            if vm.tty:
                                SHM.sessions[sid].stdout('%s\r\n' % str(e))
                        except SessionCtrl, e:
                            if vm.tty:
                                ctrl, state = str(e).split(':')
                                if ctrl == 'M':
                                    if state == '1':
                                        SHM.sessions[sid].enable_mouse()
                                    else:
                                        SHM.sessions[sid].disable_mouse()
                        except VMNetData, e:
                            ctrl, idx = str(e).split(':')
                            if ctrl == 'CONN':
                                hd = vm.host
                                entry = hd['nettbl'][int(idx)]
                                log.info('Connect to %s:%s' % (entry['ip_addr'], entry['port']))
                            elif ctrl == 'SEND':
                                hd = vm.host
                                entry = hd['nettbl'][int(idx)]
                                log.info('Send buffer to %s:%s' % (entry['ip_addr'], entry['port']))
                        except:
                            vm.running = False
                            log.critical('Unhandled VM error: [%s]%s' % (sys.exc_info()[0], sys.exc_info()[1]))
                            if vm.tty:
                                SHM.sessions[sid].stdout(' * Critical game VM error occurred!\r\n')
                            try:
                                send_traceback(sys.exc_info())
                            except:
                                log.critical('Unable to send traceback message...')
                        if not vm.running:
                            self.__stop_vm(sid, vm)
                for sid, vm in self.vms.items():
                    if vm.running:
                        self.process.set()

hypervisor = VMManager()
