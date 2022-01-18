.export _read
.import ldax0sp, incsp4
.importzp ptr1, tmp1

.proc _read: near
       STA tmp1
       JSR ldax0sp
       STA ptr1
       STX ptr1+1
       LDY #0
loop:  LDA $FFE0
       STA (ptr1),Y
       INY
       CPY tmp1
       BNE loop
       JMP incsp4
.endproc
