# Need for Speed Underground et Underground 2 (Xbox USA)

La MX-5 RF remplace la **Mazda Miata**, qui est dans les deux jeux : elle garde son son moteur, sa
marque Mazda et sa place dans le jeu. Pour les portages Switch
[nfsu1-sw](https://github.com/antoxa2584x/nfsu1-sw) et [nfsu2-sw](https://github.com/antoxa2584x/nfsu2-sw),
qui font tourner la version Xbox USA extraite dans `sdmc:/switch/nfsu1x/game/` et
`sdmc:/switch/nfsu2x/game/`.

```bash
python make_car.py --game ug1 --iso "Need for Speed - Underground (USA).iso" --kn5 mazda_mx5_rf.kn5 --zip u1_mx5.zip --top closed
python make_car.py --game ug2 --iso "Need for Speed - Underground 2 (USA).iso" --kn5 mazda_mx5_rf.kn5 --zip u2_mx5.zip --top open
```

- **Underground** : le zip contient `game/CARS/MIATA/GEOMETRY.BIN` et `TEXTURES.BIN`.
- **Underground 2** range ses fichiers dans `NFSUNDER/ZZDATA*.BIN` (index `NFSUNDER/ZDIR.BIN`).
  Le zip contient les deux fichiers en clair (`game/CARS/MIATA/…`) et, dans `planB/`, le
  `ZZDATA2.BIN` du jeu avec la MX-5 à la place de la Miata (mêmes secteurs : les nouveaux
  fichiers sont plus petits) et le `ZDIR.BIN` avec leurs nouvelles tailles.

## Ce que fait la conversion

Le modèle vient du convertisseur de Most Wanted (`build_mx5.collect` : mêmes pièces, mêmes
matériaux), déplacé pour que ses roues tombent où le jeu met celles de la Miata (CarTypeInfo de
`GLOBALB` : essieux à x = 1,03 et −1,26, centres des roues à z = 0,122). Puis, solide par solide,
sur le fichier de la Miata :

- pièces de série (caisse, base avec l'habitacle et les vitres, capot, phares, feux,
  rétroviseurs) : celles de la MX-5, en trois ou quatre niveaux de détail ;
- carrosseries larges, capots et phares des kits : copies de ceux de la MX-5 ;
- pare-chocs, bas de caisse, toits, ailerons, moteur, échappement, portes (U2) et pièces de
  décalcomanies des kits : un triangle invisible chacun, leurs repères gardés et déplacés
  (échappements, plaque, halos des feux) ;
- roues et freins : ceux du jeu.

`GEOMETRY.BIN` reste toujours plus petit que celui de la Miata (le jeu a la mémoire pour ça) :
les budgets de triangles baissent tant qu'il ne l'est pas.

Textures : les images de la MX-5 (planche habitacle / plastiques / détails, feux) prennent la
place de textures de la Miata que la voiture n'utilise plus (moteurs), au même format (DXT1) ;
peinture : celle du jeu (`MIATA_SKIN1`).

## Les formats

| | Underground | Underground 2 |
|---|---|---|
| en-tête de solide (0x134011) | 176 octets, nom en 0x94 | 192 octets, nom en 0xA4 |
| sommet (0x134B01) | 36 octets : position, couleur, uv, normale | 32 octets : position, uv, normale |
| groupe (0x134B02) | 64 octets : boîte, nombre d'indices, texture, drapeaux, premier indice, 0, shader | idem |
| indices (0x134B03) | listes de triangles (u16) | idem |
| table 0x134004 | 20 octets | 24 octets |
| textures | flux JDLZ des pixels, infos dans 0x33310004 | flux JDLZ ou HUFF : pixels + infos (124) + infos Xbox (60) |

`geo_ug.py` relit et réécrit à l'octet près les `GEOMETRY.BIN` de la Miata (U1 et U2) et de
la RX-7 ; `tpk_ug.py` réécrit à l'identique les `TEXTURES.BIN`. Les noms des morceaux
(0x134011 ESOLID, 0x134B00 XBOX_PLATINFO, 0x134017-19 lissage des normales…) sont ceux d'EA,
d'après la [décompilation de Most Wanted](https://github.com/dbalatoni13/nfsmw).

## Conduite et nom (options de `make_car.py`, actives par défaut)

- `--perf rf184` (`perf_ug.py`) : le CarTypeInfo de la Miata (bloc 0x34600 de
  `GLOBAL/GLOBALB.BUN`, le même compressé JDLZ dans `GLOBALB.LZC`) reçoit les chiffres d'une
  MX-5 RF 2.0 184 ch : 1125 kg (inertie recalculée), couple réel (9 points du ralenti au
  rupteur), 7500 / 8000 tr/min, boîte 6 de la ND et pont 3,454, plus d'adhérence (arrière > avant),
  freins et appuis du niveau RX-7 / RX-8 ; les améliorations moteur / ECU / turbo / pneus suivent.
  `--wheels mx5` : empattement 2,309 m, voies 1,495 / 1,505 m, pneus 205/45 R17.
- `--names on` (`lang_ug.py`, `fe_ug.py`) : « MX-5 RF » dans toutes les langues
  (`CAR_NAME_MIATA`, `FULL_NAME_MIATA`… ; U1 en UTF-16, U2 en 8 bits) et le badge
  « Mazda / MX-5 RF » (`SECONDARY_LOGO_MIATA`, `_MX5`, `_MIATA_RO`, DXT3 256x64).
- Underground 2 : ces fichiers vont dans un nouveau `ZZDATA12.BIN` ; `zdir_ug2.py` redirige
  leurs entrées (toutes les copies, ZZDATA2 et ZZDATA5) dans n'importe quel `ZDIR.BIN`, VF
  comprise (`--vf-zzdata10` : le texte français de la VF reçoit aussi le nom).
  `make_extras.py` fait seulement ces fichiers, sans refaire la voiture.
