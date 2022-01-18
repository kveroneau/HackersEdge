.import __IOBASE__
.export _print, _input, _ptrzp, _strcmp, _lf, _copytbl, _lookuptbl
.exportzp ptr1, ptr2

COUT = __IOBASE__+$d0
CIN = __IOBASE__+$e0

.macro ptraxy
  sta ptr1
  stx ptr1+1
  ldy #0
.endmacro

.zeropage

ptr1: .res 2, $00
ptr2: .res 2, $00
tmp1: .res 1, $00

.code

.proc _print: near
  ptraxy
: lda (ptr1),Y
  beq :+
  sta COUT
  iny
  bne :-
: rts
.endproc

.proc _input: near
  ptraxy
: lda CIN
  cmp #$a
  beq :+
  sta (ptr1),Y
  iny
  bne :-
: lda #0
  sta (ptr1),Y
  rts
.endproc

.proc _ptrzp: near
  sta $00,X
  inx
  sty $00,X
  dex
  rts
.endproc

.proc _strcmp: near
  ldy #0
: lda (ptr2),Y
  cmp (ptr1),Y
  bne :+
  lda #0
  cmp (ptr1),Y
  beq :+
  iny
  bne :-
: rts
.endproc

_lf: pha
     lda #$a
     sta COUT
     pla
     rts

.proc _copytbl: near
  sta ptr1
  stx ptr1+1
  dey
  sty ptr2
  ldy #0
  sty ptr2+1
  lda (ptr1),Y
  tay
: lda (ptr1),Y
  sta (ptr2),Y
  beq :+
  dey
  bne :-
: rts
.endproc

.proc _lookuptbl: near
  ldx #0
: lda $10,X
  beq :+
  sta ptr2
  inx
  lda $10,X
  sta ptr2+1
  jsr _strcmp
  beq :++
  inx
  bne :-
: ldx #$ff
: dex
  rts
.endproc
