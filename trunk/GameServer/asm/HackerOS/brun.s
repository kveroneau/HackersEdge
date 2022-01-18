.export _main

.include "ioapi.inc"
.include "kernel.inc"

.rodata

helpmsg:
    .byte "Usage: brun 1a00",$a,$0

R: .byte "R",$0

.code

.proc _main: near
  lda ARGS
  bne :+
  lda #<helpmsg
  ldx #>helpmsg
  jsr _print
  brk
: sta HEPTR1
  lda ARGS+1
  sta HEPTR1+1
  lda #HEMON
  sta HEAPI
  lda HEAPI
  lda #<R
  sta HEPTR1
  lda #>R
  sta HEPTR1+1
  lda HEAPI
  jmp (HEPTR2)
.endproc

