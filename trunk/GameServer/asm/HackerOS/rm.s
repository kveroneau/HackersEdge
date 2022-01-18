.setcpu "65C02"
.import __IOBASE__
.export _main

COUT = __IOBASE__+$d0

.rodata

errormsg:
    .byte "?File not found!", $a,$0

.code

.proc _main: near
  lda $e0
  sta $ff80
  lda $e1
  sta $ff81
  lda #$4
  sta $ff82
  lda $ff82
  beq :+
  lda #<errormsg
  ldx #>errormsg
  jsr $fe00
: brk
.endproc
