#!/usr/bin/python

import os, sys, zipfile, hashlib

host = sys.argv[1]
host_dir = 'hosts/%s/%s/files' % ('.'.join(host.split('.')[:2]), host)
osimage = sys.argv[2]

if not os.path.exists(host_dir):
    print "Host does not exist or does not have a hostfs available."
    sys.exit(1)

print " * Generating OSImage %s.img from host %s..." % (osimage, host)
print "Host dir: %s" % host_dir
print "Reading in index file..."
try:
    idx = open('%s/idx' % host_dir, 'rb').read().split(chr(255))
except:
    print "Host does not have any files!"
    sys.exit(2)

zf = zipfile.ZipFile('osimages/%s.img' % osimage, 'w')
for fname in idx:
    if fname == '':
        continue
    print " * Writing %s..." % fname
    hname = '%s/%s' % (host_dir, hashlib.md5(fname).hexdigest())
    zf.write(hname, fname)
zf.close()

print " * Process complete!"
