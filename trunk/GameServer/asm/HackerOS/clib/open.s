.export _open, _close
.import addysp, popax
.importzp tmp1

.proc _open: near
       DEY
       DEY
       DEY
       DEY
       JSR addysp
       JSR popax
       STA tmp1
       JSR popax
       STA $ff80
       STX $ff81
       LDA #3
       STA $ff82
       LDA $ff82
       BEQ found
       LDA #$ff
       LDX #$ff
found: RTS
.endproc

_close: RTS
