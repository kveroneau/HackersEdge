.ORG $800
.TYP RAW

.INC ioapi.inc
; Declare pages
def fbuf $f5 ; Page of file system buffer in memory.

; Declare 16-bit address pointers
def src $fa ; Address pointer to $802
def dst $fc ; Address pointer to $f5xx

BRA ldblk
@kernel:
DCS KERNEL.SYS\0
ldblk:
  LDA #fbuf
  STA fmpage
  LDA #$1
  STA fblk1
  STA fcntl
  LDA #$8
  STA $fb
  LDA #$2
  STA src
  LDA #fbuf
  STA $fd
  LDA #$1
  STA dst
  LDY #0
cmploop:
  LDA (src),Y
  CMP (dst),Y
  BNE cmpne
  LDA #0
  CMP (dst),Y
  BEQ loadkrnl
  INY
  BRA cmploop
cmpne:
  ; Currently we're only checking the first filename.
  LDA #"!"
  STA pout
  LDA #$a
  STA pout
  BRK
loadkrnl:
  INY
  LDA (dst),Y
  STA fblk1
  LDA #$f0
  STA fmpage
  LDA #$1
  STA fcntl
  INY
  LDA (dst),Y
  CMP #1
  BEQ execkrnl
  STA $ff
  DEC $ff
  INC fblk1
  LDA #$f1
  STA fmpage
  LDA #$1
  STA fcntl
execkrnl:
  JMP $f000
