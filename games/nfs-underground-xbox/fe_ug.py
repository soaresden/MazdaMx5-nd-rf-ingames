"""The MX-5 RF's name badge in the car menus of Need for Speed Underground and Underground 2.

The car select shows SECONDARY_LOGO_<CAR> of the frontend pack, 256 x 64 DXT3, white with the
artwork in the alpha: "Mazda" over "Miata" in script and a small "MX-5" for the Miata. The game
also has SECONDARY_LOGO_MX5 ("Mazda" over "MX-5", the European name) and, in Underground 2,
SECONDARY_LOGO_MIATA_RO ("Mazda" over "Roadster", the Japanese one). All of them become the
"Mazda / MX-5 RF" badge: the game's own "Mazda" and "MX-5" (from SECONDARY_LOGO_MX5), and an "RF"
drawn after them with the strokes of that "MX-5" (stem and bar widths, corners, height measured
on it), the line made smaller if it no longer fits.

Underground: FRONTEND/FRONTB.BUN (and FRONTEND/FrontB.lzc, the same data JDLZ-compressed: the
game knows both names), 4 mip levels. Underground 2: FRONTEND\\FRONTB.LZC in the ZZDATA packs,
1 level. Texture pack 0xB3300000: texture info 0x33310004 (124 bytes each: +0x0C name, +0x30
data offset, +0x38 size, +0x44 u16 width, height), Xbox info 0x33310005 (60 bytes: +0x0C format,
0x0E = DXT3); pixels from the payload of 0x33320001 (Underground) / 0x33320002 (Underground 2)
rounded up to 128 bytes, linear, largest level first.
"""
import io
import struct

import numpy as np
from PIL import Image, ImageDraw

TEMPLATE = 'SECONDARY_LOGO_MX5'
TARGETS = {'ug1': ('SECONDARY_LOGO_MIATA', 'SECONDARY_LOGO_MX5'),
           'ug2': ('SECONDARY_LOGO_MIATA', 'SECONDARY_LOGO_MX5', 'SECONDARY_LOGO_MIATA_RO')}
DXT3 = 0x0E


def _chunks(d, o, end, out):
    while o + 8 <= end:
        cid, size = struct.unpack_from('<II', d, o)
        out.setdefault(cid, (o + 8, o + 8 + size))
        if cid & 0x80000000:
            _chunks(d, o + 8, o + 8 + size, out)
        o += 8 + size
    return out


def textures(fe):
    """{name: dict(info offset, start, size, w, h, mips, fmt)} of the frontend texture pack."""
    c = _chunks(fe, 0, len(fe), {})
    b4, e4 = c[0x33310004]
    b5, _ = c[0x33310005]
    pix = c.get(0x33320002, c.get(0x33320001))[0]
    base = (pix + 0x7F) & ~0x7F
    out = {}
    for k in range((e4 - b4) // 124):
        o = b4 + 124 * k
        name = fe[o + 12:o + 36].split(b'\0')[0].decode('latin-1')
        w, h = struct.unpack_from('<HH', fe, o + 0x44)
        size = struct.unpack_from('<I', fe, o + 0x38)[0]
        mips, n, lw, lh = 0, 0, w, h
        while n < size:
            n += max(1, lw // 4) * max(1, lh // 4) * 16
            mips += 1
            lw, lh = max(1, lw // 2), max(1, lh // 2)
        out[name] = dict(info=o, start=base + struct.unpack_from('<I', fe, o + 0x30)[0], size=size,
                         w=w, h=h, mips=mips, fmt=struct.unpack_from('<I', fe, b5 + 60 * k + 12)[0])
    return out


def decode(data, w, h):
    hdr = struct.pack('<4sIIIIIII44xII4sIIIIIIIIII', b'DDS ', 124, 0x81007, h, w, w * h, 0, 1,
                      32, 4, b'DXT3', 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    im = Image.open(io.BytesIO(hdr + bytes(data[:w * h])))
    im.load()
    return im.convert('RGBA')


def encode(alpha, mips):
    """Alpha (h x w, 0..255 float) -> DXT3 levels, white texels (as EA's badges)."""
    out = bytearray()
    a = alpha.astype(np.float64)
    for level in range(mips):
        h, w = a.shape
        q = np.clip(np.round(a / 17.0), 0, 15).astype(np.uint8)   # 4 bits
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                b = q[by:by + 4, bx:bx + 4].reshape(-1)
                out += bytes((b[i] | (b[i + 1] << 4)) for i in range(0, 16, 2))
                out += b'\xff\xff\xff\xff\x00\x00\x00\x00'
        if level + 1 < mips:
            a = a.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    return bytes(out)


def _runs(mask):
    idx = np.flatnonzero(mask)
    if not len(idx):
        return []
    cuts = np.flatnonzero(np.diff(idx) > 1)
    starts = np.r_[idx[0], idx[cuts + 1]]
    ends = np.r_[idx[cuts], idx[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


def measure(alpha):
    """The two lines of the badge and the strokes of its 'MX-5'."""
    rows = _runs(alpha.max(axis=1) > 40)
    if len(rows) < 2:
        raise ValueError('badge : deux lignes attendues')
    (t0, t1), (l0, l1) = rows[0], rows[-1]
    line = alpha[l0:l1 + 1]
    cols = _runs(line.max(axis=0) > 40)
    x0, x1 = cols[0][0], cols[-1][1]
    five = cols[-1]
    ink = line > 128
    mid = (l1 - l0) // 2
    stem = _runs(ink[mid, cols[0][0]:cols[0][1] + 1])[0]
    cx = (five[0] + five[1]) // 2
    bars = _runs(ink[:, cx])                 # top, middle and bottom bars of the 5
    return dict(top=(t0, t1), line=(l0, l1), x=(x0, x1), five=five, glyph_gap=cols[-1][0] - cols[-2][1] - 1,
                stem=stem[1] - stem[0] + 1, bar=bars[0][1] - bars[0][0] + 1,
                mid=(bars[1][0] + bars[1][1]) / 2.0 if len(bars) > 2 else (l1 - l0) * 0.47,
                level=float(np.median(line[ink])) if ink.any() else 255.0)


def draw_rf(m, scale=8):
    """'RF' alpha (float 0..1) at the height of the line, in the strokes of its 'MX-5'."""
    h = m['line'][1] - m['line'][0] + 1
    wr = m['five'][1] - m['five'][0] + 1          # R as wide as the 5
    wf = int(round(wr * 0.86))
    gap = max(2, m['glyph_gap'])
    sv, sh, ym = m['stem'], m['bar'], m['mid']
    W, H = (wr + gap + wf + 2) * scale, h * scale
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    S = float(scale)
    rad = max(1.0, sh * 1.1) * S
    # R: stem, bowl (outer minus inner), leg
    bowl_bot = (ym + sh / 2.0) * S
    d.rectangle([0, 0, sv * S - 1, H - 1], fill=255)
    d.rounded_rectangle([0, 0, wr * S - 1, bowl_bot], radius=rad, fill=255)
    d.rounded_rectangle([sv * S, sh * S, (wr - sv) * S - 1, bowl_bot - sh * S],
                        radius=max(0.0, rad - min(sv, sh) * S), fill=0)
    d.rectangle([0, 0, sv * S - 1, H - 1], fill=255)
    leg = sv * 1.15
    xa = wr * 0.42
    d.polygon([(xa * S, bowl_bot - sh * S), ((xa + leg) * S, bowl_bot - sh * S),
               (wr * S, H), ((wr - leg) * S, H)], fill=255)
    # F: stem, top bar, middle bar
    fx = (wr + gap) * S
    d.rectangle([fx, 0, fx + sv * S - 1, H - 1], fill=255)
    d.rectangle([fx, 0, fx + wf * S - 1, sh * S - 1], fill=255)
    d.rectangle([fx, (ym - sh / 2.0) * S, fx + wf * 0.82 * S - 1, (ym + sh / 2.0) * S - 1], fill=255)
    small = im.resize((W // scale, h), Image.BOX)
    return np.asarray(small, np.float64) / 255.0


def badge(template_rgba):
    """'Mazda / MX-5 RF' alpha (64 x 256 float 0..255) from SECONDARY_LOGO_MX5."""
    a = np.asarray(template_rgba, np.float64)[..., 3]
    m = measure(a)
    l0, l1 = m['line']
    x0, x1 = m['x']
    mx5 = a[l0:l1 + 1, x0:x1 + 1] / 255.0
    rf = draw_rf(m) * (m['level'] / 255.0)
    h = l1 - l0 + 1
    space = int(round(h * 0.75))
    line = np.zeros((h, mx5.shape[1] + space + rf.shape[1]))
    line[:, :mx5.shape[1]] = mx5
    line[:, mx5.shape[1] + space:] = rf
    W = a.shape[1]
    fit = min(1.0, (W - 16) / float(line.shape[1]))
    img = Image.fromarray((line * 255).astype(np.uint8))
    if fit < 1.0:
        img = img.resize((max(1, int(round(line.shape[1] * fit))), max(1, int(round(h * fit)))),
                         Image.LANCZOS)
    piece = np.asarray(img, np.float64)
    out = a.copy()
    out[l0:l1 + 1, :] = 0
    cx = (x0 + x1 + 1) / 2.0
    cy = (l0 + l1 + 1) / 2.0
    px = int(round(cx - piece.shape[1] / 2.0))
    py = int(round(cy - piece.shape[0] / 2.0))
    px = min(max(px, 0), W - piece.shape[1])
    out[py:py + piece.shape[0], px:px + piece.shape[1]] = piece
    return out


def patch(fe, game, log=print):
    """(new frontend bytes, [(start, end)] changed, preview RGBA image)."""
    tex = textures(fe)
    t = tex[TEMPLATE]
    if t['fmt'] != DXT3 or (t['w'], t['h']) != (256, 64):
        raise ValueError('%s : DXT3 256x64 attendu' % TEMPLATE)
    alpha = badge(decode(fe[t['start']:t['start'] + t['size']], 256, 64))
    out = bytearray(fe)
    ranges = []
    for name in TARGETS[game]:
        x = tex.get(name)
        if x is None:
            continue
        if x['fmt'] != DXT3 or (x['w'], x['h']) != (256, 64):
            raise ValueError('%s : DXT3 256x64 attendu' % name)
        data = encode(alpha, x['mips'])
        assert len(data) == x['size'], (name, len(data), x['size'])
        out[x['start']:x['start'] + x['size']] = data
        ranges.append((x['start'], x['start'] + x['size']))
        log('  %s : Mazda / MX-5 RF (%d niveau%s)' % (name, x['mips'], 'x' if x['mips'] > 1 else ''))
    # read back
    again = textures(bytes(out))
    for name in TARGETS[game]:
        if name in again:
            x = again[name]
            got = np.asarray(decode(out[x['start']:x['start'] + x['size']], 256, 64))[..., 3]
            assert np.abs(got.astype(int) - np.clip(np.round(alpha / 17) * 17, 0, 255)).max() <= 1
    before = [decode(fe[tex[n]['start']:], 256, 64) for n in TARGETS[game] if n in tex]
    after = decode(out[tex[TARGETS[game][0]]['start']:], 256, 64)
    sheet = Image.new('RGBA', (16 + 264 * (len(before) + 1), 80), (24, 24, 40, 255))
    for i, im in enumerate(before + [after]):
        sheet.alpha_composite(im, (8 + 264 * i, 8))
    return bytes(out), ranges, sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)


def patch_lzc(blob, new_fe, ranges, limit=None):
    """The JDLZ copy of the pack with the same changes, re-encoded only around them; no bigger
    than `limit` (default: the original size). Checked with the game's decoder."""
    import jdlz
    limit = len(blob) if limit is None else limit
    new = jdlz.splice_to_fit(blob, new_fe, ranges, limit)
    if new is None:
        raise ValueError('FRONTB.LZC ne tient pas dans %d octets' % limit)
    assert jdlz.game_decompress(new) == new_fe
    return new
