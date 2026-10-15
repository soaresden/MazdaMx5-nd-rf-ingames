# Gran Turismo (PS1, PAL SCES-00984)

🇫🇷 [Version française](README.md)

The MX-5 RF replaces the game's Eunos Roadsters (new from Mazda, used, race versions),
hardtop closed or top down. The result is a `.bin/.cue` disc image for DuckStation (and the
other emulators), made from **your** `.chd` image of the game. Tested in game in DuckStation.

**In the browser**: [the Gran Turismo page](https://soaresden.github.io/MazdaMx5-nd-rf-ingames/web/gt1.html)
(`web/gt1.html`) runs these same tools with [Pyodide](https://pyodide.org). The disc
image (~690 MB) is never held whole in memory: `Disc.bin_chunks` hands it out a few MB
at a time, written as it goes to the chosen file (Chrome, Edge) or to the site's private
storage (OPFS) before the download.

On the command line:

```bash
python make_car.py --chd "Gran Turismo [SCES_009.84].chd" --kn5 mazda_mx5_rf.kn5 --out "GT MX5.bin" --top closed --price 29900
```

`--car aminn` (repeatable) to replace only some Roadsters; all of them by default.
`--price 100` to have it from day one.

## What the conversion does

- **Model**: a closed shell, built the way the game's cars are. First a detailed shell
  (≈ 56 sections × 34 points around the Assetto Corsa body), then its right half
  simplified (quadrics, keeping a closed, oriented surface) and mirrored: ≈ 185
  vertices and 260 faces at the most detailed level (the cars on the disc: up to 272), three
  levels. The faces are checked one by one (each edge twice, in opposite directions) and in
  the same winding as the game's faces, otherwise the PS1 does not draw them.
- **Texture**: side, top, front and rear views of the detailed model, packed
  into the game's 4-bit texture; each face takes its texels from the view that sees it. 16
  palettes of 16 colors, including the paint ones: eight MX-5 RF paints
  (Deep Crystal Blue, Soul Red Crystal, Machine Grey…), tail lights on the braking palettes.
- **Data** (`CARINF.DAT`): name "MX-5 RF ND2 2.0", 184 PS, 205 Nm, 1,125 kg, 6-speed gearbox,
  205/45 R17 tyres, paint names, price.
- **Menus** (`MENU_IMG.ARC`, six languages): the car name as an image ("MX-5" emblem and
  "RF" in the game's lettering), and the Mazda dealer thumbnails (name, picture of the
  MX-5, price redrawn with the game's digits).
- **INFO page** (`MENU_IMG.ARC`, image 408 `CIAN16N.slt`, six languages): the history text is drawn
  into the page image, and all the Roadsters (new and used) show the same one. It
  is redrawn with the title "Mazda MX-5 RF" and the history of the RF ND2, in Liberation Sans
  Bold (the same character widths as Arial Bold, SIL OFL license, in `fonts/`) at the sizes measured
  on the original (25 and 14 px) and in the page's greys. So replacing a single Roadster
  also changes the INFO page of the others.
- **Disc**: `CAR.DAT`, `CARINF.DAT` and `MENU_IMG.ARC` rewritten in place (no file
  moves), sectors rebuilt with their EDC/ECC; the rest is an exact copy of the CHD.

## The formats (what we worked out)

| File | |
|---|---|
| `common/chd.py` | CHD v5 (cdlz / cdzl), Huffman-compressed map, mode 2 sector ECC (header zeroed) |
| `gtarc.py` | `@(#)GT-ARC` archives, the game's LZSS; optimal-parsing compressor (10% tighter than the game's own), match search with numpy |
| `gt1car.py` | `@(#)GT-CAR` models: 680 of the 688 models on the disc rewritten byte for byte; quads in 0-1-2-3 loop order; face cross product pointing inward |
| `gt1data.py`, `carinf.py` | `@(#)SPEC`, `@(#)COLOR`… tables (records + string tables) |
| `pslz.py` | backwards-compressed executables (`PSLZ`) |
| `tim.py`, `slt.py`, `titles.py`, `dealer.py`, `infopage.py`, `menus.py` | menu images (4-bit TIM, 640×480 pages in six VRAM blocks) |
| `shell.py`, `decimate.py`, `views.py`, `mx5scene.py`, `build_car.py`, `preview.py` | the conversion |
| `disc.py`, `make_car.py` | ISO 9660 file system and `.bin/.cue` image (EDC and ECC computed with numpy, in batches of sectors) |
| `fonts/` | Liberation Sans Bold and its license (SIL Open Font License) |

The file numbers inside the archives (the Roadsters in `CAR.DAT`, the menu pages)
come from the file lists of [pez2k/gt2tools](https://github.com/pez2k/gt2tools), whose
format descriptions helped a lot (none of its code is reused here).
