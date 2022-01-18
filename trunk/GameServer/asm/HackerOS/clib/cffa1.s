.export _cffa1_available, _cffa1_format, _cffa1_error, _cffa1_savefile
.import popax, _strlen

.include "CFFA1_API.s"

.proc _cffa1_available: near
        LDA CFFA1_ID1
        CMP #$CF
        BNE nocard
        LDA CFFA1_ID2
        CMP #$FA
        BNE nocard
        LDX #1
        RTS
nocard: LDX #0
        RTS
.endproc

.proc _cffa1_format: near
          JSR _cffa1_available
          BNE nocard
          LDA #CFFA1_FormatDrive
          JSR CFFA1_API
          BCC formatok
nocard:   LDX #0
          RTS
formatok: LDX #1
          RTS
.endproc

.proc _cffa1_error: near
       LDX #CFFA1_DisplayError
       JMP CFFA1_API
.endproc

.proc _cffa_savefile: near
       JSR $9140
       STA Destination
       STX Destination+1
       JSR _strlen
       
       JSR popax
       STA Filename
       STX Filename+1
       SEC
       
       JSR $9135
.endproc
