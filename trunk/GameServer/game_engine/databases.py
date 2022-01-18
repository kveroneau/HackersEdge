import settings, logging, os, redis
from asynchttp import HTTPClient
import cPickle as pickle

log = logging.getLogger('Databases')

r = redis.Redis(db=1)

def userdb(owner, *syscall):
    return HTTPClient(owner, settings.USERDB_RPC, chr(0).join(syscall))

def site_ping(owner):
    return userdb(owner, 'ping')

def get_user(owner, username):
    return userdb(owner, 'user', username)

def get_last_login(owner, username):
    return userdb(owner, 'last_login', username)

def hosts(owner, *syscall):
    return HTTPClient(owner, settings.HOSTS_RPC, chr(0).join(syscall))

def get_host_dir(ip_addr):
    return 'hosts/%s' % '.'.join(ip_addr.split('.')[:2])

def set_host(owner, ip_addr, data):
    if data.has_key('host_dir'):
        del data['host_dir']
    log.info('Setting host: %s' % ip_addr)
    result = hosts(owner, 'set_host', ip_addr, pickle.dumps(data))
    data['host_dir'] = get_host_dir(ip_addr)
    host_dir = get_host_dir(ip_addr)
    try:
        os.mkdir(host_dir)
        log.info('Created host directory %s' % host_dir)
    except OSError:
        pass
    try:
        os.mkdir('%s/%s' % (host_dir, ip_addr))
        log.info('Created host directory of %s/%s' % (host_dir, ip_addr))
    except OSError:
        pass
    if data.has_key('files'):
        try:
            os.mkdir('%s/%s/files' % (host_dir, ip_addr))
            log.info('Created host directory for file storage for %s' % ip_addr)
        except OSError:
            pass
    return result

def get_host(ip_addr):
    data = hosts.get_host(ip_addr)
    if data == False:
        return False
    host_dir = get_host_dir(ip_addr)
    data.update({'host_dir':host_dir})
    if not os.path.exists(host_dir):
        os.mkdir(host_dir)
        log.info('Created host directory %s' % host_dir)
    if not os.path.exists('%s/%s' % (host_dir, ip_addr)):
        os.mkdir('%s/%s' % (host_dir, ip_addr))
        log.info('Created host directory of %s/%s' % (host_dir, ip_addr))
    if data.has_key('files') and not os.path.exists('%s/%s/files' % (host_dir, ip_addr)):
        os.mkdir('%s/%s/files' % (host_dir, ip_addr))
        log.info('Created host directory for file storage for %s' % ip_addr)
    return data

def handle_return(rt):
    print rt
    if rt is None:
        return None
    if rt[1] == 'OK':
        return True
    else:
        return False

def cc65():
    r.rpush('CC', 'test')
    return handle_return(r.blpop('test', 5))

def ca65():
    log.debug('Calling ca65()...')
    r.rpush('ASM', 'test')
    log.debug('Pushed...')
    return handle_return(r.blpop('test', 5))

