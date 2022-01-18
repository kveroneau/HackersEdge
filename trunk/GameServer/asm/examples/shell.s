.import _print, _input, _lf, _copytbl, _lookuptbl

.rodata

prompt:
    .byte "Login: ",$0

checker:
    .byte "Kevin",$0

correct:
    .byte "Welcome ",$0

badlogin:
    .byte "?BAD LOGIN",$a,$0

user2:
    .byte "Bob",$0

user3:
    .byte "Tom",$0

usertab:
    .byte 3*2
    .addr checker, user2, user3

.data

username: .res 40,$00

.code

.segment "STARTUP"

  lda #<usertab
  ldx #>usertab
  ldy #$10
  jsr _copytbl
: lda #<prompt
  ldx #>prompt
  jsr _print
  lda #<username
  ldx #>username
  jsr _input
  jsr _lookuptbl
  bpl :+
  lda #<badlogin
  ldx #>badlogin
  jsr _print
  beq :-
: stx $40
  lda #<correct
  ldx #>correct
  jsr _print
  lda #<username
  ldx #>username
  jsr _print
  jsr _lf
  jmp $f000
