"""Hash -> name dictionary built from the game files (light materials, shared car textures)."""
import struct

import tpk
import zzdata


def h(s):
    x = 0xFFFFFFFF
    for c in s.encode():
        x = (x * 33 + c) & 0xFFFFFFFF
    return x


def build(disc, extra_tpks=()):
    """disc: zzdata.Disc of the Xbox 360 image. extra_tpks: TEXTURES.BIN contents (bytes)."""
    names = {}
    d = disc.read(zzdata.path('GLOBAL', 'GLOBALB.BUN'))
    off = 0
    while off + 8 <= len(d):
        cid, size = struct.unpack_from('<II', d, off)
        if cid == 0x135200:
            nm = d[off + 8 + 20:off + 8 + 20 + 32].split(b'\0')[0].decode()
            names[h(nm)] = 'LM:' + nm
        off += 8 + size
    for data in (disc.read(zzdata.path('CARS', 'TEXTURES.BIN')),) + tuple(extra_tpks):
        for t in tpk.read(data):
            names.setdefault(t['hash'], 'TX:' + t['name'])
    for nm in ('CARSKIN',):
        names.setdefault(h(nm), nm)
    return names
