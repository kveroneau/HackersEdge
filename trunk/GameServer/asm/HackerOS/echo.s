.import __IOBASE__
.export _main

COUT = __IOBASE__+$d0

.proc _main: near
  lda $e0
  ldx $e1
  jsr $fe00
  lda #$a
  sta COUT
  brk
.endproc
