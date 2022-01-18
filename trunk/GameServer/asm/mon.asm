.ORG $f000
.TYP RAW

.INC ioapi.inc
def %buffer ($e0)

JMP @testit
LDA #$f1
STA $e1
LDA #0
STA $e0
@prompt:
  LDA #$a
  STA pout
  LDA #"*"
  STA pout
  LDY #0
getstr:
  LDA inp
  STA %buffer,Y
  CMP #$a
  BEQ parse
  INY
  BRA getstr
parse:
  LDA #0
  STA %buffer,Y
  LDY #0
  LDA %buffer,Y
  CMP #"Q"
  BEQ quit
  EOR #%0011.0000
  CMP #$a
  BCC dig
  STA phex
  ;JSR @syntax
  JMP @prompt
quit:
  BRK
dig:
  ASL
  ASL
  ASL
  ASL
@syntax:
  LDA #"?"
  STA pout
  RTS
@cmdtbl:
  DCS TEST\0
  DCW @testit
  DCS HELLO\0
  DCW @hello
  DCB $00
@tstr:
  DCS Test String.\n\0
@hstr:
  DCS Hello World.\n\0
@testit:
  LDA #>@tstr
  STA $f0
  LDA #<@tstr
  STA $f1
  JMP @print
@hello:
  LDA #>@hstr
  STA $f0
  LDA #<@hstr
  STA $f1
  JMP @print
@print:
  LDY #0
ploop:
  LDA ($f0),Y
  CMP #0
  BEQ pdone
  STA pout
  INY
  BRA ploop
pdone:
  RTS
