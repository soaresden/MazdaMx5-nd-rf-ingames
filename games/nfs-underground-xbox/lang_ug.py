"""The MX-5 RF's name in the menus of Need for Speed Underground and Underground 2: the language
files (one chunk 0x39000 each), with the Miata's strings renamed in every language.

Underground (LANGUAGES/LANGUAGE_<LANGUAGE>.BIN, loose files): after the chunk header, u32 count,
then count x (u32 hash of the label, u32 byte offset of the text), sorted by hash, then the texts
in UTF-16 LE, each ended by 0x0000 (accented letters are sign-extended bytes: e acute is 0xFFE9).
The labels are in LANGUAGE_LABELS.BIN; their hash is bStringHash (x33, from 0xFFFFFFFF).
Underground 2 (LANGUAGES\\<LANGUAGE>.BIN in the ZZDATA packs): u32 offset of extra data (0x10),
u32 count, u32 offset of the table, u32 offset of the texts (from the payload), then the extra
data (fonts), count x (hash, offset), and 8-bit texts ended by 0 (layout from SpeedReflect/Nikki
STRBlock). A padding chunk (id 0) follows: the chunk grows into it, the file keeps its size.

New texts are appended after the last one (other labels may share a text: none is changed in
place) and their entries point to them; the rest of the file is unchanged.
"""
import re
import struct

LANG_CHUNK = 0x39000
NAME = 'MX-5 RF'
YEAR = '2019'   # first model year of the ND2 2.0 184 ch in Europe


def bstringhash(s):
    h = 0xFFFFFFFF
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def _rename(text):
    """'Miata', 'MX-5', 'Mazda MX-5 Miata', 'la Mazda MX-5 del 1999', '1999 Mazda MX-5 Miata'...
    -> the same with MX-5 RF (and the ND2's model year)."""
    t = text.replace('MX-5 Miata', NAME).replace('Miata', NAME)
    if NAME not in t:
        t = t.replace('MX-5', NAME)
    return t.replace('1999', YEAR)


# label -> new text from the old one ('' stays '': the Asian files leave some names empty)
UG1_LABELS = ('CAR_NAME_MIATA', 'CAR_MODEL_NAME_MIATA', 'FULL_NAME_MIATA', 'YEAR_FULL_NAME_MIATA',
              # the European name of the same car (used by the game for some languages)
              'CAR_MODEL_NAME_MX5', 'FULL_NAME_MX5', 'YEAR_FULL_NAME_MX5')
UG2_LABELS = ('CAR_NAME_MIATA',)
# the files with the texts (not LANGUAGE_LABELS, which holds the label names)
UG1_FILES = ('ENGLISH', 'FRENCH', 'GERMAN', 'ITALIAN', 'SPANISH', 'DUTCH', 'SWEDISH', 'KOREAN',
             'CHINESE', 'LARGEST')
UG2_FILES = ('ENGLISH', 'FRENCH', 'GERMAN', 'ITALIAN', 'SPANISH', 'DUTCH', 'SWEDISH', 'DANISH',
             'KOREAN')


# --- Underground ---------------------------------------------------------------------------
def ug1_parse(d):
    cid, size = struct.unpack_from('<II', d, 0)
    if cid != LANG_CHUNK:
        raise ValueError('pas un fichier de langue')
    n = struct.unpack_from('<I', d, 8)[0]
    base = 12 + 8 * n
    out = {}
    for i in range(n):
        h, o = struct.unpack_from('<II', d, 12 + 8 * i)
        s = e = base + o
        while d[e:e + 2] != b'\0\0':
            e += 2
        out[h] = (i, o, d[s:e])
    return out, base, 8 + size


def _u16(raw):
    """UTF-16 code units -> str, the game's sign-extended bytes as Latin-1."""
    return ''.join(chr(c & 0xFF if c >= 0xFF00 else c) for c in struct.unpack('<%dH' % (len(raw) // 2), raw))


def _to_u16(s, like):
    """str -> code units, with accented letters sign-extended as in the file `like` came from."""
    sign = any(c >= 0xFF00 for c in struct.unpack('<%dH' % (len(like) // 2), like))
    return b''.join(struct.pack('<H', (0xFF00 | ord(c)) if sign and 0x80 <= ord(c) < 0x100 else ord(c))
                    for c in s)


def ug1_patch(d, labels=UG1_LABELS):
    """(new file bytes, [(label, old, new)])."""
    strings, base, end = ug1_parse(d)
    if end != len(d):
        raise ValueError('données après le texte (%d / %d)' % (end, len(d)))
    out = bytearray(d)
    changes = []
    for lab in labels:
        h = bstringhash(lab)
        if h not in strings:
            continue
        i, o, raw = strings[h]
        old = _u16(raw)
        new = _rename(old)
        if not old or new == old:
            continue
        if len(out) % 2:
            out += b'\0'
        struct.pack_into('<I', out, 12 + 8 * i + 4, len(out) - base)
        out += _to_u16(new, raw) + b'\0\0'
        changes.append((lab, old, new))
    struct.pack_into('<I', out, 4, len(out) - 8)
    # read back
    again, b2, e2 = ug1_parse(bytes(out))
    assert b2 == base and e2 == len(out) and set(again) == set(strings)
    for lab, old, new in changes:
        assert _u16(again[bstringhash(lab)][2]) == new
    for h, (i, o, raw) in strings.items():
        if h not in {bstringhash(c[0]) for c in changes}:
            assert again[h][2] == raw
    return bytes(out), changes


# --- Underground 2 -------------------------------------------------------------------------
def ug2_parse(d):
    cid, size = struct.unpack_from('<II', d, 0)
    if cid != LANG_CHUNK:
        raise ValueError('pas un fichier de langue')
    udat, n, hoff, toff = struct.unpack_from('<4i', d, 8)
    out = {}
    for i in range(n):
        h, o = struct.unpack_from('<Ii', d, 8 + hoff + 8 * i)
        s = 8 + toff + o
        out[h] = (i, o, d[s:d.index(b'\0', s)])
    return out, (udat, n, hoff, toff), 8 + size


def ug2_patch(d, labels=UG2_LABELS):
    """(new file bytes, [(label, old, new)]): same size, or 128 bytes more."""
    strings, (udat, n, hoff, toff), end = ug2_parse(d)
    # after the last text (some texts are empty: their 0 must stay)
    text_end = max(8 + toff + o + len(raw) + 1 for i, o, raw in strings.values())
    chunk = bytearray(d[:text_end])
    changes = []
    for lab in labels:
        h = bstringhash(lab)
        if h not in strings:
            continue
        i, o, raw = strings[h]
        old = raw.decode('latin-1')
        new = _rename(old)
        if not old or new == old:
            continue
        struct.pack_into('<i', chunk, 8 + hoff + 8 * i + 4, len(chunk) - 8 - toff)
        chunk += new.encode('latin-1') + b'\0'
        changes.append((lab, old, new))
    while len(chunk) % 4:
        chunk += b'\0'
    rest = d[end:]
    if len(chunk) <= end:
        chunk += b'\0' * (end - len(chunk))       # still inside the old chunk
        struct.pack_into('<I', chunk, 4, end - 8)
        out = bytes(chunk) + rest
    else:
        # grow into the padding chunk that follows (id 0); if it is too small, the next chunks
        # move by a multiple of 128 bytes (they keep their alignment) and the file grows
        pid, psize = struct.unpack_from('<II', rest, 0)
        if pid != 0:
            raise ValueError('pas de bloc de remplissage après le texte')
        rest = rest[8 + psize:]
        start = end + 8 + psize                   # where the next chunk was
        while start - len(chunk) < 8:
            start += 0x80
        struct.pack_into('<I', chunk, 4, len(chunk) - 8)
        gap = start - len(chunk) - 8
        out = bytes(chunk) + struct.pack('<II', 0, gap) + b'\0' * gap + rest
    assert out[len(out) - len(rest):] == d[len(d) - len(rest):]
    again, hdr2, _ = ug2_parse(out)
    assert hdr2 == (udat, n, hoff, toff) and set(again) == set(strings)
    done = {bstringhash(c[0]): c[2] for c in changes}
    for h, (i, o, raw) in strings.items():
        assert again[h][2] == (done[h].encode('latin-1') if h in done else raw)
    return out, changes


def find(d, pattern, game):
    """[(hash, text)] of the texts matching `pattern` (to look for other names)."""
    if game == 'ug1':
        strings = {h: _u16(r) for h, (i, o, r) in ug1_parse(d)[0].items()}
    else:
        strings = {h: r.decode('latin-1') for h, (i, o, r) in ug2_parse(d)[0].items()}
    return [(h, t) for h, t in strings.items() if re.search(pattern, t, re.I)]
