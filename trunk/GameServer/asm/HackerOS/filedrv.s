.setcpu "65C02"
.import netdrv_flag, _print
.export _fload, _fsave, _load_config, _save_config

.include "ioapi.inc"

.segment "FILEDRV"

fileio_header:
    .addr $0000,fileio_version,jsr_tbl

jsr_tbl:
    .addr _fload, _fsave, _load_config, _save_config, $0000

fileio_version:
    .byte "HackerFileIO v0.2 $Rev: 304 $", $a,$0

.proc _fload: near
  sta FNAME
  stx FNAME+1
  sty FPAGE+1
  lda #FREAD
  sta FCNTL
  lda FCNTL
  rts
.endproc

.proc _fsave: near
  sta FSIZE
  stx FSIZE+1
  sty FPAGE+1
  pla
  plx
  sta FNAME
  stx FNAME+1
  lda #FWRITE
  sta FCNTL
  rts
.endproc

.proc _load_config: near
  ldy #$f5
  jsr _fload
  bne :+
  lda $f500
  sta netdrv_flag
: rts
.endproc

.proc _save_config: near
  phx
  pha
  lda netdrv_flag
  sta $f500
  lda #$20
  ldx #$0
  ldy #$f5
  jsr _fsave
  rts
.endproc
