"""Gran Turismo 2 car models (carobj/<car>.cdo, .cno for the night version): read and write.

Layout from pez2k's GT2ModelTool (github.com/pez2k/gt2tools), checked here by rewriting the 1110
models of the disc byte for byte:
  0x00 "GT\\x02"; 0x18 menu wheel radius / width (front, rear); 0x20 4 wheel positions (x, y, z,
  menu x: shorts); zeros; 0x868 LOD count (3), then per LOD: 2 zero bytes, its max distance, its file
  offset (0 for LOD0); the 3 LODs; the shadow. At most 0x5000 bytes (what the game reserves).
LOD: an 0x50 header (counts, offsets from the LOD start, bounds, scale), vertices (4 shorts),
  normals (x, y, z in 10 signed bits each, / 500), triangles and quads (16 bytes: 4 vertex bytes,
  normal and draw data, face type << 24 | 24-bit colour), textured triangles and quads (+12 bytes:
  4 texture coordinates, palette). A polygon names its vertices with one byte: 256 at most.
Shadow: counts, bounds, scale, 2-short vertices, polygons packed in one word each.
"""
import struct

MAX_SIZE = 0x5000
HEADER = 0x50


class Poly:
    """A polygon; the 16 raw bytes are kept apart from the fields we change."""
    __slots__ = ('v', 'normals', 'order', 'flags', 'face_type', 'colour', 'uv', 'palette', 'raw_pal', 'unk')

    def __init__(self, v, normals=(0, 0, 0, 0), order=0, flags=0, face_type=32, colour=0, uv=None,
                 palette=0, raw_pal=None, unk=(0, 0)):
        self.v, self.normals, self.order, self.flags = list(v), list(normals), order, flags
        self.face_type, self.colour, self.uv, self.palette = face_type, colour, uv, palette
        self.raw_pal, self.unk = raw_pal, unk


class LOD:
    def __init__(self):
        self.verts, self.normals, self.tris, self.quads, self.uv_tris, self.uv_quads = [], [], [], [], [], []
        self.bounds = (0,) * 8
        self.scale = 0
        self.scale2 = 0x13E8
        self.unknown_counts = (0, 0)
        self.extra = (0, 0)           # the two words after the counts (always 0)


class _P(Poly):
    """A polygon read from the disc: `raw` keeps its draw words, whose unknown bits are written back."""
    __slots__ = ('raw',)


def _read_poly(d, o, quad, textured):
    v0, v1, v2, v3, a, b, n, ft = struct.unpack_from('<4BHHII', d, o)
    p = _P([v0, v1, v2, v3] if quad else [v0, v1, v2], [(a >> 5) & 0x1FF, (n >> 1) & 0x1FF, (n >> 10) & 0x1FF,
           (n >> 19) & 0x1FF], a & 0x1F, b, ft >> 24, ft & 0xFFFFFF)
    p.raw = (a, b, n, v3)
    if textured:
        u0, pal, u1, k13, k14, u2, u3 = struct.unpack_from('<2sH2sBB2s2s', d, o + 16)
        p.uv = [tuple(u0), tuple(u1), tuple(u2), tuple(u3)]
        p.raw_pal, p.unk = pal, (k13, k14)
        p.palette = (pal >> 4) + (pal & 0x3F)
    return p


def _write_poly(p, quad, textured):
    raw = getattr(p, 'raw', None)
    n0, n1, n2, n3 = (p.normals + [0, 0, 0, 0])[:4]
    a = (n0 << 5) | p.order
    n = (n1 << 1) | (n2 << 10) | (n3 << 19)
    if raw is not None:
        # unknown bits of the game's own polygons kept as they were
        a |= raw[0] & ~((0x1FF << 5) | 0x1F) & 0xFFFF
        n |= raw[2] & ~((0x1FF << 1) | (0x1FF << 10) | (0x1FF << 19)) & 0xFFFFFFFF
    v3 = p.v[3] if quad else (raw[3] if raw is not None else 0)
    out = struct.pack('<4BHHII', p.v[0], p.v[1], p.v[2], v3, a & 0xFFFF, p.flags & 0xFFFF, n & 0xFFFFFFFF,
                      ((p.face_type & 0xFF) << 24) | (p.colour & 0xFFFFFF))
    if textured:
        uv = [bytes(x) for x in (p.uv + [(0, 0)] * 4)[:4]]
        pal = p.raw_pal if p.raw_pal is not None else _raw_palette(p.palette)
        out += struct.pack('<2sH2sBB2s2s', uv[0], pal, uv[1], p.unk[0], p.unk[1], uv[2], uv[3])
    return out


def _raw_palette(index):
    """The stored word of palette `index` as the game's own models write it (index << 6 over 16)."""
    return ((index // 16) << 6) | (index % 16) if index else 0


def read_lod(d, s):
    L = LOD()
    nv, nn, nt, nq, x0, x1, ut, uq = struct.unpack_from('<8H', d, s)
    L.unknown_counts = (x0, x1)
    z0, voff, z1 = struct.unpack_from('<III', d, s + 16)
    offs = struct.unpack_from('<7I', d, s + 28)
    L.bounds = struct.unpack_from('<8h', d, s + 0x3C)
    L.scale, L.scale2 = struct.unpack_from('<HH', d, s + 0x4C)
    o = s + voff
    L.verts = [struct.unpack_from('<4h', d, o + 8 * i) for i in range(nv)]
    o = s + offs[0]
    L.normals = [struct.unpack_from('<I', d, o + 4 * i)[0] for i in range(nn)]
    end = voff + 8 * nv
    for lst, start, count, quad, tex in ((L.tris, offs[1], nt, False, False), (L.quads, offs[2], nq, True, False),
                                         (L.uv_tris, offs[5], ut, False, True), (L.uv_quads, offs[6], uq, True, True)):
        size = 28 if tex else 16
        for i in range(count):
            lst.append(_read_poly(d, s + start + size * i, quad, tex))
        if count:
            end = max(end, start + size * count)
    if nn:
        end = max(end, offs[0] + 4 * nn)
    # empty sections: some models give them the offset of what follows, others 0
    L.zero_offsets = tuple(i for i, x in enumerate(offs) if x == 0)
    return L, s + end


def write_lod(L):
    body = b''.join(struct.pack('<4h', *v) for v in L.verts)
    offs = []
    pos = HEADER + len(body)
    parts = [body]
    zero = getattr(L, 'zero_offsets', ())
    for k, chunk in enumerate((b''.join(struct.pack('<I', n) for n in L.normals),
                               b''.join(_write_poly(p, False, False) for p in L.tris),
                               b''.join(_write_poly(p, True, False) for p in L.quads), b'', b'',
                               b''.join(_write_poly(p, False, True) for p in L.uv_tris),
                               b''.join(_write_poly(p, True, True) for p in L.uv_quads))):
        offs.append(0 if (k in zero and not chunk) else pos)
        parts.append(chunk)
        pos += len(chunk)
    if len(L.verts) > 256:
        raise ValueError('%d sommets : 256 au plus par niveau de détail' % len(L.verts))
    head = struct.pack('<8H', len(L.verts), len(L.normals), len(L.tris), len(L.quads), *L.unknown_counts,
                       len(L.uv_tris), len(L.uv_quads))
    head += struct.pack('<III', 0, HEADER, 0) + struct.pack('<7I', *offs) + struct.pack('<I', 0)
    head += struct.pack('<8h', *L.bounds) + struct.pack('<HH', L.scale, L.scale2)
    assert len(head) == HEADER
    return head + b''.join(parts)


class Shadow:
    def __init__(self):
        self.verts, self.tris, self.quads = [], [], []
        self.bounds, self.scale, self.scale2, self.unknown = (0,) * 8, 0, 0, 0


def read_shadow(d, o):
    S = Shadow()
    nv, nt, nq, S.unknown = struct.unpack_from('<4H', d, o)
    S.bounds = struct.unpack_from('<8h', d, o + 8)
    S.scale, S.scale2 = struct.unpack_from('<HH', d, o + 24)
    o += 28
    S.verts = [struct.unpack_from('<2h', d, o + 4 * i) for i in range(nv)]
    o += 4 * nv
    S.tris = [struct.unpack_from('<I', d, o + 4 * i)[0] for i in range(nt)]
    o += 4 * nt
    S.quads = [struct.unpack_from('<I', d, o + 4 * i)[0] for i in range(nq)]
    o += 4 * nq
    return S, o


def write_shadow(S):
    return (struct.pack('<4H', len(S.verts), len(S.tris), len(S.quads), S.unknown) + struct.pack('<8h', *S.bounds) +
            struct.pack('<HH', S.scale, S.scale2) + b''.join(struct.pack('<2h', *v) for v in S.verts) +
            b''.join(struct.pack('<I', q) for q in S.tris) + b''.join(struct.pack('<I', q) for q in S.quads))


class Model:
    def __init__(self):
        self.menu_wheels = (0, 0, 0, 0)       # front radius, width, rear radius, width
        self.wheels = [(0, 0, 0, 0)] * 4      # x, y, z, menu x
        self.distances = [5, 15, 300]
        self.lods = []
        self.shadow = Shadow()
        self.tail = b''                       # whatever follows the shadow in the file


def read(d):
    if d[:3] != b'GT\x02':
        raise ValueError("pas un modèle de Gran Turismo 2 (en-tête %r)" % d[:3])
    M = Model()
    M.menu_wheels = struct.unpack_from('<4H', d, 0x18)
    M.wheels = [struct.unpack_from('<4h', d, 0x20 + 8 * i) for i in range(4)]
    n, = struct.unpack_from('<I', d, 0x868)
    q = 0x86C
    M.stored_offsets = []
    for i in range(n):
        _, dist, off = struct.unpack_from('<HHI', d, q)
        M.distances[i] = dist
        M.stored_offsets.append(off)
        q += 8
    # the levels follow each other; the stored offsets are not always filled in (0)
    end = q
    for i in range(n):
        L, end = read_lod(d, end)
        M.lods.append(L)
    M.shadow, o = read_shadow(d, end)
    M.tail = d[o:]
    return M


def write(M):
    head = bytearray(0x868)
    head[0:3] = b'GT\x02'
    struct.pack_into('<4H', head, 0x18, *M.menu_wheels)
    for i, w in enumerate(M.wheels):
        struct.pack_into('<4h', head, 0x20 + 8 * i, *w)
    lods = [write_lod(L) for L in M.lods]
    table = struct.pack('<I', len(lods))
    pos = 0x868 + 4 + 8 * len(lods)
    offsets = []
    for L in lods:
        offsets.append(pos)
        pos += len(L)
    stored = getattr(M, 'stored_offsets', None) or []
    for i in range(len(lods)):
        off = 0 if i == 0 or (i < len(stored) and stored[i] == 0) else offsets[i]
        table += struct.pack('<HHI', 0, M.distances[i], off)
    out = bytes(head) + table + b''.join(lods) + write_shadow(M.shadow) + M.tail
    if len(out) >= MAX_SIZE:
        raise ValueError('modèle de %d octets : %d au plus' % (len(out), MAX_SIZE))
    return out


def stats(M):
    return [(len(L.verts), len(L.tris) + len(L.uv_tris), len(L.quads) + len(L.uv_quads)) for L in M.lods]
