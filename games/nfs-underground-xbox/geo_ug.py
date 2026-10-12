"""Car GEOMETRY.BIN of Need for Speed Underground (Xbox): reading, for analysis and as the template
of the files we write.

Chunks (u32 id, u32 size; ids with the top bit hold other chunks). A payload may start with 0x11
bytes up to an alignment boundary (as in Most Wanted):
  0x80134000 solid pack: 0x80134001 (0x134002 header, 0x134003 keys, 0x134004 offsets, 0x80134008),
             then 0x80134010 per solid:
               0x134011 header (bounding box, matrix, name), 0x134012 texture keys, 0x134013,
               0x80134100 mesh: 0x134B00 mesh header, 0x134B01 vertices, 0x134B02 groups,
                                0x134B03 indices
               0x134017, 0x134018, 0x134019 ...
"""
import struct

PAD = 0x11


def chunks(d, o, end):
    """[(id, header offset, payload start, payload end)]"""
    out = []
    while o + 8 <= end:
        cid, size = struct.unpack_from('<II', d, o)
        out.append((cid, o, o + 8, o + 8 + size))
        o += 8 + size
    return out


def unpad(d, b, e, align):
    """Payload start after the 0x11 padding (absolute offsets): the largest of the alignments
    0x80, 0x20, 0x10 (up to `align`) that is padded with 0x11 up to the payload."""
    for al in (0x80, 0x20, 0x10):
        if al > align:
            continue
        a = b + ((-b) % al)
        if b < a <= e and all(x == PAD for x in d[b:a]):
            return a
    return b


class Solid:
    pass


def read(d):
    top = chunks(d, 0, len(d))
    solids = []
    for cid, h, b, e in top:
        if cid != 0x80134000:
            continue
        for c2, h2, b2, e2 in chunks(d, b, e):
            if c2 != 0x80134010:
                continue
            s = Solid()
            s.offset = h2
            s.chunks = chunks(d, b2, e2)
            for c3, h3, b3, e3 in s.chunks:
                if c3 == 0x134011:
                    a = unpad(d, b3, e3, 16)
                    s.header = d[a:e3]
                    s.name = s.header[0x94:].split(b'\0')[0].decode('latin-1')
                    s.bbox = struct.unpack_from('<8f', s.header, 0x20)
                elif c3 == 0x134012:
                    s.tex = list(struct.unpack_from('<%dI' % ((e3 - b3) // 4), d, b3)[::2])
                elif c3 == 0x80134100:
                    s.mesh = chunks(d, b3, e3)
                    for c4, h4, b4, e4 in s.mesh:
                        if c4 == 0x134B00:
                            a = unpad(d, b4, e4, 16)
                            s.mheader = d[a:e4]
                        elif c4 == 0x134B01:
                            a = unpad(d, b4, e4, 0x80)
                            s.vb = d[a:e4]
                        elif c4 == 0x134B02:
                            a = unpad(d, b4, e4, 0x80)
                            s.groups_raw = d[a:e4]
                        elif c4 == 0x134B03:
                            a = unpad(d, b4, e4, 0x20)
                            s.ib = d[a:e4]
            solids.append(s)
    return solids


# ---------------------------------------------------------------------------------------------
# writing

def chunk(cid, payload):
    return struct.pack('<II', cid, len(payload)) + payload


def bstringhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def _padded(pos, align, payload):
    """0x11 bytes from pos (absolute offset of the payload) up to the alignment, then payload."""
    return bytes([PAD]) * ((-pos) % align) + payload


def solid_chunk(base, s):
    """The 0x80134010 chunk of a solid whose chunk header goes at file offset `base` (a multiple
    of 0x80). `s` holds: header (176 bytes), tex, shaders (key lists), mheader (52 bytes), vb,
    groups_raw, ib, and pre / post: [(id, payload)] chunks kept as they are, before and after the
    mesh."""
    out = bytearray()
    pos = base + 8

    def emit(cid, make):
        nonlocal pos
        p = make(pos + 8)
        out.extend(chunk(cid, p))
        pos += 8 + len(p)

    emit(0x134011, lambda p: _padded(p, 16, s.header))
    emit(0x134012, lambda p: b''.join(struct.pack('<II', k, 0) for k in s.tex))
    emit(0x134013, lambda p: b''.join(struct.pack('<II', k, 0) for k in s.shaders))
    for cid, payload in s.pre:
        emit(cid, lambda p, payload=payload: payload)
    mesh = bytearray()
    mpos = pos + 8

    def memit(cid, make):
        nonlocal mpos
        p = make(mpos + 8)
        mesh.extend(chunk(cid, p))
        mpos += 8 + len(p)

    memit(0x134B00, lambda p: _padded(p, 16, s.mheader))
    memit(0x134B01, lambda p: _padded(p, 0x80, s.vb))
    memit(0x134B02, lambda p: _padded(p, 16, s.groups_raw))
    memit(0x134B03, lambda p: _padded(p, 16, s.ib))
    emit(0x80134100, lambda p: bytes(mesh))
    for cid, payload in s.post:
        emit(cid, lambda p, payload=payload: payload)
    return chunk(0x80134010, bytes(out))


def split_extra(d, s):
    """The chunks of a solid that are kept as they are (before and after its mesh)."""
    s.pre, s.post = [], []
    seen = False
    for cid, h, b, e in s.chunks:
        if cid == 0x80134100:
            seen = True
        elif cid not in (0x134011, 0x134012, 0x134013):
            (s.post if seen else s.pre).append((cid, d[b:e]))
    c13 = [(b, e) for c, h, b, e in s.chunks if c == 0x134013][0]
    s.shaders = list(struct.unpack_from('<%dI' % ((c13[1] - c13[0]) // 4), d, c13[0])[::2])


def write(template, solids):
    """A GEOMETRY.BIN: the template's pack header and trailing chunks, these solids (in key order,
    as the game wants them)."""
    top = chunks(template, 0, len(template))
    pack = top[0]
    inner = chunks(template, pack[2], pack[3])
    info = [x for x in inner if x[0] == 0x80134001][0]
    ic = chunks(template, info[2], info[3])
    h2 = bytearray(template[ic[0][2]:ic[0][3]])
    solids = sorted(solids, key=lambda s: struct.unpack_from('<I', s.header, 0x10)[0])
    keys = [struct.unpack_from('<I', s.header, 0x10)[0] for s in solids]
    struct.pack_into('<I', h2, 12, len(solids))
    tail = [x for x in ic if x[0] not in (0x134002, 0x134003, 0x134004)]

    def info_chunk(offsets):
        body = chunk(0x134002, bytes(h2)) + chunk(0x134003, b''.join(struct.pack('<II', k, 0) for k in keys))
        body += chunk(0x134004, b''.join(struct.pack('<5I', k, o, n, 0, 0) for k, (o, n) in zip(keys, offsets)))
        for cid, h, b, e in tail:
            body += chunk(cid, template[b:e])
        return chunk(0x80134001, body)

    # pass 1: sizes, pass 2: offsets (the info chunk size does not depend on the offsets)
    offsets = [(0, 0)] * len(solids)
    head = chunk(0, b'') + info_chunk(offsets)
    pos = 8 + len(head)
    blobs = []
    for s in solids:
        # solids start on 0x80 boundaries, after an empty chunk filling the gap (none if aligned)
        filler = b'' if pos % 0x80 == 0 else chunk(0, b'\0' * ((-(pos + 8)) % 0x80))
        start = pos + len(filler)
        blob = solid_chunk(start, s)
        offsets_i = (start, len(blob))
        blobs.append(filler + blob)
        offsets[len(blobs) - 1] = offsets_i
        pos = start + len(blob)
    # the pack header gives the place of the chunk after the solids (0x80034020)
    old_at, = struct.unpack_from('<I', h2, 104)
    pack_len = 8 + len(chunk(0, b'') + info_chunk(offsets)) + sum(len(x) for x in blobs)
    at = pack_len
    for cid, h, b, e in top[1:]:
        if h == old_at:
            struct.pack_into('<I', h2, 104, at)
        at += e - h
    head = chunk(0, b'') + info_chunk(offsets)
    pack_body = head + b''.join(blobs)
    out = chunk(0x80134000, pack_body)
    for cid, h, b, e in top[1:]:
        out += template[h:e]
    return out
