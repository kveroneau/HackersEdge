.setcpu "65C02"
.import __IOBASE__
.export _main

.include "kernel.inc"
.include "ioapi.inc"

.rodata

intro:
    .byte "HackerKernel API Unittest.", $a,$0

itest:
    .byte "Input test? ", $0

str1:
    .byte "String1", $0

str2:
    .byte "String1", $0

str3:
    .byte "String2", $0

rok:
    .byte " Passed.", $a,$0

rfail:
    .byte " Failed.", $a,$0

cmpstr:
    .byte "_cmpstr", $0

memcpy:
    .byte "_memcpy", $0

memclr:
    .byte "_memclr", $0

.bss

buffer: .res 40,$0

.code

.proc _saypass: near
  jsr _print
  lda #<rok
  ldx #>rok
  jmp _print
.endproc

.proc _sayfail: near
  jsr _print
  lda #<rfail
  ldx #>rfail
  jmp _print
.endproc

.proc _doprint: near
  lda #<intro
  ldx #>intro
  jmp _print
.endproc

.proc _doinput: near
  lda #<itest
  ldx #>itest
  jsr _print
  lda #<buffer
  ldx #>buffer
  jsr _input
  jsr _print
  lda #'*'
  sta COUT
  lda #$a
  sta COUT
  rts
.endproc

.proc _docmpstr: near
  lda #<str1
  sta PARAM1
  lda #>str1
  sta PARAM1+1
  lda #<str2
  sta PARAM2
  lda #>str2
  sta PARAM2+1
  jsr _cmpstr
  lda RESULT
  beq :++
: lda #<cmpstr
  ldx #>cmpstr
  jmp _sayfail
: lda #<str3
  sta PARAM2
  lda #>str3
  sta PARAM2+1
  jsr _cmpstr
  lda RESULT
  beq :--
  lda #<cmpstr
  ldx #>cmpstr
  jmp _saypass
.endproc

.proc _domemcpy: near
  lda #0
  sta PARAM1
  sta PARAM2
  lda #$8
  sta PARAM1+1
  lda #$50
  sta PARAM2+1
  ldy #$80
  jsr _memcpy
  ldy #$80
: lda (PARAM1),Y
  sta $ff
  lda (PARAM2),Y
  cmp $ff
  bne :+
  dey
  bne :-
  lda #<memcpy
  ldx #>memcpy
  jmp _saypass
: lda #<memcpy
  ldx #>memcpy
  jmp _sayfail
.endproc

.proc _domemclr: near
  lda #0
  sta PARAM1
  lda #$50
  sta PARAM1+1
  lda #0
  ldy #$80
  jsr _memclr
  ldy #$80
: lda (PARAM1),Y
  bne :+
  dey
  bne :-
  lda #<memclr
  ldx #>memclr
  jmp _saypass
: lda #<memclr
  ldx #>memclr
  jmp _sayfail
.endproc

_main: jsr _doprint
       jsr _doinput
       jsr _docmpstr
       jsr _domemcpy
       jsr _domemclr
       brk
