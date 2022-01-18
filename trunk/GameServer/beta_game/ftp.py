from databases import userdb, get_host
from sessions import asynclock
import asyncore, asynchat, socket, logging, hashlib, os, hostops, sys

log = logging.getLogger('FTP')

LIST_TEMPL = "%s %3s %-8s %-8s %8s %s %s\r\n"

def auth(func):
    def wrapped_f(*args):
        return func(*args)
    f = wrapped_f
    f.auth = True
    return f

class DTPChannel(asynclock):
    def __init__(self, sock, chan, fd=None):
        asynclock.__init__(self, sock)
        self.chan = chan
        self.receive = False
        self.fd = fd
        self.total_size = 0
    def handle_read(self):
        with self.__read_lock:
            data = self.recv(1024)
            if self.fd is not None:
                self.total_size+=len(data)
                if self.total_size>4096:
                    self.fd.close()
                    self.fd = None
                    self.receive = False
                    self.chan.push('552 File too large.\r\n')
                    self.close()
                    return
                self.fd.write(data)
                self.receive = True
    def handle_close(self):
        if self.receive:
            self.fd.close()
            self.fd = None
            self.receive = False
            self.chan.push('226 Transfer complete.\r\n')
        self.close()

class DTPServer(asyncore.dispatcher):
    def __init__(self, chan):
        asyncore.dispatcher.__init__(self)
        self.chan = chan
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('0.0.0.0', 2122))
        self.listen(1)
        local_ip = self.chan.socket.getsockname()[0]
        self.chan.push('227 Entering Passive Mode (%s,8,74).\r\n' % ','.join(local_ip.split('.')))
        self.buffer = ''
        self.fname = None
    def handle_accept(self):
        sock, addr = self.accept()
        log.info('DTP Connection from %s' % addr[0])
        self.close()
        fd = None
        if self.fname is not None:
            fd = hostops.open_file(self.fname, 'w')
            self.fname = None
        self.chan.data_channel = DTPChannel(sock, self.chan, fd)
        if self.buffer != '':
            self.chan.data_channel.push(self.buffer)
            self.chan.data_channel.close_when_done()
            self.chan.data_channel = None

class FTPChannel(asynclock):
    def __init__(self, sock):
        asynclock.__init__(self, sock)
        self.ibuffer = ''
        self.data_channel = None
        self.dtp_srv = None
        self.udata = None
        self.auth = False
        self.set_terminator('\r\n')
        self.push('220 HackerFTPd v0.4.1 $Revision: 198 $\r\n')
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def cmd_QUIT(self, param):
        self.push('221 Goodbye.\r\n')
        self.handle_close()
    def cmd_USER(self, param):
        log.info('User sign in attempt: %s' % param)
        self.username = param
        self.udata = userdb.get_user(self.username)
        self.push('331 Please specify the password.\r\n')
    def cmd_PASS(self, param):
        if self.udata is None:
            self.push('503 Login with USER first.\r\n')
            return
        if self.username == 'anonymous':
            self.push('530 Anonymous access not allowed.\r\n')
            return
        if hashlib.md5(param).hexdigest() == self.udata['password']:
            self.auth = True
            self.push('230 Login successful.\r\n')
        else:
            self.push('530 Authentication failed.\r\n')
    def cmd_SYST(self, param):
        self.push('215 UNIX Type: L8\r\n')
    @auth
    def cmd_PWD(self, param):
        self.push('257 "/"\r\n')
    @auth
    def cmd_TYPE(self, param):
        if param == 'I':
            self.push('200 Switching to Binary mode.\r\n')
        elif param == 'A':
            self.push('200 Switching to ACSII mode.\r\n')
    @auth
    def cmd_PASV(self, param):
        if self.data_channel is not None:
            self.data_channel.close()
            self.data_channel = None
        if self.dtp_srv is not None:
            self.dtp_srv.close()
            self.dtp_srv = None
        self.dtp_srv = DTPServer(self)
    @auth
    def cmd_CWD(self, param):
        if param == '/':
            self.push('250 Changed working directory.\r\n')
        else:
            self.push('550 Flat file system.\r\n')
    @auth
    def cmd_LIST(self, param):
        host_data = get_host(self.udata['ip_addr'])
        if self.data_channel is not None:
            self.push('150 Here comes the directory listing.\r\n')
            for f in host_data['files']:
                try:
                    sz = os.stat(hostops.get_file('%s:%s' % (self.udata['ip_addr'], f))).st_size
                except:
                    sz = 0
                self.data_channel.push(LIST_TEMPL % ('-r--r-----', 1, self.username, self.username, sz, 'Jul 31 14:00', f))
            self.data_channel.close()
            self.push('226 Directory send OK.\r\n')
        elif self.dtp_srv is not None:
            self.push('150 Here comes the directory listing.\r\n')
            for f in host_data['files']:
                try:
                    sz = os.stat(hostops.get_file('%s:%s' % (self.udata['ip_addr'], f))).st_size
                except:
                    sz = 0
                self.dtp_srv.buffer += LIST_TEMPL % ('-r--r-----', 1, self.username, self.username, sz, 'Jul 31 14:00', f)
            self.push('226 Directory send OK.\r\n')
        else:
            self.push('425 Use PASV first.\r\n')
    @auth
    def cmd_SIZE(self, param):
        fname = param.strip('/')
        try:
            sz = os.stat(hostops.get_file('%s:%s' % (self.udata['ip_addr'], fname))).st_size
            self.push('213 %s\r\n' % sz)
        except:
            self.push('550 File not found.\r\n')
    @auth
    def cmd_MDTM(self, param):
        fname = param.strip('/')
        try:
            sz = os.stat(hostops.get_file('%s:%s' % (self.udata['ip_addr'], fname))).st_size
            self.push('213 20160731140000\r\n')
        except:
            self.push('550 File not found.\r\n')
    @auth
    def cmd_RETR(self, param):
        fname = param.strip('/')
        try:
            data = hostops.open_file('%s:%s' % (self.udata['ip_addr'], fname), 'r').read()
        except:
            self.push('550 File not found.\r\n')
            return
        if self.data_channel is not None:
            log.info('Using data channel...')
            self.push('150 Opening BINARY mode data connection for %s.\r\n' % param)
            self.data_channel.push(data)
            self.data_channel.close_when_done()
            self.push('226 Transfer complete.\r\n')
            log.info('Transfer complete.')
        elif self.dtp_srv is not None:
            self.push('150 Opening BINARY mode data connection for %s.\r\n' % param)
            self.dtp_srv.buffer = data
            self.push('226 Transfer complete.\r\n')
        else:
            self.push('425 Use PASV first.\r\n')
    @auth
    def cmd_STOR(self, param):
        fname = param.strip('/')
        if self.data_channel is not None:
            self.data_channel.fd = hostops.open_file('%s:%s' % (self.udata['ip_addr'], fname), 'w')
            self.push('125 Data channel is already open. Transfer starting.\r\n')
        elif self.dtp_srv is not None:
            self.dtp_srv.fname = '%s:%s' % (self.udata['ip_addr'], fname)
            self.push('125 Data channel is already open. Transfer starting.\r\n')
        else:
            self.push('425 Use PASV first.\r\n')
    @auth
    def cmd_DELE(self, param):
        fname = param.strip('/')
        try:
            hostops.delete_file('%s:%s' % (self.udata['ip_addr'], fname))
            self.push('250 File removed.\r\n')
        except:
            self.push('550 File not found.\r\n')
    def found_terminator(self):
        log.debug('Command: %s' % self.ibuffer)
        try:
            cmd, param = self.ibuffer.split(' ',1)
        except ValueError:
            cmd, param = self.ibuffer, ''
        cmd = cmd.upper()
        self.ibuffer = ''
        handler = getattr(self, 'cmd_%s' % cmd, None)
        auth = getattr(handler, 'auth', False)
        if handler is None:
            self.push('502 Command not implemented.\r\n')
            return
        if auth:
            if not self.auth:
                self.push('530 Anonymous access not allowed.\r\n')
                return
        try:
            if param is None:
                handler()
            else:
                handler(param)
        except:
            log.error('Exception occurred during command: %s' % cmd)
            if self.data_channel is not None:
                self.data_channel.close()
            if self.dtp_srv is not None:
                self.dtp_srv.close()
            self.handle_close()
    def handle_close(self):
        log.info('Connection closing.')
        if self.data_channel is not None:
            self.data_channel.close()
            self.data_channel = None
        self.close()

class FTPServer(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('0.0.0.0', 2121))
        self.listen(5)
        log.info('Listening on port %s.' % self.socket.getsockname()[1])
    def handle_accept(self):
        channel = None
        try:
            sock, addr = self.accept()
            log.info('Connection from %s' % addr[0])
            c = FTPChannel(sock)
        except:
            if channel is None:
                raise
            channel.close()
            log.critical('Unhandled exception in Server module:[%s] %s' % (sys.exc_info()[0], sys.exc_info()[1]))
    def log_info(self, message, type='info'):
        log.critical(message)
