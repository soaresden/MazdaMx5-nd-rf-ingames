# Need for Speed: Most Wanted (2005), Xbox 360

🇫🇷 [Version française](README.md)

The MX-5 RF replaces the car of your choice (tested in game: the **Lexus IS 300**, the first car
of the career). Made for the **Xbox 360** version of the game, as run by the Switch port
[nfsmw-nx](https://github.com/StevensND/nfsmw-nx). The files do not work with the PC version: the
geometry and the textures are not in the same format there.

Status: **works on Switch** (11/10/2026).

- Body, black roof, grille, cabin and driver (the Elise's, moved into the seat).
- Hardtop closed (RF) or top down (`--top open`).
- Mazda logo and "MX-5 Miata" name in the menus; tuning hoods and kits = those of the MX-5.
- Performance of an MX-5 RF 2.0 184 hp; the game's Miata engine sound.
- The police radio calls it "Mazda" (`--police keep`: the brand of the replaced car).
- Wheels and brakes: those of the replaced car (the MX-5 wheels do not show up yet).
- Color: in the game's workshop; the closest to Deep Crystal Blue is **Metallic no. 75**.

## The easiest way: the page or `make_car.py`

The [project page](https://soaresden.github.io/MazdaMx5-nd-rf-ingames/nfs-most-wanted/) does everything in the browser.
On the command line, `make_car.py` does the same thing and writes a zip ready to copy:

```bash
python make_car.py --iso "NFS Most Wanted (X360).iso" --kn5 mazda_mx5_rf.kn5 --zip mx5.zip [--car IS300] [--top open] [--sound miata|keep] [--perf rf184|keep] [--logo MAZDA|none] [--name badge.png] [--vf]
```

`--vf`: tick it if the French dub of nfsmw-nx is installed. Its `GLOBALMEMORYFILE.BIN` hides the
English texts, and ours must do the same, otherwise the menus go back to English.

The following sections describe the separate tools that `make_car.py` runs one after the other.

## Building the car (`build_mx5.py`)

Choose the car to replace with `--car`: it is the name of its folder in `CARS`, for example
`IS300` for the Lexus from the start of the career, or `ELISE`.

```bash
python build_mx5.py --iso "NFS Most Wanted (X360).iso" --kn5 ks_mazda_mx5_rf/mazda_mx5_rf.kn5 --out build --car IS300 [--base-root <your current game_root>] [--top open]
```

The script writes into `build/`:

- `CARS/<VOITURE>/GEOMETRY.BIN` and `TEXTURES.BIN`, each at the exact size of the original file.
  This is required: the game reads the files placed next to the archives with the size given in
  `ZDIR.BIN`.
- `GLOBAL/GLOBALMEMORYFILE.BIN`, if the wheelbase of the replaced car is not the MX-5's. Its wheel
  positions (`ecar/<voiture>` → `TireOffsets`, in `ATTRIBUTES.BIN`) take those of the MX-5,
  otherwise the wheels would stick out of the wheel arches. Pass `--base-root` to start from your
  installation, for example with the French dub, and not lose its changes.

`--top open` makes a top-down RF: the roof panels, their trim and the rear window are stowed, the
side windows are lowered; the roll hoops and the windshield stay. Only `CARS/<VOITURE>` changes: to
switch from one to the other, just copy these two files again.

The parts the MX-5 does not have (rear windows, body kits, tuning hoods, damage) stay empty. The
driver is the Elise's, moved into the MX-5 seat.

By default, the wheels and brakes stay those of the replaced car, placed at the MX-5 wheel
positions. With `--mx5-wheels`, the script converts the MX-5's, but the game does not draw them
yet: they are missing even in the shadow passes.

Everything that is neither paint, nor glass, nor headlight (plastics, grille, black roof, rubbers,
chrome, mirrors, side skirts, details, interior) uses the `DULLPLASTIC` material and a single
512 × 512 texture, stored under the name of the Lexus `IS300_INTERIOR`:
- top left, the cockpit image;
- top right, those of the side skirts and details;
- bottom, solid squares (black, grey, white), where the UVs of the solid parts point.

What the tests on Switch showed (squares test, 11/10/2026):
- the game drew no group that used one of our separate solid textures (32 × 32, then 256 × 128),
  whatever its name; the atlas, on the other hand, shows up;
- it ignores the vertex color: the color must be in the texture;
- with our textures, the `MOLDINGS`, `INTERIOR` and `HEADLIGHTREFLECTOR` materials drew nothing;
  `DULLPLASTIC`, `CARSKIN` and `LICENSEPLATE` show up.

The images of the Assetto Corsa mod have an alpha at 0 (it is the gloss, not the transparency):
`build_textures` removes it before any resizing, otherwise Pillow multiplies the colors by the
alpha and the image turns black.

The tuning hoods (`STYLExx_HOOD`) and the body kits (`KIT01` to `KIT04`) get the hood and the body
of the MX-5, at a lower level of detail to fit in the file size.

`MX5_DIAG=1` (one color per group, useless since the game ignores the vertex color) and
`MX5_SQUARES=1` (rows of squares in front of the bumper, one per material or texture) build the
diagnostic versions.

The game does not allow adding a car without modifying the port: the number of cars is fixed in
the code. On PC, this is what NFSMW Unlimiter does.

Preview of the car as the game assembles it:

```bash
python preview_car.py --iso "NFS Most Wanted (X360).iso" build/CARS/IS300/GEOMETRY.BIN apercu.png --car IS300 --globalmem build/GLOBAL/GLOBALMEMORYFILE.BIN
```

### Logo and name in the menus

In the menus, the brand logo and the model name ("IS 300") are images from
`FRONTEND/FRONTB.LZC`:
- `CARSELECT_MANUFACTURER_<MARQUE>`: 128×64 in DXT5;
- `SECONDARY_LOGO_<VOITURE>`: 256×64 in DXT5.

Both are white on a transparent background, with 3 mipmaps.

`fe_badges.py` copies the logo of another brand over the car's (all logos have the same format).
It also draws the name from one or more images, a dark drawing on a light background or white on a
transparent background, placed side by side. `image.png:x0,y0,x1,y1` keeps only a part of it.

```bash
python fe_badges.py --iso "NFS Most Wanted (X360).iso" --out build --car IS300 --logo MAZDA --name mx5.png --name miata.png:0,0,560,330 --preview badges.png
```

The recompressed file must fit in the original size (5 703 541 bytes).
- `jdlz.splice` only re-encodes the changed bytes.
- If it does not fit, the tool recompresses everything: our compressor makes about 2 KB less per
  MB than EA's, which leaves about 35 KB of margin.

## Installing on the Switch

### Plan A: files placed next to the archives

Copy the contents of `build/` into `sdmc:/switch/nfsmw-nx/game_root/`: the `CARS` folders and,
if there are any, `GLOBAL` and `FRONTEND`.

The game always tries to open a "loose" file before looking for it in the `ZZDATA` archives. This
works for the cars: the port's log shows
`abrir 'D:\CARS\ELISE\GEOMETRY.BIN' (abierto)`.

### Plan B: the car written into the game's archive (not needed if plan A works)

```bash
python pack_zzdata.py --iso "NFS Most Wanted (X360).iso" --src build --out build/game_root [--zdir <your current ZDIR.BIN>]
```

The script writes `ZZDATA2.BIN` and `ZDIR.BIN`:

- `ZZDATA2.BIN` (394 MB): the MX-5 takes the place of the Elise in it; everything else is identical
  and the archive keeps its size.
- `ZDIR.BIN`: only the 2 entries of the Elise change.

Back up your two original files, then copy the new ones into `game_root/NFS/`.

If you have already modified your `ZDIR.BIN`, for example with the
[nfsmw-nx French dub](https://github.com/StevensND/nfsmw-nx/tree/main/tools/french-dub), pass it with
`--zdir` to keep those changes.

## Disc image for Xenia (`make_iso.py`)

A new Xbox 360 image with folders placed over the disc files (the last one wins, names are
case-insensitive), for example the nfsmw-nx French dub then the MX-5:

```bash
python make_iso.py --iso "Need for Speed - Most Wanted (Europe).iso" --add "Patch VF/game_root"                    --add "MX5 RF/FINAL/game_root" --add "MX5 RF/FINAL/variante_decapotee/game_root"                    --out "Need for Speed - Most Wanted (Europe) VF MX-5 RF.iso"
```

The game opens a loose file before looking for it in the archives (plan A), as on the Switch: the
MX-5 files stay separate files, checked against the size given by `ZDIR.BIN`. The `NFS/PAD*.BIN`
(padding that places the data on the real disc) are left out (`--keep-pad` to keep them): 5.1 GB
instead of 7.8. The image is a plain XDVDFS (file system at sector 32), read back at the end.
Tested in Xenia on 15/10/2026: French dub, and the MX-5 in place of the Lexus IS300.

## Limitations

- The vinyls are drawn for the shape of the replaced car.
- The wheels and brakes stay those of the replaced car.
- The plastics and chrome are matte: they all go through the `DULLPLASTIC` material, the only one
  that shows up with our textures (see above).
- The parts are simplified to respect the engine limits (next section). The levels of detail B to
  E are derived from level A; tuning hoods and kits use a lower level to fit in the file size.
- Only the IS300 has been tried in game; the other cars are built the same way.

## The engine limits

A body that is too heavy crashes the game as soon as it loads the car:
`Unhandled guest access violation: read of guest 0x00000018`, right after the part is read.

| Per part (`eSolid`) | Maximum across the 31 cars on the disc | Limit set by `build_mx5.py` |
|---|---|---|
| material groups | 18 | 16 |
| triangles | 9 338 | 8 500 |
| vertices | 11 280 | 11 000 |
| triangles per group | 1 000 | 1 000 |
| size | 589 KB | about 300 KB |

To stay within these limits, `common/qem.py` simplifies the meshes with a quadric error metric.
Panel edges and texture seams are preserved.

## The Xbox 360 format

For the PC format, the reference is the documentation of
[47PADO47/nfs-mw](https://github.com/47PADO47/nfs-mw/tree/main/docs/formats). On Xbox 360, what
changes:

### Geometry (`GEOMETRY.BIN`)

`geo360.py` reads and rewrites the original Elise **byte for byte**.

- **Structure**: the chunks and the part headers (`0x134011`) stay little-endian, as on PC.
- **Material group** (`0x134B02`): 256 bytes, aligned on 0x80.

  | Offset | Contents |
  |---|---|
  | `+0x00` | bounding box |
  | `+0x18` | first index |
  | `+0x1C` | type: 7 for one vertex stream, 8 for two streams (normal maps) |
  | `+0x20` | key, tied to the lighting material (see below) |
  | `+0x24` | flags |
  | `+0x28` | number of indices (u16) |
  | `+0x2A` | 6 bytes: lighting material, then diffuse, normal, height, specular, opacity textures |
  | `+0x58` | vertex buffer size |
  | `+0x5C` | `00 00 20 80` (32-byte stride) |

- **Vertices** (`0x134B01`, aligned on 0x80, padded with `0x11`): one buffer per group, preceded by
  an empty `0x134C02` chunk. Each vertex is 32 bytes, in **big-endian**:
  - position (3 float);
  - UV (2 float);
  - ARGB color (ambient occlusion);
  - normal as 4 × int16 (w = 32767).

  Type 8 groups have two buffers, of 24 and 16 bytes.
- **Indices** (`0x134B03`, aligned on 0x20): **big-endian** u16. Each group stops at 3 000
  indices.
- **Normal smoothing**: the chunks `0x134017` to `0x134019` come **after** the mesh. They can be
  removed.
- **Padding**: the file ends with empty chunks, and the `0x134002` header contains the total file
  size.

**The `+0x20` key**: there are only 103 of them on the whole disc, and each one always goes with
**a single** lighting material and the same flags, whatever the car and the texture.
`build_mx5.py` only uses key + flags + material combinations that exist on the disc, and only the
30 lighting materials that the game's cars use.

### Textures (`TEXTURES.BIN`)

`tpk360.py` writes this format. The layout is the compressed one, as on PC:

- each texture is compressed with JDLZ or HUFF and followed by `TextureInfo` (0x7C) and a 0x20-byte
  platform record;
- format `0x1A200152` for DXT1, `0x1A200154` for DXT5;
- **Xenos-tiled** pixels, 16-bit words swapped, surface aligned on 32 × 32 blocks.

**JDLZ compression**: the game's decoder (`JLZDecompress` in the
[decompilation](https://github.com/dbalatoni13/nfsmw/blob/main/src/Speed/Indep/Src/Misc/LZCompress.cpp))
works like this:

- it **counts down the input bytes** (`while (Size != 0)`) instead of stopping when the output is
  full;
- it reloads a flag byte **right after** the instruction that empties the register, including
  after the last one.

EA's compressor (`JLZCompress`) therefore follows three rules, and `jdlz.py` reproduces them:

- it reserves the next flag byte as soon as the current one is full;
- its loop runs one more time than the data, which adds a literal;
- the unused bits are set to 1.

A stream that does not follow these rules makes the decoder overflow. The game then crashes on an
invalid pointer: `read of guest 0x00000018`, or the value `0xDFDFDFDF`.

`jdlz.game_decompress` is a copy of this decoder, and `tpk360.py` uses it to check each texture it
writes.

### Useful names

- **Headlights and lights**: the parts use the generic names `HEADLIGHT_LEFT`,
  `BRAKELIGHT_LEFT`… The game replaces them with `<VOITURE>_KIT00_HEADLIGHT_OFF/ON` and
  `<VOITURE>_KIT00_BRAKELIGHT_OFF/ON`, which must be in the car's texture pack.
- **Paint**: the `CARSKIN` lighting material is replaced by the chosen paint. The
  `<VOITURE>_SKIN1` texture is made by the game.
- **Wheels**: `ecar/elise` in `GLOBAL/ATTRIBUTES.BIN` (big-endian on 360) gives:
  - front (1.11; ±0.83);
  - rear (−1.19; ±0.86);
  - radius 0.31.

  The tire is a right wheel model, outer face at y = −0.01, and it carries a
  `FRONT_BRAKE` / `REAR_BRAKE` marker at (0; 0.045; 0).

### The scripts

| File | Role |
|---|---|
| `make_car.py` | everything at once: car, menus, performance, sound, French dub, zip (the web page runs this script) |
| `build_mx5.py` | the conversion: part split, materials, lights, wheels, brakes, levels of detail, textures, performance and sound |
| `fe_badges.py` | brand logo and model name in the menus (`FRONTEND/FRONTB.LZC`) |
| `attrib360.py` | attribute database (`ATTRIBUTES.BIN`): collections, class fields, writing values and references |
| `save360.py` | 360 save: money, unlocking all parts, checksums |
| `dxt.py` | DXT1/DXT5 compression in numpy, when Pillow cannot write DDS (in the browser) |
| `geo360.py`, `sol360.py`, `solids.py` | reading and writing 360 parts |
| `tpk.py`, `tpk360.py` | reading and writing texture packs |
| `jdlz.py`, `huff.py`, `xenos.py` | EA compressions and 360 texture tiling |
| `zzdata.py`, `xdvdfs.py` | reading the disc image and the `ZZDATA` archives |
| `names.py` | recovers the names of materials and textures from their hashes |
| `chunks.py`, `dump_tex.py` | file inspection (chunk tree, textures as PNG) |
| `pack_zzdata.py`, `preview_car.py` | plan B and preview |

## The save (`save360.py`)

```bash
python save360.py DENIS --money 2000000 --unlock-all --out DENIS_modifiee
```

- Format: `MC02`, 62 688 bytes, the PC version layout with big-endian values.
- Checks to rewrite after any change, in this order:
  1. the MD5 of `[0x34, fin - 16)`, in the last 16 bytes;
  2. three big-endian EA CRC32s: `0x10` over `[0x1C, 0x24)`, `0x14` over `[0x24, fin)`, then `0x18`
     over `[0x00, 0x18)`. Without them, the game says the save is damaged.
- `--unlock-all` sets byte `0xE895` (`CareerModeHasBeenCompletedAtLeastOnce`) to 1. All parts,
  all performance levels and all decal slots become available, in career as well as in quick race.
  Progress does not change. Tested on Switch.
- On the Switch, the save read by the game is
  `sdmc:/switch/nfsmw-nx/nfsmw/<profil>/454107D9/00000001/<nom>/<nom>`. The
  `sdmc:/switch/nfsmw-nx/saves/` folder only keeps copies of it, which the game never reads again.
- The web editor [nfsmw-save-editor](https://github.com/x07x08/nfsmw-save-editor) also reads
  360 saves since our contribution ([x07x08/nfsmw-save-editor#6](https://github.com/x07x08/nfsmw-save-editor/pull/6)).
