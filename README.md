# Mazda MX-5 RF (ND) dans les jeux de voitures

🇬🇧 [English version](README.en.md)

J'adore cette voiture. Le projet : la **convertir dans les jeux de voitures que j'aime** pour
pouvoir la conduire, sur **plusieurs générations de consoles**, de la PS1 à la Xbox 360.

La voiture : une Mazda MX-5 RF (ND2) 2.0 de 184 ch **Deep Crystal Blue**, toit
noir brillant, jantes sombres et étriers Brembo rouges.

![La MX-5 RF décapotée dans le garage de Need for Speed Most Wanted](docs/mx5_en_jeu.jpg)

## Fabriquer la voiture en un clic

**➜ [soaresden.github.io/MazdaMx5-nd-rf-ingames](https://soaresden.github.io/MazdaMx5-nd-rf-ingames/)**,
le hub du projet, avec une page par jeu (pour l'instant :
[Need for Speed Most Wanted](https://soaresden.github.io/MazdaMx5-nd-rf-ingames/web/nfsmw.html)).

Chaque page fabrique la voiture **dans ton navigateur**, à partir de **tes** fichiers. Rien n'est
envoyé sur internet, et ce dépôt ne contient **aucun fichier du jeu ni du modèle 3D**.

1. Choisis ton image disque du jeu et le modèle Assetto Corsa (voir plus bas).
2. Choisis la voiture remplacée, le toit (fermé ou décapoté), le son moteur, les performances,
   le logo, et éventuellement ton propre badge pour le nom.
3. Clique sur **Fabriquer** : en une à deux minutes, la page te donne un `.zip` avec un dossier
   `game_root/` à copier sur la carte SD, et un `LISEZMOI.txt`.

## Les jeux

| Jeu | Plateforme | Voiture remplacée | État |
|---|---|---|---|
| [Need for Speed: Most Wanted (2005)](games/nfs-most-wanted-x360/) | Xbox 360, sur Switch via [nfsmw-nx](https://github.com/StevensND/nfsmw-nx) | au choix (testé : Lexus IS 300) | **fonctionne** |
| [Gran Turismo](games/gran-turismo-ps1/) | PS1 (PAL), image .bin/.cue pour DuckStation | les Eunos Roadster (neuves, d'occasion) | **en test** (fonctionne en jeu) |
| [Need for Speed: Underground](games/nfs-underground-xbox/) | Xbox USA, sur Switch via [nfsu1-sw](https://github.com/antoxa2584x/nfsu1-sw) | Mazda Miata | **en test** |
| [Need for Speed: Underground 2](games/nfs-underground-xbox/) | Xbox USA, sur Switch via [nfsu2-sw](https://github.com/antoxa2584x/nfsu2-sw) | Mazda Miata | **en test** |
| Need for Speed: Carbon | à définir | — | prévu |
| Gran Turismo 2 | PS1 | — | prévu |

### Need for Speed: Most Wanted, ce que fait la conversion

- **Modèle** : le modèle détaillé d'Assetto Corsa (211 000 triangles), simplifié sous les limites
  du moteur (8 500 triangles par pièce) avec cinq niveaux de détail, habitacle et pilote compris.
- **Toit** : RF fermé, ou décapoté (panneaux du toit et vitre arrière rangés, vitres baissées).
- **Menus** : logo Mazda et nom « MX-5 Miata » à la place de ceux de la voiture remplacée.
- **Tuning** : capots et kits carrosserie du jeu remplacés par la carrosserie de la MX-5.
- **Performances** : celles d'une MX-5 RF 2.0 de 184 ch (1 125 kg, boîte 6, zone rouge à
  7 500 tr/min, autobloquant).
- **Son** : le jeu contient un enregistrement de **Mazda Miata** qu'aucune voiture n'utilise ; la
  MX-5 le reprend.
- **Peinture** : celle de l'atelier du jeu. La plus proche du Deep Crystal Blue est
  **Métallisé n° 75**.

Le détail technique (formats, limites du moteur, ce qui a été appris sur Switch) est dans
[games/nfs-most-wanted-x360](games/nfs-most-wanted-x360/).

## Ce qu'il faut

- **Ta copie du jeu**, en image disque (pour Most Wanted : l'image Xbox 360, `.iso`).
- **Le modèle** : le mod Assetto Corsa **`ks_mazda_mx5_rf`**
  ([Mazda MX-5 RF Hardtop sur Modland](https://www.modland.net/assetto-corsa-mods/cars/mazda-mx-5-rf-hardtop.html)), extrait ; seul le fichier `mazda_mx5_rf.kn5` sert.
  Il n'est pas fourni ici.
- Pour la page : un navigateur récent (Chrome, Edge, Firefox). Pour la ligne de commande :
  Python 3.10 ou plus récent avec `numpy` et `Pillow` :

  ```bash
  pip install -r requirements.txt
  ```

  ```bash
  python games/nfs-most-wanted-x360/make_car.py --iso "NFS Most Wanted (X360).iso" --kn5 mazda_mx5_rf.kn5 --zip mx5.zip --car IS300 --top open --vf
  ```

## Le dépôt

| Dossier | Contenu |
|---|---|
| `index.html` | le hub : le projet et la liste des jeux |
| `web/` | une page par jeu (`nfsmw.html`…) et le worker qui fait tourner les outils Python dans le navigateur ([Pyodide](https://pyodide.org)) |
| `common/` | ce qui sert à tous les jeux : lecteur KN5 d'Assetto Corsa, chargement du modèle, simplification de maillage (QEM), petit moteur de rendu pour les aperçus |
| `games/<jeu>/` | les outils et la documentation propres à chaque jeu |
| `docs/` | images du README |

## Remerciements

- **[StevensND](https://github.com/StevensND)** pour [nfsmw-nx](https://github.com/StevensND/nfsmw-nx),
  le portage de Most Wanted sur Switch, et ses journaux qui ont permis de tout déboguer.
- **Kunos Simulazioni** pour le modèle de la MX-5 RF d'Assetto Corsa (`ks_mazda_mx5_rf`), et
  [Modland](https://www.modland.net/assetto-corsa-mods/cars/mazda-mx-5-rf-hardtop.html) qui le met à disposition.
- **[x07x08](https://github.com/x07x08)** pour [nfsmw-save-editor](https://github.com/x07x08/nfsmw-save-editor),
  auquel ce projet a ajouté les sauvegardes Xbox 360.
- **[sprintstate](https://github.com/sprintstate)** pour [nfs-mw-save-editor](https://github.com/sprintstate/nfs-mw-save-editor)
  et sa description des CRC des sauvegardes.
- **[dbalatoni13](https://github.com/dbalatoni13)** et les contributeurs de la
  [décompilation de NFS Most Wanted](https://github.com/dbalatoni13/nfsmw), qui a expliqué le
  déblocage des pièces.
- **[vgmstream](https://github.com/vgmstream/vgmstream)** pour la lecture des sons d'EA.
- **OfficialWhippy** pour le dessin « MX-5 » et l'auteur du « Miata » manuscrit, réunis dans le
  badge des menus.

Need for Speed est une marque d'Electronic Arts, Mazda, MX-5 et Miata sont des marques de Mazda
Motor Corporation. Projet de fan, sans lien avec eux.

Le code est sous licence [GPL-3.0](LICENSE).
