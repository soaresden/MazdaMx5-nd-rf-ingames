"""Parse NFS MW GEOMETRY.BIN (PC-like chunk layout) into solids with their raw platform chunks."""
import struct


def iter_chunks(d, off, end):
    while off + 8 <= end:
        cid, size = struct.unpack_from('<II', d, off)
        yield cid, off, off + 8, off + 8 + size
        off += 8 + size


def skip_pad(d, off, end, pad=0x11):
    while off < end and d[off] == pad:
        off += 1
    return off


def parse(d):
    solids = []
    for cid, hoff, b, e in iter_chunks(d, 0, len(d)):
        if cid != 0x80134000:
            continue
        for cid2, h2, b2, e2 in iter_chunks(d, b, e):
            if cid2 != 0x80134010:
                continue
            s = {'off': h2, 'end': e2, 'chunks': []}
            for cid3, h3, b3, e3 in iter_chunks(d, b2, e2):
                s['chunks'].append((cid3, h3, b3, e3))
                if cid3 == 0x134011:
                    p = b3
                    while p < e3 and d[p] == 0:
                        p += 1
                    # header starts after 12 blank bytes aligned; find version byte 0x16
                    base = b3 + ((-b3) % 16) if False else b3
                    s['hdr'] = d[b3:e3]
                    name_start = d.find(b'\x00', b3 + 0xA0)
                    a = b3 + ((-b3) % 16)
                    raw = d[a:e3]
                    s['hdr_off'] = a
                    # name is the last null-terminated string in the header chunk
                    nm = raw[0xA0:].split(b'\x00')[0]
                    s['name'] = nm.decode('latin-1')
                elif cid3 == 0x80134100:
                    s['mesh'] = [(c, hh, bb, ee) for c, hh, bb, ee in iter_chunks(d, b3, e3)]
            solids.append(s)
    return solids
