.export _puts, _cputsxy
.import popa, gotoxy
.importzp ptr1

.proc _puts: near
       JMP $fe00
.endproc

_cputsxy: STA ptr1
          STX ptr1+1
          JSR popa
          JSR gotoxy
          JMP _puts
