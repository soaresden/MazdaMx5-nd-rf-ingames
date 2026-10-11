"""Read and write Xbox 360 NFS Most Wanted car GEOMETRY.BIN files.

A solid is kept as plain data:
  name, header (0xA0 bytes before the name, template), tex [hashes], lm [hashes],
  extra [(chunk id, payload)] (markers, normal smoothing...) written after the tables,
  desc (0x48-byte 134900 payload template), groups [dict], vbs [bytes per 134B01], ib (bytes),
  c02 [payload per 134C02 chunk, in order]
A group dict holds 'raw' (256 bytes, already patched).
"""
import struct

import solids as solidparse

PAD11 = 0x11


def chunk(cid, payload):
    return struct.pack('<II', cid, len(payload)) + payload


def bstringhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def _pad(pos, align, fill):
    return bytes([fill]) * ((-pos) % align)


def read(d):
    """Parse a 360 GEOMETRY.BIN into (pack header payload, [solid dicts])."""
    out = []
    for s in solidparse.parse(d):
        sol = {'name': s['name'], 'extra': [], 'post': [], 'c02': []}
        seen_mesh = False
        for cid, h, b, e in s['chunks']:
            if cid == 0x134011:
                a = b + ((-b) % 16)
                sol['header'] = d[a:a + 0xA0]
            elif cid == 0x134012:
                sol['tex'] = list(struct.unpack_from('<%dI' % ((e - b) // 4), d, b)[::2])
            elif cid == 0x134013:
                sol['lm'] = list(struct.unpack_from('<%dI' % ((e - b) // 4), d, b)[::2])
            elif cid == 0x80134100:
                seen_mesh = True
            else:
                a = b + ((-b) % 16) if cid == 0x13401A else b
                (sol['post'] if seen_mesh else sol['extra']).append((cid, d[a:e]))
        vbs = []
        groups = []
        for cid, h, b, e in s['mesh']:
            if cid == 0x134900:
                a = b + ((-b) % 16)
                sol['desc'] = d[a:e]
            elif cid == 0x134B02:
                a = b + ((-b) % 0x80)
                for o in range(a, e, 256):
                    groups.append({'raw': d[o:o + 256]})
            elif cid == 0x134B01:
                a = b + ((-b) % 0x80)
                vbs.append(d[a:e])
                sol.setdefault('vbseq', []).append(('B01', d[a:e]))
            elif cid == 0x134B03:
                a = b + ((-b) % 0x20)
                sol['ib'] = d[a:e]
            elif cid == 0x134C02:
                sol['c02'].append(d[b:e])
                sol.setdefault('vbseq', []).append(('C02', d[b:e]))
        sol['groups'] = groups
        sol['vbs'] = vbs
        out.append(sol)
    a = 0x18 + 8
    pack_header = d[0x20:0x20 + 144]
    return pack_header, out


def solid_bytes(sol, base):
    """The full 0x80134010 chunk for a solid that starts at file offset `base`."""
    parts = []
    pos = base + 8  # payload start of the solid pack

    def emit(cid, payload_fn):
        nonlocal pos
        body = payload_fn(pos + 8)
        c = chunk(cid, body)
        parts.append(c)
        pos += len(c)

    name = sol['name'].encode() + b'\0'
    hdr_body = sol['header'] + name
    hdr_body += b'\0' * ((-len(hdr_body)) % 4)
    emit(0x134011, lambda p: _pad(p, 16, 0) + hdr_body)
    emit(0x134012, lambda p: b''.join(struct.pack('<II', h, 0) for h in sol['tex']))
    emit(0x134013, lambda p: b''.join(struct.pack('<II', h, 0) for h in sol['lm']))
    for cid, payload in sol['extra']:
        if cid == 0x13401A:
            emit(cid, lambda p, pl=payload: _pad(p, 16, PAD11) + pl)
        else:
            emit(cid, lambda p, pl=payload: pl)

    # mesh container
    mesh_start = pos
    mparts = []
    mpos = mesh_start + 8

    def memit(cid, payload_fn):
        nonlocal mpos
        body = payload_fn(mpos + 8)
        c = chunk(cid, body)
        mparts.append(c)
        mpos += len(c)

    memit(0x134900, lambda p: _pad(p, 16, PAD11) + sol['desc'])
    memit(0x134B02, lambda p: _pad(p, 0x80, PAD11) + b''.join(g['raw'] for g in sol['groups']))
    for kind, data in sol['vbseq']:
        if kind == 'C02':
            memit(0x134C02, lambda p, data=data: data)
        else:
            memit(0x134B01, lambda p, data=data: _pad(p, 0x80, PAD11) + data)
    memit(0x134B03, lambda p: _pad(p, 0x20, PAD11) + sol['ib'])
    mesh = chunk(0x80134100, b''.join(mparts))
    parts.append(mesh)
    pos += len(mesh)
    for cid, payload in sol.get('post', []):
        emit(cid, lambda p, pl=payload: pl)
    return chunk(0x80134010, b''.join(parts))


def write(pack_header, sols, tail=None):
    """Assemble a GEOMETRY.BIN. Returns bytes."""
    n = len(sols)
    hashes = [bstringhash(s['name']) for s in sols]
    # info container: header, keys, offsets (offsets patched after layout)
    info_len = 8 + 8 + (8 + 144) + (8 + 8 * n) + (8 + 24 * n) + 8
    body = bytearray()
    cur = 8 + info_len  # position after top header + info container
    offsets = {}
    blobs = []
    for s, h in zip(sols, hashes):
        # padding chunk so the solid pack starts 0x80-aligned
        gap = (-cur) % 0x80
        if gap and gap < 8:
            gap += 0x80
        pad_chunk = chunk(0, b'\0' * (gap - 8)) if gap else b''
        cur += len(pad_chunk)
        sb = solid_bytes(s, cur)
        offsets[h] = (cur, len(sb))
        blobs.append(pad_chunk + sb)
        cur += len(sb)
    container_size = cur
    if tail is None:
        tail = max(0x10000, container_size // 50)
    tail += (-(container_size + 8 + tail)) % 0x40
    file_size = container_size + 8 + tail
    order = sorted(range(n), key=lambda i: hashes[i])
    ph = bytearray(pack_header)
    struct.pack_into('<I', ph, 12, n)
    struct.pack_into('<I', ph, 26 * 4, file_size)
    keys = b''.join(struct.pack('<II', hashes[i], 0) for i in order)
    offs = b''.join(struct.pack('<6I', hashes[i], offsets[hashes[i]][0], offsets[hashes[i]][1],
                                offsets[hashes[i]][1], 0, 0) for i in order)
    info = chunk(0, b'') + chunk(0x80134001, chunk(0x134002, bytes(ph)) + chunk(0x134003, keys)
                                 + chunk(0x134004, offs) + chunk(0x80134008, b''))
    assert len(info) == info_len
    top = chunk(0x80134000, info + b''.join(blobs))
    assert len(top) == container_size
    return top + chunk(0, b'\0' * tail)
