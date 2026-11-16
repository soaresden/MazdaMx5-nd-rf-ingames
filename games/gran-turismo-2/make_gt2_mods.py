"""The MX-5 RF for the PC port gt-2-pc (github.com/dubrovskiy-yevhen-stakelogic/gt-2-pc): a zip to
unpack into the port's data folder, instead of a new disc image. The game's files stay as they are.

python make_gt2_mods.py --disc "Gran Turismo 2 (USA) (Simulation Mode) (Rev 2).chd" --kn5 mazda_mx5_rf.kn5
                        --out gt2pc_mx5.zip [--car aminn=closed --car amivn=open ...]

The zip holds mods/mx5/, a car expansion of gt-2-pc (catalogue.version + assets/<file of GT2.VOL>),
JOUER_MX5.bat, which starts the game with GT2_CAR_EXPANSION pointing at it, and LISEZMOI.txt /
README.txt. The port's car layer only takes carobj/, carparam/, .carinfo*, .carcolor and .cclatain
(src/gt2vfs/gtfs.cpp): the menu pictures and texts stay the game's.
"""
import argparse
import io
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_gt2  # noqa: E402

FORMAT = 'gt2-car-expansion-1'
MOD = 'mods/mx5'
LAUNCHER = '\r\n'.join([
    '@echo off',
    'setlocal',
    'rem Gran Turismo 2 (gt-2-pc) with the MX-5 RF: mods\\mx5 is read over the game',
    'set "GT2_CAR_EXPANSION=%~dp0mods\\mx5"',
    'cd /d "%~dp0"',
    '"%~dp0gt2game.exe" --player %*',
    'if errorlevel 1 pause', ''])
README = {
    'LISEZMOI.txt': """La MX-5 RF pour Gran Turismo 2 sur PC (gt-2-pc)
================================================

Fait par la page https://soaresden.github.io/MazdaMx5-nd-rf-ingames/web/gt2.html à partir de ton
disque ; ne le partage pas (il contient des données du jeu).

Installer : décompresse ce zip dans le dossier de données de gt-2-pc, celui qui contient
gt2game.exe et PLAY.bat (choisi à l'installation). Puis lance JOUER_MX5.bat à la place de PLAY.bat.
PLAY.bat lance toujours le jeu d'origine : mods\\mx5 ne modifie rien du jeu.

{cars}
On les trouve chez Mazda, voitures d'occasion des années 90.

Pas encore dans gt-2-pc : l'image du titre et la description du concessionnaire restent celles
d'origine (sa couche voitures ne prend que les modèles, caractéristiques, noms et peintures).
""",
    'README.txt': """The MX-5 RF for Gran Turismo 2 on PC (gt-2-pc)
===============================================

Made by https://soaresden.github.io/MazdaMx5-nd-rf-ingames/web/gt2.html from your disc; do not
share it (it holds game data).

Install: unpack this zip into gt-2-pc's data folder, the one with gt2game.exe and PLAY.bat (chosen
when installing). Then start JOUER_MX5.bat instead of PLAY.bat. PLAY.bat still starts the original
game: mods\\mx5 changes nothing of the game.

{cars}
Found at Mazda, used cars of the 90s.

Not in gt-2-pc yet: the title picture and the dealer's description stay the original ones (its
car layer only takes the models, figures, names and paints).
"""}
OLD = {'aminn': ("MX-5 (Miata) '93", "MX-5 (Miata) '93"),
       'amivn': ("MX-5 (Miata) V-Special '93", "MX-5 (Miata) V-Special '93")}


def expansion_file(name):
    """Whether gt-2-pc's car layer takes this GT2.VOL file (src/gt2vfs/gtfs.cpp)."""
    return name.startswith(('carobj/', 'carparam/', '.carinfo')) or name in ('.carcolor', '.cclatain')


def package(new, cars):
    """The zip (bytes) from make_gt2.generate's files."""
    kept = sorted(n for n in new if expansion_file(n))
    lines = {}
    for lang, k in (('fr', 0), ('en', 1)):
        roof = {'closed': ('capotée', 'hardtop closed'), 'open': ('décapotée', 'top down')}
        lines[lang] = '\n'.join('%s -> MX-5 RF %s' % (OLD.get(c, (c, c))[k], roof[t][k]) for c, t in cars.items())
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(MOD + '/catalogue.version', FORMAT + '\n')
        for n in kept:
            z.writestr(MOD + '/assets/' + n, new[n])
        z.writestr('JOUER_MX5.bat', LAUNCHER)
        z.writestr('LISEZMOI.txt', README['LISEZMOI.txt'].format(cars=lines['fr']).replace('\n', '\r\n'))
        z.writestr('README.txt', README['README.txt'].format(cars=lines['en']).replace('\n', '\r\n'))
    return out.getvalue(), kept


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--disc', required=True, help='ton image de Gran Turismo 2 Simulation : .chd, .cue ou .bin')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 du mod Assetto Corsa')
    ap.add_argument('--out', required=True, help='le .zip à écrire')
    ap.add_argument('--car', action='append', metavar='CODE=closed|open',
                    help='MX-5 remplacée et son toit (à répéter ; par défaut aminn=closed, amivn=open)')
    a = ap.parse_args()
    cars = {}
    for c in a.car or ['%s=%s' % kv for kv in make_gt2.DEFAULT.items()]:
        code, _, top = c.partition('=')
        if code not in make_gt2.MX5 or top not in ('closed', 'open'):
            raise SystemExit('--car %s : CODE=closed|open, CODE parmi %s' % (c, ', '.join(make_gt2.MX5)))
        cars[code] = top
    _, new = make_gt2.generate(a.disc, a.kn5, cars, version='', menus_too=False)
    data, kept = package(new, cars)
    with open(a.out, 'wb') as f:
        f.write(data)
    print('%s : %d fichiers de la voiture (%s)' % (a.out, len(kept), ', '.join(kept)))


if __name__ == '__main__':
    main()
