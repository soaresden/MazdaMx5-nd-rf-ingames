"""Car TEXTURES.BIN of Need for Speed Underground (Xbox): its textures, and new pixels for some of
them in place (same size, format and mip count: the file keeps its layout).

  0xB3300000 { 0xB3310000 { 0x33310001 header, 0x33310002 hashes, 0x33310003 data table,
                            0x33310004 texture info (124 bytes each), 0x33310005 Xbox info (60) },
               0x33320001 pixels }
Texture info: +0x0C name (24), +0x24 hash, +0x30 data offset (from the start of the pixels),
+0x38 data size, +0x44 u16 width, height, +0x4E u8 mip levels. Xbox info: +0x0C format
(0x0C DXT1, 0x0E DXT3, 0x0B 8-bit paletted). DXT data is linear (not swizzled), largest mip first.
"""
import struct

import numpy as np

DXT1, DXT3, P8 = 0x0C, 0x0E, 0x0B


def _find(d, cid, o=0, end=None):
    end = len(d) if end is None else end
    while o + 8 <= end:
        c, s = struct.unpack_from('<II', d, o)
        if c == cid:
            return o + 8, o + 8 + s
        if c & 0x80000000:
            r = _find(d, cid, o + 8, o + 8 + s)
            if r:
                return r
        o += 8 + s
    return None


def xbox_swizzle(w, h):
    """Offset of each texel (y, x) in an Xbox swizzled texture: the bits of x and y interleaved
    (x first) while both have bits left, then the remaining ones."""
    ys, xs = np.mgrid[0:h, 0:w]
    off = np.zeros_like(xs)
    bit = bx = by = 0
    wb, hb = w.bit_length() - 1, h.bit_length() - 1
    while bx < wb or by < hb:
        if bx < wb:
            off |= ((xs >> bx) & 1) << bit
            bit += 1
            bx += 1
        if by < hb:
            off |= ((ys >> by) & 1) << bit
            bit += 1
            by += 1
    return off


def _p8(im, t, stock):
    """8-bit paletted texture data: swizzled indices of each mip level, then the 256-colour palette
    (BGRA), as the Miata's headlight textures store them. The game keeps the texture's original
    palette (a new one is ignored: the black cockpit came out cream and orange, the headlight's
    colours), so the pixels take the nearest colours of the original palette, which is kept."""
    from PIL import Image
    w, h = t['w'], t['h']
    pal = np.frombuffer(stock[-1024:], np.uint8).reshape(256, 4)
    ref = Image.new('P', (1, 1))
    ref.putpalette(pal[:, 2::-1].ravel().tolist())
    q = im.convert('RGB').resize((w, h), Image.LANCZOS).quantize(palette=ref, dither=Image.Dither.NONE)
    out = b''
    for level in range(max(1, t['mips'])):
        lw, lh = max(1, w >> level), max(1, h >> level)
        idx = np.asarray(q if level == 0 else q.resize((lw, lh), Image.NEAREST), np.uint8)
        flat = np.zeros(lw * lh, np.uint8)
        flat[xbox_swizzle(lw, lh).ravel()] = idx.ravel()
        out += flat.tobytes()
    out = out[:t['size']].ljust(t['size'], b'\0')
    return out + pal.tobytes()


class Tpk:
    """0x33310003 gives, per texture: hash, file offset and size of its JDLZ-compressed pixels,
    flags; the streams follow each other in 0x33320001 (its payload padded with 0x11 to 0x80)."""

    def __init__(self, data):
        self.data = bytes(data)
        b4, e4 = _find(data, 0x33310004)
        b5, _ = _find(data, 0x33310005)
        self.table = _find(data, 0x33310003)
        self.pix = _find(data, 0x33320001)
        self.tex = []
        for k in range((e4 - b4) // 124):
            r = data[b4 + 124 * k:b4 + 124 * (k + 1)]
            t = dict(index=k, name=r[12:36].split(b'\0')[0].decode('latin-1'),
                     hash=struct.unpack_from('<I', r, 0x24)[0], size=struct.unpack_from('<I', r, 0x38)[0],
                     w=struct.unpack_from('<H', r, 0x44)[0], h=struct.unpack_from('<H', r, 0x46)[0],
                     mips=r[0x4E], fmt=struct.unpack_from('<I', data, b5 + 60 * k + 12)[0])
            self.tex.append(t)
        self.by_hash = {t['hash']: t for t in self.tex}
        b, e = self.table
        self.streams = [list(struct.unpack_from('<5I', data, o)) for o in range(b, e, 20)]
        self.new = {}

    def pixels(self, hash_):
        import jdlz
        for h, off, size, flags, _ in self.streams:
            if h == hash_:
                return jdlz.decompress(self.data[off:off + size])
        raise KeyError(hex(hash_))

    def put(self, hash_, rgba):
        """New pixels (RGBA uint8 array, any size: resized) for the texture `hash_`, encoded in
        its format with its mip levels."""
        from PIL import Image
        import dxt
        t = self.by_hash[hash_]
        im = Image.fromarray(np.asarray(rgba, np.uint8), 'RGBA')
        if t['fmt'] == P8:
            self.new[hash_] = _p8(im, t, self.pixels(hash_))
            return t
        if t['fmt'] not in (DXT1, DXT3):
            raise ValueError('%s: format %#x not supported' % (t['name'], t['fmt']))
        kind = 'DXT1' if t['fmt'] == DXT1 else 'DXT3'
        out = b''
        w, h = t['w'], t['h']
        for level in range(max(1, t['mips'])):
            lw, lh = max(4, w >> level), max(4, h >> level)
            out += dxt.encode(im.resize((lw, lh), Image.LANCZOS), kind)
        out = out[:t['size']].ljust(t['size'], b'\0')
        self.new[hash_] = out
        return t

    def write(self):
        import jdlz
        d = self.data
        pb, pe = self.pix
        start = pb + ((-pb) % 0x80)
        blobs = []
        for h, off, size, flags, z in self.streams:
            blobs.append(jdlz.compress(self.new[h]) if h in self.new else d[off:off + size])
        body = bytearray(d[pb:start])
        table = bytearray()
        pos = start
        for (h, off, size, flags, z), blob in zip(self.streams, blobs):
            table += struct.pack('<5I', h, pos, len(blob), flags, z)
            body += blob
            pos += len(blob)
        old_end = max(off + size for _, off, size, _, _ in self.streams)
        body += d[old_end:pe]                       # what followed the streams in the chunk
        tb, te = self.table
        out = bytearray(d[:tb]) + table + d[te:pb - 8]
        out += struct.pack('<II', 0x33320001, len(body)) + body
        out += d[pe:]
        # sizes of the enclosing chunks: the outer pack and the ones in front of the pixels
        outer, = struct.unpack_from('<I', d, 4)
        struct.pack_into('<I', out, 4, outer + (len(out) - len(d)))
        return bytes(out)


class Tpk2:
    """Underground 2 (Xbox): 0x33310003 gives per texture hash, file offset, compressed and
    uncompressed sizes, flags; each JDLZ (or HUFF) stream holds the pixels, then the texture info (124
    bytes, as in Underground) and the Xbox info (60 bytes). The streams sit in 0x33320002, each on
    a 64-byte boundary."""
    TAIL = 124 + 60

    def __init__(self, data):
        import huff
        import jdlz
        self.data = bytes(data)
        self.table = _find(data, 0x33310003)
        self.pix = _find(data, 0x33320002)
        b, e = self.table
        self.streams = [list(struct.unpack_from('<IIiiII', data, o)) for o in range(b, e - 23, 24)]
        self.tex = []
        self.raw = {}
        for h, off, size, usize, flags, z in self.streams:
            blob = self.data[off:off + size]
            raw = huff.decompress(blob) if blob[:4] == b'HUFF' else jdlz.decompress(blob)
            info = raw[-self.TAIL:-60]
            plat = raw[-60:]
            t = dict(hash=h, name=info[12:36].split(b'\0')[0].decode('latin-1'),
                     w=struct.unpack_from('<H', info, 0x44)[0], h=struct.unpack_from('<H', info, 0x46)[0],
                     mips=info[0x4E], fmt=struct.unpack_from('<I', plat, 12)[0], size=len(raw) - self.TAIL)
            self.tex.append(t)
            self.raw[h] = raw
        self.by_hash = {t['hash']: t for t in self.tex}
        self.new = {}

    def pixels(self, hash_):
        return self.raw[hash_][:-self.TAIL]

    put = Tpk.put

    def write(self):
        import jdlz
        d = self.data
        pb, pe = self.pix
        by_off = sorted(range(len(self.streams)), key=lambda i: self.streams[i][1])
        first = self.streams[by_off[0]][1]
        body = bytearray(d[pb:first])
        pos = first
        new_entries = {}
        last_end = first
        for i in by_off:
            h, off, size, usize, flags, z = self.streams[i]
            if h in self.new:
                raw = self.new[h] + self.raw[h][-self.TAIL:]
                blob = jdlz.compress(raw)
                usize = len(raw)
            else:
                blob = d[off:off + size]
            pad = (-pos) % 0x40
            body += d[last_end:last_end + pad] if last_end + pad <= off else bytes(pad)
            pos += pad
            new_entries[i] = (h, pos, len(blob), usize, flags, z)
            body += blob
            pos += len(blob)
            last_end = off + size
        body += d[last_end:pe]
        tb, te = self.table
        table = b''.join(struct.pack('<IIiiII', *new_entries[i]) for i in range(len(self.streams)))
        out = bytearray(d[:tb]) + table + d[te:pb - 8]
        out += struct.pack('<II', 0x33320002, len(body)) + body + d[pe:]
        grow = len(out) - len(d)
        # the chunks around the pixels grow with them: 0xB3320000 and the outer 0xB3300000
        for cid in (0xB3300000, 0xB3320000):
            o = 0
            while o + 8 <= len(d):
                c, s = struct.unpack_from('<II', d, o)
                if c == cid:
                    struct.pack_into('<I', out, o + 4, s + grow)
                    break
                if c & 0x80000000 and c != 0xB3320000:
                    o += 8
                    continue
                o += 8 + s
        return bytes(out)
