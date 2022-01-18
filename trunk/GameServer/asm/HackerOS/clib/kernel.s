.export _get_param

.proc _get_param: near
  lda $e0
  ldx $e1
  rts
.endproc
