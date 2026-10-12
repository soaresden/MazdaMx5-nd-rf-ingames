"""The MX-5 RF in Need for Speed Underground (Xbox, played on the Switch with nfsu1-sw), in place of
the Mazda Miata: CARS/MIATA/GEOMETRY.BIN and TEXTURES.BIN, made from the player's disc image and
the Assetto Corsa model.

The model comes from the Most Wanted converter (build_mx5.collect: the same parts and materials),
moved so that its wheels sit where the game puts the Miata's (CarTypeInfo of GLOBALB: axles at
x = 1.03 and -1.26, wheel centres at z = 0.122). Then, solid by solid, on the Miata's own file:
- stock parts (body, base with the cockpit and the windows, hood, lights, mirrors): the MX-5's;
- wide bodies, hoods and lights of the body kits: copies of the MX-5's (the car stays the MX-5
  whatever is fitted);
- bumpers, skirts, roofs, spoilers, engine, exhaust and decal pieces of the kits: one invisible
  triangle each (their position markers kept: exhausts, plate, lights);
- wheels: the game's.
Textures: the MX-5's pictures in place of Miata textures the car no longer uses (same size and
format, so TEXTURES.BIN keeps its layout).
"""
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('../nfs-most-wanted-x360', '../../common'):
    sys.path.insert(0, os.path.join(HERE, p))

import build_mx5 as MW   # noqa: E402
import geo_ug            # noqa: E402
import tpk_ug            # noqa: E402

H = geo_ug.bstringhash
CAR = 'MIATA'
# where the game puts the Miata's wheels (GLOBALB CarTypeInfo) and where the MX-5 model has them
GAME_FRONT_AXLE, GAME_WHEEL_Z = 1.03, 0.122
SHIFT = np.array([GAME_FRONT_AXLE - MW.MX5_FRONT[0], 0.0, GAME_WHEEL_Z - MW.MX5_WHEEL_Z])

SH = {'CARSKIN': 0xD6D6080A, 'DULLPLASTIC': 0x0FEDEE40, 'WINDSHIELD': 0x471A1DCA,
      'HEADLIGHTREFLECTOR': 0xB51B3ACF, 'HEADLIGHTGLASS': 0xA6348EE3, 'BRAKELIGHT': 0x05BC3A3C}
SKIN = H(CAR + '_SKIN1')          # the paint (made by the game)
WINDOW = 0x7B220DDF               # WINDOW_FRONT, the game's window glass
HEADLIGHT_GLASS = 0xD17A8EBE      # the glass texture of the Miata's headlights
ATLAS_SLOT = CAR + '_ENGINE'      # 256x256 DXT1: cockpit, plastics, details
LIGHTS_SLOT = CAR + '_STYLE01_ENGINE'   # 256x256 DXT1 (mips): the lamps
OPAQUE, BLENDED = 0x14180, 0x1C180
# vertex layouts: Underground 36 bytes (position, colour, uv, normal), Underground 2 32 bytes
# (position, uv, normal: no colour)
STRIDE = {'ug1': 36, 'ug2': 32}
GAME = 'ug1'

ATLAS = 'atlas'
LIGHTS = 'lights'
# MW material -> (shader, texture, flags)
MATS = {
    'paint': ('CARSKIN', SKIN, OPAQUE), 'int_paint': ('CARSKIN', SKIN, OPAQUE),
    'glass': ('WINDSHIELD', WINDOW, BLENDED),
    'hlg_L': ('HEADLIGHTGLASS', HEADLIGHT_GLASS, BLENDED), 'hlg_R': ('HEADLIGHTGLASS', HEADLIGHT_GLASS, BLENDED),
    'lights_ext': ('HEADLIGHTREFLECTOR', LIGHTS, OPAQUE),
    'hl_L': ('HEADLIGHTREFLECTOR', LIGHTS, OPAQUE), 'hl_R': ('HEADLIGHTREFLECTOR', LIGHTS, OPAQUE),
    'hlp_L': ('HEADLIGHTREFLECTOR', LIGHTS, OPAQUE), 'hlp_R': ('HEADLIGHTREFLECTOR', LIGHTS, OPAQUE),
    'bl_L': ('BRAKELIGHT', LIGHTS, OPAQUE), 'bl_R': ('BRAKELIGHT', LIGHTS, OPAQUE),
}
# Underground 2 lamps (as the Miata's): only the game's shared textures of each side, which it
# swaps when the lights go on; a car texture on them is not drawn (see-through lamps). Lamp
# bodies: shader 0x12C9453C and HEADLIGHT_LEFT / RIGHT; glass: HEADLIGHT_GLASS_LEFT / RIGHT; brake
# lights: shader 0xF7FC7674 and BRAKELIGHT_LEFT / RIGHT. No HEADLIGHTREFLECTOR shader in this game.
LAMP_UG2, BRAKE_UG2 = 0x12C9453C, 0xF7FC7674
GLASS_UG2 = {'L': H('HEADLIGHT_GLASS_LEFT'), 'R': H('HEADLIGHT_GLASS_RIGHT')}
HEAD_UG2 = {'L': H('HEADLIGHT_LEFT'), 'R': H('HEADLIGHT_RIGHT')}
BRAKE_TEX_UG2 = {'L': H('BRAKELIGHT_LEFT'), 'R': H('BRAKELIGHT_RIGHT')}
DROP = {'plate', 'tyre', 'rim', 'logo', 'disc', 'caliper'}   # the game draws plate and wheels
# The paint texture is made by the game from the Miata's door lines and shading
# (MIATA_DOORLINE*, 8-bit, swizzled, laid out for the Miata): the MX-5's own UVs would pick those
# lines up as stickers. The paint takes one plain spot of it instead, blank in all six overlays
# of both games (72 texels of 512 around it).
SKIN_UV = (0.8213, 0.3799)
# the first group of the Miata's BASE is the driver (texture DRIVER): the game draws it on its own
# (Underground does not show it in the menus), so it stays first
DRIVER = H('DRIVER')

# MW parts -> the Miata solid they go into (without the LOD letter)
PARTS = {
    'KIT00_BODY': 'KIT00_BODY', 'KIT00_HOOD': 'KIT00_HOOD', 'BASE': 'BASE', 'KIT00_INTERIOR': 'BASE',
    'KIT00_FRONT_WINDOW': 'BASE', 'KIT00_REAR_WINDOW': 'BASE', 'KIT00_FRONT_LEFT_WINDOW': 'BASE',
    'KIT00_FRONT_RIGHT_WINDOW': 'BASE',
    'KIT00_LEFT_HEADLIGHT': 'KIT00_HEADLIGHT', 'KIT00_RIGHT_HEADLIGHT': 'KIT00_HEADLIGHT',
    'KIT00_LEFT_HEADLIGHT_GLASS': 'KIT00_HEADLIGHT', 'KIT00_RIGHT_HEADLIGHT_GLASS': 'KIT00_HEADLIGHT',
    'KIT00_LEFT_BRAKELIGHT': 'KIT00_BRAKELIGHT', 'KIT00_RIGHT_BRAKELIGHT': 'KIT00_BRAKELIGHT',
    'KIT00_LEFT_SIDE_MIRROR': 'KIT00_LEFT_SIDE_MIRROR', 'KIT00_RIGHT_SIDE_MIRROR': 'KIT00_RIGHT_SIDE_MIRROR',
}
# Underground 2 has the headlights in two solids (the kits' ones are mostly in one)
SPLIT_HEADLIGHTS = {'KIT00_LEFT_HEADLIGHT': 'KIT00_HEADLIGHT_LEFT', 'KIT00_RIGHT_HEADLIGHT': 'KIT00_HEADLIGHT_RIGHT',
                    'KIT00_LEFT_HEADLIGHT_GLASS': 'KIT00_HEADLIGHT_LEFT', 'KIT00_RIGHT_HEADLIGHT_GLASS': 'KIT00_HEADLIGHT_RIGHT'}
# triangles of the most detailed level, per solid; the other levels a share of it
BUDGET = {'KIT00_BODY': 9000, 'BASE': 9000, 'KIT00_HOOD': 2500, 'KIT00_HEADLIGHT': 2500,
          'KIT00_HEADLIGHT_LEFT': 1300, 'KIT00_HEADLIGHT_RIGHT': 1300,
          'KIT00_BRAKELIGHT': 1500, 'KIT00_LEFT_SIDE_MIRROR': 400, 'KIT00_RIGHT_SIDE_MIRROR': 400}
LOD_SHARE = {'A': 1.0, 'B': 0.45, 'C': 0.2, 'D': 0.08}


def solid_kind(name):
    """(our part or None, how): 'ours', 'copy' (a kit piece that becomes ours), 'empty', 'keep'."""
    n = name[len(CAR) + 1:]
    if '_WHEEL' in n or '_BRAKE_' in n or n.endswith('_BRAKE'):
        return None, 'keep'
    if n.startswith('KIT00_HEADLIGHT_LEFT'):
        return 'KIT00_HEADLIGHT_LEFT', 'ours'
    if n.startswith('KIT00_HEADLIGHT_RIGH'):
        return 'KIT00_HEADLIGHT_RIGHT', 'ours'
    if n.startswith('STYLE') and '_HEADLIGHT_LEFT' in n:
        return 'KIT00_HEADLIGHT_LEFT', 'copy'
    if n.startswith('STYLE') and '_HEADLIGHT_RIGH' in n:
        return 'KIT00_HEADLIGHT_RIGHT', 'copy'
    for part in ('KIT00_BODY', 'KIT00_HOOD', 'BASE', 'KIT00_HEADLIGHT', 'KIT00_BRAKELIGHT'):
        if n.startswith(part + '_'):
            return part, 'ours'
    if n.startswith('KIT00_LEFT_SIDE_MIRRO'):
        return 'KIT00_LEFT_SIDE_MIRROR', 'ours'
    if n.startswith('KIT00_RIGHT_SIDE_MIRR'):
        return 'KIT00_RIGHT_SIDE_MIRROR', 'ours'
    if n.startswith('KITW') and '_BODY_' in n:
        return 'KIT00_BODY', 'copy'
    if n.startswith('STYLE') and '_HOOD_' in n:
        return 'KIT00_HOOD', 'copy'
    if n.startswith('STYLE') and '_HEADLIGHT' in n:
        return 'KIT00_HEADLIGHT', 'copy'
    if n.startswith('STYLE') and '_BRAKELIGH' in n:
        return 'KIT00_BRAKELIGHT', 'copy'
    return None, 'empty'


def collect(kn5, top):
    MW.OPEN_TOP = top == 'open'
    MW.SKIP_NAMES = {'gum_07'}   # the aerial
    textures, parts, wheel_c = MW.collect(kn5)
    out = {}
    for part, subs in parts.items():
        if part not in PARTS:
            continue
        for sb in subs:
            if sb.mat in DROP:
                continue
            sb = MW.Sub(sb.mat, sb.pos + SHIFT.astype(sb.pos.dtype), sb.nrm, sb.uv, sb.col, sb.tri)
            out.setdefault(PARTS[part], []).append(sb)
            if GAME == 'ug2' and part in SPLIT_HEADLIGHTS:
                out.setdefault(SPLIT_HEADLIGHTS[part], []).append(sb)
    return textures, out


def material(mat):
    if mat in MATS:
        shader, texture, flags = MATS[mat]
        if GAME == 'ug2':
            side = mat[-1] if mat[-2:] in ('_L', '_R') else 'L'
            if shader == 'HEADLIGHTGLASS':
                texture = GLASS_UG2[side]
            elif shader == 'HEADLIGHTREFLECTOR':
                shader, texture = LAMP_UG2, HEAD_UG2[side]
            elif shader == 'BRAKELIGHT':
                shader, texture = BRAKE_UG2, BRAKE_TEX_UG2[side]
        return shader, texture, flags
    return ('DULLPLASTIC', ATLAS, OPAQUE)


def lods(part, subs, letters, scale=1.0):
    """{letter: [Sub]} with the triangle budget of the part (times scale)."""
    MW.MAX_TRIS = 1 << 20        # no split of the groups
    MW.MAX_GROUPS = 16
    merged = MW.merge(subs)
    out = {}
    for L in letters:
        total = max(12, int(BUDGET.get(part, 2000) * scale * LOD_SHARE[L]))
        src = merged if L == 'A' else out['A']
        tg = MW.budget(src, total)
        out[L] = [r for r in (MW.reduce(sb, t) for sb, t in zip(src, tg)) if len(r.tri)]
    return out


def make_mesh(subs, keys):
    """Vertex buffer, index buffer, groups and key lists of a solid from its Subs.
    keys: {ATLAS: hash, LIGHTS: hash}."""
    tex, shaders = [], []
    vb, ib, groups = [], [], []
    base = 0
    lo_all, hi_all = None, None
    by = {}
    for sb in subs:
        by.setdefault(material(sb.mat), []).append(sb)
    for (shader, texture, flags), lst in by.items():
        tk = keys.get(texture, texture)
        if tk not in tex:
            tex.append(tk)
        sk = SH.get(shader, shader)
        if sk not in shaders:
            shaders.append(sk)
        start = len(ib)
        lo, hi = None, None
        for sb in lst:
            if texture == ATLAS:
                uv = MW.atlas_uv(sb.mat, sb.uv)
            elif texture == SKIN:
                uv = np.tile(np.array(SKIN_UV, sb.uv.dtype), (len(sb.uv), 1))
            else:
                uv = sb.uv
            used = np.unique(sb.tri)
            remap = np.full(len(sb.pos), -1, np.int64)
            remap[used] = np.arange(len(used)) + base
            p = sb.pos[used].astype(np.float32)
            vb.append(pack_vertices(p, uv[used], sb.nrm[used], sb.col[used]))
            ib.append(remap[sb.tri].astype(np.uint16).ravel())
            base += len(used)
            lo = p.min(0) if lo is None else np.minimum(lo, p.min(0))
            hi = p.max(0) if hi is None else np.maximum(hi, p.max(0))
        groups.append([lo, hi, tex.index(tk), flags, shaders.index(sk), lst])
        lo_all = lo if lo_all is None else np.minimum(lo_all, lo)
        hi_all = hi if hi_all is None else np.maximum(hi_all, hi)
    if base > 65535:
        raise ValueError('too many vertices for one solid: %d' % base)
    idx = np.concatenate(ib)
    # groups in index order
    raw = b''
    start = 0
    for (lo, hi, ti, flags, si, lst) in groups:
        n = sum(len(sb.tri) * 3 for sb in lst)
        raw += struct.pack('<3f3f6I', *lo, *hi, n, ti, flags, start, 0, si) + bytes(16)
        start += n
    return dict(vb=np.concatenate(vb).tobytes(), ib=idx.tobytes(), groups=raw, ngroups=len(groups),
                nverts=base, ntris=len(idx) // 3, tex=tex, shaders=shaders, lo=lo_all, hi=hi_all)


def pack_vertices(pos, uv, nrm, col):
    if STRIDE[GAME] == 32:
        v = np.zeros((len(pos), 8), np.float32)
        v[:, 0:3], v[:, 3:5], v[:, 5:8] = pos, uv, nrm
        return v
    v = np.zeros((len(pos), 9), np.float32)
    v[:, 0:3], v[:, 4:6], v[:, 6:9] = pos, uv, nrm
    v.view(np.uint32)[:, 3] = np.asarray(col).astype(np.uint32)
    return v


def letter_of(s):
    """LOD letter of a solid. Names longer than 27 characters are cut in the header: the letter is
    found from the key (the hash of the whole name)."""
    if len(s.name) < 27:
        return s.name[-1] if s.name[-2] == '_' else 'A'
    key, = struct.unpack_from('<I', s.header, 0x10)
    for mid in ('', '_', 'R_', 'OR_', 'T_', 'HT_', 'GHT_', 'IGHT_', 'E_', 'ER_'):
        for L in 'ABCDE':
            if geo_ug.bstringhash(s.name + mid + L) == key:
                return L
    return 'A'


def with_driver(s, m):
    """The mesh m with the template solid's driver group (its first group, texture DRIVER) put
    back in front of its own groups, as in the Miata's BASE."""
    box = struct.unpack_from('<6f', s.groups_raw, 0)
    n, ti, flags, start, z, si = struct.unpack_from('<6I', s.groups_raw, 24)
    if ti >= len(s.tex) or s.tex[ti] != DRIVER:
        return m
    stride = struct.unpack_from('<I', s.mheader, 8)[0] >> 16
    idx = np.frombuffer(s.ib, np.uint16)[start:start + n].astype(np.int64)
    used = np.unique(idx)
    remap = {v: k for k, v in enumerate(used)}
    vb = b''.join(s.vb[v * stride:(v + 1) * stride] for v in used)
    nd = len(used)
    m = dict(m)
    tex, shaders = list(m['tex']), list(m['shaders'])
    if DRIVER not in tex:
        tex.append(DRIVER)
    if s.shaders[si] not in shaders:
        shaders.append(s.shaders[si])
    raw = struct.pack('<6f6I', *box, n, tex.index(DRIVER), flags, 0, z, shaders.index(s.shaders[si])) + s.groups_raw[48:64]
    rest = bytearray(m['groups'])
    for o in range(0, len(rest), 64):
        st, = struct.unpack_from('<I', rest, o + 36)
        struct.pack_into('<I', rest, o + 36, st + n)
    ib = np.array([remap[v] for v in idx], np.uint16).tobytes() +         (np.frombuffer(m['ib'], np.uint16).astype(np.int64) + nd).astype(np.uint16).tobytes()
    if m['nverts'] + nd > 65535:
        raise ValueError('too many vertices with the driver')
    dl, dh = np.array(box[:3]), np.array(box[3:])
    m.update(vb=vb + m['vb'], ib=ib, groups=raw + bytes(rest), ngroups=m['ngroups'] + 1, nverts=m['nverts'] + nd,
             ntris=m['ntris'] + n // 3, tex=tex, shaders=shaders, lo=np.minimum(m['lo'], dl), hi=np.maximum(m['hi'], dh))
    return m


def degenerate_mesh(keys):
    pos = np.array([[0, 0, 0], [0.001, 0, 0], [0, 0.001, 0]], np.float32)
    v = pack_vertices(pos, np.zeros((3, 2), np.float32), np.tile([0, 0, 1.0], (3, 1)), np.full(3, 0xFF000000))
    raw = struct.pack('<3f3f6I', 0, 0, 0, 0.001, 0.001, 0, 3, 0, OPAQUE, 0, 0, 0) + bytes(16)
    return dict(vb=v.tobytes(), ib=np.array([0, 1, 2], np.uint16).tobytes(), groups=raw, ngroups=1, nverts=3,
                ntris=1, tex=[keys[ATLAS]], shaders=[SH['DULLPLASTIC']], lo=np.zeros(3), hi=np.full(3, 0.001))


def apply_mesh(s, m, markers=None):
    """Put a mesh into a parsed solid of the template (header, mesh header and key lists)."""
    h = bytearray(s.header)
    struct.pack_into('<H', h, 0x14, min(m['ntris'], 0xFFFF))
    h[0x19], h[0x1A] = len(m['tex']), len(m['shaders'])
    struct.pack_into('<4f', h, 0x20, *m['lo'], 0)
    struct.pack_into('<4f', h, 0x30, *m['hi'], 0)
    s.header = bytes(h)
    mh = bytearray(s.mheader)
    w1, = struct.unpack_from('<I', mh, 4)
    struct.pack_into('<I', mh, 4, (m['nverts'] << 16) | (w1 & 0xFFFF))
    struct.pack_into('<I', mh, 8, (STRIDE[GAME] << 16) | m['ngroups'])
    s.mheader = bytes(mh)
    s.vb, s.ib, s.groups_raw = m['vb'], m['ib'], m['groups']
    s.tex, s.shaders = m['tex'], m['shaders']
    # no normal smoothing between parts (the chunks of the Miata's vertices); markers kept
    s.post = [(cid, p) for cid, p in s.post if cid not in (0x134017, 0x134018, 0x134019)]
    if markers is not None:
        s.pre = [(cid, markers(p) if cid == 0x13401A else p) for cid, p in s.pre]


def move_markers(payload, where):
    """Markers payload (0x11 padding then 80-byte records: key, 12 bytes, 4x4 matrix) with the
    translation of each record set by where(key, xyz) -> xyz."""
    p = bytearray(payload)
    a = 0
    while a < len(p) and p[a] == 0x11:
        a += 1
    for o in range(a, len(p) - 79, 80):
        key, = struct.unpack_from('<I', p, o)
        xyz = np.array(struct.unpack_from('<3f', p, o + 16 + 48))
        struct.pack_into('<3f', p, o + 16 + 48, *where(key, xyz))
    return bytes(p)


def build(geometry, textures_bin, kn5, top='closed', game='ug1', log=print):
    """(GEOMETRY.BIN, TEXTURES.BIN) of the MX-5 from the Miata's (game: 'ug1' or 'ug2'). The new
    GEOMETRY.BIN is kept smaller than the Miata's (the game has memory for that much): the
    triangle budgets go down until it is."""
    scale = 1.0
    while True:
        geo, tex = _build(geometry, textures_bin, kn5, top, game, log, scale)
        if len(geo) <= 0.95 * len(geometry) or scale < 0.2:
            log('  GEOMETRY.BIN %d octets (Miata : %d)' % (len(geo), len(geometry)))
            return geo, tex
        scale *= 0.8 * len(geometry) / len(geo)
        log('  trop gros (%d octets, Miata %d) : budgets x %.2f' % (len(geo), len(geometry), scale))


def _build(geometry, textures_bin, kn5, top, game, log, scale):
    from PIL import Image
    global GAME
    GAME = game
    ac_tex, parts = collect(kn5, top)
    tpk = (tpk_ug.Tpk2 if game == 'ug2' else tpk_ug.Tpk)(textures_bin)
    slot = {t['name']: t for t in tpk.tex}
    keys = {ATLAS: slot[ATLAS_SLOT]['hash'], LIGHTS: slot[LIGHTS_SLOT]['hash']}
    # textures: the atlas of Most Wanted (same layout, 256 texels) and the lamps
    n = 256

    def pic(name, size):
        im = Image.open(__import__('io').BytesIO(ac_tex[name])).convert('RGB').convert('RGBA')
        return im.resize(size, Image.LANCZOS)

    atlas = Image.new('RGBA', (n, n), (0, 0, 0, 255))
    for (u0, v0, u1, v1), picture in MW.ATLAS_IMAGES.values():
        box = (int(u0 * n), int(v0 * n), int(u1 * n), int(v1 * n))
        atlas.paste(pic(picture, (box[2] - box[0], box[3] - box[1])), box[:2])
    for (u, v), k in MW.INTERIOR_PATCHES.values():
        g = int(round(255 * k))
        atlas.paste((g, g, g, 255), (int(u * n) - 30, int(v * n) - 30, int(u * n) + 30, int(v * n) + 30))
    tpk.put(keys[ATLAS], np.asarray(atlas))
    tpk.put(keys[LIGHTS], np.asarray(pic('EXT_Lights.dds', (256, 256))))
    # geometry
    d = geometry
    solids = geo_ug.read(d)
    for s in solids:
        geo_ug.split_extra(d, s)
    letters = {}
    for s in solids:
        part, how = solid_kind(s.name)
        if part:
            letters.setdefault(part, set()).add(letter_of(s))
    meshes = {}
    for part, subs in parts.items():
        L = sorted(letters.get(part, {'A'}) | {'A'})
        meshes[part] = {k: make_mesh(v, keys) for k, v in lods(part, subs, L, scale).items() if v}
        log('  %-24s %s' % (part, ', '.join('%s %d' % (k, m['ntris']) for k, m in sorted(meshes[part].items()))))
    # markers: lamps at the MX-5's lamps, the rear ones (exhausts, plate) moved with the rear end
    body = np.concatenate([sb.pos for sb in parts['KIT00_BODY']])
    miata_rear = min(sb.bbox[0] for sb in solids if sb.name == CAR + '_KIT00_BODY_A')
    rear_dx = body[:, 0].min() - miata_rear

    def lamp_centre(part, left):
        pts = [sb.pos[np.unique(sb.tri)] for sb in parts.get(part, [])]
        if not pts:
            return None
        p = np.concatenate(pts)
        p = p[(p[:, 1] > 0) == left]
        return p.mean(0) if len(p) else None

    lamps = {0x9DB90133: lamp_centre('KIT00_HEADLIGHT', True), 0xD09091C6: lamp_centre('KIT00_HEADLIGHT', False),
             0x31A66786: lamp_centre('KIT00_BRAKELIGHT', True), 0xBF700A79: lamp_centre('KIT00_BRAKELIGHT', False)}

    def where(key, xyz):
        if key in lamps and lamps[key] is not None:
            return lamps[key]
        if xyz[0] < -1.0:            # rear: exhausts, plate
            return xyz + [rear_dx, 0, 0]
        return xyz

    done = {'ours': 0, 'copy': 0, 'empty': 0, 'keep': 0}
    for s in solids:
        part, how = solid_kind(s.name)
        if how == 'keep':
            done['keep'] += 1
            continue
        letter = letter_of(s)
        m = None
        if part in meshes:
            if how == 'copy':   # kit pieces: the lightest level (the file must not grow)
                m = meshes[part][max(meshes[part])]
            else:
                m = meshes[part].get(letter) or meshes[part]['A']
        if m is None:
            m = degenerate_mesh(keys)
            how = 'empty'
        elif part == 'BASE':
            m = with_driver(s, m)
        apply_mesh(s, m, lambda p: move_markers(p, where))
        done[how] += 1
    log('  solides : %d MX-5, %d copies (kits), %d vides, %d gardés (roues)'
        % (done['ours'], done['copy'], done['empty'], done['keep']))
    geo = geo_ug.write(d, solids)
    return geo, tpk.write()
