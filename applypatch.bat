@echo off
copy rom\LostVikings.sfc rom\LostVikingsM.sfc
asar mod\%1 rom\LostVikingsM.sfc
pause