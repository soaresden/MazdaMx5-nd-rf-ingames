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
        if t['fmt'] != DXT1:
            raise ValueError('%s: format %#x not supported' % (t['name'], t['fmt']))
        im = Image.fromarray(np.asarray(rgba, np.uint8), 'RGBA')
        out = b''
        w, h = t['w'], t['h']
        for level in range(max(1, t['mips'])):
            lw, lh = max(4, w >> level), max(4, h >> level)
            out += dxt.encode(im.resize((lw, lh), Image.LANCZOS), 'DXT1')
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
