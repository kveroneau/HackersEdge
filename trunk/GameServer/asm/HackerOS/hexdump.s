.export _main

.include "ioapi.inc"
.include "kernel.inc"

.proc _main: near
  lda ARGS
  sta FNAME
  lda ARGS+1
  sta FNAME+1
  lda #$80
  sta FCNTL
  brk
.endproc
