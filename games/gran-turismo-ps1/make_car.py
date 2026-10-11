"""Make the MX-5 RF for Gran Turismo (PS1, PAL SCES-00984) as a patched disc image.

python make_car.py --chd "Gran Turismo [SCES_009.84].chd" --kn5 mazda_mx5_rf.kn5 --out gt_mx5.bin
                   [--car aminn ...] [--top closed|open]

Writes gt_mx5.bin and gt_mx5.cue (for DuckStation and the other emulators). Everything is made
from the player's own disc and Assetto Corsa model; nothing of either is in this repository.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'common'))

import build_car as B   # noqa: E402
import disc             # noqa: E402
import gtarc            # noqa: E402
import mx5scene         # noqa: E402

BOOT = 'SCES_009.84'
# The Roadsters of CAR.DAT (PAL): code -> index of the day texture (model = +1; night = +688).
# The archive has no names: its entries are in the alphabetical order of the car codes.
ROADSTERS = {
    'aminn': (70, "Eunos Roadster '89"), 'aminr': (72, "Eunos Roadster '89 (course)"),
    'amisn': (74, "Eunos Roadster '92"), 'amisr': (76, "Eunos Roadster '92 (course)"),
    'amivn': (78, "Eunos Roadster '90"), 'amivr': (80, "Eunos Roadster '90 (course)"),
    'arodn': (86, 'Eunos Roadster'),
    'a-ian': (8, 'Roadster (spéciale)'), 'a-iar': (10, 'Roadster (spéciale, course)'),
}
NIGHT = 688


def mx5(kn5, top, log=print):
    """The model and the scene, centred between the axles; wheel centres FL, FR, RL, RR."""
    sp, st, scene, wheels = mx5scene.load(kn5, top)
    zc = (wheels['LF'][2] + wheels['LR'][2]) / 2
    sp = sp - [0, 0, zc]
    for P in scene.parts:
        P['pos'] = P['pos'] - np.float32([0, 0, zc])
    W = [wheels[k] - [0, 0, zc] for k in ('LF', 'RF', 'LR', 'RR')]
    return sp, st, scene, W


def generate(chd, kn5, cars=('aminn',), top='closed', log=print):
    """{file name on the disc: new bytes}, and the Disc."""
    d = disc.Disc(chd)
    cnf = d.read('SYSTEM.CNF').decode('latin-1')
    if BOOT not in cnf:
        raise ValueError("ce n'est pas Gran Turismo PAL (%s)" % BOOT)
    log('1/3 la MX-5 (modèle et texture)')
    sp, st, scene, W = mx5(kn5, top)
    lods = [B.make_shell(sp, st, n, k) for n, k in B.LODS]
    hv, hf, _ = lods[0]
    ht = np.array([t for f in hf for t in ([(f[0], f[1], f[2]), (f[0], f[2], f[3])] if len(f) == 4 else [tuple(f)])])
    atlas = B.Atlas(scene, sp, (hv, ht))
    log('2/3 CAR.DAT')
    arc = gtarc.Arc(d.read('CAR.DAT'))
    new = {}
    for code in cars:
        i = ROADSTERS[code][0]
        tex, ftex, _, _ = B.build_texture(atlas, lods, arc[i])
        car, _ = B.build_car(arc[i + 1], lods, ftex, W, sp[:, 1].min())
        for k in (i, i + NIGHT):
            new[k] = tex
        new[i + 1] = car
        new[i + 1 + NIGHT] = car
        log('  %s : %s' % (code, ROADSTERS[code][1]))
    data = gtarc.replace(arc, new)
    room = d.room('CAR.DAT')
    if len(data) > room:
        raise ValueError('CAR.DAT : %d octets de trop' % (len(data) - room))
    return {'CAR.DAT': data}, d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chd', required=True, help='your disc image of Gran Turismo (PAL), .chd')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--out', required=True, help='.bin to write (the .cue goes next to it)')
    ap.add_argument('--car', action='append', choices=sorted(ROADSTERS), help='Roadster(s) to replace (default: all)')
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    a = ap.parse_args()
    t0 = time.time()
    files, d = generate(a.chd, a.kn5, a.car or list(ROADSTERS), a.top)
    print('3/3 the disc image')
    d.write_bin(a.out, files, progress=lambda i, n: print('  %d%%' % (100 * i // n), end='\r'))
    print('written', a.out, 'in %.0f s' % (time.time() - t0))


if __name__ == '__main__':
    main()
