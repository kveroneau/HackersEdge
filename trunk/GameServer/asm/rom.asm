.ORG $200
.TYP RAW

.INC ioapi.inc

LDA #$8
STA fmpage
LDA #$0
STA fdev
STA fblk1
STA fblk2
LDA #$1
STA fcntl
JMP $800
