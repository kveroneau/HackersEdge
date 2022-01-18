.import __IOBASE__
.export _main

.include "kernel.inc"
.include "ioapi.inc"

.rodata

okmsg:
    .byte "That is correct!", $a,$0

failmsg:
    .byte "Wrong Password.", $a
    .byte "HINT: Read the source code.  Press Ctrl-C to abort.", $a,$0

prompt:
    .byte "Password? ", $0

password:
    .byte "1234", $0

.bss

buffer: .res 40, $0

.code

_main: lda TCNTL
       ora #TMASK
       sta TCNTL
       lda #<password
       sta PARAM1
       lda #>password
       sta PARAM1+1
       lda #<buffer
       sta PARAM2
       lda #>buffer
       sta PARAM2+1
ask_password:
       lda #<prompt
       ldx #>prompt
       jsr _print
       lda #<buffer
       ldx #>buffer
       jsr _input
       jsr _cmpstr
       lda RESULT
       bne show_error
       lda #<okmsg
       ldx #>okmsg
       jsr _print
       brk
show_error:
       lda #<failmsg
       ldx #>failmsg
       jsr _print
       jmp ask_password
