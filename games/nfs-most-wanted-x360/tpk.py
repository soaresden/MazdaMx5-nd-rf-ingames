"""NFS MW compressed TPK (car TEXTURES.BIN) reader."""
import struct

import huff
import jdlz


def iter_chunks(d, off, end):
    while off + 8 <= end:
        cid, size = struct.unpack_from('<II', d, off)
        yield cid, off + 8, off + 8 + size
        off += 8 + size


def find(d, cid, off=0, end=None):
    end = len(d) if end is None else end
    for c, b, e in iter_chunks(d, off, end):
        if c == cid:
            return b, e
        if c & 0x80000000:
            r = find(d, cid, b, e)
            if r:
                return r
    return None


def read(d):
    """[{hash, name, w, h, comp, mips, info(bytes 0x7C), plat(bytes 0x20), pixels}]"""
    b, e = find(d, 0x33310003)
    out = []
    for o in range(b, e - 23, 24):
        h, off, size, usize, flags, _ = struct.unpack_from('<IIiiII', d, o)
        blob = d[off:off + size]
        raw = huff.decompress(blob) if blob[:4] == b'HUFF' else jdlz.decompress(blob)
        assert len(raw) == usize
        info = raw[-0x9C:-0x20]
        plat = raw[-0x20:]
        name = info[0x0C:0x24].split(b'\0')[0].decode('latin-1')
        nh, = struct.unpack_from('<I', info, 0x24)
        img_size, = struct.unpack_from('<i', info, 0x38)
        w, hh = struct.unpack_from('<hh', info, 0x44)
        comp = info[0x4A]
        mips = info[0x4E]
        out.append(dict(hash=h, name=name, name_hash=nh, w=w, h=hh, comp=comp, mips=mips,
                        img_size=img_size, info=info, plat=plat, pixels=raw[:len(raw) - 0x9C],
                        entry=d[o:o + 24], blob=blob))
    return out
