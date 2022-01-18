.import __IOBASE__

.include "ioapi.inc"

_print = $fe00

.rodata

kernelfile:
    .byte "KERNEL.SYS", $0

bootmsg:
    .byte "Loading KERNEL.SYS...", $a,$0

booterr:
    .byte "Boot Error, cannot load KERNEL.SYS!", $a
    .byte "Press Enter to halt...", $0

prompt:
    .byte "BOOT>", $0

.code

.proc _bootkern: near
  lda #$f0
  sta $ff84
  lda #<kernelfile
  sta $ff80
  lda #>kernelfile
  sta $ff81
  lda #$1
  sta $ff82
  lda $ff82
  bne :+
  lda #<bootmsg
  ldx #>bootmsg
  jsr _print
  lda $ff1a
  and #$df
  sta $ff1a
  jmp $f000
: lda #<booterr
  ldx #>booterr
  jsr _print
  lda CIN
  brk
.endproc

.segment "STARTUP"

  lda TCNTL
  ora #TRAW
  sta TCNTL
  lda #<prompt
  ldx #>prompt
  jsr _print
: lda CIN
  cmp #$a
  bne :-
  jmp _bootkern
