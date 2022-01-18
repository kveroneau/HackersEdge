.setcpu "65C02"
.export _main

.include "kernel.inc"

.rodata

down_str:
    .byte "Network unconfigured.", $a,$0

errstr:
    .byte "Unknown parameter.", $a,$0

configfile:
    .byte "CONFIG.SYS", $0

.code

_main: lda $e0
       bne chk_param
       lda $ff70
       beq net_down
       ldy #0
       jsr _printip
       lda #$a
       sta $ffd0
       brk
net_down:
       lda #<down_str
       ldx #>down_str
       jsr _print
       brk
chk_param:
       ldy #0
       lda ($e0),Y
       cmp #'d'
       beq ifdown
       cmp #'u'
       beq ifup
       lda #<errstr
       ldx #>errstr
       jsr _print
       brk
ifdown:
       stz $ff70
       jmp net_down
ifup:
       lda #<ret
       pha
       lda #>ret
       pha
       jmp ($f300)
ret:   brk
set_flag:
       ldx #0
       sta netdrv_flag,X
       lda #<configfile
       ldx #>configfile
       jmp _save_config
