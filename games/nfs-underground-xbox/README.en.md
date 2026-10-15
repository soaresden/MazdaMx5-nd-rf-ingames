# Need for Speed Underground and Underground 2 (Xbox USA)

🇫🇷 [Version française](README.md)

![The MX-5 RF with the top down in the Need for Speed Underground garage, headlights on](../../docs/nfsu1_en_jeu.jpg)
![The rear of the MX-5 RF in Underground, lights on](../../docs/nfsu1_arriere.jpg)

**Underground 2** (the car is red: it is the Miata's base color):

![The MX-5 RF with the top down at the Need for Speed Underground 2 dealership](../../docs/nfsu2_en_jeu.jpg)
![The rear of the MX-5 RF in Underground 2](../../docs/nfsu2_arriere.jpg)
![“Mazda MX-5 RF” in the dealership menu, in French](../../docs/nfsu2_nom.jpg)

The MX-5 RF replaces the **Mazda Miata**, which is in both games: it keeps its engine sound, its
Mazda brand and its place in the game. For the Switch ports
[nfsu1-sw](https://github.com/antoxa2584x/nfsu1-sw) and [nfsu2-sw](https://github.com/antoxa2584x/nfsu2-sw),
which run the Xbox USA version extracted in `sdmc:/switch/nfsu1x/game/` and
`sdmc:/switch/nfsu2x/game/`.

```bash
python make_car.py --game ug1 --iso "Need for Speed - Underground (USA).iso" --kn5 mazda_mx5_rf.kn5 --zip u1_mx5.zip --top closed
python make_car.py --game ug2 --iso "Need for Speed - Underground 2 (USA).iso" --kn5 mazda_mx5_rf.kn5 --zip u2_mx5.zip --top open
```

- **Underground**: the zip contains `game/CARS/MIATA/GEOMETRY.BIN` and `TEXTURES.BIN`.
- **Underground 2** stores its files in `NFSUNDER/ZZDATA*.BIN` (index `NFSUNDER/ZDIR.BIN`).
  The zip contains the two files as plain files (`game/CARS/MIATA/…`) and, in `planB/`, the
  game's `ZZDATA2.BIN` with the MX-5 in place of the Miata (same sectors: the new
  files are smaller) and the `ZDIR.BIN` with their new sizes.

## Ready-made folder for the SD card (`make_sd.py`)

The port's release zip + your USA disc give the `switch/` folder to copy to the
card, with the French version (Europe disc) and the MX-5 RF as options:

```bash
python make_sd.py --game ug1 --usa "Need for Speed - Underground (USA).iso" --release nfsu1x.zip --out SD                   --europe "Need for Speed - Underground (Europe) (En,Fr,De).iso" --kn5 mazda_mx5_rf.kn5 --top open
```

`--langue fr|de|it|es` picks the language with `--europe` (French by default; Underground 2:
fr, de, it, the Europe disc has no Spanish voices; German and Italian still need to be tried in
game). The Windows package (`package/`, `make_package.py`) opens a local page (`ui_server.py`, `package/ui/index.html`: 127.0.0.1 only, FR/EN) that finds the files, opens the Windows dialogs and follows the build; `fabriquer_sd.py ug1|ug2` asks the same questions in the console. Options: `--nro` (another NRO),
`--env` (your settings), `--perf`, `--names`, `--no-autoload`. The output folder must be empty:
nothing is written to an already installed card or to the images.

- **Underground** in French: the texts and voices are already on the USA disc, only the
  dubbed cutscenes are missing (`MOVIES/FR*.MAD` from the Europe disc). With an NRO that knows
  `NFSU1_LANGUAGE` ([antoxa2584x/nfsu1-sw#8](https://github.com/antoxa2584x/nfsu1-sw/pull/8)):
  `NFSU1_LANGUAGE=fr`; otherwise the USA `default.xbe` in which data tables make French
  language 0 (`vf_ug1.py`, the code is not touched). `NFSU1_AUTOLOAD=1`
  ([#9](https://github.com/antoxa2584x/nfsu1-sw/pull/9)) when the NRO knows it.
- **Underground 2** in French, port unchanged (`vf_ug2.py`): `ZZDATA10.BIN` (French texts, voices and
  cutscenes from the Europe disc), `ZZDATA11.BIN` (the two preloaded files
  `FrontEndMemoryFile` / `InGameMemoryFile` with the French voice index: with the English one, the
  career froze after its first cutscene) and `ZDIR.BIN`, which redirects the English
  names there (the original stays as `ZDIR_anglais.BIN`).


## What the conversion does

The model comes from the Most Wanted converter (`build_mx5.collect`: same parts, same
materials), moved so that its wheels land where the game puts the Miata's (CarTypeInfo from
`GLOBALB`: axles at x = 1.03 and −1.26, wheel centers at z = 0.122). Then, solid by solid,
on the Miata's file:

- stock parts (body, base with the cabin and the windows, hood, headlights, lights,
  mirrors): those of the MX-5, in three or four levels of detail;
- kit wide bodies, hoods and headlights: copies of the MX-5's;
- kit bumpers, side skirts, roofs, spoilers, engine, exhaust, doors (U2) and decal
  parts: one invisible triangle each, their markers kept and moved
  (exhausts, plate, light halos);
- wheels and brakes: the game's.

`GEOMETRY.BIN` always stays smaller than the Miata's (the game has the memory for that):
the triangle budgets go down as long as it is not.

Textures: the MX-5 images (cockpit / plastics / details atlas, lights) take the
place of Miata textures, in the same format; paint: the game's (`MIATA_SKIN1`).

- **Underground 2**: the atlas in `MIATA_ENGINE`, lights in `MIATA_STYLE01_ENGINE` (DXT1);
  the headlights and rear lights on the game's shared textures (`HEADLIGHT_LEFT` / `RIGHT`…),
  which it replaces when the lights turn on.
- **Underground** does not draw the engine textures on the other parts, nor draw as is what
  is in the car's light textures: it replaces `MIATA_KIT00_HEADLIGHT_LEFT` /
  `RIGHT` with `HEADLIGHT_ON` (headlights on, in the garage as in races) or `HEADLIGHT_OFF`, and
  the rear lights with their lit version. So the atlas (left half) and the headlights (right
  half) make a single 128x64 image, put in the four headlight textures (8-bit
  palettized, Xbox-swizzled, in the colors of each one's original palette); in `ON`, the
  headlights are brightened. The headlight glass gets, as on the Miata, one game texture
  per side at a single point: the game makes it glow (the halo, 3 cm in front of the glass).

## The formats

| | Underground | Underground 2 |
|---|---|---|
| solid header (0x134011) | 176 bytes, name at 0x94 | 192 bytes, name at 0xA4 |
| vertex (0x134B01) | 36 bytes: position, color, uv, normal | 32 bytes: position, uv, normal |
| group (0x134B02) | 64 bytes: box, index count, texture, flags, first index, 0, shader | same |
| indices (0x134B03) | triangle lists (u16) | same |
| table 0x134004 | 20 bytes | 24 bytes |
| textures | JDLZ stream of the pixels, info in 0x33310004 | JDLZ or HUFF stream: pixels + info (124) + Xbox info (60) |

`geo_ug.py` reads back and rewrites byte for byte the `GEOMETRY.BIN` files of the Miata (U1 and U2) and of
the RX-7; `tpk_ug.py` rewrites the `TEXTURES.BIN` files identically. The chunk names
(0x134011 ESOLID, 0x134B00 XBOX_PLATINFO, 0x134017-19 normal smoothing…) are EA's,
from the [Most Wanted decompilation](https://github.com/dbalatoni13/nfsmw).

## Handling and name (`make_car.py` options, on by default)

- `--perf rf184` (`perf_ug.py`): the Miata's CarTypeInfo (block 0x34600 of
  `GLOBAL/GLOBALB.BUN`, the same one JDLZ-compressed in `GLOBALB.LZC`) gets the figures of an
  MX-5 RF 2.0 184 hp: 1125 kg (inertia recomputed), real torque (9 points from idle to the
  rev limiter), 7500 / 8000 rpm, the ND's 6-speed gearbox and 3.454 final drive, more grip (rear > front),
  brakes and downforce at the RX-7 / RX-8 level; the engine / ECU / turbo / tire upgrades follow.
  `--wheels mx5`: wheelbase 2.309 m, tracks 1.495 / 1.505 m, 205/45 R17 tires.
- `--names on` (`lang_ug.py`, `fe_ug.py`): “MX-5 RF” in all languages
  (`CAR_NAME_MIATA`, `FULL_NAME_MIATA`…; U1 in UTF-16, U2 in 8-bit) and the
  “Mazda / MX-5 RF” badge (`SECONDARY_LOGO_MIATA`, `_MX5`, `_MIATA_RO`, DXT3 256x64).
- Underground 2: these files go into a new `ZZDATA12.BIN`; `zdir_ug2.py` redirects
  their entries (all the copies, ZZDATA2 and ZZDATA5) in any `ZDIR.BIN`, French version
  included (`--vf-zzdata10`: the French text of the French version also gets the name).
  `make_extras.py` only makes these files, without rebuilding the car.
