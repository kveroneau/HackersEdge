.setcpu "65C02"

.export _listen
.export _netclose
.export _netreply
.export _netsend
.export _netseg
.export _connect
.export _netrecv
.export _aton
.export _ntoa
.import popa, popax
.importzp ptr1

.include "../ioapi.inc"

.proc netconv: near
  sta HEPTR2
  stx HEPTR2+1
  jsr popax
  sta HEPTR1
  stx HEPTR1+1
  rts
.endproc

.proc _aton: near
  jsr netconv
  lda #HEATON
  sta HEAPI
  lda HEAPI
  rts
.endproc

.proc _ntoa: near
  jsr netconv
  lda #HENTOA
  sta HEAPI
  lda HEAPI
  rts
.endproc

.proc _netseg: near
  lda NETSEG
  rts
.endproc

.proc _listen: near
  sta NETIRQ
  stx NETIRQ+1
  jsr popa
  sta NETPORT
  lda #NLISTEN
  sta NETCNTL
  lda NETCNTL
  bne :+
  ldx NETIDX
  inx
  txa
  rts
: lda #0
  rts
.endproc

.proc _netclose: near
  sta NETIDX
  dec NETIDX
  lda #NSTOP
  sta NETCNTL
  lda NETCNTL
  rts
.endproc

.proc bufferdata: near
  sta ptr1
  stx ptr1+1
  phy
  ldy #0
: lda (ptr1),Y
  beq :+
  sta NETOUT
  iny
  bra :-
: ply
  rts
.endproc

.proc _netreply: near
  jsr bufferdata
  lda #NREPLY
  sta NETCNTL
  rts
.endproc

.proc _netsend: near
  jsr bufferdata
  jsr popa
  sta NETIDX
  dec NETIDX
  lda #NSEND
  sta NETCNTL
  rts
.endproc

.proc _connect: near
  sta NETIRQ
  stx NETIRQ+1
  jsr popa
  sta NETPORT
  jsr popax
  sta NETIP
  stx NETIP+1
  lda #NCONN
  sta NETCNTL
  lda NETCNTL
  bne :+
  ldx NETIDX
  inx
  txa
  rts
: lda #0
  rts
.endproc

.proc _netrecv: near
  sta ptr1
  stx ptr1+1
  jsr popa
  sta NETIDX
  dec NETIDX
  phy
  ldy #0
: lda NETOUT
  sta (ptr1),Y
  beq :+
  iny
  bra :-
: tya
  ldx #0
  ply
  rts
.endproc

