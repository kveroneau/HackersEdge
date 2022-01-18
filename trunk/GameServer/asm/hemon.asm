.ORG $f000
.TYP RAW

.INC ioapi.inc
def %buffer ($e0)

JSR @initdata
LDA #>@data
JSR @printstr
LDA #$0
STA he1
STA $e0
LDA #$e0
STA he2
STA $e1
LDA #hemon
STA heapi
@prompt:
  LDA #"@"
  STA pout
  LDY #0
getchar:
  LDA inp
  CMP #$a
  BEQ parse
  STA %buffer,Y
  INY
  BRA getchar
parse:
  LDA #0
  STA %buffer,Y
  LDA heapi
  BNE perror
  JMP @prompt
perror:
  BPL run
  LDA #>@syntax
  JSR @printstr
  JMP @prompt
run:
  JMP ($fff3)
@initdata:
  PHA
  LDA #>@data
  STA $a0
  LDA #<@data
  STA $a1
  PLA
  RTS
@printstr:
  STA $a0
  PHY
  LDY #0
ploop:
  LDA ($a0),Y
  CMP #0
  BEQ done
  STA pout
  INY
  BRA ploop
done:
  PLY
  RTS
@data:
DCS HackerMon v0.1 $Rev: 239 $\n\0
@syntax:
DCS ?SYNTAX ERROR\n\0
