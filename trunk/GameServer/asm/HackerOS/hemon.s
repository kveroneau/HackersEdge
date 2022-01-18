.setcpu "65C02"
.import __IOBASE__
.export _main

COUT = __IOBASE__+$d0
CIN = __IOBASE__+$e0

.rodata

hemon_version:
    .byte "HackerMon v0.1 $Rev$", $a,$0

syntax_error:
    .byte "?SYNTAX ERROR", $a,$0

.bss

buffer: .res 40, $00

.code

.proc _hemon: near
  lda #<buffer
  sta $fff0
  lda #>buffer
  sta $fff1
  lda #$30
  sta $fff2
: lda #'@'
  sta COUT
  ldy #0
: lda CIN
  cmp #$a
  beq :+
  sta buffer,Y
  iny
  bra :-
: lda #0
  sta buffer,Y
  lda $fff2
  bne :+
  beq :---
: bpl :+
  lda #<syntax_error
  ldx #>syntax_error
  jsr $fe00
  bra :----
: jmp ($fff3)
.endproc

_main:
  lda #<hemon_version
  ldx #>hemon_version
  jsr $fe00
  jmp _hemon
