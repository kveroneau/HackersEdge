.export _main

.include "kernel.inc"
.include "ioapi.inc"

.rodata

basicsys:
    .byte "BASIC.SYS", $0

cffa1_load:
    .byte "Enabling CFFA1 firmware...", $a,$0

err_str:
    .byte "Cannot locate ",$0

.code

_main: lda #$50
       sta FPAGE+1
       lda #<basicsys
       sta FNAME
       lda #>basicsys
       sta FNAME+1
       lda #$1
       sta FCNTL
       lda FCNTL
       bne load_error
       lda ROMFLAG
       and #$df
       sta ROMFLAG
       lda #<cffa1_load
       ldx #>cffa1_load
       jsr _print
       lda CFFA1
       ora #$20
       sta CFFA1
       jmp $5000
load_error:
       lda #<err_str
       ldx #>err_str
       jsr _print
       lda #<basicsys
       ldx #>basicsys
       jsr _print
       lda #$a
       sta COUT
       brk
