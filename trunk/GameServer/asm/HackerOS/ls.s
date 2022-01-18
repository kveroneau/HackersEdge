.export _main

.bss

flist: .res 200, $00

.rodata

file_count:
    .byte " files.",$a,$0

.code

.proc _list_files: near
  ldx #0
: lda flist, X
  beq :+
  sta $ffd0
  inx
  bne :-
: lda #$a
  sta $ffd0
  dey
  beq :+
  inx
  bne :--
: brk
.endproc

.proc _main: near
  lda #<flist
  sta $ff83
  lda #>flist
  sta $ff84
  lda #$5
  sta $ff82
  ldy flist
  sty $ffd1
  lda #<file_count
  ldx #>file_count
  jsr $fe00
  jmp _list_files
.endproc
