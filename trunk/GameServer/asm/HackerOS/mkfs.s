.export _main

.rodata

format_msg:
    .byte "Formatting file system, please wait...", $a,$0

.code

_main: lda #<format_msg
       ldx #>format_msg
       jsr $fe00
       lda #$6
       sta $ff82
       brk
