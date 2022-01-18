#!/usr/bin/python

from beta_game.databases import get_host, set_host, get_host_dir
from beta_game.utils import ipv4
import sys, os

ip_addr = sys.argv[1]
if not ipv4.match(ip_addr):
    print "Invalid IP given."
    sys.exit(1)

host = get_host(ip_addr)
if host != False:
    print "Host already exists."
    sys.exit(1)

data = {'files':['KERNEL.SYS'],
        'acl':{},
        'online':True}

if not set_host(ip_addr, data):
    print ' ** There was an error setting up the host.'
    sys.exit(1)

yn = raw_input('Configure for mail? ')
if yn == 'y':
    print "Configuring for mail..."
    data['mailboxes'] = []
    set_host(ip_addr, data)
    host_dir = get_host_dir(ip_addr)
    mail_dir = '%s/%s/mail' % (host_dir, ip_addr)
    os.mkdir(mail_dir)
    print "Done."
