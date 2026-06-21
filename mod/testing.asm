; these are just temporary tests. they override single and multi player.

org $809204 ; disable irq
LDA.B #$81  ; changed #$A1 to #$81 to disable irq
 
org $808B1D ; remove shadow flush 1 (video mode)
NOP         ; no longer needed bc removing old hud system
NOP
NOP

org $808B26 ; remove shadow flush 2 (Color math)
NOP         ; no longer needed bc removing old hud system
NOP
NOP
