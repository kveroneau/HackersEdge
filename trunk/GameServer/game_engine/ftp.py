import asyncore, asynchat, socket, logging, sys, urllib2, pickle, hashlib, os
from settings import HACKER_TOKEN, USERDB_RPC, HOSTS_RPC, EXPOSED, DESIGNER
from databases import get_host_dir

log = logging.getLogger('FTP')

ROOT_LIST = (
    ('motd.txt', '-rw-r--r--', 'chronoboy'),
    ('README.txt', '-rw-r--r--', 'chronoboy'),
)

README_FILE = """Hacker's Edge FTP Server access readme file.

Welcome to your personal FTP access into Hacker's Edge!  Using this service, you can access the
file systems of any host machine under your control which has the HostFS device installed.

If you see no folders shown here, then you should create a character in-game connected to a machine type
with the HostFS device.

You will not be-able to modify any files in this root directory, and you will not be able to create new directories.

In the future, additional features may be added to this FTP Server.
"""

LIST_TEMPL = "%s %3s %-8s %-8s %8s %s %s\r\n"

def get_user(username):
    headers = {'User-Agent':'HackerEngine/1.0','X-Hacker-Token':HACKER_TOKEN}
    data = chr(0).join(['user',username])
    req = urllib2.Request(USERDB_RPC, data, headers)
    r = urllib2.urlopen(req)
    if r.code != 200:
        raise
    data = r.read().split(chr(0))
    if data[0] != 'udata':
        raise
    return pickle.loads(data[1])

def get_host(ip_addr):
    headers = {'User-Agent':'HackerEngine/1.0','X-Hacker-Token':HACKER_TOKEN}
    data = chr(0).join(['get_host',ip_addr])
    req = urllib2.Request(HOSTS_RPC, data, headers)
    r = urllib2.urlopen(req)
    if r.code != 200:
        raise
    data = r.read().split(chr(0))
    print data
    if data[0] != 'get_host':
        raise
    if data[1] == 'ERR'+chr(255):
        raise
    return pickle.loads(data[1])

def hostfs_dir(ip_addr):
    return '%s/%s/files' % (get_host_dir(ip_addr), ip_addr)

def read_idx(ip_addr):
    idx = open('%s/%s' % (hostfs_dir(ip_addr), 'idx'), 'rb').read()
    if idx == '':
        return []
    return idx.split(chr(255))

def write_idx(ip_addr, flist):
    idx = chr(255).join(flist)
    open('%s/%s' % (hostfs_dir(ip_addr), 'idx'), 'wb').write(idx)

def hostfs_file(ip_addr, fname):
    if ip_addr in EXPOSED.keys():
        return '%s%s' % (EXPOSED[ip_addr], fname)
    hname = '%s/%s' % (hostfs_dir(ip_addr), hashlib.md5(fname).hexdigest())
    return hname    

def hostfs_open(ip_addr, fname, mode):
    if 'w' in mode:
        flist = read_idx(ip_addr)
        if fname not in flist:
            flist.append(fname)
            write_idx(ip_addr, flist)
    hname = hostfs_file(ip_addr, fname)
    return open(hname, mode)

def auth(func):
    def wrapped_f(*args):
        return func(*args)
    f = wrapped_f
    f.auth = True
    return f

class DTPChannel(asynchat.async_chat):
    def __init__(self, sock, chan, fd=None):
        asynchat.async_chat.__init__(self, sock)
        self.chan = chan
        self.receive = False
        self.fd = fd
        self.total_size = 0
    def handle_read(self):
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
            log.debug('fname was sent in.')
            fd = hostfs_open(self.fname[0], self.fname[1], 'w')
            self.fname = None
        self.chan.data_channel = DTPChannel(sock, self.chan, fd)
        if self.buffer != '':
            self.chan.data_channel.push(self.buffer)
            self.chan.data_channel.close_when_done()
            self.chan.data_channel = None

class FTPChannel(asynchat.async_chat):
    def __init__(self, sock):
        asynchat.async_chat.__init__(self, sock)
        self.ibuffer = ''
        self.data_channel = None
        self.dtp_srv = None
        self.udata = None
        self.auth = False
        self.host = None
        self.set_terminator('\r\n')
        self.push('220 HackerFTPd v0.5.3 $Rev: 320 $\r\n')
    def collect_incoming_data(self, data):
        self.ibuffer+=data
    def cmd_QUIT(self, param):
        self.push('221 Goodbye.\r\n')
        self.handle_close()
    def cmd_USER(self, param):
        log.info('User sign in attempt: %s' % param)
        self.username = param
        self.udata = get_user(self.username)
        self.push('331 Please specify the password.\r\n')
    def cmd_PASS(self, param):
        success = False
        if self.udata is None:
            self.push('503 Login with USER first.\r\n')
            return
        if self.udata is False:
            self.push('430 Authentication failed.\r\n')
            return
        if self.username == 'anonymous':
            self.push('530 Anonymous access not allowed.\r\n')
            return
            self.auth = True
            self.host_list = []
            self.push('230 Login successful.\r\n')
            return
        try:
            gamedata = pickle.loads(open('players/%s/gamedata' % self.username, 'rb').read())
        except:
            self.push('430 Log into game server first.\r\n')
        if gamedata.has_key('api_key'):
            if param == gamedata['api_key']:
                success = True
            else:
                self.push('430 Login using your API Key.\r\n')
                return
        elif hashlib.md5(param).hexdigest() == self.udata['password']:
            success = True
        if success:
            self.auth = True
            self.push('230 Login successful.\r\n')
            self.host_list = []
            for host in gamedata['host_list']:
                if os.path.exists('%s/idx' % hostfs_dir(host)):
                    self.host_list.append(str(host))
        else:
            self.push('430 Authentication failed.\r\n')
    def cmd_SYST(self, param):
        self.push('215 UNIX Type: L8\r\n')
    @auth
    def cmd_PWD(self, param):
        cwd = '/' if self.host is None else '/%s' % self.host
        self.push('257 "%s"\r\n' % cwd)
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
        if param[0] != '/':
            param = '/%s' % param
        if len(param) > 1 and param.endswith('/'):
            param = param[:-1]
        if param == '/':
            self.host = None
            log.info('Switched to root')
            self.push('250 Changed working directory.\r\n')
        elif param[1:] in EXPOSED.keys():
            if param[1:] in DESIGNER and not self.udata['designer']:
                self.push('550 Host not available.\r\n')
                return
            self.host = param[1:]
            log.info('Switched to %s' % self.host)
            self.push('250 Changed working directory.\r\n')
        else:
            if param[1:] in self.host_list:
                self.host = param[1:]
                log.info('Switched to host %s' % self.host)
                self.push('250 Changed working directory.\r\n')
            else:
                self.push('550 Host not available.\r\n')
    @auth
    def cmd_LIST(self, param):
        if self.host is None:
            flist = list(ROOT_LIST)
            for fname in EXPOSED.keys():
                if self.udata['designer']:
                    flist.append((fname,'dr-xr-xr-x','root'))
                else:
                    if fname not in DESIGNER:
                        flist.append((fname,'dr-xr-xr-x','root'))
            for fname in self.host_list:
                flist.append((fname,'drwxr-x---',self.username))
            if os.path.exists('players/%s/bucket' % self.username):
                flist.append(('bucket','dr-xr-x---',self.username))
        elif self.host in EXPOSED.keys():
            flist = []
            for fname in os.listdir(EXPOSED[self.host]):
                flist.append((fname,'-rw-r--r--','root'))
        else:
            flist = []
            for fname in read_idx(self.host):
                flist.append((fname,'-rw-rw----',self.username))
        if self.data_channel is not None:
            self.push('150 Here comes the directory listing.\r\n')
            for f in flist:
                try:
                    sz = os.stat(hostfs_file(self.host, f[0])).st_size
                except:
                    if f[0] == 'motd.txt':
                        sz = os.stat('motd.txt').st_size
                    elif f[0] == 'README.txt':
                        sz = len(README_FILE)
                    else:
                        sz = 0
                self.data_channel.push(LIST_TEMPL % (f[1], 1, f[2], f[2], sz, 'Jul 31 14:00', f[0]))
            self.data_channel.close()
            self.data_channel = None
            self.push('226 Directory send OK.\r\n')
        elif self.dtp_srv is not None:
            self.push('150 Here comes the directory listing.\r\n')
            for f in flist:
                try:
                    sz = os.stat(hostfs_file(self.host, f[0])).st_size
                except:
                    if f[0] == 'motd.txt':
                        sz = os.stat('motd.txt').st_size
                    elif f[0] == 'README.txt':
                        sz = len(README_FILE)
                    else:
                        sz = 0
                self.dtp_srv.buffer += LIST_TEMPL % (f[1], 1, f[2], f[2], sz, 'Jul 31 14:00', f[0])
            self.push('226 Directory send OK.\r\n')
        else:
            self.push('425 Use PASV first.\r\n')
    @auth
    def cmd_SIZE(self, param):
        if param == '/motd.txt':
            self.push('213 %s\r\n' % os.stat('motd.txt').st_size)
            return
        elif param == '/README.txt':
            self.push('213 %s\r\n' % len(README_FILE))
            return
        parts = param[1:].split('/')
        try:
            sz = os.stat(hostfs_file(parts[0], parts[1])).st_size
            self.push('213 %s\r\n' % sz)
        except:
            self.push('550 File not found.\r\n')
    @auth
    def cmd_MDTM(self, param):
        parts = param[1:].split('/')
        try:
            sz = os.stat(hostfs_file(parts[0], parts[1])).st_size
            self.push('213 20160731140000\r\n')
        except:
            self.push('550 File not found.\r\n')
    @auth
    def cmd_RETR(self, param):
        if param[0] != '/':
            param = '%s/%s' % (self.host, param)
            parts = param.split('/')
        else:
            parts = param[1:].split('/')
        try:
            data = hostfs_open(parts[0], parts[1], 'r').read()
        except:
            if param == '/motd.txt':
                data = open('motd.txt', 'r').read()
            elif param == '/README.txt':
                data = str(README_FILE)
            else:
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
        if param[0] != '/':
            param = '%s/%s' % (self.host, param)
            parts = param.split('/')
        else:
            parts = param[1:].split('/')
        if len(parts) != 2:
            self.push('550 Not possible.\r\n')
            return
        if parts[0] in EXPOSED.keys():
            self.push('550 Not possible.\r\n')
            return
        if len(read_idx(parts[0])) > 50:
            self.push('552 HostFS file limit exceeded.\r\n')
            return
        if self.data_channel is not None:
            self.data_channel.fd = hostfs_open(parts[0], parts[1], 'w')
            self.push('125 Data channel is already open. Transfer starting.\r\n')
        elif self.dtp_srv is not None:
            self.dtp_srv.fname = (parts[0], parts[1])
            self.push('125 Data channel is already open. Transfer starting.\r\n')
        else:
            self.push('425 Use PASV first.\r\n')
    @auth
    def cmd_DELE(self, param):
        if param[0] != '/':
            param = '%s/%s' % (self.host, param)
            parts = param.split('/')
        else:
            parts = param[1:].split('/')
        if parts[0] in EXPOSED.keys():
            self.push('550 Not possible.\r\n')
            return
        try:
            flist = read_idx(self.host)
            if parts[1] not in flist:
                raise
            flist.remove(parts[1])
            os.unlink(hostfs_file(parts[0], parts[1]))
            write_idx(parts[0], flist)
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
                self.data_channel = None
            if self.dtp_srv is not None:
                self.dtp_srv.close()
                self.dtp_srv = None
            self.handle_close()
    def handle_close(self):
        log.info('Connection closing.')
        if self.data_channel is not None:
            self.data_channel.close()
            self.data_channel = None
        if self.dtp_srv is not None:
            self.dtp_srv.close()
            self.dtp_srv = None
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
