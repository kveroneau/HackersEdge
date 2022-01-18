.setcpu "65C02"
.export _shell_init, _exec_cmd

.include "kernel.inc"
.include "ioapi.inc"

.segment "SHELL_DATA"

cmd: .res 40, $00
param: .res 40, $00

.segment "SHELL"

shell_version:
    .byte "HackerShell v0.3 $Rev: 293 $", $a,$0

shell_error:
    .byte "?Command not found.", $a,$0

shell_prompt:
    .byte "$ ", $0

bin_type:
    .byte ".bin", $0

ctrl_c:
    .byte "^C", $a,$0

.proc _shell_init: near
  lda #<shell_version
  ldx #>shell_version
  jsr _print
  lda #<_brk_handle
  sta $fffe
  lda #>_brk_handle
  sta $ffff
  jmp _shell_parser
.endproc

.proc _append_typ: near
  pha
  phx
  ldx #0
: lda bin_type,X
  sta cmd,Y
  beq :+
  inx
  iny
  bne :-
: plx
  pla
  rts
.endproc

.proc _brk_handle: near
  pla
  and #$10
  bne :+
  lda #<ctrl_c
  ldx #>ctrl_c
  jsr _print
: ldx #$FF
  txs
  cld
  lda #$0
  sta TCNTL
.endproc

.proc _shell_parser: near
  lda $ff70
  beq :+
  ldy #0
  jsr _printip
: lda #<shell_prompt
  ldx #>shell_prompt
  jsr _print
  lda #<cmd
  ldx #>cmd
  jsr _input
  ldy $ff
  beq _shell_parser
  jsr _split_cmd
  jsr _append_typ
.endproc

.proc _exec_cmd: near
  ldy #$8
  jsr _fload
  bne :+
  jsr _ds_move
  jmp ($800)
: lda #<shell_error
  ldx #>shell_error
  jsr _print
  jmp _shell_parser
.endproc

.proc _ds_move: near
  ldy $802
  beq :+++
  ldx #0
: lda $804,X
  sta $fa,X
  inx
  cpx #5
  beq :+
  bne :-
: jmp _memcpy
: rts
.endproc

.proc _split_cmd: near
  phx
  ldy #0
  ldx #0
  stx $e0
: lda cmd,Y
  beq :+++
  cmp #$20
  beq :+
  iny
  bra :-
: lda #0
  sta cmd,Y
  sty $ff
  lda #<param
  sta $e0
  lda #>param
  sta $e1
: iny
  lda cmd,Y
  sta param,X
  beq :+
  inx
  bne :-
: ldy $ff
  plx
  rts
.endproc
