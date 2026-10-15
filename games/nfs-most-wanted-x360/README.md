# Need for Speed: Most Wanted (2005), Xbox 360

🇬🇧 [English version](README.en.md)

La MX-5 RF remplace la voiture de ton choix (testé en jeu : la **Lexus IS 300**, la première
voiture de la carrière). Fait pour la version **Xbox 360** du jeu, telle que la fait tourner le
portage Switch [nfsmw-nx](https://github.com/StevensND/nfsmw-nx). Les fichiers ne conviennent pas à
la version PC : la géométrie et les textures n'y sont pas au même format.

État : **fonctionne sur Switch** (11/10/2026).

- Carrosserie, toit noir, grille, habitacle et pilote (celui de l'Elise, recalé dans le siège).
- Toit fermé (RF) ou décapoté (`--top open`).
- Logo Mazda et nom « MX-5 Miata » dans les menus ; capots et kits du tuning = ceux de la MX-5.
- Performances d'une MX-5 RF 2.0 184 ch ; son moteur Miata du jeu.
- La radio de la police l'appelle « Mazda » (`--police keep` : la marque de la voiture remplacée).
- Jantes et freins : ceux de la voiture remplacée (les jantes de la MX-5 ne s'affichent pas encore).
- Couleur : dans l'atelier du jeu ; la plus proche du Deep Crystal Blue est **Métallisé n° 75**.

## Le plus simple : la page ou `make_car.py`

La [page du projet](https://soaresden.github.io/MazdaMx5-nd-rf-ingames/nfs-most-wanted/) fait tout dans le navigateur.
En ligne de commande, `make_car.py` fait la même chose et écrit un zip prêt à copier :

```bash
python make_car.py --iso "NFS Most Wanted (X360).iso" --kn5 mazda_mx5_rf.kn5 --zip mx5.zip [--car IS300] [--top open] [--sound miata|keep] [--perf rf184|keep] [--logo MAZDA|none] [--name badge.png] [--vf]
```

`--vf` : à cocher si la VF de nfsmw-nx est installée. Son `GLOBALMEMORYFILE.BIN` masque les textes
anglais, et le nôtre doit faire pareil, sinon les menus repassent en anglais.

Les sections suivantes détaillent les outils séparés que `make_car.py` enchaîne.

## Fabriquer la voiture (`build_mx5.py`)

Choisis la voiture à remplacer avec `--car` : c'est le nom de son dossier dans `CARS`, par exemple
`IS300` pour la Lexus du début de carrière, ou `ELISE`.

```bash
python build_mx5.py --iso "NFS Most Wanted (X360).iso" --kn5 ks_mazda_mx5_rf/mazda_mx5_rf.kn5 --out build --car IS300 [--base-root <ton game_root actuel>] [--top open]
```

Le script écrit dans `build/` :

- `CARS/<VOITURE>/GEOMETRY.BIN` et `TEXTURES.BIN`, chacun à la taille exacte du fichier d'origine.
  C'est nécessaire : le jeu lit les fichiers posés à côté des archives avec la taille indiquée dans
  `ZDIR.BIN`.
- `GLOBAL/GLOBALMEMORYFILE.BIN`, si l'empattement de la voiture remplacée n'est pas celui de la
  MX-5. Ses positions de roues (`ecar/<voiture>` → `TireOffsets`, dans `ATTRIBUTES.BIN`) prennent
  celles de la MX-5, sinon les roues sortiraient des passages de roue. Passe `--base-root` pour
  partir de ton installation, par exemple avec la VF, et ne pas perdre ses modifications.

`--top open` fait une RF décapotée : les panneaux du toit, leur garniture et la vitre arrière sont
rangés, les vitres latérales baissées ; les arceaux et le pare-brise restent. Seuls `CARS/<VOITURE>`
changent : pour passer de l'une à l'autre, il suffit de recopier ces deux fichiers.

Les pièces que la MX-5 n'a pas (vitres arrière, kits carrosserie, capots du tuning, dégâts) restent
vides. Le pilote est celui de l'Elise, recalé dans le siège de la MX-5.

Les jantes et les freins restent par défaut ceux de la voiture remplacée, posés aux positions de
roues de la MX-5. Avec `--mx5-wheels`, le script convertit ceux de la MX-5, mais le jeu ne les
dessine pas encore : ils manquent même dans les passes d'ombre.

Tout ce qui n'est ni peinture, ni vitre, ni phare (plastiques, grille, toit noir, caoutchoucs,
chromes, rétroviseurs, bas de caisse, détails, intérieur) utilise le matériau `DULLPLASTIC` et une
seule texture de 512 × 512, rangée sous le nom de la Lexus `IS300_INTERIOR` :
- en haut à gauche, l'image du cockpit ;
- en haut à droite, celles des bas de caisse et des détails ;
- en bas, des carrés unis (noir, gris, blanc), où pointent les UV des pièces unies.

Ce qu'ont montré les essais sur Switch (test des carrés, 11/10/2026) :
- le jeu ne dessinait aucun groupe qui utilisait une de nos textures unies séparées (32 × 32,
  puis 256 × 128), quel que soit son nom ; l'atlas, lui, s'affiche ;
- il ignore la couleur des sommets : la couleur doit être dans la texture ;
- avec nos textures, les matériaux `MOLDINGS`, `INTERIOR` et `HEADLIGHTREFLECTOR` ne dessinaient
  rien ; `DULLPLASTIC`, `CARSKIN` et `LICENSEPLATE` s'affichent.

Les images du mod Assetto Corsa ont un alpha à 0 (c'est la brillance, pas la transparence) :
`build_textures` le supprime avant tout redimensionnement, sinon Pillow multiplie les couleurs par
l'alpha et l'image devient noire.

Les capots du tuning (`STYLExx_HOOD`) et les kits carrosserie (`KIT01` à `KIT04`) reçoivent le capot
et la caisse de la MX-5, un niveau de détail plus bas pour tenir dans la taille du fichier.

`MX5_DIAG=1` (une couleur par groupe, inutile puisque le jeu ignore la couleur des sommets) et
`MX5_SQUARES=1` (rangées de carrés devant le pare-chocs, une par matériau ou texture) fabriquent les
versions de diagnostic.

Le jeu ne permet pas d'ajouter une voiture sans modifier le portage : le nombre de voitures est
figé dans le code. Sur PC, c'est ce que fait NFSMW Unlimiter.

Aperçu de la voiture telle que le jeu l'assemble :

```bash
python preview_car.py --iso "NFS Most Wanted (X360).iso" build/CARS/IS300/GEOMETRY.BIN apercu.png --car IS300 --globalmem build/GLOBAL/GLOBALMEMORYFILE.BIN
```

### Logo et nom dans les menus

Dans les menus, le logo de la marque et le nom du modèle (« IS 300 ») sont des images de
`FRONTEND/FRONTB.LZC` :
- `CARSELECT_MANUFACTURER_<MARQUE>` : 128×64 en DXT5 ;
- `SECONDARY_LOGO_<VOITURE>` : 256×64 en DXT5.

Les deux sont blanches sur fond transparent, avec 3 mipmaps.

`fe_badges.py` copie le logo d'une autre marque par-dessus celui de la voiture (tous les logos ont
le même format). Il dessine aussi le nom à partir d'une ou plusieurs images, un dessin sombre sur
fond clair ou blanc sur fond transparent, mises côte à côte. `image.png:x0,y0,x1,y1` n'en garde
qu'un morceau.

```bash
python fe_badges.py --iso "NFS Most Wanted (X360).iso" --out build --car IS300 --logo MAZDA --name mx5.png --name miata.png:0,0,560,330 --preview badges.png
```

Le fichier recompressé doit tenir dans la taille d'origine (5 703 541 octets).
- `jdlz.splice` ne réencode que les octets changés.
- Si ça ne tient pas, l'outil recompresse tout : notre compresseur fait environ 2 Ko de moins par
  Mo que celui d'EA, ce qui laisse environ 35 Ko de marge.

## Installer sur la Switch

### Plan A : fichiers posés à côté des archives

Copie le contenu de `build/` dans `sdmc:/switch/nfsmw-nx/game_root/` : les dossiers `CARS` et,
s'il y en a, `GLOBAL` et `FRONTEND`.

Le jeu essaie toujours d'ouvrir un fichier « en clair » avant d'aller le chercher dans les archives
`ZZDATA`. Ça marche pour les voitures : le log du portage affiche
`abrir 'D:\CARS\ELISE\GEOMETRY.BIN' (abierto)`.

### Plan B : la voiture écrite dans l'archive du jeu (inutile si le plan A marche)

```bash
python pack_zzdata.py --iso "NFS Most Wanted (X360).iso" --src build --out build/game_root [--zdir <ton ZDIR.BIN actuel>]
```

Le script écrit `ZZDATA2.BIN` et `ZDIR.BIN` :

- `ZZDATA2.BIN` (394 Mo) : la MX-5 y prend la place de l'Elise ; tout le reste est identique et
  l'archive garde sa taille.
- `ZDIR.BIN` : seules les 2 entrées de l'Elise changent.

Sauvegarde tes deux fichiers d'origine, puis copie les nouveaux dans `game_root/NFS/`.

Si tu as déjà modifié ton `ZDIR.BIN`, par exemple avec la
[VF de nfsmw-nx](https://github.com/StevensND/nfsmw-nx/tree/main/tools/french-dub), passe-le avec
`--zdir` pour garder ces modifications.

## Image disque pour Xenia (`make_iso.py`)

Une nouvelle image Xbox 360 avec des dossiers posés par-dessus les fichiers du disque (le dernier
gagne, noms sans casse), par exemple la VF de nfsmw-nx puis la MX-5 :

```bash
python make_iso.py --iso "Need for Speed - Most Wanted (Europe).iso" --add "Patch VF/game_root"                    --add "MX5 RF/FINAL/game_root" --add "MX5 RF/FINAL/variante_decapotee/game_root"                    --out "Need for Speed - Most Wanted (Europe) VF MX-5 RF.iso"
```

Le jeu ouvre un fichier en clair avant de le chercher dans les archives (plan A), comme sur la
Switch : les fichiers de la MX-5 restent des fichiers à part, vérifiés contre la taille que donne
`ZDIR.BIN`. Les `NFS/PAD*.BIN` (remplissage qui place les données sur le vrai disque) sont laissés
de côté (`--keep-pad` pour les garder) : 5,1 Go au lieu de 7,8. L'image est un XDVDFS simple
(système de fichiers au secteur 32), relue à la fin. Testé dans Xenia le 15/10/2026 : VF, et la MX-5 à la place de la Lexus IS300.

## Limites

- Les vinyles sont dessinés pour la forme de la voiture remplacée.
- Les jantes et freins restent ceux de la voiture remplacée.
- Les plastiques et chromes sont mats : ils passent tous par le matériau `DULLPLASTIC`, le seul
  qui s'affiche avec nos textures (voir plus haut).
- Les pièces sont simplifiées pour respecter les limites du moteur (section suivante). Les
  niveaux de détail B à E sont tirés du niveau A ; capots et kits du tuning reprennent un niveau
  plus bas pour tenir dans la taille du fichier.
- Seule l'IS300 a été essayée en jeu ; les autres voitures sont construites de la même façon.

## Les limites du moteur

Une caisse trop lourde fait planter le jeu dès qu'il charge la voiture :
`Unhandled guest access violation: read of guest 0x00000018`, juste après la lecture de la pièce.

| Par pièce (`eSolid`) | Maximum sur les 31 voitures du disque | Limite que s'impose `build_mx5.py` |
|---|---|---|
| groupes de matériaux | 18 | 16 |
| triangles | 9 338 | 8 500 |
| sommets | 11 280 | 11 000 |
| triangles par groupe | 1 000 | 1 000 |
| taille | 589 Ko | environ 300 Ko |

Pour tenir dans ces limites, `common/qem.py` simplifie les maillages par métrique quadrique. Les
bords des panneaux et les coutures de texture sont préservés.

## Le format Xbox 360

Pour le format PC, la référence est la documentation de
[47PADO47/nfs-mw](https://github.com/47PADO47/nfs-mw/tree/main/docs/formats). Sur Xbox 360, ce qui
change :

### Géométrie (`GEOMETRY.BIN`)

`geo360.py` relit et réécrit l'Elise d'origine **à l'octet près**.

- **Structure** : les chunks et les en-têtes de pièces (`0x134011`) restent en little-endian,
  comme sur PC.
- **Groupe de matériau** (`0x134B02`) : 256 octets, aligné sur 0x80.

  | Offset | Contenu |
  |---|---|
  | `+0x00` | boîte englobante |
  | `+0x18` | premier indice |
  | `+0x1C` | type : 7 pour un flux de sommets, 8 pour deux flux (cartes normales) |
  | `+0x20` | clé, liée au matériau d'éclairage (voir plus bas) |
  | `+0x24` | drapeaux |
  | `+0x28` | nombre d'indices (u16) |
  | `+0x2A` | 6 octets : matériau d'éclairage, puis textures diffuse, normale, hauteur, spéculaire, opacité |
  | `+0x58` | taille du tampon de sommets |
  | `+0x5C` | `00 00 20 80` (pas de 32 octets) |

- **Sommets** (`0x134B01`, aligné sur 0x80, rempli de `0x11`) : un tampon par groupe, précédé d'un
  chunk `0x134C02` vide. Chaque sommet fait 32 octets, en **big-endian** :
  - position (3 float) ;
  - UV (2 float) ;
  - couleur ARGB (occlusion ambiante) ;
  - normale en 4 × int16 (w = 32767).

  Les groupes de type 8 ont deux tampons, de 24 et 16 octets.
- **Indices** (`0x134B03`, aligné sur 0x20) : u16 **big-endian**. Chaque groupe s'arrête à 3 000
  indices.
- **Lissage des normales** : les chunks `0x134017` à `0x134019` viennent **après** le maillage. On
  peut les retirer.
- **Remplissage** : le fichier se termine par des chunks vides, et l'en-tête `0x134002` contient la
  taille totale du fichier.

**La clé `+0x20`** : il n'en existe que 103 sur tout le disque, et chacune va toujours avec **un
seul** matériau d'éclairage et les mêmes drapeaux, quelles que soient la voiture et la texture.
`build_mx5.py` ne prend que des combinaisons clé + drapeaux + matériau qui existent sur le disque,
et seulement les 30 matériaux d'éclairage que portent les voitures du jeu.

### Textures (`TEXTURES.BIN`)

`tpk360.py` écrit ce format. La forme est compressée, comme sur PC :

- chaque texture est compressée en JDLZ ou HUFF et suivie de `TextureInfo` (0x7C) et d'un
  enregistrement plateforme de 0x20 octets ;
- format `0x1A200152` pour le DXT1, `0x1A200154` pour le DXT5 ;
- pixels **entrelacés Xenos**, mots de 16 bits inversés, surface alignée sur 32 × 32 blocs.

**Compression JDLZ** : le décodeur du jeu (`JLZDecompress` dans la
[décompilation](https://github.com/dbalatoni13/nfsmw/blob/main/src/Speed/Indep/Src/Misc/LZCompress.cpp))
fonctionne ainsi :

- il **décompte les octets d'entrée** (`while (Size != 0)`) au lieu de s'arrêter quand la sortie est
  pleine ;
- il recharge un octet d'indicateurs **juste après** l'instruction qui vide le registre, y compris
  après la dernière.

Le compresseur d'EA (`JLZCompress`) suit donc trois règles, et `jdlz.py` les reproduit :

- il réserve l'octet d'indicateurs suivant dès que l'actuel est plein ;
- sa boucle fait un tour de plus que les données, ce qui ajoute un littéral ;
- les bits inutilisés valent 1.

Un flux qui ne respecte pas ces règles fait déborder le décodeur. Le jeu plante alors sur un
pointeur invalide : `read of guest 0x00000018`, ou la valeur `0xDFDFDFDF`.

`jdlz.game_decompress` est une copie de ce décodeur, et `tpk360.py` s'en sert pour vérifier chaque
texture écrite.

### Noms utiles

- **Phares et feux** : les pièces utilisent les noms génériques `HEADLIGHT_LEFT`,
  `BRAKELIGHT_LEFT`… Le jeu les remplace par `<VOITURE>_KIT00_HEADLIGHT_OFF/ON` et
  `<VOITURE>_KIT00_BRAKELIGHT_OFF/ON`, qui doivent se trouver dans la pochette de textures de la
  voiture.
- **Peinture** : le matériau d'éclairage `CARSKIN` est remplacé par la peinture choisie. La
  texture `<VOITURE>_SKIN1` est fabriquée par le jeu.
- **Roues** : `ecar/elise` dans `GLOBAL/ATTRIBUTES.BIN` (en big-endian sur 360) donne :
  - avant (1,11 ; ±0,83) ;
  - arrière (−1,19 ; ±0,86) ;
  - rayon 0,31.

  Le pneu est un modèle de roue droite, face extérieure à y = −0,01, et il porte un repère
  `FRONT_BRAKE` / `REAR_BRAKE` à (0 ; 0,045 ; 0).

### Les scripts

| Fichier | Rôle |
|---|---|
| `make_car.py` | tout en une fois : voiture, menus, performances, son, VF, zip (la page web fait tourner ce script) |
| `build_mx5.py` | la conversion : répartition des pièces, matériaux, feux, roues, freins, niveaux de détail, textures, performances et son |
| `fe_badges.py` | logo de la marque et nom du modèle dans les menus (`FRONTEND/FRONTB.LZC`) |
| `attrib360.py` | base d'attributs (`ATTRIBUTES.BIN`) : collections, champs des classes, écriture de valeurs et de références |
| `save360.py` | sauvegarde 360 : argent, déblocage de toutes les pièces, sommes de contrôle |
| `dxt.py` | compression DXT1/DXT5 en numpy, quand Pillow ne sait pas écrire de DDS (dans le navigateur) |
| `geo360.py`, `sol360.py`, `solids.py` | lecture et écriture des pièces 360 |
| `tpk.py`, `tpk360.py` | lecture et écriture des pochettes de textures |
| `jdlz.py`, `huff.py`, `xenos.py` | compressions d'EA et entrelacement des textures 360 |
| `zzdata.py`, `xdvdfs.py` | lecture de l'image disque et des archives `ZZDATA` |
| `names.py` | retrouve les noms des matériaux et des textures à partir de leurs empreintes |
| `chunks.py`, `dump_tex.py` | inspection des fichiers (arbre des chunks, textures en PNG) |
| `pack_zzdata.py`, `preview_car.py` | plan B et aperçu |

## La sauvegarde (`save360.py`)

```bash
python save360.py DENIS --money 2000000 --unlock-all --out DENIS_modifiee
```

- Format : `MC02`, 62 688 octets, la disposition de la version PC avec des valeurs big-endian.
- Contrôles à réécrire après toute modification, dans cet ordre :
  1. le MD5 de `[0x34, fin - 16)`, dans les 16 derniers octets ;
  2. trois CRC32 d'EA big-endian : `0x10` sur `[0x1C, 0x24)`, `0x14` sur `[0x24, fin)`, puis `0x18`
     sur `[0x00, 0x18)`. Sans eux, le jeu dit que la sauvegarde est endommagée.
- `--unlock-all` met à 1 l'octet `0xE895` (`CareerModeHasBeenCompletedAtLeastOnce`). Toutes les
  pièces, tous les niveaux de performance et tous les emplacements d'autocollants deviennent
  disponibles, en carrière comme en course rapide. La progression ne change pas. Testé sur Switch.
- Sur la Switch, la sauvegarde lue par le jeu est
  `sdmc:/switch/nfsmw-nx/nfsmw/<profil>/454107D9/00000001/<nom>/<nom>`. Le dossier
  `sdmc:/switch/nfsmw-nx/saves/` n'en garde que des copies, que le jeu ne relit jamais.
- L'éditeur web [nfsmw-save-editor](https://github.com/x07x08/nfsmw-save-editor) lit aussi les
  sauvegardes 360 depuis notre ajout ([x07x08/nfsmw-save-editor#6](https://github.com/x07x08/nfsmw-save-editor/pull/6)).
