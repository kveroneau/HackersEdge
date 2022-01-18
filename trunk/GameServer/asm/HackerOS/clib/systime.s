.export __systime
.importzp sreg

__systime: LDA $FF2A
           STA sreg+1
           LDA $FF29
           STA sreg
           LDX $FF28
           LDA $FF27
           RTS
