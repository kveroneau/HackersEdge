.INC kernel.inc
.OUT FILEIO.SYS
.TYP RAW
def %jsrload ($f206)
DCW @init,@version,@jsrtbl,@jsrload
@version:
DCS HackerFileIO v0.1 $Rev: 163 $\n\0
@jsrtbl:
DCW @finit,@fcount,@fexists,$0000
@init:
LDA #$f2
STA $f207
STA $f1
LDY $f202
JSR %print
JSR %jsrload
LDA #$f1
STA $f1
RTS
@jsrload:
LDA #$20
STA $70
LDA $f204
STA $f0
LDY #0
jsrloop:
  LDA ($f0),Y
  BEQ jsrdone
  STA ($70),Y
  INY
  LDA #$f2
  STA ($70),Y
  INY
  BRA jsrloop
jsrdone:
LDA #0
STA $f0
RTS
@finit:
PHA
LDA #$80
STA $ff80
LDA #0
STA $ff81
LDA #$f5
STA $81
PLA
RTS
@fcount:
LDA #5
STA $ff82
LDA $ff84
RTS
@fexists:
PHA
PHX
LDA #$fa
STA $ff80
LDA #$20
STA $fa
LDA #$f5
STA $fb
LDA #5
STA $ff82
LDX $ff84
loop1:
  DEX
  PHX
  STX $ff84
  JSR %strcmp
  LDA $ff
  BEQ equal1
  PLX
  BNE loop1
BRA done1
equal1:
PLX
done1:
LDA #$80
STA $ff80
PLX
PLA
RTS
