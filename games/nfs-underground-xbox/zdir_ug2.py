"""Underground 2: new versions of files of the ZZDATA packs, stored in a new pack ZZDATA12.BIN, and
the ZDIR.BIN entries that point to them.

ZDIR.BIN: 24-byte entries (name hash, ZZDATA number, sector, global sector, size, checksum), and
many files twice (in ZZDATA2 and ZZDATA5, e.g. GLOBAL\\GLOBALB.BUN, LANGUAGES\\ENGLISH.BIN): every
entry of a changed file is redirected. The game (default.xbe, 0x183A80) opens NFSUNDER\\ZZDATA0
to ZZDATA15 when they exist and reads at <sector> x 2048 of the pack <number> (0x185900); the
global sector (ZZDATA0.. packs end to end) only feeds its seek statistics. ZZDATA10 and ZZDATA11
are the French version's (4_VF_francais), so this pack is ZZDATA12, its global sectors counted
after them, whether or not they are installed.

Each new file remembers the places (pack, sector) of the data it was made from: an entry is
redirected when it points to one of them. So one ZZDATA12.BIN serves every ZDIR.BIN: the game's,
the MX-5's (2_MX5_*), and the French version's (ENGLISH.BIN -> French text in ZZDATA10 sector 0:
its entries go to the French text with the MX-5 RF's name).

python zdir_ug2.py --manifest ZZDATA12.json --zdir <ZDIR.BIN> --out <new ZDIR.BIN>
"""
import argparse
import json
import os
import struct
import sys

SECTOR = 2048
NUMBER = 12
# sectors of ZZDATA10.BIN and ZZDATA11.BIN of the French version (4_VF_francais/manifest.txt)
VF_SECTORS = (285725, 10)
BS = chr(92)


def bstringhash(name):
    h = 0xFFFFFFFF
    for c in name.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


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
    """POSIX cksum, as the ZDIR entries (the game does not seem to check it)."""
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CK[(crc >> 24) ^ b]
    n = len(data)
    while n:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CK[(crc >> 24) ^ (n & 0xFF)]
        n >>= 8
    return ~crc & 0xFFFFFFFF


def entries(zdir):
    return [list(struct.unpack_from('<6I', zdir, i)) for i in range(0, len(zdir) - 23, 24)]


def build_pack(items, global_base):
    """items: [(name, data, [(pack, sector) of the sources])] -> (ZZDATA12 bytes, manifest)."""
    out = bytearray()
    manifest = {'number': NUMBER, 'global_base': global_base, 'files': []}
    for name, data, sources in items:
        sector = len(out) // SECTOR
        out += data
        out += b'\0' * (-len(out) % SECTOR)
        manifest['files'].append(dict(name=name, hash='%08x' % bstringhash(name.replace('/', BS)),
                                      sector=sector, size=len(data), cksum=cksum(data),
                                      sources=[list(s) for s in sources]))
    return bytes(out), manifest


def apply(zdir, manifest, log=print):
    """ZDIR bytes with the entries of the manifest's files redirected; [(row, old, new)]."""
    rows = entries(zdir)
    out = bytearray(zdir)
    changed = []
    number, gbase = manifest['number'], manifest['global_base']
    for f in manifest['files']:
        h = int(f['hash'], 16)
        sources = {tuple(s) for s in f['sources']}
        new = [h, number, f['sector'], gbase + f['sector'], f['size'], f['cksum']]
        hits = 0
        for i, e in enumerate(rows):
            if e[0] == h and (e[1], e[2]) in sources:
                struct.pack_into('<6I', out, 24 * i, *new)
                changed.append((i, e, new))
                hits += 1
        log('  %-34s %d entrée(s)' % (f['name'] + (' (' + f['label'] + ')' if f.get('label') else ''), hits))
    # read back
    again = entries(bytes(out))
    for i, e, new in changed:
        assert again[i] == new
    assert len(out) == len(zdir)
    return bytes(out), changed


def check_untouched(zdir, manifest):
    """Entries of the changed names that still point elsewhere (to report)."""
    names = {int(f['hash'], 16): f['name'] for f in manifest['files']}
    return [(names[e[0]], e[1], e[2]) for e in entries(zdir)
            if e[0] in names and e[1] != manifest['number']]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--manifest', required=True, help='ZZDATA12.json written with ZZDATA12.BIN')
    ap.add_argument('--zdir', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with open(a.manifest, encoding='utf-8') as f:
        manifest = json.load(f)
    with open(a.zdir, 'rb') as f:
        zdir = f.read()
    new, changed = apply(zdir, manifest)
    left = check_untouched(new, manifest)
    for name, n, s in left:
        print('  attention : %s pointe encore vers ZZDATA%d secteur %d' % (name, n, s))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'wb') as f:
        f.write(new)
    print('écrit', a.out, '(%d entrées changées)' % len(changed))
    return 0 if not left else 1


if __name__ == '__main__':
    sys.exit(main())
