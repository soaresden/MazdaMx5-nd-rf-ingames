"""Minimal reader for the Xbox 360 AttribSys pack (GLOBAL/ATTRIBUTES.BIN, `VPAK`).

The pack header is little-endian; the vault blobs (.vlt and .bin) are big-endian on the 360.
Read: the export table (ExpN), the collection records, the pointer fix-ups (PtrN) and the class field
definitions, enough to find and change the fields stored in a collection's layout block.
"""
import struct

EXPORT_COLLECTION = 0x8E112EB7
EXPORT_CLASS = 0x5E970CBC  # Attrib::ClassLoadData


def _mix(a, b, c):
    M = 0xFFFFFFFF
    a = (a - b - c) & M; a ^= c >> 13
    b = (b - c - a) & M; b ^= (a << 8) & M
    c = (c - a - b) & M; c ^= b >> 13
    a = (a - b - c) & M; a ^= c >> 12
    b = (b - c - a) & M; b ^= (a << 16) & M
    c = (c - a - b) & M; c ^= b >> 5
    a = (a - b - c) & M; a ^= c >> 3
    b = (b - c - a) & M; b ^= (a << 10) & M
    c = (c - a - b) & M; c ^= b >> 15
    return a, b, c


def key(s, init=0xABCDEF00):
    """Attrib::StringToKey (Bob Jenkins' lookup2)."""
    k = s.encode()
    a = b = 0x9E3779B9
    c = init
    i, n = 0, len(k)
    while n - i >= 12:
        a = (a + struct.unpack_from('<I', k, i)[0]) & 0xFFFFFFFF
        b = (b + struct.unpack_from('<I', k, i + 4)[0]) & 0xFFFFFFFF
        c = (c + struct.unpack_from('<I', k, i + 8)[0]) & 0xFFFFFFFF
        a, b, c = _mix(a, b, c)
        i += 12
    c = (c + n) & 0xFFFFFFFF
    rest = k[i:]
    for j, ch in enumerate(rest):
        if j < 4:
            a = (a + (ch << (8 * j))) & 0xFFFFFFFF
        elif j < 8:
            b = (b + (ch << (8 * (j - 4)))) & 0xFFFFFFFF
        else:
            c = (c + (ch << (8 * (j - 8 + 1)))) & 0xFFFFFFFF
    a, b, c = _mix(a, b, c)
    return c


class Pack:
    def __init__(self, data):
        self.d = data
        assert data[:4] == b'VPAK'
        _, binsize, vltsize, binoff, vltoff = struct.unpack_from('<5I', data, 0x10)
        self.bin_off, self.vlt_off = binoff, vltoff
        v = data[vltoff:vltoff + vltsize]
        chunks = {}
        p = 0
        while p + 8 <= len(v):
            cid = v[p:p + 4].decode('latin-1')
            size, = struct.unpack_from('>I', v, p + 4)
            chunks[cid] = (p + 8, p + size)
            p += size
        self.v = v
        b, e = chunks['PtrN']
        self.fix = {}  # pointers stored in the .vlt (fix-up target 0) -> offset in the .bin
        target = None
        for o in range(b, e - 11, 12):
            fo, kind, idx, dest = struct.unpack_from('>IHHI', v, o)
            if kind == 0:
                break
            if kind == 2:
                target = idx
            elif kind == 3 and target == 0:
                self.fix[fo] = dest
        b, e = chunks['ExpN']
        n, = struct.unpack_from('>I', v, b)
        self.exports = [struct.unpack_from('>5I', v, b + 4 + i * 20) for i in range(n)]

    def collections(self):
        """{(class key, collection key): absolute file offset of the layout block, or None}"""
        out = {}
        # pointers in the .vlt are fixed up by their offset in the .vlt blob
        for eid, typ, _, size, off in self.exports:
            if typ != EXPORT_COLLECTION:
                continue
            ckey, cls, parent = struct.unpack_from('>III', self.v, off)
            lay = self.fix.get(off + 0x1C)
            out[(cls, ckey)] = None if lay is None else self.bin_off + lay
        return out

    def fields(self, cls):
        """{field key: (offset in the layout, element size, max count, flags)} of a class.
        flags & 1: array (8-byte header: u16 capacity, u16 count, u16 element size, pad);
        flags & 2: stored in the layout block (the others live in the collection's own table)."""
        for eid, typ, _, size, off in self.exports:
            if typ == EXPORT_CLASS and struct.unpack_from('>I', self.v, off)[0] == key(cls):
                n, = struct.unpack_from('>I', self.v, off + 8)
                d = self.bin_off + self.fix[off + 12]
                out = {}
                for i in range(n):
                    k, _, o, sz, mc, fl, _ = struct.unpack_from('>IIHHHBB', self.d, d + 16 * i)
                    out[k] = (o, sz, mc, fl)
                return out
        raise KeyError(cls)


def set_field(data, pack, cls, coll, name, value):
    """Write a float field (or a list of floats for an array field) of collection cls/coll in
    `data` (a bytearray of the whole ATTRIBUTES.BIN)."""
    lay = pack.collections()[(key(cls), key(coll))]
    o, sz, mc, fl = pack.fields(cls)[key(name)]
    assert fl & 2 and sz == 4, (cls, name, 'not a float stored in the layout')
    if fl & 1:
        value = list(value)
        assert len(value) <= mc, (name, len(value), mc)
        struct.pack_into('>H', data, lay + o + 2, len(value))
        struct.pack_into('>%df' % mc, data, lay + o + 8, *(value + [0.0] * (mc - len(value))))
    else:
        struct.pack_into('>f', data, lay + o, value)


def set_refs(data, pack, cls, coll, field, ref_class, ref_keys):
    """Point the RefSpec array `field` of collection cls/coll (an optional field, stored in the
    collection's own table) at collections `ref_keys` of class `ref_class`. The array keeps its
    capacity: ref_keys is repeated or cut to fill it."""
    for eid, typ, _, size, off in pack.exports:
        if typ != EXPORT_COLLECTION:
            continue
        ck, cl = struct.unpack_from('>II', pack.v, off)
        if (ck, cl) != (key(coll), key(cls)):
            continue
        n_types, = struct.unpack_from('>I', pack.v, off + 0x18)
        for o in range(off + 0x20 + 4 * n_types, off + size, 12):
            if struct.unpack_from('>I', pack.v, o)[0] == key(field):
                a = pack.bin_off + pack.fix[o + 4]
                cap, cnt, esz = struct.unpack_from('>HHH', data, a)
                assert esz == 12, esz
                for i in range(cnt):
                    struct.pack_into('>II', data, a + 8 + 12 * i, key(ref_class), ref_keys[i % len(ref_keys)])
                return cnt
    raise KeyError((cls, coll, field))
