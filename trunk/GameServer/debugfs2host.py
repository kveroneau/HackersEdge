#!/usr/bin/python

import os, hashlib, sys, shutil

host = sys.argv[1]
host_dir = 'hosts/%s/%s/files' % ('.'.join(host.split('.')[:2]), host)

if not os.path.exists(host_dir):
    print "Host does not exist or does not have a hostfs available."
    sys.exit(1)

print "Host dir: %s" % host_dir
print "Reading in index file..."
try:
    idx = open('%s/idx' % host_dir, 'rb').read().split(chr(255))
except:
    idx = []

DEBUGFS = '/tmp/debugfs'

for fname in os.listdir(DEBUGFS):
    print "Copying %s..." % fname
    shutil.copy('%s/%s' % (DEBUGFS, fname), '%s/%s' % (host_dir, hashlib.md5(fname).hexdigest()))
    if fname not in idx:
        idx.append(fname)

print "Writing index file..."
open('%s/idx' % host_dir, 'wb').write(chr(255).join(idx))

print "Operation complete."
