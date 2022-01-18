.include "ioapi.inc"
.export _main

.code

_main: lda #'H'
       sta ANSI
       lda #'J'
       sta ANSI
       brk
