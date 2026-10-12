"""Make the MX-5 RF for Need for Speed Underground (Xbox USA, played on the Switch with nfsu1-sw) as
a zip, in place of the Mazda Miata.

python make_car.py --iso "Need for Speed - Underground (USA).iso" --kn5 mazda_mx5_rf.kn5 --zip mx5.zip
                   [--top closed|open]

The zip holds game/CARS/MIATA/GEOMETRY.BIN and TEXTURES.BIN, to copy over the extracted disc in
sdmc:/switch/nfsu1x/game/, and a LISEZMOI.txt. Everything is made from the player's own disc image
and Assetto Corsa model: nothing of either is in this repository.
"""
import argparse
import io
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs-most-wanted-x360'))

import build_ug1   # noqa: E402
import xdvdfs      # noqa: E402

FILES = ('CARS/MIATA/GEOMETRY.BIN', 'CARS/MIATA/TEXTURES.BIN')

LISEZMOI = """MX-5 RF (ND) pour Need for Speed Underground (Xbox USA / Switch avec nfsu1-sw)
==============================================================================

La MX-5 RF remplace la Mazda Miata (son, marque et place dans le jeu de la Miata).
Toit : {top}

INSTALLER (jeu fermé)
Garder une copie de sdmc:/switch/nfsu1x/game/CARS/MIATA/, puis copier le dossier game/ du zip
dans sdmc:/switch/nfsu1x/ en remplaçant les fichiers :
  game/CARS/MIATA/GEOMETRY.BIN
  game/CARS/MIATA/TEXTURES.BIN
Pour revenir à la Miata : remettre les deux fichiers d'origine.

Kits de carrosserie : capots, phares et carrosseries larges restent ceux de la MX-5 ; les
pare-chocs, bas de caisse, ailerons et prises d'air des kits n'apparaissent pas.

Fait avec https://github.com/soaresden/MazdaMx5-nd-rf-ingames à partir de TA copie du jeu et du modèle.
"""


def read_iso(iso, name):
    files = xdvdfs.list_files(iso)
    size, off = files[name]
    with open(iso, 'rb') as f:
        f.seek(off)
        return f.read(size)


def generate(iso, kn5, top='closed', log=print):
    """{path in the zip: bytes}."""
    files = xdvdfs.list_files(iso)
    for name in FILES:
        if name not in files:
            raise ValueError("%s introuvable : ce n'est pas l'image de NFS Underground (Xbox)" % name)
    geo, tex = (read_iso(iso, n) for n in FILES)
    log('la MX-5 (géométrie et textures)')
    g, t = build_ug1.build(geo, tex, kn5, top, log=log)
    return {'game/' + FILES[0]: g, 'game/' + FILES[1]: t,
            'LISEZMOI.txt': LISEZMOI.format(top='ouvert' if top == 'open' else 'fermé').encode('utf-8')}


def write_zip(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for k, v in entries.items():
            z.writestr(k, v)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--iso', required=True, help='your Xbox disc image of NFS Underground (USA)')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--zip', required=True)
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    a = ap.parse_args()
    entries = generate(a.iso, a.kn5, a.top)
    os.makedirs(os.path.dirname(os.path.abspath(a.zip)), exist_ok=True)
    open(a.zip, 'wb').write(write_zip(entries))
    print('written', a.zip, sorted(entries))


if __name__ == '__main__':
    main()
