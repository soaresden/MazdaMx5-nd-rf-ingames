"""French version of NFS Underground for nfsu1-sw (Xbox NTSC-U recompiled for Switch).

The French text and speech are already on the USA disc; only the dubbed cut-scenes are not:
MOVIES/FR*.MAD of the Europe disc (only their sound differs from the USA ones). The port picks
the language with NFSU1_LANGUAGE (antoxa2584x/nfsu1-sw#8). For a port without it, plan B: the USA
default.xbe with data tables swapped so that language 0 is French (code untouched, so the
lifted C still matches; tested on Switch 2026-10-12).
"""
import hashlib
import os
import struct

import disc_ug

USA_XBE_SHA1 = 'a181e75f458e1158cc908a11271c81f53d97ad6d'
EUR_XBE_SHA1 = '71eea18985727861b32f0c414b65ef6596ebdbf9'

LANG_TABLE = 0x255258      # 9 x {id, name, file}       (sub_00159290)
MOVIE_TABLE = 0x2552F0     # 22 rows x 9 x {id, name}   (sub_001595C0)
MOVIE_END = 0x255920
STREAMS = 0x24B438         # 9 x {.ast stream, .abk bank}; 4 English, 5 French
LOCALE_EN = 0x1F4874       # "memcard\XBOX_LOCALE_ENGLISH.loc" (32 bytes)


def french_movies(eu_iso, usa_iso, game_dir, log=print):
    """MOVIES/FR*.MAD of the Europe disc into game_dir/MOVIES; FR04GUME.MAD, asked for in French
    but on neither disc, is the English 04_GUM_E. Returns how many."""
    te, tu = disc_ug.tree(eu_iso), disc_ug.tree(usa_iso)
    ke = disc_ug.find(te, 'default.xbe')
    if not ke or hashlib.sha1(disc_ug.read(eu_iso, te[ke])).hexdigest() != EUR_XBE_SHA1:
        log('  attention : ce disque Europe n\'est pas celui qui a été étudié')
    n = 0
    for k in sorted(te):
        up = k.upper()
        if up.startswith('MOVIES/FR') and up.endswith('.MAD'):
            disc_ug.copy(eu_iso, te[k], os.path.join(game_dir, *k.split('/')))
            n += 1
    if not n:
        raise SystemExit("pas de cinématiques françaises : ce n'est pas le disque Europe de NFS Underground")
    if not disc_ug.find(te, 'MOVIES/FR04GUME.MAD'):
        k = disc_ug.find(tu, 'MOVIES/04_GUM_E.MAD')
        disc_ug.copy(usa_iso, tu[k], os.path.join(game_dir, 'MOVIES', 'FR04GUME.MAD'))
    log('  %d cinématiques françaises (disque Europe)' % n)
    return n


class _Xbe:
    def __init__(self, d):
        self.d = bytearray(d)
        self.base, = struct.unpack_from('<I', d, 0x104)
        n, sh = struct.unpack_from('<II', d, 0x11C)
        self.secs = []
        for i in range(n):
            _, va, vs, ra, rs = struct.unpack_from('<IIIII', d, sh - self.base + i * 0x38)
            self.secs.append((va, ra, rs))

    def off(self, va):
        for sva, ra, rs in self.secs:
            if sva <= va < sva + rs:
                return ra + va - sva
        raise KeyError(hex(va))

    def u32(self, va):
        return struct.unpack_from('<I', self.d, self.off(va))[0]

    def put32(self, va, v):
        struct.pack_into('<I', self.d, self.off(va), v)


def patch_xbe(data, log=print):
    """Plan B: the USA default.xbe with French as language 0 (text, cut-scenes, speech, save
    labels)."""
    if hashlib.sha1(data).hexdigest() != USA_XBE_SHA1:
        raise SystemExit('default.xbe USA inattendu (sha1) : correctif refusé')
    x = _Xbe(data)
    # text: language 0 loads LANGUAGE_FRENCH.BIN (ids 0 and 1 swapped)
    assert x.u32(LANG_TABLE) == 0 and x.u32(LANG_TABLE + 12) == 1
    x.put32(LANG_TABLE, 1)
    x.put32(LANG_TABLE + 12, 0)
    # cut-scenes: in each row the French entry becomes language 0's
    rows = 0
    for row in range(MOVIE_TABLE, MOVIE_END, 0x48):
        if x.u32(row) == 0 and x.u32(row + 8) == 1:
            x.put32(row, 1)
            x.put32(row + 8, 0)
            rows += 1
    # speech: the "English" stream (4) becomes STRM_French_Speech_MB
    a, b = x.off(STREAMS + 4 * 8), x.off(STREAMS + 5 * 8)
    x.d[a:a + 8], x.d[b:b + 8] = bytes(x.d[b:b + 8]), bytes(x.d[a:a + 8])
    # save labels on the dashboard
    o = x.off(LOCALE_EN)
    assert bytes(x.d[o:o + 31]) == b'memcard\\XBOX_LOCALE_ENGLISH.loc'
    x.d[o:o + 32] = b'memcard\\XBOX_LOCALE_FRENCH.loc'.ljust(32, b'\0')
    log('  default.xbe : langue 0 = français (textes, %d lignes de cinématiques, voix, sauvegardes)' % rows)
    return bytes(x.d)
