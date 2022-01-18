#!/bin/env python

from intelhex import IntelHex
import sys

h = IntelHex()
h.loadbin(sys.argv[2],offset=int(sys.argv[1], 16))
h.tofile('output.hex',format='hex')
