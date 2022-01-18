.setcpu "65C02"
.import __JSRTBL__, _shell_init, _save_config, _load_config, _fsave, _fload, _printip, _exec_cmd
.export _print

.include "ioapi.inc"

.macro ptraxy
  php
  phy
  sta ptr
  stx ptr+1
  ldy #0
.endmacro

.rodata

kernel_version:
    .byte "HackerKernel v0.5 $Rev: 305 $", $a,$0

jsr_table:
    .addr _print, _input, _cmpstr, _memclr, _memcpy, $0000

loadedx:
    .byte " driver loaded.", $a,$0

loaderr:
    .byte " failed to load.", $a,$0

fileio:
    .byte "FILEIO.SYS", $0

netdrv:
    .byte "NETDRV.SYS", $0

shellprg:
    .byte "SHELL.SYS", $0

configfile:
    .byte "CONFIG.SYS", $0

shellerr:
    .byte "Failed to load SHELL.SYS!", $a,$0

.zeropage

ptr: .res 2, $00
tbl: .res 1, $00
hdr: .res 2, $00

.code

.proc _export: near
  sta ptr
  stx ptr+1
  lda #<_exec_cmd
  sta $fdfe
  lda #>_exec_cmd
  sta $fdff
  ldx tbl
  ldy #0
: lda #$4c
  sta __JSRTBL__,X
  lda (ptr),Y
  beq :+
  inx
  sta __JSRTBL__,X
  iny
  lda (ptr),Y
  inx
  sta __JSRTBL__,X
  inx
  iny
  bra :-
: lda #0
  sta __JSRTBL__,X
  stx tbl
  rts
.endproc

.proc _print: near
  ptraxy
: lda (ptr),Y
  beq :+
  sta COUT
  iny
  bne :-
: ply
  plp
  rts
.endproc

.proc _input: near
  pha
  phx
  ptraxy
: lda CIN
  cmp #$a
  beq :+
  sta (ptr),Y
  iny
  bne :-
: lda #0
  sta (ptr),Y
  sty $ff
  ply
  plp
  plx
  pla
  rts
.endproc

.proc _cmpstr: near
  pha
  phy
  ldy #0
: lda ($fa),Y
  sta $ff
  lda ($fc),Y
  cmp $ff
  bne :++
  iny
  lda #0
  cmp $ff
  bne :-
  sta $ff
: ply
  pla
  rts
: lda #1
  sta $ff
  bne :--
.endproc

.proc _memclr: near
: sta ($fa),Y
  dey
  bne :-
  sta ($fa),Y
  rts
.endproc

.proc _memcpy: near
: lda ($fa),Y
  sta ($fc),Y
  dey
  bne :-
  lda ($fa),Y
  sta ($fc),Y
  rts
.endproc

.proc _drvload: near
  sta FNAME
  stx FNAME+1
  sty FPAGE+1
  pha
  lda #0
  sta hdr
  sty hdr+1
  lda #$1
  sta FCNTL
  lda FCNTL
  beq :+
  lda #$1f
  sta TFG
  pla
  jsr _print
  lda #<loaderr
  ldx #>loaderr
  jsr _print
  lda #$20
  sta TFG
  lda #1
  rts
: phx
  ldy #5
  lda (hdr),Y
  tax
  dey
  lda (hdr),Y
  dey
  phy
  jsr _export
  ply
  lda (hdr),Y
  tax
  dey
  lda (hdr),Y
  jsr _print
  dey
  lda (hdr),Y
  bne :++
: plx
  pla
  jsr _print
  lda #<loadedx
  ldx #>loadedx
  jsr _print
  rts
: sta $f402
  dey
  lda (hdr),Y
  sta $f401
  lda #$4c
  sta $f400
  jsr $f400
  bra :--
.endproc

.proc _startup: near
  lda #<fileio
  ldx #>fileio
  ldy #$f2
  jsr _drvload
  bne :+
  lda #<configfile
  ldx #>configfile
  jsr _load_config
: lda #<netdrv
  ldx #>netdrv
  ldy #$f3
  jsr _drvload
  lda #<shellprg
  ldx #>shellprg
  ldy #$fc
  jsr _fload
  bne :+
  jmp _shell_init
: lda #<shellerr
  ldx #>shellerr
  jsr _print  
  lda CIN
  brk
.endproc

.segment "STARTUP"

ldx #$FF
txs
cld
lda #0
sta TCNTL
lda #<jsr_table
ldx #>jsr_table
jsr _export
lda #$20
sta $ffd4
lda #<kernel_version
ldx #>kernel_version
jsr $fe00
jmp _startup
