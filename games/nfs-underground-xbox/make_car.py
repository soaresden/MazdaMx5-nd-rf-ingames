"""Make the MX-5 RF for Need for Speed Underground or Underground 2 (Xbox USA, played on the Switch
with nfsu1-sw / nfsu2-sw) as a zip, in place of the Mazda Miata.

python make_car.py --game ug1|ug2 --iso <the game's Xbox disc image (USA)> --kn5 mazda_mx5_rf.kn5
                   --zip mx5.zip [--top closed|open] [--perf rf184|keep] [--wheels mx5|keep]
                   [--names on|off] [--vf-zzdata10 <ZZDATA10.BIN of the French version>]

Underground: the zip holds game/CARS/MIATA/GEOMETRY.BIN and TEXTURES.BIN, to copy over the
extracted disc (sdmc:/switch/nfsu1x/game/).
Underground 2 keeps its files in NFSUNDER/ZZDATA*.BIN, found through NFSUNDER/ZDIR.BIN. The zip
holds the same two files as loose files (game/CARS/MIATA/..., if the game reads loose files) and,
in planB/, the game's ZZDATA2.BIN with the MX-5 in place of the Miata (on the same sectors: the
new files are smaller) and its ZDIR.BIN with their new sizes.
--perf rf184 (default): handling and performance of an MX-5 RF 2.0 184 ch (perf_ug: the Miata's
CarTypeInfo in GLOBAL/GLOBALB.BUN and GLOBALB.LZC); --wheels mx5 (default) also gives it the
MX-5's wheelbase, tracks and tyres. --names on (default): "MX-5 RF" in the menus, in every
language (lang_ug), and the "Mazda / MX-5 RF" badge of the car select (fe_ug).
Underground: those files are loose files of the zip (game/GLOBAL, game/FRONTEND, game/LANGUAGES).
Underground 2: they go into a new pack, planB/NFSUNDER/ZZDATA12.BIN, and planB's ZDIR.BIN points to
them (zdir_ug2); planB/NFSUNDER/ZZDATA12.json lets zdir_ug2.py do the same to any other ZDIR.BIN
(the French version's ones). With --vf-zzdata10, the French version's text gets the new name too.
Everything is made from the player's own disc image and Assetto Corsa model.
"""
import argparse
import json
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs-most-wanted-x360'))

import build_ug    # noqa: E402
import fe_ug       # noqa: E402
import lang_ug     # noqa: E402
import perf_ug     # noqa: E402
import xdvdfs      # noqa: E402
import zdir_ug2    # noqa: E402
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
Conduite : {perf}
Nom dans les menus : {names}

Fait avec https://github.com/soaresden/MazdaMx5-nd-rf-ingames à partir de TA copie du jeu et du modèle.
"""

PLAN_B = """
Si la Miata reste la Miata (le jeu ne lit que ses archives) : enlever game/CARS/MIATA/ et copier à
la place les fichiers de planB/NFSUNDER/ dans sdmc:/switch/{folder}/game/NFSUNDER/
({planb_files} ; ceux d'origine sauvegardés avant).
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

    def read_all(self, name):
        """The file, checking that all its copies (ZZDATA2 and ZZDATA5) are the same."""
        h = zzdata.bstringhash(name.replace('/', BS))
        copies = set()
        for e in zdir_ug2.entries(self.zdir):
            if e[0] == h:
                _, base = self.files['NFSUNDER/ZZDATA%d.BIN' % e[1]]
                with open(self.iso, 'rb') as f:
                    f.seek(base + e[2] * SECTOR)
                    copies.add(f.read(e[4]))
        if len(copies) != 1:
            raise ValueError('%s : %d versions' % (name, len(copies)))
        return copies.pop()

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


def disc_names(iso):
    """{upper-case path: the path as written on the disc} (loose files keep their case)."""
    out = {}
    with open(iso, 'rb') as f:
        base = xdvdfs._find_partition(f)
        f.seek(base + 32 * SECTOR + 20)
        root_sector, root_size = struct.unpack('<II', f.read(8))

        def walk(sector, size, prefix):
            f.seek(base + sector * SECTOR)
            data = f.read(size)
            stack, seen = [0], set()
            while stack:
                off = stack.pop()
                if off in seen or off + 14 > len(data):
                    continue
                seen.add(off)
                left, right, start, length, attr, n = struct.unpack_from('<HHIIBB', data, off)
                if left == 0xFFFF and right == 0xFFFF:
                    continue
                name = data[off + 14:off + 14 + n].decode('latin-1')
                if attr & 0x10:
                    if length:
                        walk(start, length, prefix + name + '/')
                else:
                    out[(prefix + name).upper()] = prefix + name
                for k in (left, right):
                    if k:
                        stack.append(k * 4)
        walk(root_sector, root_size, '')
    return out


def extras(read, game, perf=True, wheels=True, names=True, log=print):
    """{disc path: new bytes} of the files outside the car: GLOBALB (handling), the language files
    and the frontend pack (name and badge). read(path) gives the disc's file."""
    out = {}
    if perf:
        log('conduite : MX-5 RF 2.0 184 ch (CarTypeInfo de GLOBALB)')
        bun = read('GLOBAL/GLOBALB.BUN')
        new, rng, report = perf_ug.patch_globalb(bun, game, wheels, log=log)
        log(perf_ug.report_table(report))
        out['GLOBAL/GLOBALB.BUN'] = new
        out['GLOBAL/GLOBALB.LZC'] = perf_ug.patch_lzc(read('GLOBAL/GLOBALB.LZC'), new, rng)
    if names:
        log('nom : MX-5 RF (textes de toutes les langues, badge du choix de voiture)')
        for lang in (lang_ug.UG1_FILES if game == 'ug1' else lang_ug.UG2_FILES):
            path = ('LANGUAGES/LANGUAGE_%s.BIN' if game == 'ug1' else 'LANGUAGES/%s.BIN') % lang
            new, changes = (lang_ug.ug1_patch if game == 'ug1' else lang_ug.ug2_patch)(read(path))
            if changes:
                out[path] = new
                log('  %s : %s' % (lang, ', '.join('%s -> %s' % (a, b) for _, a, b in changes)))
        if game == 'ug1':
            fe = read('FRONTEND/FRONTB.BUN')
            new, rng, _ = fe_ug.patch(fe, game, log=log)
            out['FRONTEND/FRONTB.BUN'] = new
            out['FRONTEND/FRONTB.LZC'] = fe_ug.patch_lzc(read('FRONTEND/FRONTB.LZC'), new, rng)
        else:
            import jdlz
            blob = read('FRONTEND/FRONTB.LZC')
            new, rng, _ = fe_ug.patch(jdlz.decompress(blob), game, log=log)
            out['FRONTEND/FRONTB.LZC'] = fe_ug.patch_lzc(blob, new, rng)
    return out


def vf_french(zzdata10):
    """The French version's French text: the file at sector 0 of its ZZDATA10.BIN (chunks 0x39000,
    padding and 0x30201 fonts, up to the next file)."""
    with open(zzdata10, 'rb') as f:
        d = f.read(1 << 20)
    o, last = 0, None
    while o + 8 <= len(d):
        cid, size = struct.unpack_from('<II', d, o)
        if cid not in (0x39000, 0, 0x30201) or (o == 0 and cid != 0x39000):
            break
        last = (cid, size, o)
        o += 8 + size
    if last and last[:2] == (0, 0):     # the zeros up to the next sector
        o = last[2]
    return d[:o]


def ug2_pack(packs, files, vf_zzdata10=None, log=print):
    """(ZZDATA12.BIN bytes, manifest) for Underground 2: `files` {disc path: new bytes}, each
    remembering where its source data is in the packs (every copy); with the French version's
    ZZDATA10.BIN, its French text (sector 0, what its ZDIR gives for ENGLISH.BIN) too."""
    items = []
    for name, data in files.items():
        h = zzdata.bstringhash(name.replace('/', BS))
        items.append((name, data, [(e[1], e[2]) for e in zdir_ug2.entries(packs.zdir) if e[0] == h]))
    if vf_zzdata10:
        new, changes = lang_ug.ug2_patch(vf_french(vf_zzdata10))
        log('  VF (ZZDATA10 secteur 0) : %s' % ', '.join('%s -> %s' % (a, b) for _, a, b in changes))
        items.append(('LANGUAGES/ENGLISH.BIN', new, [(10, 0)]))
    sectors = sum(packs.files['NFSUNDER/ZZDATA%d.BIN' % k][0] // SECTOR for k in range(10))
    pack, manifest = zdir_ug2.build_pack(items, sectors + sum(zdir_ug2.VF_SECTORS))
    if vf_zzdata10:
        manifest['files'][-1]['label'] = 'texte VF'
    return pack, manifest


def read_iso(iso, name):
    files = xdvdfs.list_files(iso)
    size, off = files[name]
    with open(iso, 'rb') as f:
        f.seek(off)
        return f.read(size)


def generate(iso, kn5, top='closed', game='ug1', perf=True, wheels=True, names=True,
             vf_zzdata10=None, log=print):
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
    listed = list(FILES)
    planb = ''
    if game == 'ug1':
        real = disc_names(iso)
        for name, data in extras(lambda n: read_iso(iso, n), game, perf, wheels, names, log).items():
            out['game/' + real[name]] = data
            listed.append(real[name])
    else:
        log('plan B : ZZDATA2.BIN et ZDIR.BIN')
        zz, zdir = packs.replaced({FILES[0]: new_geo, FILES[1]: new_tex})
        for k, v in zz.items():
            out['planB/NFSUNDER/' + k] = v
        planb_files = sorted(zz)
        more = extras(packs.read_all, game, perf, wheels, names, log)
        if more:
            pack, manifest = ug2_pack(packs, more, vf_zzdata10, log)
            zdir, _ = zdir_ug2.apply(zdir, manifest, log=log)
            left = zdir_ug2.check_untouched(zdir, manifest)
            if left:
                raise ValueError('entrées non redirigées : %r' % left)
            out['planB/NFSUNDER/ZZDATA12.BIN'] = pack
            out['planB/NFSUNDER/ZZDATA12.json'] = json.dumps(manifest, indent=1).encode()
            planb_files.append('ZZDATA12.BIN')
        out['planB/NFSUNDER/ZDIR.BIN'] = zdir
        planb = PLAN_B.format(planb_files=', '.join(planb_files + ['ZDIR.BIN']), **g)
    listing = '\n'.join('  game/' + f for f in listed)
    out['LISEZMOI.txt'] = LISEZMOI.format(
        top='ouvert' if top == 'open' else 'fermé', files=listing, planb=planb,
        perf='MX-5 RF 2.0 184 ch (1125 kg, 205 N.m, 6 rapports)' if perf else 'celle de la Miata',
        names='MX-5 RF' if names else 'Miata', **g).encode('utf-8')
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
    ap.add_argument('--perf', default='rf184', choices=('rf184', 'keep'),
                    help="handling and performance: the MX-5 RF 2.0 184 ch's, or the Miata's")
    ap.add_argument('--wheels', default='mx5', choices=('mx5', 'keep'),
                    help="with --perf rf184: the MX-5's wheelbase, tracks and tyres, or the Miata's")
    ap.add_argument('--names', default='on', choices=('on', 'off'), help='"MX-5 RF" in the menus')
    ap.add_argument('--vf-zzdata10', help="Underground 2: ZZDATA10.BIN of the French version")
    a = ap.parse_args()
    entries = generate(a.iso, a.kn5, a.top, a.game, a.perf == 'rf184', a.wheels == 'mx5',
                       a.names == 'on', a.vf_zzdata10)
    os.makedirs(os.path.dirname(os.path.abspath(a.zip)), exist_ok=True)
    write_zip(entries, a.zip)
    print('written', a.zip, sorted(entries))


if __name__ == '__main__':
    main()
