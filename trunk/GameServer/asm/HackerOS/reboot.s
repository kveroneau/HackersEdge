.export _main

.include "ioapi.inc"

_main: lda #$79
       sta HEAPI
       brk

