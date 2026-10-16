"""Make the MX-5 RF for Gran Turismo 2 (PAL): a patched image of the Simulation disc, of a
combined disc (GT2-Combined-Disc) or of GT2 Plus.

python make_gt2.py --disc "Gran Turismo 2 Combined (Europe).chd" --kn5 mazda_mx5_rf.kn5
                   --out "GT2 MX-5 RF.chd" [--car aminn=closed --car amivn=open ...]

The RF replaces the MX-5s given (default: the '93, the 7735 Cr one in the used cars, hardtop
closed; the V-Special '93, the 8084 Cr one, top down), and their racing versions (the bodies the
racing modification puts on). Everything is made from the player's own disc and Assetto Corsa
model; nothing of either is in this repository.
"""
import argparse
import gzip
import os
import struct
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_gt2car  # noqa: E402  (puts ../gran-turismo-ps1 and ../../common in the path)
import chdmake       # noqa: E402
import gt2data       # noqa: E402
import gt2disc       # noqa: E402
import gt2menu       # noqa: E402

# the MX-5s of GT2 (road car codes; the racing version of each ends in 'r'). Their names are
# read from the disc (.carinfoe): mx5_names()
MX5 = ('aminn', 'amisn', 'amivn', 'an16n', 'as16n', 'av16n', 'arodn',
       'a26sn', 'a2vsn', 'a2abn', 'a2ran', 'a2rcn', 'a2rdn')
# the '93 sold used at 7735 Cr, hardtop closed; the V-Special '93 at 8084 Cr, top down
DEFAULT = {'aminn': 'closed', 'amivn': 'open'}
USED_OPEN = 8084   # the used '93 sold as the V-Special: the RF top down
VERSION = 'HD PLUS'   # written on the start screens
PLUS_VERSION = 'beta 7'   # the GT2 Plus the tool was made with (its volume is GRANTURISMO2PLUS)


def mx5_names(vol):
    """{code: name in the European lists} of the MX-5s on the disc."""
    d = vol.read('.carinfoe')
    j = vol.read('.carinfoj')
    n, = struct.unpack_from('<I', d, 4)
    out = {}
    for i in range(n):
        cid, off, _ = struct.unpack_from('<IHH', d, (i + 1) * 8)
        code = gt2data.car_code(cid)
        if code in MX5:
            colours = ((struct.unpack_from('<H', j, (i + 1) * 8 + 6)[0] & 0x3C) >> 2) + 1
            o = off + colours * 3
            out[code] = d[o + 1:o + 1 + d[o]].decode('latin-1')
    return out
EXTS = ('.cdo', '.cno', '.cdp', '.cnp')


def regz(original, data):
    """data gzipped with the original's header (file name, time), as the disc's files are."""
    flg = original[3]
    end = 10
    if flg & 4:
        end += 2 + struct.unpack_from('<H', original, 10)[0]
    if flg & 8:
        end = original.index(b'\0', end) + 1
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    body = c.compress(data) + c.flush()
    head = bytearray(original[:end])
    head[3] = flg & 8   # name only
    return bytes(head) + body + struct.pack('<II', zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)


def generate(image, kn5, cars, log=print, version=None, sub=None):
    """(Gt2Disc, {VOL path: new bytes}). cars: {code: 'closed' | 'open'}."""
    d = gt2disc.Gt2Disc(image)
    vol = d.vol
    new = {}
    # the racing versions follow their road car
    todo = dict(cars)
    for code, top in cars.items():
        r = code[:-1] + 'r'
        if 'carobj/%s.cdo.gz' % r in vol.paths:
            todo[r] = top
    log('1/4 les modèles (%s)' % ', '.join('%s %s' % (c, 'décapotée' if t == 'open' else 'capotée') for c, t in todo.items()))
    for code, top in todo.items():
        orig = {e: vol.read('carobj/%s%s.gz' % (code, e)) for e in EXTS}
        raw = {e: gzip.decompress(b) for e, b in orig.items()}
        cdo, cno, cdp, cnp, _ = build_gt2car.build(kn5, top, raw['.cdo'], raw['.cdp'], raw['.cnp'], log=lambda *a: None)
        for e, b in zip(EXTS, (cdo, cno, cdp, cnp)):
            new['carobj/%s%s.gz' % (code, e)] = regz(orig[e], b)
        log('  %s : %d sommets, %d octets' % (code, len(build_gt2car.gt2model.read(cdo).lods[0].verts), len(cdo)))
    log('2/4 caractéristiques et noms')
    variants = {c: (1 if t == 'open' else 0) for c, t in cars.items()}
    for lang in gt2data.LANGS:
        pre = lang + '_' if lang else ''
        gp, sp = 'carparam/%sgtmode_data.dat.gz' % pre, 'carparam/%sunistrdb.dat.gz' % pre
        if gp not in vol.paths or sp not in vol.paths:
            continue
        g0, s0 = vol.read(gp), vol.read(sp)
        strings = gt2data.Strings(gzip.decompress(s0))
        g, done = gt2data.patch_gtmode(gzip.decompress(g0), variants, strings, lang)
        new[gp] = regz(g0, g)
        new[sp] = regz(s0, strings.bytes())
        log('  %s : %s' % (lang or 'jpn', ', '.join(done)))
    for r in 'jae':
        p = '.carinfo' + r
        new[p] = gt2data.rename_carinfo(vol.read(p), r, variants)
    log('  peintures : %s' % ', '.join(n for n, _ in gt2data.PAINTS))
    new['.carcolor'], new['.cclatain'], new['.ccjapanese'] = gt2data.name_colours(
        vol.read('.carcolor'), vol.read('.cclatain'), vol.read('.ccjapanese'), vol.read('.carinfoj'), variants)
    log('3/4 menus : titres, description, occasions')
    menus(vol, todo, cars, new, log)
    plus = b'PLUS' in d.c.user_data(16)[40:72]
    if version is None:
        # GT2 Plus: "HD PLUS" and its version with the RF; the other discs: the RF alone
        version = VERSION if plus else 'MX-5 RF'
    if version:
        if sub is None:
            sub = PLUS_VERSION + ' · MX-5 RF' if plus else ''
        start_screens(vol, version, sub, new, log)
    return d, new


def same_pages(m, a, b):
    """Whether the two-page descriptions at screens a and b show the same (their tiles may be
    stored in another order)."""
    for k in (0, 1):
        x, y = m.screen(a + k), m.screen(b + k)
        if len(x) != len(y):
            return False
        try:
            ix, iy = gt2menu.Screen(x).index, gt2menu.Screen(y).index
        except ValueError:
            return False
        if ix.shape != iy.shape or not (ix == iy).all():
            return False
    return True


def start_screens(vol, text, sub, new, log=print):
    """The version badge (`text`, `sub` under it) on the language screen and the title screens."""
    done = 0
    for p, place in gt2menu.VERSION_PLACES.items():
        if p in vol.paths:
            g = vol.read(p)
            new[p] = regz(g, gt2menu.version_screen(gzip.decompress(g), text, place, sub))
            done += 1
    log('  « %s » (%s) sur %d écrans de démarrage (langues, titres)' % (text, sub, done))


def menus(vol, todo, cars, new, log=print):
    """The RF's title pictures, its description in every language, the used car dealer."""
    titles = 0
    for code in todo:
        for k, letter in enumerate('lmnopq'):
            p = 'carlogo/%s%s--.tim' % (code, letter)
            if p in vol.paths:
                new[p] = gt2menu.title_tim(vol.read(p))
                titles += 1
    log('  titres « Mazda MX-5 RF » : %d images' % titles)
    road = [gt2data.car_id(c) for c in cars]
    for lang in gt2menu.LANGS:
        base = 'gtmenu/%s/' % lang
        if base + 'gtmenudat.dat' not in vol.paths:
            continue
        sp = base + 'solodata.dat.gz'
        s0 = vol.read(sp)
        solo = gt2menu.Solo(gzip.decompress(s0))
        pages = [solo.page(c) for c in road if solo.page(c) is not None]
        if not pages:
            continue
        m = gt2menu.MenuData(vol.read(base + 'gtmenudat.idx'), vol.read(base + 'gtmenudat.dat'))
        users = {}
        for c, pg in solo.rows:
            users.setdefault(pg, set()).add(c)
        # the pages to write over: those that only the replaced cars show; else the other cars
        # that show them go to a copy of the same text (the Eunos' is on the disc twice: GT2 Plus
        # gives the '93's to its special Roadster too, the '89 has the copy)
        own = [pg for pg in pages if users[pg] <= set(road)]
        if own:
            page = own[0]
        else:
            page = pages[0]
            same = [pg for pg in sorted(users) if pg != page and same_pages(m, pg, page)]
            others = users[page] - set(road)
            if same:
                for c in others:
                    solo.set_page(c, same[0])
                log('  %s : %s -> la copie de leur description (pages %d-%d)' % (
                    lang, ', '.join(gt2data.car_code(c) for c in others), same[0], same[0] + 1))
            else:
                log("  %s : la description est aussi celle de %s" % (lang, ', '.join(gt2data.car_code(c) for c in others)))
        a, b = gt2menu.description_pages(m.screen(page), m.screen(page + 1), gt2menu.TEXTS[lang])
        m.set(page, a)
        m.set(page + 1, b)
        for c in road:
            solo.set_page(c, page)
        new[base + 'gtmenudat.idx'], new[base + 'gtmenudat.dat'] = m.bytes()
        new[sp] = regz(s0, solo.bytes())
        log('  description %s : pages %d-%d' % (lang, page, page + 1))
    # the used car dealer: the '93 at 8084 Cr becomes the V-Special (the RF top down)
    if cars.get('aminn') == 'closed' and cars.get('amivn') == 'open':
        for p in ('.usedcar', '.usedcar_usa', '.usedcar_jpn'):
            if p not in vol.paths:
                continue
            u0 = vol.read(p)
            gz = u0[:2] == bytes([0x1F, 0x8B])
            raw = gzip.decompress(u0) if gz else u0
            out, n = gt2menu.move_used_car(raw, gt2data.car_id('aminn'), USED_OPEN, gt2data.car_id('amivn'), '1')
            if n:
                new[p] = regz(u0, out) if gz else out
                log('  %s : %d annonce(s) à %d Cr -> la RF décapotée' % (p, n, USED_OPEN))


def cheat_patcher():
    """gt2cheat.patcher of the GranTurismo2-OverlayCheat project (github.com/soaresden/
    GranTurismo2-OverlayCheat): next to this script in the Windows package (outils/gt2cheat),
    else the project's folder next to this repository, or GT2CHEAT_DIR."""
    for base in (os.environ.get('GT2CHEAT_DIR', ''), os.path.join(HERE, '..', '..'),
                 os.path.join(HERE, '..', '..', '..', 'GranTurismo2-OverlayCheat')):
        if base and os.path.isfile(os.path.join(base, 'gt2cheat', 'patcher.py')):
            if base not in sys.path:
                sys.path.insert(0, base)
            from gt2cheat import patcher
            return patcher
    raise SystemExit('cheat introuvable : il faut le projet GranTurismo2-OverlayCheat '
                     '(dossier gt2cheat), ou GT2CHEAT_DIR')


def cheat_files(d, log=print):
    """{disc file: new bytes} of the overlay cheat (SELECT: freeze the licence timer, credits)."""
    patcher = cheat_patcher()
    log('+ le cheat GranTurismo2-OverlayCheat (SELECT : chrono des permis, crédits)')
    try:
        return {'SCES_123.80': patcher.patch_exe(d.read('SCES_123.80')),
                'GT2.OVL': patcher.patch_ovl(d.read('GT2.OVL'))}
    except patcher.PatchError as e:
        raise SystemExit('cheat : %s' % e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--disc', required=True, help='your Gran Turismo 2 disc image (Simulation, combined or GT2 Plus): .chd, .cue or .bin')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--out', required=True, help='.chd or .bin to write (a .bin gets its .cue)')
    ap.add_argument('--version', default=None,
                    help='text written on the language and title screens (default: "HD PLUS" on GT2 Plus, else "MX-5 RF"; "": none)')
    ap.add_argument('--version-sub', default=None,
                    help='the line under it (default: "beta 7 · MX-5 RF" on GT2 Plus, else none)')
    ap.add_argument('--car', action='append', metavar='CODE=closed|open',
                    help='MX-5 to replace and its roof (repeat; default: aminn=closed, amivn=open)')
    ap.add_argument('--cheat', action='store_true',
                    help='add the GranTurismo2-OverlayCheat menu (hold SELECT: licence timer, credits)')
    a = ap.parse_args()
    t0 = time.time()
    cars = {}
    for c in a.car or ['%s=%s' % kv for kv in DEFAULT.items()]:
        code, _, top = c.partition('=')
        if code not in MX5:
            raise SystemExit('%s : pas une MX-5 du jeu (%s)' % (code, ', '.join(MX5)))
        if top not in ('closed', 'open'):
            raise SystemExit('%s : toit %r (closed ou open)' % (code, top))
        cars[code] = top
    src = os.path.abspath(a.disc)
    if src.lower() == os.path.abspath(a.out).lower():
        raise SystemExit('--out écraserait ton image : choisis un autre nom')
    d, new = generate(a.disc, a.kn5, cars, version=a.version, sub=a.version_sub)
    files = cheat_files(d) if a.cheat else None
    size, delta = d.plan(new)
    print('4/4 l\'image du disque (GT2.VOL %d Mo%s)' % (
        size >> 20, ', %d secteurs de plus : les fichiers suivants décalés' % delta if delta else ''))
    out = a.out
    progress = lambda i, n: print('  %d%%' % (100 * i // n), end='\r')
    if out.lower().endswith('.chd'):
        # the .bin on the way to the .chd: a name no emulator or frontend takes for a game (in a
        # roms folder, Batocera opened the .bin while the .chd was being made)
        part = out + '.bin.part'
        with open(part, 'wb') as f:
            for b in d.bin_chunks(new, progress=progress, files=files):
                f.write(b)
        chdmake.write(part, out, 'MODE2_RAW')
        try:
            os.remove(part)
        except OSError as e:
            print('(%s reste à effacer : %s)' % (part, e.strerror))
    else:
        d.write_bin(out, new, progress=progress, files=files)
    print('écrit', out, 'en %.0f s' % (time.time() - t0))


if __name__ == '__main__':
    main()
