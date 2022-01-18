.export _cgetc
.importzp tmp1

.include "../ioapi.inc"

.proc _cgetc: near
  lda TCNTL
  sta tmp1
  ora #TRAW
  sta TCNTL
  lda CIN
  pha
  lda tmp1
  sta TCNTL
  pla
  rts
.endproc
