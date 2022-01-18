.export _main

.include "kernel.inc"

.rodata

helpcmd:
    .byte "cat.bin", $0
    .byte "readme.txt", $0

.code

_main: lda #<helpcmd
       ldx #>helpcmd
       sta $fa
       stx $fb
       lda #0
       ldx #$fd
       sta $fc
       stx $fd
       ldy #19
       jsr _memcpy
       lda #8
       sta $e0
       stx $e1
       lda #0
       jmp ($fdfe)
