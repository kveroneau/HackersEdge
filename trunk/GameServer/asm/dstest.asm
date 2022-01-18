.ORG $800
.TYP RAW

.INITDATA $f0

LDY #myvar
loop:
  LDA %ds,Y
  BEQ done
  STA $ffd0
  INY
  BRA loop
done:
BRK

.DATA
myvar:
DCS Hello Data segment!\n\0
