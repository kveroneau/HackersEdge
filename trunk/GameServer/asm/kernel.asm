.ORG $f000
.TYP RAW
.OUT KERNEL.SYS

.INITDATA $f0

LDA #$fe
STA $71
LDA #0
STA $70
LDY #jsrtbl
jsrloop:
  LDA %ds,Y
  BEQ jsrdone
  STA ($70),Y
  INY
  LDA #$f0
  STA ($70),Y
  INY
  BRA jsrloop
jsrdone:
LDY #kernel_version ; Print Kernel version
JSR ($fe00)
BRK ; For now we exit as we have no drivers we can load...

; The following copied directly from original kernel code
; It needs to be updated to work with new system.
LDA #fileio ; Load file system driver
STA $80
LDA $f1
STA $81
LDA #$f2
JSR @drvload
LDY #fileio
LDA $ff86
BNE failed
JSR @ploaded
LDA #$f2
STA $f201
JSR ($f200)
LDA #netdrv ; Load network driver
STA $80
LDA #$f3
JSR @drvload
LDY #netdrv
LDA $ff86
BNE failed
JSR @ploaded
LDA #$f3
STA $f301
JSR ($f300)
done:
LDY #$ff
LDA #$00
STA $fa
LDA #$8
STA $fb
LDA #0
JSR @memclr
LDA #$2 ; Sets the default data segment.
STA $f1
BRK
failed:
JSR @perror
BRA done

@print: ; A basic label used for our branching routines.
PHP
PHA
loop1:
 LDA %ds,Y ; Load byte from [data+Y] offset into A.
 CMP #$00 ; Compare A to a null(0x00)
 BEQ done1 ; If A == null, branch to done.
 STA $ffd0 ; Store A in memory at address 0xffd0
 INY ; Increment Y
 BNE loop1 ; If A != null, branch to loop.
done1: ; Done label
PLA
PLP
RTS ; Break out of application
@input:
PHP
PHA
loop2:
  LDA $ffe0
  STA %ds,Y
  CMP #$a
  BEQ done2
  INY
  BNE loop2
done2:
LDA #0
STA %ds,Y
PLA
PLP
RTS
@cmpstr:
PHA
PHY
LDY #0
loop3:
  LDA ($fa),Y
  STA $ff
  LDA ($fc),Y
  CMP $ff
  BNE ne3
  INY
  LDA #0
  CMP $ff
  BNE loop3
  STA $ff
done3:
  PLY
  PLA
  RTS
ne3:
  LDA #1
  STA $ff
  BNE done3
@memclr:
loop4:
  STA ($fa),Y
  DEY
  BNE loop4
  STA ($fa),Y
RTS
@memcpy:
loop5:
  LDA ($fa),Y
  STA ($fc),Y
  DEY
  BNE loop5
  LDA ($fa),Y
  STA ($fc),Y
RTS

@drvload:
PHA
LDA #3
STA $ff82
STZ $ff83
STZ $ff85
PLA
STA $ff84
RTS
@ploaded:
JSR @print
LDY #loadedx
JSR @print
RTS
@perror:
LDA #$1f
STA $ffd4
JSR @print
LDY #loaderr
JSR @print
LDA #$20
STA $ffd4
RTS

.DATA
kernel_version:
DCS HackerKernel v0.3 $Rev: 260 $\n\0
jsrtbl:
DCW @print,@input,@cmpstr,@memclr,@memcpy,$0000
loadedx:
DCS  driver loaded.\n\0
loaderr:
DCS  failed to load.\n\0
fileio:
DCS FILEIO.SYS\0
netdrv:
DCS NETDRV.SYS\0
