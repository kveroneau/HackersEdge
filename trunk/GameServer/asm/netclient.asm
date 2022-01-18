.ORG $200
.TYP RAW

.INC ioapi.inc

def netseg $f2
def cport

LDA #netseg
STA npage
LDA #>@ipaddr
STA nip1
LDA #<@ipaddr
STA nip2
LDA #cport
STA nport
LDA #>@netin
STA ncb1
LDA #<@netin
STA ncb2
LDA #$2
STA ncntl
LDA ncntl
BEQ netok
BRK

netok:
LDY #>@sendthis
loop:
  LDA $200,Y
  BEQ done
  STA ncomm
  INY
  BRA loop
done:
LDA #$5
STA ncntl

LDA inp
LDA #$4
STA ncntl
LDA #65
STA pout
LDA #10
STA pout
LDA inp
BRK

@ipaddr:
DCB $31,$43,$8,$1
@sendthis:
DCS Hello World!\0

@netin:
loop2:
  LDA ncomm
  BEQ done2
  STA pout
  BRA loop2
done2:
LDA #10
STA pout
RTI
