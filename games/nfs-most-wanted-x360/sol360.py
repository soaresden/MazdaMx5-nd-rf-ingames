"""Read Xbox 360 NFS MW solids (GEOMETRY.BIN) into groups of vertices and triangles."""
import struct

import numpy as np

import solids

GROUP = 256


def groups(d, s):
    """[{off, raw, first, typ, key, flags, nidx, ids, vbsize, stride, vbsize2, stride2}] of a solid."""
    out = []
    for cid, h, b, e in s['mesh']:
        if cid != 0x134B02:
            continue
        bb = b + ((-b) % 0x80)
        for i in range((e - bb) // GROUP):
            o = bb + i * GROUP
            first, typ, key, flags = struct.unpack_from('<IIII', d, o + 0x18)
            nidx, = struct.unpack_from('<H', d, o + 0x28)
            out.append(dict(off=o, raw=d[o:o + GROUP], first=first, typ=typ, key=key, flags=flags,
                            nidx=nidx, ids=list(d[o + 0x2A:o + 0x30]),
                            vbsize=struct.unpack_from('<I', d, o + 0x58)[0], stride=d[o + 0x5E],
                            vbsize2=struct.unpack_from('<I', d, o + 0x78)[0], stride2=d[o + 0x7E]))
    return out


def buffers(d, s):
    vbs, ib = [], None
    for cid, h, b, e in s['mesh']:
        if cid == 0x134B01:
            bb = b + ((-b) % 0x80)
            vbs.append(d[bb:e])
        elif cid == 0x134B03:
            bb = b + ((-b) % 0x10)
            ib = d[bb:e]
    return vbs, ib


def decode(d, s):
    """Yield (group, positions Nx3, uvs Nx2, colors N (u32), normals Nx3, triangles Mx3)."""
    gs = groups(d, s)
    vbs, ib = buffers(d, s)
    total = sum(g['nidx'] for g in gs)
    idx = np.frombuffer(ib[len(ib) - 2 * total:], dtype='>u2')
    vi = 0
    for g in gs:
        if g['typ'] == 7:
            vb = vbs[vi]
            vb = vb[len(vb) - g['vbsize']:]
            vi += 1
            n = g['vbsize'] // 32
            a = np.frombuffer(vb[:n * 32], dtype=np.dtype([('p', '>f4', 3), ('uv', '>f4', 2), ('c', '>u4'),
                                                             ('n', '>i2', 4)]))
            pos, uv, col = a['p'].astype(np.float32), a['uv'].astype(np.float32), a['c']
            nrm = a['n'][:, :3].astype(np.float32) / 32767.0
        else:
            vb = vbs[vi]
            vb = vb[len(vb) - g['vbsize']:]
            vi += 2  # second stream not decoded
            n = g['vbsize'] // 24
            a = np.frombuffer(vb[:n * 24], dtype=np.dtype([('p', '>f4', 3), ('uv', '>f4', 2), ('c', '>u4')]))
            pos, uv, col = a['p'].astype(np.float32), a['uv'].astype(np.float32), a['c']
            nrm = np.zeros((n, 3), np.float32)
        tri = idx[g['first']:g['first'] + g['nidx']].astype(np.int64).reshape(-1, 3)
        yield g, pos, uv, col, nrm, tri
