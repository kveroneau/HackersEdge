.export _gotoxy, gotoxy
.import popa

_gotoxy:
gotoxy: STA $FFD7
        JSR popa
        STA $FFD6
        RTS
