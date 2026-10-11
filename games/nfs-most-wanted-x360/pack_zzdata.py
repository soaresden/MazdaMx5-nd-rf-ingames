"""Plan B: write the new car files inside the Elise's own space in ZZDATA2 and patch ZDIR.BIN.

pack_zzdata.py --iso <Xbox 360 image> --src <dir with GEOMETRY.BIN, TEXTURES.BIN> --out <game_root>
               [--zdir <ZDIR.BIN to start from, e.g. the French dub one; default: the disc's>]
The Elise GEOMETRY.BIN slot (7 MB) holds both new files; ZZDATA2 keeps its size, so the global
sectors of the other archives do not move.
"""
import argparse
import os
import struct

import zzdata

SECTOR = 2048

ap = argparse.ArgumentParser()
ap.add_argument('--iso', required=True)
ap.add_argument('--src', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--zdir')
a = ap.parse_args()
X360, src, out = a.iso, a.src, a.out
disc = zzdata.Disc(X360)
geo = open(os.path.join(src, 'GEOMETRY.BIN'), 'rb').read()
tex = open(os.path.join(src, 'TEXTURES.BIN'), 'rb').read()
zdir = bytearray(open(a.zdir, 'rb').read() if a.zdir else disc.zdir)

h_geo = zzdata.bstringhash(zzdata.path('CARS', 'ELISE', 'GEOMETRY.BIN'))
h_tex = zzdata.bstringhash(zzdata.path('CARS', 'ELISE', 'TEXTURES.BIN'))
ent = {}
for i in range(0, len(zdir) - 23, 24):
    h, number, sector, gsector, length, chk = struct.unpack_from('<6I', zdir, i)
    if h in (h_geo, h_tex):
        ent[h] = (i, number, sector, gsector, length, chk)
gi, gnum, gsec, ggs, glen, _ = ent[h_geo]
assert gnum == 2
slot = glen + (-glen) % SECTOR
geo_sectors = (len(geo) + SECTOR - 1) // SECTOR
need = geo_sectors * SECTOR + len(tex)
assert need <= slot, (need, slot)

size, off = disc.files['NFS/ZZDATA2.BIN']
os.makedirs(os.path.join(out, 'NFS'), exist_ok=True)
dst = os.path.join(out, 'NFS', 'ZZDATA2.BIN')
with open(X360, 'rb') as f, open(dst, 'wb') as o:
    f.seek(off)
    left = size
    while left:
        b = f.read(min(left, 1 << 24))
        o.write(b)
        left -= len(b)
with open(dst, 'r+b') as o:
    o.seek(gsec * SECTOR)
    o.write(b'\0' * slot)
    o.seek(gsec * SECTOR)
    o.write(geo)
    o.seek((gsec + geo_sectors) * SECTOR)
    o.write(tex)
struct.pack_into('<6I', zdir, gi, h_geo, 2, gsec, ggs, len(geo), ent[h_geo][5])
ti = ent[h_tex][0]
struct.pack_into('<6I', zdir, ti, h_tex, 2, gsec + geo_sectors, ggs + geo_sectors, len(tex), ent[h_tex][5])
open(os.path.join(out, 'NFS', 'ZDIR.BIN'), 'wb').write(zdir)
print('ZZDATA2', size, 'geometry at sector', gsec, 'textures at sector', gsec + geo_sectors)
