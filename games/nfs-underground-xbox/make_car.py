"""Make the MX-5 RF for Need for Speed Underground or Underground 2 (Xbox USA, played on the Switch
with nfsu1-sw / nfsu2-sw) as a zip, in place of the Mazda Miata.

python make_car.py --game ug1|ug2 --iso <the game's Xbox disc image (USA)> --kn5 mazda_mx5_rf.kn5
                   --zip mx5.zip [--top closed|open]

Underground: the zip holds game/CARS/MIATA/GEOMETRY.BIN and TEXTURES.BIN, to copy over the
extracted disc (sdmc:/switch/nfsu1x/game/).
Underground 2 keeps its files in NFSUNDER/ZZDATA*.BIN, found through NFSUNDER/ZDIR.BIN. The zip
holds the same two files as loose files (game/CARS/MIATA/..., if the game reads loose files) and,
in planB/, the game's ZZDATA2.BIN with the MX-5 in place of the Miata (on the same sectors: the
new files are smaller) and its ZDIR.BIN with their new sizes.
Everything is made from the player's own disc image and Assetto Corsa model.
"""
import argparse
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs-most-wanted-x360'))

import build_ug    # noqa: E402
import xdvdfs      # noqa: E402
import zzdata      # noqa: E402

FILES = ('CARS/MIATA/GEOMETRY.BIN', 'CARS/MIATA/TEXTURES.BIN')
BS = chr(92)
SECTOR = 2048

LISEZMOI = """MX-5 RF (ND) pour Need for Speed {title} (Xbox USA / Switch avec {port})
==============================================================================

La MX-5 RF remplace la Mazda Miata (son, marque et place dans le jeu de la Miata).
Toit : {top}

INSTALLER (jeu fermé)
Garder une copie des fichiers remplacés, puis copier le dossier game/ du zip dans
sdmc:/switch/{folder}/ en remplaçant les fichiers :
{files}
{planb}
Kits de carrosserie : capots, phares et carrosseries larges restent ceux de la MX-5 ; les
pare-chocs, bas de caisse, ailerons et prises d'air des kits n'apparaissent pas.

Fait avec https://github.com/soaresden/MazdaMx5-nd-rf-ingames à partir de TA copie du jeu et du modèle.
"""

PLAN_B = """
Si la Miata reste la Miata (le jeu ne lit que ses archives) : enlever game/CARS/MIATA/ et copier à
la place les deux fichiers de planB/NFSUNDER/ dans sdmc:/switch/{folder}/game/NFSUNDER/
(ZZDATA2.BIN et ZDIR.BIN, ceux d'origine sauvegardés avant).
"""

GAMES = {'ug1': dict(title='Underground', port='nfsu1-sw', folder='nfsu1x'),
         'ug2': dict(title='Underground 2', port='nfsu2-sw', folder='nfsu2x')}


def _ck_table():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else c << 1
        t.append(c & 0xFFFFFFFF)
    return t


_CK = _ck_table()


def cksum(data):
    """POSIX cksum (what the ZDIR entries hold; the game does not seem to check it)."""
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CK[(crc >> 24) ^ b]
    n = len(data)
    while n:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CK[(crc >> 24) ^ (n & 0xFF)]
        n >>= 8
    return ~crc & 0xFFFFFFFF


class Packs:
    """NFSUNDER/ZDIR.BIN and the ZZDATA files of an Underground 2 disc image."""

    def __init__(self, iso):
        self.iso = iso
        self.files = xdvdfs.list_files(iso)
        size, off = self.files['NFSUNDER/ZDIR.BIN']
        with open(iso, 'rb') as f:
            f.seek(off)
            self.zdir = bytearray(f.read(size))
        self.index = {}
        for i in range(0, len(self.zdir) - 23, 24):
            h = struct.unpack_from('<I', self.zdir, i)[0]
            self.index[h] = i

    def entry(self, name):
        i = self.index[zzdata.bstringhash(name.replace('/', BS))]
        return i, struct.unpack_from('<6I', self.zdir, i)

    def read(self, name):
        _, (h, number, sector, _, length, _) = self.entry(name)
        _, base = self.files['NFSUNDER/ZZDATA%d.BIN' % number]
        with open(self.iso, 'rb') as f:
            f.seek(base + sector * SECTOR)
            return f.read(length)

    def replaced(self, new):
        """({ZZDATA file name: bytes}, ZDIR bytes) with the files of `new` written over the old
        ones, in place (each must fit in the sectors the old one had before the next file)."""
        packs = {}
        zdir = bytearray(self.zdir)
        starts = {}
        for i in range(0, len(zdir) - 23, 24):
            h, number, sector, _, length, _ = struct.unpack_from('<6I', zdir, i)
            starts.setdefault(number, []).append(sector)
        for name, data in new.items():
            i, (h, number, sector, g, length, ck) = self.entry(name)
            later = [s for s in starts[number] if s > sector]
            pack = 'ZZDATA%d.BIN' % number
            if pack not in packs:
                size, off = self.files['NFSUNDER/' + pack]
                with open(self.iso, 'rb') as f:
                    f.seek(off)
                    packs[pack] = bytearray(f.read(size))
            room = ((min(later) if later else len(packs[pack]) // SECTOR) - sector) * SECTOR
            if len(data) > room:
                raise ValueError('%s : %d octets, place pour %d' % (name, len(data), room))
            o = sector * SECTOR
            packs[pack][o:o + room] = data + bytes(room - len(data))
            struct.pack_into('<6I', zdir, i, h, number, sector, g, len(data), cksum(data))
        return {k: bytes(v) for k, v in packs.items()}, bytes(zdir)


def read_iso(iso, name):
    files = xdvdfs.list_files(iso)
    size, off = files[name]
    with open(iso, 'rb') as f:
        f.seek(off)
        return f.read(size)


def generate(iso, kn5, top='closed', game='ug1', log=print):
    """{path in the zip: bytes}."""
    g = GAMES[game]
    if game == 'ug1':
        files = xdvdfs.list_files(iso)
        for name in FILES:
            if name not in files:
                raise ValueError("%s introuvable : ce n'est pas l'image de NFS Underground (Xbox)" % name)
        geo, tex = (read_iso(iso, n) for n in FILES)
    else:
        packs = Packs(iso)
        geo, tex = (packs.read(n) for n in FILES)
    log('la MX-5 (géométrie et textures)')
    new_geo, new_tex = build_ug.build(geo, tex, kn5, top, game, log=log)
    out = {'game/' + FILES[0]: new_geo, 'game/' + FILES[1]: new_tex}
    planb = ''
    if game == 'ug2':
        log('plan B : ZZDATA2.BIN et ZDIR.BIN')
        zz, zdir = packs.replaced({FILES[0]: new_geo, FILES[1]: new_tex})
        for k, v in zz.items():
            out['planB/NFSUNDER/' + k] = v
        out['planB/NFSUNDER/ZDIR.BIN'] = zdir
        planb = PLAN_B.format(**g)
    listing = '\n'.join('  game/' + f for f in FILES)
    out['LISEZMOI.txt'] = LISEZMOI.format(top='ouvert' if top == 'open' else 'fermé', files=listing,
                                          planb=planb, **g).encode('utf-8')
    return out


def write_zip(entries, path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for k, v in entries.items():
            # the big archives as they are (compressed data already, and much quicker)
            z.writestr(k, v, zipfile.ZIP_STORED if len(v) > 50 << 20 else zipfile.ZIP_DEFLATED)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', default='ug1', choices=sorted(GAMES))
    ap.add_argument('--iso', required=True, help="the game's Xbox disc image (USA)")
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--zip', required=True)
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    a = ap.parse_args()
    entries = generate(a.iso, a.kn5, a.top, a.game)
    os.makedirs(os.path.dirname(os.path.abspath(a.zip)), exist_ok=True)
    write_zip(entries, a.zip)
    print('written', a.zip, sorted(entries))


if __name__ == '__main__':
    main()
