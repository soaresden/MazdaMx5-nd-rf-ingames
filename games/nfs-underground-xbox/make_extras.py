"""The MX-5 RF's handling and menu name for Need for Speed Underground / Underground 2 on their own,
for players who already have the car (2_MX5_capotee / 3_MX5_decapotee): the same files as
make_car.py (--perf, --wheels, --names), without rebuilding the car.

Underground:   python make_extras.py --game ug1 --iso <USA image> --out <folder>
  writes <folder>/switch/nfsu1x/game/GLOBAL, FRONTEND and LANGUAGES files (the loose files that
  change: GLOBALB.BUN and GlobalB.lzc, FRONTB.BUN and FrontB.lzc, LANGUAGE_*.bin).
Underground 2: python make_extras.py --game ug2 --iso <USA image> --out <folder>
                   [--vf-zzdata10 <French version ZZDATA10.BIN>] [--zdir NAME=<ZDIR.BIN> ...]
  writes <folder>/switch/nfsu2x/game/NFSUNDER/ZZDATA12.BIN, ZZDATA12.json, and for each --zdir
  the same ZDIR.BIN with the changed files' entries pointing to ZZDATA12:
  <folder>/NAME/switch/nfsu2x/game/NFSUNDER/ZDIR.BIN.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_car as M   # noqa: E402
import zdir_ug2        # noqa: E402

SECTOR = 2048


def ug1(iso, out, perf=True, wheels=True, names=True, log=print):
    real = M.disc_names(iso)
    game = os.path.join(out, 'switch', 'nfsu1x', 'game')
    written = []
    for name, data in M.extras(lambda n: M.read_iso(iso, n), 'ug1', perf, wheels, names, log).items():
        path = os.path.join(game, *real[name].split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        written.append(real[name])
    return written


def ug2(iso, out, zdirs=(), vf_zzdata10=None, perf=True, wheels=True, names=True, log=print):
    packs = M.Packs(iso)
    more = M.extras(packs.read_all, 'ug2', perf, wheels, names, log)
    pack, manifest = M.ug2_pack(packs, more, vf_zzdata10, log)
    nd = os.path.join(out, 'switch', 'nfsu2x', 'game', 'NFSUNDER')
    os.makedirs(nd, exist_ok=True)
    with open(os.path.join(nd, 'ZZDATA12.BIN'), 'wb') as f:
        f.write(pack)
    with open(os.path.join(out, 'ZZDATA12.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1)
    verify_pack(pack, manifest, more)
    results = {}
    for name, src in zdirs:
        with open(src, 'rb') as f:
            zdir = f.read()
        log('ZDIR %s' % name)
        new, changed = zdir_ug2.apply(zdir, manifest, log=log)
        left = zdir_ug2.check_untouched(new, manifest)
        path = os.path.join(out, name, 'switch', 'nfsu2x', 'game', 'NFSUNDER', 'ZDIR.BIN')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(new)
        results[name] = (len(changed), left, diff_rows(zdir, new))
    return manifest, results


def verify_pack(pack, manifest, files):
    """Each file of the manifest read back from the pack, as made."""
    for f in manifest['files']:
        got = pack[f['sector'] * SECTOR:f['sector'] * SECTOR + f['size']]
        assert zdir_ug2.cksum(got) == f['cksum']
        if f.get('label') is None:
            assert got == files[f['name']]


def diff_rows(a, b):
    return [i for i in range(0, len(a), 24) if a[i:i + 24] != b[i:i + 24]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', required=True, choices=('ug1', 'ug2'))
    ap.add_argument('--iso', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--perf', default='rf184', choices=('rf184', 'keep'))
    ap.add_argument('--wheels', default='mx5', choices=('mx5', 'keep'))
    ap.add_argument('--names', default='on', choices=('on', 'off'))
    ap.add_argument('--vf-zzdata10')
    ap.add_argument('--zdir', action='append', default=[], help='NAME=path of a ZDIR.BIN to redirect')
    a = ap.parse_args()
    opts = dict(perf=a.perf == 'rf184', wheels=a.wheels == 'mx5', names=a.names == 'on')
    if a.game == 'ug1':
        print('\n'.join(ug1(a.iso, a.out, **opts)))
    else:
        zdirs = [z.split('=', 1) for z in a.zdir]
        _, results = ug2(a.iso, a.out, zdirs, a.vf_zzdata10, **opts)
        for name, (n, left, rows) in results.items():
            print('%s : %d entrées redirigées%s' % (name, n, ', NON REDIRIGÉES : %r' % left if left else ''))


if __name__ == '__main__':
    main()
