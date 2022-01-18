.export _load_file, _save_file
.import popax

.include "../ioapi.inc"

.proc _load_file: near
  sta FPAGE
  stx FPAGE+1
  jsr popax
  sta FNAME
  stx FNAME+1
  lda #FREAD
  sta FCNTL
  lda FCNTL
  bne :+
  lda FSIZE
  ldx FSIZE+1
  rts
: lda #0
  tax
  rts
.endproc

.proc _save_file: near
  sta FSIZE
  stx FSIZE+1
  jsr popax
  sta FPAGE
  stx FPAGE+1
  jsr popax
  sta FNAME
  stx FNAME+1
  lda #FWRITE
  sta FCNTL
  lda FCNTL
  tax
  rts
.endproc

