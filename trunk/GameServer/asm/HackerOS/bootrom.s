.import __IOBASE__

COUT = __IOBASE__+$d0
CIN = __IOBASE__+$e0

.rodata

bootfile:
    .byte "BOOT.SYS", $0

welcomemsg:
    .byte "Hacker's Edge BootROM v0.1", $a,$0

booterr:
    .byte "Boot Error, cannot load BOOT.SYS!", $a
    .byte "Press Enter to halt...", $0

bootmsg:
    .byte "Loading BOOT.SYS...", $a,$0

.zeropage

ptr: .res 2, $00

.code

.proc _bootsys: near
  lda #$0
  sta $ff8a
  sta $ff83
  lda #$8
  sta $ff84
  lda #<bootfile
  sta $ff80
  lda #>bootfile
  sta $ff81
  lda #$1
  sta $ff82
  lda $ff82
  bne :+
  lda #<bootmsg
  ldx #>bootmsg
  jsr _print
  jmp $800
: lda #<booterr
  ldx #>booterr
  jsr _print
  lda CIN
  brk
.endproc

.proc _print: near
  sta ptr
  stx ptr+1
  ldy #0
: lda (ptr),Y
  beq :+
  sta COUT
  iny
  bne :-
: rts
.endproc

.proc _export: near
  lda #$4c
  sta $fe00
  lda #<_print
  sta $fe01
  lda #>_print
  sta $fe02
  rts
.endproc

.segment "STARTUP"

ldx #$FF
txs
cld
lda #<welcomemsg
ldx #>welcomemsg
jsr _print
jsr _export
jmp _bootsys
