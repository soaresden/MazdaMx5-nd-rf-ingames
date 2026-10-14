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

import binimage         # noqa: E402
import build_car as B   # noqa: E402
import carinf           # noqa: E402
import disc             # noqa: E402
import gtarc            # noqa: E402
import menus            # noqa: E402
import mx5scene         # noqa: E402

BOOT = 'SCES_009.84'
BADGE = os.path.join(HERE, '..', 'nfs-most-wanted-x360', 'assets', 'badge_mx5_miata_1024.png')
PRICE = 29900   # Cr: about the real price, on the game's scale
# The Roadsters of CAR.DAT (PAL): code -> index of the day texture (model = +1; night = +688).
# The archive has no names: its entries are in the alphabetical order of the car codes.
ROADSTERS = {
    # new cars (Mazda dealer)
    'aminn': (70, 'Eunos Roadster NORMAL (neuve, 17 400 Cr)'), 'aminr': (72, 'Eunos Roadster NORMAL (course)'),
    'amisn': (74, 'Eunos Roadster S-SPECIAL (neuve, 22 250 Cr)'), 'amisr': (76, 'Eunos Roadster S-SPECIAL (course)'),
    'amivn': (78, 'Eunos Roadster V-SPECIAL (neuve, 24 400 Cr)'), 'amivr': (80, 'Eunos Roadster V-SPECIAL (course)'),
    # used cars
    'an16n': (82, "Eunos Roadster '89 (occasion)"), 'an16r': (84, "Eunos Roadster '89 (occasion, course)"),
    'as16n': (88, "Eunos Roadster '92 S-SPECIAL (occasion)"), 'as16r': (90, "Eunos Roadster '92 (occasion, course)"),
    'av16n': (92, "Eunos Roadster '90 V-SPECIAL (occasion)"), 'av16r': (94, "Eunos Roadster '90 (occasion, course)"),
    # others
    'arodn': (86, 'Eunos Roadster RS'),
    'a-ian': (8, 'Eunos Roadster (spéciale)'), 'a-iar': (10, 'Eunos Roadster (spéciale, course)'),
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


def cheat_patcher():
    """gt1cheat.patcher of the GranTurismo1-OverlayCheat project (github.com/soaresden/
    GranTurismo1-OverlayCheat): next to this script in the Windows package (outils/gt1cheat),
    else the project's folder next to this repository, or GT1CHEAT_DIR."""
    for base in (os.environ.get('GT1CHEAT_DIR', ''), os.path.join(HERE, '..', '..'),
                 os.path.join(HERE, '..', '..', '..', 'GranTurismo1-OverlayCheat')):
        if base and os.path.isfile(os.path.join(base, 'gt1cheat', 'patcher.py')):
            if base not in sys.path:
                sys.path.insert(0, base)
            from gt1cheat import patcher
            return patcher
    raise ValueError('cheat introuvable : il faut le projet GranTurismo1-OverlayCheat '
                     '(dossier gt1cheat), ou GT1CHEAT_DIR')


def generate(chd, kn5, cars=('aminn',), top='closed', price=PRICE, log=print, cheat=False):
    """{file name on the disc: new bytes}, and the Disc."""
    d = disc.Disc(chd)
    cnf = d.read('SYSTEM.CNF').decode('latin-1')
    if BOOT not in cnf:
        raise ValueError("ce n'est pas Gran Turismo PAL (%s)" % BOOT)
    log('1/4 la MX-5 (modèle et texture)')
    sp, st, scene, W = mx5(kn5, top)
    lods = [B.make_shell(sp, st, n, (W[0][2], W[2][2]), smooth=top == 'open', log=log) for n in B.LODS]
    hv, hf, _ = lods[0]
    ht = np.array([t for f in hf for t in ([(f[0], f[1], f[2]), (f[0], f[2], f[3])] if len(f) == 4 else [tuple(f)])])
    atlas = B.Atlas(scene, sp, (hv, ht))
    log('2/4 CAR.DAT')
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
        last_car, last_tex = car, tex
        log('  %s : %s' % (code, ROADSTERS[code][1]))
    files = {'CAR.DAT': gtarc.replace(arc, new)}
    log('3/4 noms, peintures, caractéristiques et prix (CARINF.DAT)')
    files['CARINF.DAT'] = carinf.patch(d.read('CARINF.DAT'), cars, [p for p, _ in B.PAINTS], price, log=log)
    log('4/4 les menus (nom, vignettes, prix)')
    files['MENU_IMG.ARC'] = menus.patch(d.read('MENU_IMG.ARC'), d.read('CARINF.DAT'), cars, BADGE,
                                        last_car, last_tex, price, log=log)
    if cheat:
        log('+ le cheat GranTurismo1-OverlayCheat (SELECT : chrono des permis, crédits)')
        patcher = cheat_patcher()
        for name in ('GTOS.EXE', 'GTMENU.EXE', 'GTMAIN.EXE'):
            files[name] = patcher.patch_exe(name, d.read(name))
    for name, data in files.items():
        if len(data) > d.room(name):
            raise ValueError('%s : %d octets de trop' % (name, len(data) - d.room(name)))
    return files, d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chd', '--disc', dest='chd', required=True,
                    help='your disc image of Gran Turismo (PAL, Europe, multi-language, SCES-00984): .chd, .cue or .bin')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--out', required=True, help='.bin to write (the .cue goes next to it)')
    ap.add_argument('--car', action='append', choices=sorted(ROADSTERS), help='Roadster(s) to replace (default: all)')
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    ap.add_argument('--price', type=int, default=PRICE, help='price at the dealer, Cr (100: from the first day)')
    ap.add_argument('--cheat', action='store_true', help='add the GranTurismo1-OverlayCheat menu (hold SELECT)')
    a = ap.parse_args()
    t0 = time.time()
    src = binimage.cue_bin(a.chd) if a.chd.lower().endswith('.cue') else a.chd
    if os.path.abspath(src).lower() == os.path.abspath(a.out).lower():
        raise SystemExit('--out would overwrite the source image: choose another name')
    files, d = generate(a.chd, a.kn5, a.car or list(ROADSTERS), a.top, a.price, cheat=a.cheat)
    print('the disc image')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    d.write_bin(a.out, files, progress=lambda i, n: print('  %d%%' % (100 * i // n), end='\r'))
    print('written', a.out, 'in %.0f s' % (time.time() - t0))


if __name__ == '__main__':
    main()
