from databases import set_host, get_host, get_host_dir, hosts
import hashlib, os, shutil, shelve, datetime
from cStringIO import StringIO
from ConfigParser import SafeConfigParser

def exists(path):
    try:
        os.stat(path)
        return True
    except:
        return False

def get_file(filename, create=False, delete=False):
    ip_addr, realfile = filename.split(':')
    host = get_host(ip_addr)
    if host == False:
        raise IOError('Host could not be found.')
    if not host.has_key('files'):
        raise IOError('File storage not available on host.')
    if host.has_key('hide') and realfile in host['hide']:
        pass
    elif realfile not in host['files']:
        if not create:
            raise IOError('File not found: %s' % realfile)
        host['files'].append(realfile)
        if not set_host(ip_addr, host):
            raise IOError('Unable to create file on host.')
    if delete:
        host['files'].remove(realfile)
        if not set_host(ip_addr, host):
            raise IOError('Unable to delete file on host.')
    dst_dir = '%s/%s/files' % (host['host_dir'], ip_addr)
    fname = realfile.split('/')[-1]
    return '%s/%s' % (dst_dir, hashlib.md5(fname).hexdigest())    

def open_file(filename, mode):
    if 'r' in mode:
        fname = get_file(filename)
        if not exists(fname):
            raise IOError('File not found: %s' % filename)
    else:
        fname = get_file(filename, True)
    if 'a'in mode and not exists(fname):
        mode = 'w'
    return open(fname, mode)

def copy_file(src, dest):
    sfile = get_file(src)
    if ':' not in dest:
        dest+=':%s' % src.split(':')[1]
    dfile = get_file(dest, True)
    shutil.copyfile(sfile, dfile)
    return True

def delete_file(filename):
    fname = get_file(filename, delete=True)
    try:
        os.unlink(fname)
    except:
        pass
    return True

def queryx_dns(dns_server, hostname):
    host = get_host(dns_server)
    if host == False:
        raise IOError('Unable to contact host.')
    try:
        dns = shelve.open('%s/%s/dns' % (host['host_dir'], dns_server), 'r')
        ip_addr = dns[hostname]
        dns.close()
        return ip_addr
    except:
        return False

def query_dns(dns_server, hostname):
    from sessions import hypervisor
    host = hypervisor.get_host(dns_server)
    if host == False:
        raise IOError('Unable to contact host.')
    if not host['online']:
        raise IOError('Unable to contact host.')
    if 'nettbl' not in host.keys():
        raise IOError('Unable to contact host.')
    addr = None
    for e in host['nettbl']:
        if e['type'] == 1 and e['port'] == 53:
            addr = e['addr']
    if not addr:
        raise IOError('Connection refused to port 53.')
    sid = hypervisor.get_vm(dns_server)
    #hypervisor.exec_isr(sid, addr)
    dns = StringIO(hypervisor.get_page(sid, addr))
    dns.read(addr & 0xff)
    entries = ord(dns.read(1))
    result = False
    for x in range(0,entries):
        elen = ord(dns.read(1))
        entry = dns.read(elen)
        try:
            name, ip_addr = entry.split(':')
            if hostname == name:
                result = ip_addr
        except:
            pass
    if sid.startswith('tmp-'):
        hypervisor.destroy(sid)
    return result

def setup_dns(dns_server, fname):
    from sessions import hypervisor
    host = hypervisor.get_host(dns_server)
    if host == False:
        raise IOError('Unable to contact host.')
    if not host.has_key('nettbl'):
        raise IOError('Network stack not enabled on host.')
    dnsdb = '%s/%s/dns' % (host['host_dir'], dns_server)
    try:
        os.unlink(dnsdb)
    except:
        pass
    addr = 0xa00
    sid = hypervisor.get_vm(dns_server)
    buf = ''
    try:
        entry_list = open_file('%s:%s' % (dns_server,fname), 'r').read().split('\n')
        buf+=chr(len(entry_list))
        for entry in entry_list:
            buf+=chr(len(entry))+entry
        hypervisor.set_page(sid, addr, buf)
        hd = hypervisor.host_data(sid)
        srv = {'type':1, 'addr':addr, 'port':53, 'contbl':[]}
        hd['nettbl'].append(srv)
        hypervisor.set_host(sid)
        if sid.startswith('tmp-'):
            hypervisor.destroy(sid)
        return True
    except:
        raise

def setupx_dns(dns_server, fname):
    host = get_host(dns_server)
    if host == False:
        raise IOError('Unable to contact host.')
    dnsdb = '%s/%s/dns' % (host['host_dir'], dns_server)
    try:
        os.unlink(dnsdb)
    except:
        pass
    try:
        entry_list = open_file('%s:%s' % (dns_server,fname), 'r').readlines()
        dns = shelve.open(dnsdb)
        for entry in entry_list:
            hostname, ip_addr = entry.split(':')
            dns[hostname] = ip_addr.replace('\n','')
        dns.close()
        return True
    except:
        raise

def logit(ip_addr, msg):
    open_file('%s:log.txt' % ip_addr, 'a').write('[%s] %s\n' % (datetime.datetime.now(), msg))

def setup_user(username, ip_addr, mail_host):
    try:
        data = get_host(ip_addr)
        set_host(ip_addr, data)
        for f in ['BOOT.SYS','KERNEL.SYS','FILEIO.SYS','NETDRV.SYS','readme.txt']:
            copy_file('96.164.6.147:%s' % f, ip_addr)
        mail_dir = '%s/%s/mail' % (get_host_dir(mail_host), mail_host)
        open('%s/%s.new' % (mail_dir, username), 'w').write('')
        open('%s/%s' % (mail_dir, username), 'w').write('')
        mh = get_host(mail_host)
        mh['mailboxes'].append(username)
        set_host(mail_host, mh)
        return True
    except:
        return False

def provision_host(ip_addr, slug):
    ini = hosts.get_template(slug)
    fp = StringIO(ini)
    cfg = SafeConfigParser()
    cfg.readfp(fp, 'host.ini')
    fp.close()
    del fp
    