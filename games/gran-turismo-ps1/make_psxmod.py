"""The MX-5 RF for gran-turismo-recomp (github.com/alexbeavs-ps1-ports/gran-turismo-recomp, the PC
recompilation of Gran Turismo USA): a .psxmod package instead of a new disc image.

python make_psxmod.py --chd "Gran Turismo (USA) (Rev 1).chd" --kn5 mazda_mx5_rf.kn5 --out mx5_rf.psxmod
                      [--car aminn=closed --car amivn=open ...] [--price 29900]

The package (a zip, docs/MOD_PACKAGES.md of psxrecomp) holds manifest.toml and the sectors that
make_car.generate changes, as disc_user overlays read over the player's stock disc, which stays as
it is: the same bytes as the new disc image, only those that differ. Each overlay is guarded by
the SHA-256 of the stock range and the package by the SHA-256 of the stock data track.
"""
import argparse
import hashlib
import io
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_car  # noqa: E402

GAME_ID = 'SCUS-94194'
BOOT = 'SCUS_941.94'
# SHA-256 of the data track of Gran Turismo (USA) (Rev 1) (Redump: SHA-1 5433c558..., 693668304
# bytes), the disc of gran-turismo-recomp: what psxrecomp measures (CUE data or CHD raw sectors)
DISC_SHA256 = 'e1ba7def96b7f213637fa82658b53c34a3a5f6c54df7d7e5ab9c3f53a2d41f03'
PACKAGE_ID = 'soaresden.mx5-rf'
VERSION = '1.0.0'
FEATURE = 'mx5-rf'
SITE = 'https://soaresden.github.io/MazdaMx5-nd-rf-ingames/web/gt1.html'


def changed_sectors(d, files):
    """{lba: 2048 new bytes} of the sectors that differ from the stock disc, as Disc.bin_chunks
    writes them: the files (the last sector padded with zeros) and the directory records of those
    whose size changes."""
    out = {}
    for name, data in files.items():
        lba, size, dlba, doff = d.files[name]
        if len(data) > d.room(name):
            raise ValueError('%s : %d octets, place pour %d' % (name, len(data), d.room(name)))
        n = (len(data) + 2047) // 2048
        # the stock file as make_car read it (d.stock) where it fills the sector, else the disc
        stock = getattr(d, 'stock', {}).get(name)
        new = data.ljust(n * 2048, b'\0')
        for i in range(n):
            s = new[i * 2048:(i + 1) * 2048]
            if stock is not None and (i + 1) * 2048 <= len(stock):
                o = stock[i * 2048:(i + 1) * 2048]
            else:
                o = d.c.read(lba + i, 1)
            if s != o:
                out[lba + i] = s
        if len(data) != size:
            sec = bytearray(out.get(dlba) or d.c.read(dlba, 1))
            struct.pack_into('<I', sec, doff + 10, len(data))
            struct.pack_into('>I', sec, doff + 14, len(data))
            out[dlba] = bytes(sec)
    return out


def runs(sectors):
    """Consecutive LBAs grouped: [(first lba, [2048-byte blocks])]."""
    out = []
    for lba in sorted(sectors):
        if out and out[-1][0] + len(out[-1][1]) == lba:
            out[-1][1].append(sectors[lba])
        else:
            out.append((lba, [sectors[lba]]))
    return out


def toml_str(s):
    return '"%s"' % s.replace('\\', '\\\\').replace('"', '\\"')


def package(d, files, cars, price):
    """The .psxmod (zip bytes) and the number of overlays."""
    if BOOT not in d.read('SYSTEM.CNF').decode('latin-1'):
        raise ValueError('gran-turismo-recomp prend le disque Gran Turismo USA (SCUS-94194), pas celui-ci')
    names = {c: make_car.ROADSTERS[c][1].split(' (')[0] for c in cars}
    roof = {'closed': 'hardtop closed', 'open': 'top down'}
    said = ', '.join('%s -> MX-5 RF %s' % (names[c], roof[t]) for c, t in cars.items() if c in make_car.ROADSTERS
                     and not c.endswith('r'))
    lines = [
        'format_version = 1',
        'id = %s' % toml_str(PACKAGE_ID),
        'version = %s' % toml_str(VERSION),
        'name = "Mazda MX-5 RF"',
        'author = "soaresden"',
        'description = %s' % toml_str(
            'The 2018 Mazda MX-5 RF (ND2) in place of Eunos Roadsters, made from your disc and the '
            'Assetto Corsa model by ' + SITE + '. Do not share it: it holds game data.'),
        'license = "GPL-3.0"',
        'resolver = "declarative"',
        '',
        '[[target]]',
        'game_id = %s' % toml_str(GAME_ID),
        'disc_sha256 = %s' % toml_str(DISC_SHA256),
        '',
        '[[feature]]',
        'id = %s' % toml_str(FEATURE),
        'name = "MX-5 RF"',
        'description = %s' % toml_str(said + ('; %d Cr at the Mazda dealer.' % price if price else '.')),
        'group = "Cars"',
        'default_enabled = true',
    ]
    out = io.BytesIO()
    count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for lba, blocks in runs(changed_sectors(d, files)):
            payload = b''.join(blocks)
            stock = d.c.read(lba, len(blocks))
            path = 'assets/%08d.bin' % lba
            z.writestr(path, payload)
            lines += ['', '[[overlay]]', 'feature = %s' % toml_str(FEATURE), 'target = "disc_user"',
                      'offset = %d' % (lba * 2048), 'file = %s' % toml_str(path),
                      'sha256 = %s' % toml_str(hashlib.sha256(payload).hexdigest()),
                      'expected_sha256 = %s' % toml_str(hashlib.sha256(stock).hexdigest())]
            count += 1
        z.writestr('manifest.toml', '\n'.join(lines) + '\n')
    return out.getvalue(), count


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chd', required=True, help='ton image de Gran Turismo (USA) (Rev 1) : .chd, .cue ou .bin')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 du mod Assetto Corsa')
    ap.add_argument('--out', required=True, help='le .psxmod à écrire')
    ap.add_argument('--car', action='append', metavar='CODE=closed|open',
                    help='Roadster remplacée et son toit (à répéter ; par défaut aminn=closed)')
    ap.add_argument('--price', type=int, default=make_car.PRICE, help='prix chez le concessionnaire Mazda (Cr)')
    a = ap.parse_args()
    cars = {}
    for c in a.car or ['aminn=closed']:
        code, _, top = c.partition('=')
        cars[code] = top or 'closed'
    for code in list(cars):                     # the race version follows its road car
        twin = code[:-1] + 'r'
        if code.endswith('n') and twin in make_car.ROADSTERS:
            cars.setdefault(twin, cars[code])
    files, d = make_car.generate(a.chd, a.kn5, cars, price=a.price, keep_layout=True)
    data, n = package(d, files, cars, a.price)
    with open(a.out, 'wb') as f:
        f.write(data)
    print('%s : %d zones du disque, %d octets' % (a.out, n, len(data)))


if __name__ == '__main__':
    main()
