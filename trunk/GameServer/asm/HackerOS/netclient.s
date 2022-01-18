.setcpu "65C02"
.import __IOBASE__
.export _main

.include "kernel.inc"
.include "ioapi.inc"

.rodata

connecting:
    .byte "Connecting to 49.67.30.3:23...", $a,$0

neterr:
    .byte "Unable to connect to port 23.", $a,$0

discoerr:
    .byte "Error trying to disconnect.", $a,$0

ipaddr:
    .byte 49,67,30,3,$0

sendthis:
    .byte "Hello Network!",$0

.zeropage

fd:  .res 1, $0
ptr: .res 2, $0

.data

.proc _netin: near
  sei
  pha
: lda NETOUT
  beq :+
  sta COUT
  bne :-
: lda #$a
  sta COUT
  pla
  cli
  rti
.endproc

.code

.proc _start: near
  lda #<_netin
  ldx #>_netin
  sta PARAM1
  stx PARAM1+1
  lda #<ipaddr
  ldx #>ipaddr
  ldy #23
  jsr _connect
  bne :+
  lda NETIDX
  sta fd
  rts
: lda #<neterr
  ldx #>neterr
  jsr _print
  brk
.endproc

.proc _senddata: near
  ldy #0
: lda sendthis,Y
  beq :+
  sta NETOUT
  iny
  bne :-
: lda #NSEND
  sta NETCNTL
.endproc

.proc _disconnect: near
  lda fd
  sta NETIDX
  lda #NSTOP
  sta NETCNTL
  lda NETCNTL
  bne :+
  brk
: lda #<discoerr
  ldx #>discoerr
  jsr _print
  brk
.endproc

_main: lda #<connecting
       ldx #>connecting
       jsr _print
       jsr _start
       jsr _senddata
       lda CIN
       jsr _disconnect
