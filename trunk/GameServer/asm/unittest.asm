.ORG $f000
.TYP RAW

.INC ioapi.inc

; Sets up our data-segment location for subroutines.
LDA #<@DATA
STA $f1
LDA #>@DATA
STA $f0
JSR @print
LDA #$f0
STA $fe01
STA $fe03
STA $fe05
LDA #>@print
STA $fe00
LDA #>@getstr
STA $fe02
LDA #>@debug
STA $fe04
LDA #>@LDBLK
STA $f0
JSR ($fe00)
LDA #0
STA $ffd3
LDA #$2
STA fmpage
LDA #$2
STA fblk1
LDA #$1
STA fcntl
LDA #>@LDDONE
STA $f0
JSR ($fe00)
LDA $202
JSR ($200)
JSR ($fe04)
BRK

@print: ; A basic label used for our branching routines.
PHP
PHA
PHY
LDY #0
loop1:
 LDA %ds,Y ; Load byte from [data+Y] offset into A.
 CMP #$00 ; Compare A to a null(0x00)
 BEQ done1 ; If A == null, branch to done.
 STA $ffd0 ; Store A in memory at address 0xffd0
 INY ; Increment Y
 BNE loop1 ; If A != null, branch to loop.
done1: ; Done label
PLY
PLA
PLP
RTS ; Break out of application
@getstr:
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
@debug:
PHA
JSR @next
TXA
JSR @next
TYA
JSR @next
TSX
TXA
JSR @next
LDA #$a
STA pout
PLA
RTS
@next:
STA phex
LDA #","
STA pout
RTS

@DATA:
DCS Hacker's Edge UnitTest\n\0
@LDBLK:
DCS Loading block from storage...\0
@LDDONE:
DCS done.\n\0
