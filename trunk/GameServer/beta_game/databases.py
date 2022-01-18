import xmlrpclib, settings, logging, os

log = logging.getLogger('Databases')

userdb = xmlrpclib.ServerProxy(settings.USERDB_RPC)
hosts = xmlrpclib.ServerProxy(settings.HOSTS_RPC)
forum = xmlrpclib.ServerProxy(settings.FORUM_RPC)

SUPERUSERS = userdb.superusers()

def get_host_dir(ip_addr):
    return 'hosts/%s' % '.'.join(ip_addr.split('.')[:2])

def set_host(ip_addr, data):
    if data.has_key('host_dir'):
        del data['host_dir']
    log.info('Setting host: %s' % ip_addr)
    result = hosts.set_host(ip_addr, data)
    data['host_dir'] = get_host_dir(ip_addr)
    if result == False:
        log.critical('Unable to set host: %s' % ip_addr)
        return False
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
    return True

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
