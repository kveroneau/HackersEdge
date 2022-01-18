.INC kernel.inc
.OUT NETDRV.SYS
.TYP RAW
def %jsrload ($f306)
def %netinit ($f308)
DCW @init,@version,@jsrtbl,@jsrload,@netinit,@ipstr
@version:
DCS HackerNetDrv v0.2 $Rev: 165 $\n\0
@ipstr:
DCS IP: \0
@jsrtbl:
DCW @printip,@listen,$0000
@init:
LDA #$f3
STA $f307
STA $f309
STA $f1
LDY $f302
JSR %print
JSR %jsrload
JSR %netinit
LDA #$f1
STA $f1
RTS
@jsrload:
LDA #$40
STA $70
LDA $f304
STA $f0
LDY #0
jsrloop:
  LDA ($f0),Y
  BEQ jsrdone
  STA ($70),Y
  INY
  LDA #$f3
  STA ($70),Y
  INY
  BRA jsrloop
jsrdone:
LDA #0
STA $f0
RTS
@netinit:
LDA #$e0
STA $ff70
LDY $f30a
JSR %print
LDY #0
JSR %printip
LDA #$a
STA $ffd0
RTS
@printip:
PHA
PHX
LDX #46
loop1:
 LDA $e000,Y
 STA $ffd1
 CPY #$03
 BEQ done1
 STX $ffd0
 INY
 BNE loop1
done1:
PLX
PLA
RTS
@listen:
STA $ff74
STX $ff72
STY $ff73
LDA #1
STA $ff75
LDA $ff75
RTS
