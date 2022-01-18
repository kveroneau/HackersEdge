.export _cputcxy
.import popa

_cputcxy: TAX
          JSR popa
          STA $FFD7
          JSR popa
          STA $FFD6
          STX $FFD0
          RTS
