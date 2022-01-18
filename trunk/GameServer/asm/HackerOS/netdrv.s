.setcpu "65C02"
.import _print
.export _printip, netdrv_flag

.include "ioapi.inc"

PARAM1 = $fa

.zeropage

tmp: .res 1,$0

.segment "NETDRV"

netdrv_header:
    .addr _netdrv_init,netdrv_version,jsr_tbl

netdrv_flag:
    .res 1,$00

jsr_tbl:
    .addr _printip, _listen, _stopserver, _connect, $0000

netdrv_version:
    .byte "HackerNetDrv v0.3 $Rev: 306 $", $a,$0

ip_str:
    .byte "IP: ", $0

offline:
    .byte "Network offline.", $a,$0

.proc _printip: near
  pha
  phx
  ldx #46
: lda $e000,Y
  sta NOUT
  cpy #$03
  beq :+
  stx COUT
  iny
  bne :-
: plx
  pla
  rts
.endproc

.proc _chknet: near
  sta tmp
  lda NETSEG
  beq :+
  lda #0
  rts
: lda netdrv_flag
  and #$1
  bne :+
  lda #<offline
  ldx #>offline
  jsr _print
: rts
.endproc

.proc _listen: near
  jsr _chknet
  beq :+
  rts
: lda tmp
  sty NETPORT
  sta NETIRQ
  stx NETIRQ+1
  lda #NLISTEN
  sta NETCNTL
  lda NETCNTL
  rts
.endproc

.proc _stopserver: near
  sta NETIDX
  lda #NSTOP
  sta NETCNTL
  lda NETCNTL
  rts
.endproc

.proc _connect: near
  jsr _chknet
  beq :+
  rts
: lda tmp
  sta NETIP
  stx NETIP+1
  sty NETPORT
  lda PARAM1
  ldx PARAM1+1
  sta NETIRQ
  stx NETIRQ+1
  lda #NCONN
  sta NETCNTL
  lda NETCNTL
  rts
.endproc

.proc _netdrv_init: near
  lda netdrv_flag
  and #$2
  bne :+
  lda #$e0
  sta NETSEG
  lda #<ip_str
  ldx #>ip_str
  jsr _print
  ldy #0
  jsr _printip
  lda #$a
  sta COUT
: rts
.endproc
