; these are just temporary tests. they override single and multi player.

org $809204 ; disable irq
    LDA.B #$81  ; changed #$A1 to #$81 to disable irq
 
org $808D0C ; modify the shadow flush 1 (video mode). we still use its "game mode" detection, but we use it to know to do our new stuff instead of the old hud logic.
    JSR.W $8CA8 ; old shadow flush jump no longer needed bc removing old hud system, but we can repurpose this spot for some testing, again, not final.
    RTS         ; rts early because we dont want to do the rest of the shadow flush code

    ;while we are jumping to old irq code, im putting the temp edits to the irq here.
    org $808CC0 ; NOP out the mainscreenshadow -> TM load/write, which is no longer needed bc removing old hud system
    NOP         ; 3 for the LDA
    NOP
    NOP
    NOP         ; and 3 for the STA
    NOP
    NOP

    org $808CF8 
    JSL $858000  ;NOTE: THIS IS JA NK! Ideally we would want to put this rerouted function in the main NMI code, but for testing purposes im putting it here since there is not enough space in the NMI code to put a long jump. 
    RTS          ;rts early because we dont want the HBlank and the INIDISP as we do not have to wait for HBlank or turn off force blank anymore, again bc removing old hud system


org $808B26 ; remove shadow flush 2 (Color math)
    NOP         ; no longer needed bc removing old hud system
    NOP
    NOP

; note: watch for a read from mainScreenShadow ($0394) at the start of a level. 
; removing the irq may cause it to never read it in the first place,
; as the original code relies on the nmi and irq switching back and forth.

; I would suggest the same for BG1SC and BG12NBA, but it seems that removing the irq doesn't cause any issues with them.
; correctcly removing the irq should cause BG1SC and BG12NBA to never be read, as they are only read in the irq code, and that makes the screen very glitchy.

; Again, these are just temporary tests. They override single and multi player, 
; I will need to rework the code to add differences between 1P and 2P modes.
; DO NOT FORGET TO REVERT THESE CHANGES BEFORE FINALIZING THE CODE.

