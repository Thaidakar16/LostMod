# IM MAD
Mostly at myself. 

## The problem:
I went to add the player 2 tilemap logic, but noticed that my "*nice*" comments, which tell me the exact location of each definition, were wrong. There were some copy/paste mistakes. So, I fixed it! However, to my dismay, The new starting value was **\$3800**.
The thing is, when I was looking for space, I never saw reads or writes to the entirety of \$3800 to \$3FFF, **EXCEPT** for **\$3800** itself. That means that \$3801 to \$3FFF is free, but I would need that ***ONE*** byte. (not to mention, I wanted to pad it for safety and start at \$3810 instead).
I could probably work around this one byte. I could do some funky swap between what the original game used it for and what I want it for, or, just upload that byte manually from a different location, or something of the sort. However, I have space concerns in other regards. Specifically, I need an ENTIRE SECOND OAM shadow on top of the one the game already uses. Thats 0x220 bytes.
Aside from space, I only ever verified the "worst case scenarios" assuming I would have a max of 3 rows per background, not 4. The time that those extra rows take is not negligible. 

## The solution:
I should shrink the row staging block.
If someone told me that it is possible to use only 2 rows for the snap-back, I would believe them, but at the cost of insane complexity. But, even if 2 is not possible, I **know** three is possible.
In all honesty, I've been avoiding it, but the correct thing to do is to drop it down to 3 rows.
I didn't want to go back to the scrolling logic! 
Well, on to it I guess.

My suspicion has been confirmed. If the camera goes to fast, ends up in the "catch-up zone". It ends up skipping a row right before the snap because it sees that it is in the snap range. The original code had a similar problem and they had that elegant solution, one that I've copied for many parts of the scrolling. That system *possibly* could be adapted to make 2 row snap work, but again, it would be very complicated. 

Instead, I'm just going to do an extra row on top of the main 2. the neat thing about those main 2 rows is that they are always in the same spot! Also, The extra row I mentioned? It is one before those for the down scroll, and one below for the up scroll. And well, because I'm lazy, and because the system was already in place, and because I didn't know I would run into this space problem, I just adjusted it to always do a row ahead and after for up and down. This made the logic so much simpler, but it has to go! 

It is done!