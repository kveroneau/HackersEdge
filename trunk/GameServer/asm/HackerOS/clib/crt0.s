.export _init, _exit
.import _main

.export __STARTUP__ : absolute = 1
.import __HEAP_START__, __HEAP_SIZE__, __DATA_SIZE__, __DATA_LOAD__, __DATA_RUN__

.import zerobss, initlib, donelib

.include "zeropage.inc"

.segment "HEADER"

.addr _init, __DATA_SIZE__, __DATA_LOAD__, __DATA_RUN__

.segment "STARTUP"

_init:  lda #<(__HEAP_START__ + __HEAP_SIZE__)
        sta sp
        lda #>(__HEAP_START__ + __HEAP_SIZE__)
        sta sp+1
        
        jsr zerobss
        jsr initlib
        jsr _main

_exit:  jsr donelib
        brk
