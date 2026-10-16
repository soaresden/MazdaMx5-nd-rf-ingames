🇫🇷 [Version française](README.md)

# The MX-5 RF in Gran Turismo 2 (PS1)

![The MX-5 RF top down at the Gran Turismo 2 used car dealer](../../docs/gt2_en_jeu.jpg)

The MX-5 RF (ND2) replaces the MX-5s of your choice. By default:
- **hardtop closed** in place of the Eunos Roadster '93, the used one at 7,735 Cr;
- **top down** in place of the V-Special '93. The used car listing at 8,084 Cr becomes this top-down one.

The racing versions (after the racing modification) are RFs too.

The tool takes the original **Simulation** disc (Europe), the **combined disc**
([GT2-Combined-Disc](https://github.com/CookiePLMonster/GT2-Combined-Disc)) or pez2k's **GT2
Plus**. It makes the image from all three. The in-game tests were done on the GT2 Plus combined disc.

![Three-quarter rear](../../docs/gt2_trois_quarts.jpg) ![Three-quarter front](../../docs/gt2_avant.jpg)

## What the conversion does

- **Model**: built from the Assetto Corsa model in the same way as the Gran Turismo version, in
  GT2's format.
  - 3 levels of detail, up to 236 vertices (152 for the game's MX-5 '93).
  - A day model and a night model: headlights on, rear lamps lit, brake lights when braking.
  - Round wheel arches, made as the game's own cars: arches cut transparent in the texture, a
    black wall behind them, and the game's wheels.
- **Paints**: 9 colours with Mazda's names (Deep Crystal Blue Mica first, Soul Red Crystal…),
  with the colour squares of the menus.
- **Data**:
  - "Mazda MX-5 RF ND2 '18"; the top-down one is "RF Open" in English, "RF décapotée" in French,
    etc.;
  - a 2.0 with 184 PS at 7,000 rpm and 20.9 kgm at 4,000 rpm, 7,500 rpm redline;
  - 1,125 kg, 6-speed;
  - tuning parts add to these values. The engine sound is the game's MX-5's.
- **Menus**:
  - "Mazda / MX-5 RF" title at the dealer;
  - the (i) button opens two pages describing the RF, in the 5 languages, laid out as the
    game's own.
- **Start screens**: a banner in the style of the GT logo, on the language screen and both title
  screens (under the copyright: the game scrolls its mode list under the logo). On GT2 Plus it
  shows "HD PLUS" with "beta 7 · MX-5 RF" under it; on the other discs, "MX-5 RF".

## Making the image

You need Python 3 with `numpy` and `Pillow`, your disc image and the `mazda_mx5_rf.kn5` file of
the Assetto Corsa mod. None of these is in this repository.

```
python make_gt2.py --disc "Gran Turismo 2 Plus Combined (Europe).chd" --kn5 mazda_mx5_rf.kn5 --out "GT2 MX-5 RF.chd"
```

- `--car CODE=closed|open`: which MX-5 to replace, and with which roof. Repeat the option for
  several cars. Default: `aminn=closed`, `amivn=open`.
- `--version` / `--version-sub`: the text of the start screen banner (`--version ""` for none).
- `--cheat`: adds the cheat menu of
  [GranTurismo2-OverlayCheat](https://github.com/soaresden/GranTurismo2-OverlayCheat) (hold
  SELECT, or L1 + R1 + L2 + R2 in Batocera: licence timer frozen, credits live). The project must be next to this repository, or
  its folder given by `GT2CHEAT_DIR`.
- `--out` ending in `.bin` gives a `.bin` + `.cue`; ending in `.chd`, a CHD directly.

## How it is made

- `gt2vol.py`: GT2.VOL, the Simulation disc's archive, read and written again. The new VOL keeps
  its place; if it grows, the files after it move down by as much.
- `gt2disc.py`: the disc image. The sectors made again get their EDC and ECC computed again.
- `gt2model.py`, `gt2texture.py`: the `.cdo` / `.cno` models and the `.cdp` / `.cnp` textures.
- `build_gt2car.py`: the RF in GT2's format. It reuses the shell, the pictures and the texture of
  the Gran Turismo version (`../gran-turismo-ps1`).
- `gt2data.py`: specifications, names, paints (`gtmode_data`, `unistrdb`, `.carinfo`,
  `.carcolor`).
- `gt2menu.py`: menu screens (`gtmenudat`), the table of descriptions (`solodata`), titles
  (`carlogo`), used car listings, start screens.
- `make_gt2.py`: everything in one command.

The formats come from [pez2k](https://github.com/pez2k/gt2tools)'s tools (GT2ModelTool,
GT2DataSplitter, GT2MenuSplitter, GT2CarInfoEditor) and from our own findings.
