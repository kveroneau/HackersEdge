.export _init
.import _main, __DATA_LOAD__, __DATA_RUN__, __DATA_SIZE__

.segment "HEADER"

.addr _init, __DATA_SIZE__, __DATA_LOAD__, __DATA_RUN__

.segment "STARTUP"

_init:
       jmp _main
