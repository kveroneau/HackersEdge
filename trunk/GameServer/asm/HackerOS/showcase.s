.import __IOBASE__
.export _main

.include "kernel.inc"

KBDFLAGS = __IOBASE__+$dc
COUT = __IOBASE__+$d0
CIN = __IOBASE__+$e0
MIRQ = __IOBASE__+$dd
MBUT = __IOBASE__+$d9
MCOL = __IOBASE__+$da
MROW = __IOBASE__+$db
COL = __IOBASE__+$d7
ROW = __IOBASE__+$d6

.rodata

welcome:
    .byte "Keyboard test program!", $a,$0

mask_input:
    .byte "Masked input: ", $0

getc_input:
    .byte "Char input test!",$a
    .byte "Do you like this [Y/N]?",$0

mouse_test:
    .byte "Mouse test!",$a
    .byte "Click anywhere to see where the mouse is!",$a
    .byte "Press ESC to stop.",$a,$0

getc_yes:
    .byte $a,"Great to hear!",$a,$0

getc_no:
    .byte $a,"Please provide feedback on the forums.",$a,$0

.zeropage

ptr: .res 2, $00

.code

.proc _mask_test: near
  lda KBDFLAGS
  ora #$10
  sta KBDFLAGS
  lda #<mask_input
  ldx #>mask_input
  jsr _print
: lda CIN
  cmp #$a
  beq :+
  bne :-
: jmp _return
.endproc

.proc _getc_test: near
  lda KBDFLAGS
  ora #$20
  sta KBDFLAGS
  lda #<getc_input
  ldx #>getc_input
  jsr _print
: lda CIN
  cmp #'Y'
  beq :+
  cmp #'N'
  beq :+++
  bne :-
: lda #<getc_yes
  ldx #>getc_yes
: jsr _print
  jmp _return
: lda #<getc_no
  ldx #>getc_no
  bne :--
.endproc

.proc _mouse_test: near
  lda #<mouse_irq
  sta MIRQ
  lda #>mouse_irq
  sta MIRQ+1
  lda KBDFLAGS
  ora #($20 | $40)
  sta KBDFLAGS
  lda #<mouse_test
  ldx #>mouse_test
  jsr _print
: lda CIN
  cmp #$1b
  beq :+
  bne :-
: jmp _return
.endproc

.proc mouse_irq: near
  sei
  lda MROW
  sta ROW
  lda MCOL
  sta COL
  lda #'X'
  sta COUT
  cli
  rti
.endproc

.proc _welcome: near
  lda #'H'
  sta $ffd3
  lda #'J'
  sta $ffd3
  lda #<welcome
  ldx #>welcome
  jsr _print
  rts
.endproc

.proc _return: near
  lda #0
  sta KBDFLAGS
  rts
.endproc

_main: jsr _welcome
       jsr _mask_test
       jsr _getc_test
       jsr _mouse_test
       brk
