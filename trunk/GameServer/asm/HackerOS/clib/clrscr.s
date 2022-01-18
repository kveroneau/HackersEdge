.export _clrscr
.import __IOBASE__

_clrscr: LDA #0
         STA __IOBASE__+$D6
         STA __IOBASE__+$D7
         LDA #'J'
         STA __IOBASE__+$D3
         RTS
