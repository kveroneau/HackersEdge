.export _write
.import ldax0sp, incsp4, _puts
.importzp tmp1

.proc _write: near
       STA tmp1
       JSR ldax0sp
       JSR _puts
       JMP incsp4
.endproc
