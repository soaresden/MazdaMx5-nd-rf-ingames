The MX-5 RF in Need for Speed Underground 1 and 2 (Xbox USA, on Switch) - on your PC (Windows)
==============================================================================================

This package makes the whole folder to copy to the Switch's SD card: the port, your extracted
disc and, as you choose, the French (or German, Italian) version, the MX-5 RF with its hardtop
closed or open in place of the Mazda Miata, its handling and its name in the menus.

You need:
  - YOUR Xbox USA disc of the game as an .iso (Need for Speed - Underground (USA).iso or
    Need for Speed - Underground 2 (USA).iso): the ports run the USA version;
  - to play in French (German, Italian): your Xbox EUROPE disc of the same game, as an .iso;
  - the port's release zip: nfsu1x.zip (github.com/antoxa2584x/nfsu1-sw/releases) or
    nfsu2x.zip (github.com/antoxa2584x/nfsu2-sw/releases);
  - for the MX-5: the Assetto Corsa model mazda_mx5_rf.kn5 (free mod, see the project page).
No game or model file is included here.

1. Put these files in this folder (next to FABRIQUER.bat): they are found on their own.
2. Double-click FABRIQUER.bat.
   - First time without Python: it downloads an official portable Python (python.org, about
     30 MB) into outils\python. Nothing is installed in Windows.
3. Answer the questions (Enter = the answer offered; they are in French): the game, the
   language, the MX-5 and its roof, its handling and name (to try), the save auto-load.
4. A few minutes later the folder is in SD_nfsu1x (or SD_nfsu2x).

Copying to the card, game closed: if the game is already on the card, first copy
sdmc:/switch/nfsu1x/game/UDATA (or nfsu2x) somewhere else (your saves). Then copy the switch
folder of SD_nfsu1x to the root of the card, OVER it (merge, replace the files), never deleting
or replacing the whole game/ folder of the card.

Your disc images are never changed.

Project: https://soaresden.github.io/MazdaMx5-nd-rf-ingames/  (code: GPL-3.0)
