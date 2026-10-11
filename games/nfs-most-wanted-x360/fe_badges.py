"""Menu badges of a car: brand logo and model name (FRONTEND/FRONTB.LZC).

The car select screens show two textures of FRONTEND/FRONTB.LZC (a JDLZ-compressed bundle that
holds one big uncompressed texture pack):
- CARSELECT_MANUFACTURER_<BRAND>: brand logo, 128x64 DXT5, 3 mips (white on transparent);
- SECONDARY_LOGO_<CAR>: model name, 256x64 DXT5, 3 mips.

This tool copies another brand's logo over the car's brand logo (every brand logo has the same
size and format) and draws the model name from one or more pictures (dark artwork on a light
background, or white artwork with transparency). Only the changed bytes are re-encoded
(jdlz.splice), so the file stays almost as EA compressed it, then it is padded to the size given
by ZDIR.BIN.

python fe_badges.py --iso <360 image> --out <game_root> --car IS300 --brand LEXUS --logo MAZDA
                    --name mx5.png --name miata.png:0,0,560,330 [--preview badges.png]
"""
import argparse
import io
import os
import re
import struct

import numpy as np
from PIL import Image, ImageOps

import jdlz
import tpk
import tpk360
import xenos
import zzdata

FRONTB = zzdata.path('FRONTEND', 'FRONTB.LZC')
DATA_ALIGN = 0x1000  # texture data offsets count from the 0x33320003 payload aligned to 4 KiB

# brand of each car (CarTypeInfo ManufacturerName), for the cars one may want to replace
BRANDS = {'IS300': 'LEXUS', 'ELISE': 'LOTUS', 'RX8': 'MAZDA', 'RX7': 'MAZDA', 'GOLF': 'VOLKSWAGEN',
          'GTI': 'VOLKSWAGEN', 'PUNTO': 'FIAT', 'CLIO': 'RENAULT', 'COBALTSS': 'CHEVROLET',
          'A3': 'AUDI', 'TT': 'AUDI', 'A4': 'AUDI', 'ECLIPSEGT': 'MITSUBISHI',
          'LANCEREVOIX': 'MITSUBISHI', 'IMPREZAWRX': 'SUBARU', 'SUPRA': 'TOYOTA'}


def textures(fe):
    """name hash -> (texture info offset, info bytes), plus the base of the pixel data."""
    ib, ie = tpk.find(fe, 0x33310004)
    db, _ = tpk.find(fe, 0x33320003)
    out = {}
    for o in range(ib, ie, 0x7C):
        out[struct.unpack_from('<I', fe, o + 0x24)[0]] = o
    return out, (db + DATA_ALIGN - 1) & ~(DATA_ALIGN - 1)


def texture(fe, infos, base, name):
    o = infos[zzdata.bstringhash(name)]
    off, size = struct.unpack_from('<Ii', fe, o + 0x30)[0], struct.unpack_from('<i', fe, o + 0x38)[0]
    w, h = struct.unpack_from('<hh', fe, o + 0x44)
    return dict(name=name, start=base + off, size=size, w=w, h=h, comp=fe[o + 0x4A],
                mips=fe[o + 0x4E])


def mip_layout(w, h, mips):
    """[(w, h, byte offset of its tile, block x, block y)]: each level has its own tile of 32x32
    blocks (aligned); a level 16 texels high sits 16 texels down in it (found on
    SECONDARY_LOGO_IS300: 64x16 at block (0, 4) of the third tile)."""
    out = []
    off = 0
    for _ in range(mips):
        out.append((w, h, off, 0, 4 if h <= 16 else 0))
        wb, hb = (w + 3) // 4, (h + 3) // 4
        off += ((wb + 31) & ~31) * ((hb + 31) & ~31) * 16
        w, h = max(1, w // 2), max(1, h // 2)
    return out


def encode(img, size, mips):
    """RGBA image -> 360 DXT5 data with its mips, `size` bytes."""
    out = bytearray(size)
    for w, h, off, bx, by in mip_layout(img.width, img.height, mips):
        level = img.resize((w, h), Image.LANCZOS)
        alpha = level.getchannel('A')
        level = Image.new('RGBA', (w, h), (255, 255, 255, 255))  # white: same colour everywhere
        level.putalpha(alpha)
        lin = tpk360.dxt_linear(level, 'DXT5')
        wb, hb = (w + 3) // 4, (h + 3) // 4
        blocks = np.frombuffer(lin, np.uint8).reshape(-1, 2)[:, ::-1].reshape(-1, 16).copy()
        # fully transparent blocks as zero bytes, like EA's: they compress to almost nothing
        a = np.asarray(alpha).reshape(hb, 4, wb, 4).max(axis=(1, 3)).reshape(-1)
        blocks[a == 0] = 0
        aw = (max(wb, 32) + 31) & ~31
        for y in range(hb):
            for x in range(wb):
                t = xenos.tiled_offset(bx + x, by + y, aw, 16)
                out[off + t * 16:off + t * 16 + 16] = blocks[y * wb + x].tobytes()
    return bytes(out)


def decode(data, w, h):
    lin = xenos.untile(data, w, h, 16)
    hdr = struct.pack('<4sIIIIIII44xII4sIIIIIIIIII', b'DDS ', 124, 0x81007, h, w, len(lin), 0, 1,
                      32, 4, b'DXT5', 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    im = Image.open(io.BytesIO(hdr + lin))
    im.load()
    return im.convert('RGBA')


def artwork(spec):
    """'picture.png[:x0,y0,x1,y1]' -> white-on-transparent RGBA, cropped to its content."""
    path, _, crop = spec.rpartition(':')
    if not path or not re.fullmatch(r'\d+,\d+,\d+,\d+', crop):  # no crop (or a drive letter)
        path, crop = spec, ''
    im = Image.open(path)
    if crop:
        im = im.crop(tuple(int(v) for v in crop.split(',')))
    rgba = np.asarray(im.convert('RGBA'), dtype=np.float32)
    lum = rgba[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    if rgba[..., 3].min() < 250:  # already has transparency: keep it, light artwork
        alpha = rgba[..., 3] * np.clip(lum / 255, 0, 1)
    else:  # dark artwork on a light background
        alpha = np.clip((190 - lum) * 255 / 140, 0, 255)
    a = Image.fromarray(alpha.astype(np.uint8))
    box = a.point(lambda v: 255 if v > 24 else 0).getbbox()
    a = a.crop(box)
    out = Image.new('RGBA', a.size, (255, 255, 255, 0))
    out.putalpha(a)
    return out


def name_badge(specs, w, h, margin=(8, 6), gap=0.12):
    """Artwork pieces side by side, same height, fitted and centred in a w x h badge."""
    parts = [artwork(s) for s in specs]
    ph = max(p.height for p in parts)
    parts = [p.resize((max(1, round(p.width * ph / p.height)), ph), Image.LANCZOS) for p in parts]
    g = round(gap * ph)
    strip = Image.new('RGBA', (sum(p.width for p in parts) + g * (len(parts) - 1), ph),
                      (255, 255, 255, 0))
    x = 0
    for p in parts:
        strip.alpha_composite(p, (x, 0))
        x += p.width + g
    strip = ImageOps.contain(strip, (w - 2 * margin[0], h - 2 * margin[1]), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    out.alpha_composite(strip, ((w - strip.width) // 2, (h - strip.height) // 2))
    return out


def make_frontb(disc, car, brand=None, logo=None, names=(), verify=True, log=print):
    """FRONTEND/FRONTB.LZC with `car`'s brand logo replaced by `logo`'s and its model name drawn
    from `names` (artwork specs). Returns (file bytes at the size ZDIR.BIN gives, decompressed
    bundle, [textures changed])."""
    blob = disc.read(FRONTB)
    fe = bytearray(jdlz.decompress(blob))
    infos, base = textures(fe)
    changed, shown = [], []
    car = car.upper()
    if logo:
        brand = (brand or BRANDS.get(car, '')).upper()
        if not brand:
            raise ValueError('the brand of %s is needed' % car)
        if brand != logo.upper():
            dst = texture(fe, infos, base, 'CARSELECT_MANUFACTURER_' + brand)
            src = texture(fe, infos, base, 'CARSELECT_MANUFACTURER_' + logo.upper())
            assert (src['w'], src['h'], src['size'], src['mips']) ==                 (dst['w'], dst['h'], dst['size'], dst['mips'])
            fe[dst['start']:dst['start'] + dst['size']] = fe[src['start']:src['start'] + src['size']]
            changed.append((dst['start'], dst['start'] + dst['size']))
            shown.append(dst)
            log('logo %s <- %s' % (brand, logo.upper()))
    if names:
        t = texture(fe, infos, base, 'SECONDARY_LOGO_' + car)
        assert t['comp'] == 0x26, 'DXT5 expected'
        img = name_badge(names, t['w'], t['h'])
        fe[t['start']:t['start'] + t['size']] = encode(img, t['size'], t['mips'])
        changed.append((t['start'], t['start'] + t['size']))
        shown.append(t)
        log('model name SECONDARY_LOGO_%s <- %s' % (car, ', '.join(names)))
    if not changed:
        return None, fe, shown
    limit = disc.entries[zzdata.bstringhash(FRONTB)][2]
    new = jdlz.splice_to_fit(blob, bytes(fe), changed, limit)
    if new is None:
        raise ValueError('FRONTB.LZC does not fit in %d bytes: simplify the artwork' % limit)
    log('FRONTB.LZC: %d bytes compressed, %d allowed' % (len(new), limit))
    if verify:
        assert jdlz.game_decompress(new) == bytes(fe)
    return new + b'\0' * (limit - len(new)), fe, shown


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument('--iso', required=True)
    ap.add_argument('--out', required=True, help='game_root: writes FRONTEND/FRONTB.LZC')
    ap.add_argument('--car', default='IS300', help='car whose badges change')
    ap.add_argument('--brand', help='its brand (CarTypeInfo ManufacturerName), e.g. LEXUS')
    ap.add_argument('--logo', help='brand whose logo replaces it, e.g. MAZDA')
    ap.add_argument('--name', action='append', default=[],
                    help='model name artwork, picture[:x0,y0,x1,y1]; repeat to put several side by side')
    ap.add_argument('--preview', help='PNG of the resulting badges')
    a = ap.parse_args()
    if not a.logo and not a.name:
        ap.error('nothing to do: give --logo and/or --name')
    data, fe, shown = make_frontb(zzdata.Disc(a.iso), a.car, a.brand, a.logo, a.name)
    path = os.path.join(a.out, 'FRONTEND', 'FRONTB.LZC')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    print('written', path)
    if a.preview:
        sheet = Image.new('RGBA', (16 + 384 + 256, 16 + 64 * 2), (24, 24, 32, 255))
        x = 8
        for t in shown:
            sheet.alpha_composite(decode(bytes(fe[t['start']:]), t['w'], t['h']), (x, 8))
            x += t['w'] + 16
        sheet.save(a.preview)
        print('preview', a.preview)


if __name__ == '__main__':
    main()
