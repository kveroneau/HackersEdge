.export _dio_open, _dio_close, _dio_read, _dio_write
.import popax, memcpy_upwards, decsp2
.importzp ptr1, ptr2, ptr3

dio_buffer = $e000

.proc _dio_open: near
            TAX
            STA $FF8A
            LDA #$ff
            STA $FF8E
            LDA $FF8E
            BNE nodev
            LDA #>dio_buffer
            STA $FF8B
            INX
done:       LDA #0
            RTS
nodev:      LDX #0
            BEQ done
.endproc

_dio_close: LDA #0
            LDX #0
            RTS

dio_params:  PHA
             JSR popax
             STA $FF8C
             STX $FF8D
             JSR popax
             DEX
             STX $FF8A
             PLA
             STA $FF8E
             RTS

.proc _dio_read: near
            STA ptr2
            STX ptr2+1
            LDA #1
            JSR dio_params
            BEQ copybuf
            JMP _dio_close
copybuf:    LDA #<dio_buffer
            STA ptr1
            LDA #>dio_buffer
            STA ptr1+1
do_bufcpy:  LDA #$ff
            STA ptr3
            LDA #0
            STA ptr3+1
            JSR decsp2
            LDY #0
            JMP memcpy_upwards
.endproc

.proc _dio_write: near
            STA ptr1
            STX ptr1+1
            LDA #<dio_buffer
            STA ptr2
            LDA #>dio_buffer
            STA ptr2+1
            JSR _dio_read::do_bufcpy
            LDA #2
            JMP dio_params
.endproc
