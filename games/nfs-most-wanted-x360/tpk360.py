"""Write Xbox 360 NFS MW compressed texture packs (car TEXTURES.BIN)."""
import io
import struct

from PIL import Image

import jdlz
import xenos


def chunk(cid, payload):
    return struct.pack('<II', cid, len(payload)) + payload


def bstringhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def dxt_linear(img, fmt):
    """PIL image -> linear DXT blocks (base level only)."""
    b = io.BytesIO()
    try:
        img.save(b, 'DDS', pixel_format=fmt)
    except (OSError, ValueError, KeyError, TypeError):
        # an older Pillow (the browser's Pyodide) cannot write DXT: our own encoder
        import dxt
        return dxt.encode(img, fmt)
    data = b.getvalue()
    assert data[:4] == b'DDS '
    off = 128
    if data[84:88] == b'DX10':
        off += 20
    w, h = img.size
    bpb = 8 if fmt == 'DXT1' else 16
    size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * bpb
    return data[off:off + size]


def make_texture(name, img, fmt, template):
    """template: a texture dict from tpk.read (info 0x7C, plat 0x20) of the same format."""
    img = img.convert('RGBA')
    if fmt == 'DXT1':
        # opaque: DXT1 would otherwise turn low alpha into cut-out pixels (wheels disappear)
        img = img.convert('RGB').convert('RGBA')
    w, h = img.size
    assert w & (w - 1) == 0 and h & (h - 1) == 0, (name, img.size)
    bpb = 8 if fmt == 'DXT1' else 16
    tiled = xenos.tile(dxt_linear(img, fmt), w, h, bpb)
    info = bytearray(template['info'])
    nm = name.encode()[:23]
    info[0x0C:0x24] = nm + b'\0' * (24 - len(nm))
    hsh = bstringhash(name)
    struct.pack_into('<I', info, 0x24, hsh)
    struct.pack_into('<i', info, 0x38, len(tiled))
    struct.pack_into('<i', info, 0x40, len(tiled))
    struct.pack_into('<hh', info, 0x44, w, h)
    info[0x48] = w.bit_length() - 1
    info[0x49] = h.bit_length() - 1
    info[0x4A] = 0x22 if fmt == 'DXT1' else 0x26
    info[0x4E] = 1
    return dict(hash=hsh, name=name, info=bytes(info), plat=template['plat'], pixels=tiled)


def write(textures, header_payload, data_header_payload):
    """textures: list of dicts (hash, info, plat, pixels). Returns TEXTURES.BIN bytes."""
    texs = sorted(textures, key=lambda t: t['hash'])
    # placements in key order
    place = 0
    for t in texs:
        info = bytearray(t['info'])
        struct.pack_into('<i', info, 0x30, place)
        place += len(t['pixels'])
        struct.pack_into('<i', info, 0x34, place)
        t['info_final'] = bytes(info)
    blobs = []
    for t in texs:
        raw = t['pixels'] + t['info_final'] + t['plat']
        # 'blob': an original compressed blob, kept as it is (diagnostics)
        comp = t['blob'] if t.get('blob') else jdlz.compress(raw)
        assert comp[:4] != b'JDLZ' or jdlz.game_decompress(comp) == raw, 'JDLZ stream the game cannot read'
        blobs.append((t, raw, comp))
    n = len(texs)
    keys = b''.join(struct.pack('<II', t['hash'], 0) for t in texs)
    info_len = 8 + (8 + len(header_payload)) + (8 + 8 * n) + (8 + 24 * n)
    # layout: B3300000 hdr @0, chunk0 48 @8 -> B3310000 @0x40
    pos = 0x40 + info_len
    gap = (-pos) % 0x80
    if gap and gap < 8:
        gap += 0x80
    pad1 = chunk(0, b'\0' * (gap - 8)) if gap else b''
    pos += len(pad1)
    data_start = pos  # B3320000 header
    pos += 8 + 8 + len(data_header_payload)  # B3320000 hdr + 33320001
    gap = (-pos) % 0x80  # 33320003 header must be 0x80-aligned
    if gap and gap < 8:
        gap += 0x80
    pad2 = chunk(0, b'\0' * (gap - 8)) if gap else b''
    pos += len(pad2)
    arr_hdr = pos
    pos += 8
    first = max(0x1000, pos + ((-pos) % 0x80))
    payload = bytearray(b'\x11' * (first - pos))
    pos = first
    entries = {}
    for t, raw, comp in blobs:
        a = (-pos) % 0x40
        payload += b'\x11' * a
        pos += a
        entries[t['hash']] = (pos, len(comp), len(raw))
        payload += comp
        pos += len(comp)
    ents = b''.join(struct.pack('<IIiiBBHI', t['hash'], entries[t['hash']][0], entries[t['hash']][1],
                                entries[t['hash']][2], 0, 1, 0, 0) for t in texs)
    info = chunk(0xB3310000, chunk(0x33310001, header_payload) + chunk(0x33310002, keys)
                 + chunk(0x33310003, ents))
    assert len(info) == info_len
    data = chunk(0xB3320000, chunk(0x33320001, data_header_payload) + pad2 + chunk(0x33320003, bytes(payload)))
    body = chunk(0, b'\0' * 48) + info + pad1 + data
    out = chunk(0xB3300000, body)
    assert struct.unpack_from('<II', out, arr_hdr)[0] == 0x33320003
    return out
