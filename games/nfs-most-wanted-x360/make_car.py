"""Make the MX-5 RF for NFS Most Wanted (Xbox 360, played on the Switch with nfsmw-nx) as a zip.

python make_car.py --iso <your 360 disc image> --kn5 <mazda_mx5_rf.kn5> --zip mx5.zip
                   [--car IS300] [--top closed|open] [--sound miata|keep] [--perf rf184|keep]
                   [--logo MAZDA|none] [--name <badge picture> ...] [--vf]

The zip holds a game_root/ folder to copy over sdmc:/switch/nfsmw-nx/game_root/ and a LISEZMOI.txt.
Everything is made from the player's own disc image and Assetto Corsa model: nothing of the game
or of the model is in this repository. The web page (index.html at the root of the repository)
runs this same code in the browser.
"""
import argparse
import io
import os
import struct
import tempfile
import zipfile

import build_mx5
import fe_badges
import zzdata

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BADGE = os.path.join(HERE, 'assets', 'badge_mx5_miata_1024.png')

# The game's player cars (CarTypeInfo, usage "Racing") and their ManufacturerName, as the game
# spells them (the brand logo of the menus is CARSELECT_MANUFACTURER_<brand>).
CARS = {
    '911TURBO': 'PORSCHE', 'CARRERAGT': 'PORSCHE', 'VIPER': 'DODGE', 'RX8': 'MAZDA',
    'IMPREZAWRX': 'SUBARU', 'LANCEREVO8': 'MITSUBISHI', 'MUSTANGGT': 'FORD', 'CAMARO': 'CHEVEROLET',
    'GTO': 'PONTIAC', 'SLR': 'MERCEDES', 'CORVETTE': 'CHEVEROLET', 'TT': 'AUDI', 'A3': 'AUDI',
    'BMWM3GTR': 'BMW', 'SL500': 'PORSCHE', '997S': 'PORSCHE', '911GT2': 'PORSCHE',
    'BMWM3GTRE46': 'BMW', 'IS300': 'LEXUS', 'MONARO': 'HOLDEN', 'SL65': 'PORSCHE', 'ELISE': 'LOTUS',
    'FORDGT': 'FORD', 'ECLIPSEGT': 'MITSUBISHI', 'SUPRA': 'TOYOTA', 'CORVETTEC6R': 'CHEVEROLET',
    'RX7': 'MAZDA', 'RX8SPEEDT': 'MAZDA', 'MURCIELAGO': 'LAMBORGHINI', 'A4': 'AUDI',
    'GTI': 'VOLKSWAGEN', 'CAYMANS': 'PORSCHE', 'CLK500': 'MERCEDES', 'CTS': 'CADILLAC',
    'DB9': 'ASTON MARTIN', 'GALLARDO': 'LAMBORGHINI', 'COBALTSS': 'CHEVEROLET', 'BMWM3': 'BMW',
    'CLIO': 'RENAULT', 'PUNTO': 'FIAT',
}
TESTED = {'IS300'}  # tested in the game; the others are built the same way but not tried

# The French dub (tools/french-dub of nfsmw-nx) hides these entries of the preloaded pack so that
# the game reads the French files; a GLOBALMEMORYFILE.BIN of ours must hide them too.
VF_HIDDEN = (zzdata.bstringhash(zzdata.path('LANGUAGES', 'ENGLISH.BIN')), 0x21D83A59)
PACK = zzdata.path('GLOBAL', 'GLOBALMEMORYFILE.BIN')


def vf_hidden(h):
    return zzdata.bstringhash(zzdata.path('FRENCH_DUB', 'HIDDEN_%08X' % h))


def hide_english(pack):
    """The French dub's change to the preloaded pack, on our copy of it."""
    pack = bytearray(pack)
    _, count = struct.unpack_from('<II', pack, 8)
    n = 0
    for i in range(count):
        o = 16 + 20 * i
        h, = struct.unpack_from('<I', pack, o)
        if h in VF_HIDDEN:
            struct.pack_into('<I', pack, o, vf_hidden(h))
            n += 1
    return bytes(pack), n


LISEZMOI = """MX-5 RF (ND) pour Need for Speed Most Wanted (Xbox 360 / Switch avec nfsmw-nx)
===============================================================================

Voiture remplacée : {car} ({brand}){tested}
Toit : {top}    Son moteur : {sound}    Performances : {perf}    Logo : {logo}    VF : {vf}

INSTALLER (jeu fermé)
Copier le contenu du dossier game_root/ dans sdmc:/switch/nfsmw-nx/game_root/ en remplaçant les
fichiers :
{files}
Pour revenir à la voiture d'origine : supprimer ces fichiers de la carte SD.

Fait avec https://github.com/soaresden/MazdaMx5NDRF à partir de TA copie du jeu et du modèle.
"""


def generate(iso, kn5, car='IS300', top='closed', sound='miata', perf='rf184', logo='MAZDA',
             names=None, vf=False, log=print, workdir=None):
    """{path in the zip: bytes}. `iso` and `kn5` are paths (in the browser, files of Pyodide's FS)."""
    car = car.upper()
    if car not in CARS:
        raise ValueError('unknown car %s' % car)
    names = [DEFAULT_BADGE] if names is None else list(names)
    tmp = workdir or tempfile.mkdtemp(prefix='mx5_')
    log('1/3 la voiture (géométrie, textures, roues, performances, son)')
    build_mx5.main(iso, kn5, tmp, car, None, 'auto', None, (), False, perf, top, sound)
    files = {}
    for rel in (('CARS', car, 'GEOMETRY.BIN'), ('CARS', car, 'TEXTURES.BIN'),
                ('GLOBAL', 'GLOBALMEMORYFILE.BIN')):
        p = os.path.join(tmp, *rel)
        if os.path.exists(p):
            files['/'.join(rel)] = open(p, 'rb').read()
    disc = zzdata.Disc(iso)
    if vf:
        pack = files.get('GLOBAL/GLOBALMEMORYFILE.BIN') or disc.read(PACK)
        files['GLOBAL/GLOBALMEMORYFILE.BIN'], n = hide_english(pack)
        log('VF : %d entrées anglaises masquées dans GLOBALMEMORYFILE.BIN' % n)
    log('2/3 les menus (logo et nom)')
    lg = None if (logo or '').lower() in ('', 'none') else logo
    data, _, _ = fe_badges.make_frontb(disc, car, CARS[car], lg, names, verify=False, log=log)
    if data:
        files['FRONTEND/FRONTB.LZC'] = data
    log('3/3 le zip')
    out = {'game_root/' + k: v for k, v in files.items()}
    out['LISEZMOI.txt'] = LISEZMOI.format(
        car=car, brand=CARS[car], tested='' if car in TESTED else ' (pas encore testée en jeu)',
        top='ouvert' if top == 'open' else 'fermé', sound=sound or "celui d'origine",
        perf='MX-5 RF 2.0 184 ch' if perf else "celles d'origine", logo=lg or 'inchangé',
        vf='oui' if vf else 'non', files='\n'.join('  ' + k for k in files)).encode('utf-8')
    return out


def write_zip(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for k, v in entries.items():
            z.writestr(k, v)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--iso', required=True, help='your Xbox 360 disc image of NFS Most Wanted')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--zip', required=True, help='zip to write')
    ap.add_argument('--car', default='IS300', choices=sorted(CARS), help='car to replace')
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    ap.add_argument('--sound', default='miata', choices=('miata', 'keep'))
    ap.add_argument('--perf', default='rf184', choices=('rf184', 'keep'))
    ap.add_argument('--logo', default='MAZDA', help="brand logo for the menus ('none': keep)")
    ap.add_argument('--name', action='append', help='badge picture(s) (default: the MX-5 Miata badge)')
    ap.add_argument('--vf', action='store_true', help='the French dub is installed')
    a = ap.parse_args()
    entries = generate(a.iso, a.kn5, a.car, a.top, None if a.sound == 'keep' else a.sound,
                       None if a.perf == 'keep' else a.perf, a.logo, a.name, a.vf)
    open(a.zip, 'wb').write(write_zip(entries))
    print('written', a.zip, sorted(entries))


if __name__ == '__main__':
    main()
