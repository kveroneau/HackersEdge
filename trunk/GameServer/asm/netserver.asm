.ORG $200
.TYP RAW

.INC ioapi.inc

def netseg $f2
def sport 23

LDA #netseg
STA npage
LDA #sport
STA nport
LDA #>@netin
STA ncb1
LDA #<@netin
STA ncb2
LDA #$1
STA ncntl
LDA ncntl
BEQ netok
BRK
netok:
LDA inp
BRK

@netin:
SEI
LDA #65
STA ncomm
LDA #$6
STA ncntl
BRK
RTI
