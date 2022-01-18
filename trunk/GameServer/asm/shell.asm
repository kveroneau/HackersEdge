.ORG $fc00
.TYP RAW

.INC kernel.inc

JMP @init
@data:
DCS HackerShell v0.1 $Rev$\n\0
@init:
LDA #>@data
STA $f0
LDA #<@data
STA $f1
JSR %print
@prompt:
LDA #"$"
STA $ffd0
LDA #$00
STA $f0
LDA #$fd
STA $f1
JSR %input
