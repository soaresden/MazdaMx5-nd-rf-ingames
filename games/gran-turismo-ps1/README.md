# Gran Turismo (PS1, PAL SCES-00984)

La MX-5 RF remplace les Eunos Roadster du jeu (neuves chez Mazda, d'occasion, versions course),
toit fermé ou décapoté. Le résultat est une image disque `.bin/.cue` pour DuckStation (et les
autres émulateurs), faite à partir de **ton** image `.chd` du jeu.

```bash
python make_car.py --chd "Gran Turismo [SCES_009.84].chd" --kn5 mazda_mx5_rf.kn5 --out "GT MX5.bin" --top closed --price 29900
```

`--car aminn` (répétable) pour ne remplacer que certaines Roadster ; par défaut toutes.
`--price 100` pour l'avoir dès le premier jour.

## Ce que fait la conversion

- **Modèle** : une coque fermée à la façon des voitures du jeu. D'abord une coque détaillée
  (≈ 56 sections × 34 points autour de la carrosserie d'Assetto Corsa), puis sa moitié droite
  simplifiée (quadriques, en gardant une surface fermée et orientée) et symétrisée : ≈ 185
  sommets et 260 faces au niveau le plus détaillé (les voitures du disque : jusqu'à 272), trois
  niveaux. Les faces sont vérifiées une par une (chaque arête deux fois, en sens inverse) et dans
  le sens des faces du jeu, sinon la PS1 ne les dessine pas.
- **Texture** : des vues de côté, de dessus, de face et d'arrière du modèle détaillé, rangées
  dans la texture 4 bits du jeu ; chaque face prend ses texels dans la vue qui la voit. 16
  palettes de 16 couleurs, dont celles de la peinture : huit peintures de la MX-5 RF
  (Deep Crystal Blue, Soul Red Crystal, Machine Grey…), feux arrière sur les palettes du freinage.
- **Données** (`CARINF.DAT`) : nom « MX-5 RF ND2 2.0 », 184 ch, 205 Nm, 1 125 kg, boîte 6,
  pneus 205/45 R17, noms des peintures, prix.
- **Menus** (`MENU_IMG.ARC`, six langues) : le nom de la voiture en image (emblème « MX-5 » et
  « RF » dans les lettres du jeu), et les vignettes du concessionnaire Mazda (nom, image de la
  MX-5, prix redessiné avec les chiffres du jeu).
- **Disque** : `CAR.DAT`, `CARINF.DAT` et `MENU_IMG.ARC` réécrits à leur place (aucun fichier ne
  bouge), secteurs refaits avec leur EDC/ECC ; le reste est la copie exacte du CHD.

## Les formats (ce qu'on a établi)

| Fichier | |
|---|---|
| `common/chd.py` | CHD v5 (cdlz / cdzl), carte compressée de Huffman, ECC des secteurs mode 2 (en-tête mis à zéro) |
| `gtarc.py` | archives `@(#)GT-ARC`, LZSS du jeu ; compresseur à analyse optimale (10 % plus serré que celui du jeu) |
| `gt1car.py` | modèles `@(#)GT-CAR` : 680 des 688 modèles du disque réécrits à l'octet près ; quads en boucle 0-1-2-3 ; produit vectoriel des faces vers l'intérieur |
| `gt1data.py`, `carinf.py` | tables `@(#)SPEC`, `@(#)COLOR`… (enregistrements + tables de chaînes) |
| `pslz.py` | exécutables compressés à l'envers (`PSLZ`) |
| `tim.py`, `slt.py`, `titles.py`, `dealer.py`, `menus.py` | images des menus (TIM 4 bits, pages 640×480 en six blocs de VRAM) |
| `shell.py`, `decimate.py`, `views.py`, `mx5scene.py`, `build_car.py`, `preview.py` | la conversion |
| `disc.py`, `make_car.py` | système de fichiers ISO 9660 et image `.bin/.cue` |

Les numéros des fichiers dans les archives (les Roadster dans `CAR.DAT`, les pages des menus)
viennent des listes de fichiers de [pez2k/gt2tools](https://github.com/pez2k/gt2tools), dont la
description des formats a beaucoup aidé (son code n'est pas repris ici).
