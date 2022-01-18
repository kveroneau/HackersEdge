.import __IOBASE__
.export _main

.include "kernel.inc"
.include "ioapi.inc"

.rodata

offline:
    .byte "Network offline.", $a,$0

started:
    .byte "Listening on port 23...", $a
    .byte "Press Enter to stop server.", $0

neterr:
    .byte "Unable to bind on port 23.", $a,$0

stoperr:
    .byte "Error trying to stop server.", $a,$0

.zeropage

fd: .res 1,$0

.data

.proc _netin: near
  sei
  lda #65
  sta NETOUT
  lda #NREPLY
  sta NETCNTL
  cli
  rti
.endproc

.code

.proc _chknet: near
  lda NETSEG
  beq :+
  rts
: lda #<offline
  ldx #>offline
  jsr _print
  brk
.endproc

.proc _start: near
  lda #23
  sta NETPORT
  lda #<_netin
  sta NETIRQ
  lda #>_netin
  sta NETIRQ+1
  lda #NLISTEN
  sta NETCNTL
  lda NETCNTL
  bne :+
  lda NETIDX
  sta fd
  rts
: lda #<neterr
  ldx #>neterr
  jsr _print
  brk
.endproc

.proc _stop: near
  lda fd
  sta NETIDX
  lda #NSTOP
  sta NETCNTL
  lda NETCNTL
  bne :+
  brk
: lda #<stoperr
  ldx #>stoperr
  jsr _print
  brk
.endproc

_main: jsr _chknet
       jsr _start
       lda #<started
       ldx #>started
       jsr _print
       lda CIN
       jmp _stop
