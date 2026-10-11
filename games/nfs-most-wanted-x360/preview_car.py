"""Render a car GEOMETRY.BIN (360) as the game assembles it.

preview_car.py --iso <Xbox 360 image> <GEOMETRY.BIN> <out.png> [--lod A] [--car IS300] [--globalmem GLOBALMEMORYFILE.BIN]
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'common'))
import names  # noqa: E402
import render  # noqa: E402
import sol360  # noqa: E402
import solids  # noqa: E402
import zzdata  # noqa: E402
import attrib360  # noqa: E402

PAINT = np.array([22, 38, 78], np.float32)  # Deep Crystal Blue, approx.
LMCOL = {'CARSKIN': PAINT * 2.2, 'REGPAINTBLACK': (40, 40, 44), 'DULLPLASTIC': (90, 90, 90), 'RUBBER': (60, 60, 60),
         'SHINYPLASTIC': (170, 170, 170), 'CHROME': (230, 230, 235), 'LICENSEPLATE': (240, 240, 240),
         'WINDSHIELD': (40, 50, 60), 'MIRROR': (200, 210, 220), 'HEADLIGHTREFLECTOR': (220, 220, 220),
         'HEADLIGHTGLASS': (200, 215, 230), 'BRAKELIGHT': (200, 40, 40), 'INTERIOR': (120, 120, 120),
         'MAGGUNMETAL': (70, 70, 75), 'BRAKEDISC': (150, 150, 150), 'CALIPER': (210, 30, 30),
         'DRIVER': (90, 70, 60), 'MAGSILVER': (200, 200, 200)}


def main(iso, path, out, lod='A', car='ELISE', globalmem=None):
    d = open(path, 'rb').read()
    N = names.build(zzdata.Disc(iso))
    ss = {s['name']: s for s in solids.parse(d)}
    meshes = []

    def add(nm, off=(0, 0, 0), flip=False):
        s = ss.get(nm)
        if s is None:
            return
        lm = []
        for cid, h, b, e in s['chunks']:
            if cid == 0x134013:
                lm = [N.get(v, '%08X' % v).replace('LM:', '') for v in struct.unpack_from('<%dI' % ((e - b) // 4), d, b)[::2]]
        for g, p, uv, c, n, t in sol360.decode(d, s):
            p = p.copy()
            if flip:
                p[:, 1] *= -1
                t = t[:, ::-1]
            p += np.array(off)
            name = lm[g['ids'][0]] if g['ids'][0] < len(lm) else '?'
            base = np.array(LMCOL.get(name, (160, 160, 160)), np.float32)
            vc = ((c >> 0) & 255).astype(np.float32)[:, None] / 255.0
            meshes.append((p, t, np.clip(base * (0.25 + 0.75 * vc), 0, 255)))

    for nm in ss:
        if nm.endswith('_' + lod) and any(k in nm for k in ('BASE', 'KIT00_')) and not any(
                k in nm for k in ('TIRE', 'BRAKE_', 'DAMAGE', 'DECAL', 'FRONT_BRAKE', 'REAR_BRAKE')):
            add(nm)
    # wheels at the car's ecar TireOffsets (from the given GLOBALMEMORYFILE.BIN, else the disc's)
    disc = zzdata.Disc(iso)
    gm = open(globalmem, 'rb').read() if globalmem else disc.read(zzdata.path('GLOBAL', 'GLOBALMEMORYFILE.BIN'))
    cnt, = struct.unpack_from('<I', gm, 12)
    ent = next(struct.unpack_from('<5I', gm, 16 + i * 20) for i in range(cnt)
               if struct.unpack_from('<I', gm, 16 + i * 20)[0] == zzdata.bstringhash(zzdata.path('GLOBAL', 'ATTRIBUTES.BIN')))
    att = gm[ent[1]:ent[1] + ent[3]]
    lay = attrib360.Pack(att).collections()[(attrib360.key('ecar'), attrib360.key(car.lower()))]
    offs = np.array(struct.unpack_from('>16f', att, lay + 0x10)).reshape(4, 4)
    tire = ss['%s_KIT00_FRONT_TIRE_A' % car]
    my = 0.045
    for cid, h, b, e in tire['chunks']:
        if cid == 0x13401A:
            my = struct.unpack_from('<f', d, b + ((-b) % 16) + 0x10 + 52)[0]
    for (x, y, z, r), br in zip(offs, ('FRONT', 'FRONT', 'REAR', 'REAR')):
        add('%s_KIT00_FRONT_TIRE_%s' % (car, lod), (x, y, r), flip=y > 0)
        add('%s_KIT00_%s_BRAKE_%s' % (car, br, lod if lod in 'ABC' else 'A'),
            (x, y + (-my if y > 0 else my), r), flip=y > 0)
    views = [render.render(meshes, (900, 400), yaw=-90, pitch=0),
             render.render(meshes, (900, 450), yaw=-35, pitch=-14),
             render.render(meshes, (900, 450), yaw=145, pitch=-14)]
    W = Image.new('RGB', (900, sum(v.size[1] for v in views)))
    y = 0
    for v in views:
        W.paste(v, (0, y))
        y += v.size[1]
    W.save(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--iso', required=True)
    ap.add_argument('geometry')
    ap.add_argument('out')
    ap.add_argument('--lod', default='A')
    ap.add_argument('--car', default='ELISE')
    ap.add_argument('--globalmem', help='GLOBALMEMORYFILE.BIN with the wheel positions (default: the disc)')
    a = ap.parse_args()
    main(a.iso, a.geometry, a.out, a.lod, a.car, a.globalmem)
