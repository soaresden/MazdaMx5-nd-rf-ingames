"""French, German or Italian version of NFS Underground 2 for nfsu2-sw (Xbox NTSC-U recompiled
for Switch), port unchanged (mode A; French tested on Switch 2026-10-12: career, French speech
in races). The Europe disc has the speech and cut-scenes of these three (suffixes _FR, _GR, _IT),
no Spanish, Dutch or Swedish speech.

From the Europe disc, into the extracted USA game's NFSUNDER/ (French shown):
  ZZDATA10.BIN  the French text, speech (UG2_Speech_FR.*) and cut-scenes (*_FR.vp6)
  ZZDATA11.BIN  Global/FrontEndMemoryFile.bin and InGameMemoryFile.bin with the French speech
                index, events and script (the game preloads a copy of them: with the English
                one, the career froze after its first cut-scene)
  ZDIR.BIN      the English names pointed at the French data (every copy of each)
The USA ZDIR.BIN is kept as ZDIR_anglais.BIN to go back to English.
"""
import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs-most-wanted-x360'))
import xdvdfs  # noqa: E402

SECTOR = 2048
US_XBE_SHA256 = 'c8cab1bfe7cf26553e84eb4ef2a26d16f6b06260f7494c583802bc00fd81dd31'
INV33 = pow(33, -1, 1 << 32)
MOVIES = ['ealogo', 'PSA', 'DriftTut', 'DragTut', 'StreetXTut'] + \
         ['Scene%02d' % i for i in [1] + list(range(5, 19)) + [20]]
UNNAMED_MOVIE_US = 0xA420FE8B   # MOVIES\<?>.vp6, a 4th tutorial-like movie (name unknown)
MEMFILES = ['Global\\FrontEndMemoryFile.bin', 'Global\\InGameMemoryFile.bin']
SPEECH = ['evt', 'idx', 'csi']
# language -> (text file, suffix of its speech and cut-scenes on the Europe disc)
LANGS = {'fr': ('FRENCH', 'FR'), 'de': ('GERMAN', 'GR'), 'it': ('ITALIAN', 'IT')}


def bhash(name):
    h = 0xFFFFFFFF
    for c in name.replace('/', '\\').upper().encode('latin-1'):
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def _back(h, s):
    for c in reversed(s.encode()):
        h = ((h - c) * INV33) & 0xFFFFFFFF
    return h


def _fwd(h, s):
    for c in s.encode():
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def entries(zdir):
    return [list(struct.unpack_from('<6I', zdir, i)) for i in range(0, len(zdir) - 23, 24)]


class EuDisc:
    def __init__(self, iso):
        self.iso = iso
        self.files = xdvdfs.list_files(iso)
        size, off = self.files['NFSUNDER/ZDIR.BIN']
        with open(iso, 'rb') as f:
            f.seek(off)
            self.e = {t[0]: t for t in entries(f.read(size))}

    def read(self, h):
        _, num, sec, _, ln, _ = self.e[h]
        _, base = self.files['NFSUNDER/ZZDATA%d.BIN' % num]
        with open(self.iso, 'rb') as f:
            f.seek(base + sec * SECTOR)
            return f.read(ln)


def plan(lang='fr', with_thx=True):
    """[(label, USA hash the port reads, Europe hash of the language's data)]"""
    text, c = LANGS[lang]
    p = [('LANGUAGES\\%s.BIN' % text, bhash('LANGUAGES\\ENGLISH.BIN'), bhash('LANGUAGES\\%s.BIN' % text))]
    for ext in ('big', 'idx', 'evt', 'csi'):
        p.append(('sound\\speech\\UG2_Speech_%s.%s' % (c, ext), bhash('sound\\speech\\UG2_Speech.' + ext),
                  bhash('sound\\speech\\UG2_Speech_%s.%s' % (c, ext))))
    for m in MOVIES:
        p.append(('MOVIES\\%s_%s.vp6' % (m, c), bhash('MOVIES\\%s.vp6' % m), bhash('MOVIES\\%s_%s.vp6' % (m, c))))
    p.append(('MOVIES\\<?>_%s.vp6' % c, UNNAMED_MOVIE_US, _fwd(_back(UNNAMED_MOVIE_US, '.VP6'), '_%s.VP6' % c)))
    if with_thx:
        p.append(('MOVIES\\THX_logo_%s.vp6' % c, bhash('MOVIES\\THX_logo.vp6'), bhash('MOVIES\\THX_logo_%s.vp6' % c)))
    return p


def _memfile_entries(b):
    """{hash: (offset, size, size2)} of a memory bundle (20-byte entries after 16 bytes)."""
    n = struct.unpack_from('<I', b, 12)[0]
    out = {}
    for i in range(n):
        h, off, size, size2, _ = struct.unpack_from('<5I', b, 16 + 20 * i)
        out[h] = (off, size, size2)
    return out


def build(game_dir, eu_iso, lang='fr', log=print):
    """Writes ZZDATA10.BIN, ZZDATA11.BIN and the ZDIR.BIN of `lang` (fr, de, it) into
    game_dir/NFSUNDER."""
    text, c = LANGS[lang]
    with open(os.path.join(game_dir, 'default.xbe'), 'rb') as f:
        if hashlib.sha256(f.read()).hexdigest() != US_XBE_SHA256:
            raise SystemExit("default.xbe n'est pas celui du disque USA (celui du portage)")
    nfs = os.path.join(game_dir, 'NFSUNDER')
    zdir_path = os.path.join(nfs, 'ZDIR.BIN')
    keep = os.path.join(nfs, 'ZDIR_anglais.BIN')
    if not os.path.exists(keep):
        shutil.copyfile(zdir_path, keep)
    with open(keep, 'rb') as f:
        rows = entries(f.read())
    sizes = [os.path.getsize(os.path.join(nfs, 'ZZDATA%d.BIN' % i)) for i in range(10)]
    base10 = sum(s // SECTOR for s in sizes)
    eu = EuDisc(eu_iso)
    if bhash('sound\\speech\\UG2_Speech_%s.big' % c) not in eu.e:
        raise SystemExit("ce disque n'a pas les voix de %s (ce n'est pas le disque Europe)" % text)
    with_thx = bhash('MOVIES\\THX_logo_%s.vp6' % c) in eu.e     # French only

    def us_read(name):
        h = bhash(name)
        e = next(r for r in rows if r[0] == h)
        with open(os.path.join(nfs, 'ZZDATA%d.BIN' % e[1]), 'rb') as f:
            f.seek(e[2] * SECTOR)
            return f.read(e[4])

    placed = {}                         # USA hash -> (pack, sector, length, checksum or None, label)
    sec = 0
    with open(os.path.join(nfs, 'ZZDATA10.BIN'), 'wb') as f:
        for label, tgt, src in plan(lang, with_thx):
            data = eu.read(src)
            placed[tgt] = (10, sec, len(data), eu.e[src][5], label)
            f.write(data + bytes(-len(data) % SECTOR))
            sec += (len(data) + SECTOR - 1) // SECTOR
    base11 = base10 + sec
    log('  ZZDATA10.BIN : %d fichiers (%s), %d Mo' % (len(placed), text, (sec * SECTOR) >> 20))
    # the two preloaded bundles, with the language's speech evt/idx/csi patched in place
    fr = {ext: eu.read(bhash('sound\\speech\\UG2_Speech_%s.%s' % (c, ext))) for ext in SPEECH}
    zz11 = bytearray()
    for name in MEMFILES:
        b = bytearray(us_read(name))
        ents = _memfile_entries(b)
        for ext in SPEECH:
            off, size, size2 = ents[bhash('sound\\speech\\UG2_Speech.' + ext)]
            if size != len(fr[ext]) or size2 != size:
                raise SystemExit('%s : taille de %s différente (%d / %d)' % (name, ext, size, len(fr[ext])))
            b[off:off + size] = fr[ext]
        placed[bhash(name)] = (11, len(zz11) // SECTOR, len(b), None, name)
        zz11 += b + bytes(-len(b) % SECTOR)
    with open(os.path.join(nfs, 'ZZDATA11.BIN'), 'wb') as f:
        f.write(zz11)
    # ZDIR: every entry (duplicates included) of each redirected name
    for h, (num, s, ln, ck, label) in placed.items():
        g = (base10 if num == 10 else base11) + s
        hit = 0
        for r in rows:
            if r[0] == h:
                # last field: an EA checksum the game does not check; the Europe one for the
                # Europe data, the old one for the two bundles
                r[1:] = [num, s, g, ln, r[5] if ck is None else ck]
                hit += 1
        if not hit:
            raise SystemExit('nom absent du ZDIR.BIN : ' + label)
    with open(zdir_path, 'wb') as f:
        for r in rows:
            f.write(struct.pack('<6I', *r))
    # check: every redirected file read back
    for label, tgt, src in plan(lang, with_thx):
        num, s, ln, _, _ = placed[tgt]
        with open(os.path.join(nfs, 'ZZDATA10.BIN'), 'rb') as f:
            f.seek(s * SECTOR)
            assert f.read(ln) == eu.read(src), label
    log('  ZZDATA11.BIN : index des voix (%s) dans les 2 fichiers préchargés ; ZDIR.BIN redirigé' % text)
    return placed
