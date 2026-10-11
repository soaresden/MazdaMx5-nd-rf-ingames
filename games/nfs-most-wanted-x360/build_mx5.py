"""Replace a car of NFS Most Wanted (Xbox 360) by the Assetto Corsa MX-5 RF.

build_mx5.py --iso <Xbox 360 image> --kn5 <mazda_mx5_rf.kn5> --out <game_root> [--car IS300]
             [--base-root <your current game_root, e.g. with the French dub>] [--wheels auto|keep|patch]

Writes <out>/CARS/<CAR>/GEOMETRY.BIN and TEXTURES.BIN and, when the wheels have to move, a
<out>/GLOBAL/GLOBALMEMORYFILE.BIN whose ATTRIBUTES.BIN has the MX-5 wheel positions for that car.
"""
import argparse
import io
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'common'))
import acmodel  # noqa: E402
import attrib360  # noqa: E402
import geo360  # noqa: E402
import qem  # noqa: E402
import sol360  # noqa: E402
import solids  # noqa: E402
import tpk  # noqa: E402
import tpk360  # noqa: E402
import zzdata  # noqa: E402

H = geo360.bstringhash


def TH(name):
    """Texture hash: bStringHash of the name, or '#xxxxxxxx' for a hash given directly."""
    return int(name[1:], 16) if name.startswith('#') else H(name)

# AC (x left, y up, z forward) -> NFS (x forward, y left, z up), then moved by SHIFT (set for the car
# that is replaced, see place_wheels). The tyre model is a right wheel whose y is (y - wheel centre y)
# + TIRE_Y; the game puts it at the ecar TireOffsets and mirrors it on the left.
SHIFT = np.zeros(3)
TIRE_Y = 0.102
BRAKE_MARKER_Y = 0.045
CAR = 'ELISE'
MAX_TRIS = 1000
# MX-5 wheel centres in the AC model (NFS axes, before SHIFT) and tyre radius
MX5_FRONT = (1.186, 0.748)
MX5_REAR = (-1.123, 0.751)
MX5_WHEEL_Z = 0.298
MX5_RADIUS = 0.308
MX5_TYRE_HALF_WIDTH = 0.112

# ---------------------------------------------------------------------------------------------
# materials: name -> (light material, texture name, flags, key)
MATS = {
    # Every (key, flags) pair is the one the game's own cars use with that light material: on the
    # disc a key always goes with a single light material. Only light materials that cars use.
    'paint':      ('CARSKIN', '{car}_SKIN1', 0x14180, 0x19405159),
    'int_paint':  ('CARSKIN', '{car}_SKIN1', 0x14180, 0x7FAD4ADB),
    # The game draws nothing with MOLDINGS, INTERIOR, MAGSILVER, BRAKEDISC or CALIPER groups of
    # ours (roof, grille, cockpit, MX-5 rims: all missing on the Switch, structure identical to the
    # game's own). DULLPLASTIC is drawn, and honours the vertex colour: used for those parts.
    # black roof: like the black plastics (white texture, black vertex colour); with the plain
    # black texture G05 the panel was not drawn either
    'roof_black': ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'plastic':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'skirt':      ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'rubber':     ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'details':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'chrome':     ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'plate':      ('LICENSEPLATE', 'LICENSEPLATE', 0x4080, 0x853C15A2),
    'glass':      ('WINDSHIELD', 'WINDOW_FRONT', 0x4180, 0x28775FCB),
    'mirror':     ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    # the generic headlight texture: the game swaps in <car>_KIT00_HEADLIGHT_OFF/ON, the same picture
    'lights_ext': ('HEADLIGHTREFLECTOR', 'HEADLIGHT_LEFT', 0x4180, 0x17D7E727),
    'hl_L':       ('HEADLIGHTREFLECTOR', 'HEADLIGHT_LEFT', 0x4180, 0x17D7E727),
    'hl_R':       ('HEADLIGHTREFLECTOR', 'HEADLIGHT_RIGHT', 0x4180, 0xC24443A4),
    'hlp_L':      ('DULLPLASTIC', 'HEADLIGHT_LEFT', 0x4180, 0x2ADF937D),
    'hlp_R':      ('DULLPLASTIC', 'HEADLIGHT_RIGHT', 0x4180, 0x9C667B8B),
    'hlg_L':      ('HEADLIGHTGLASS', 'HEADLIGHT_GLASS_LEFT', 0x14180, 0xFB62D448),
    'hlg_R':      ('HEADLIGHTGLASS', 'HEADLIGHT_GLASS_RIGHT', 0x14180, 0x6EF95D50),
    'bl_L':       ('BRAKELIGHT', 'BRAKELIGHT_LEFT', 0x4180, 0xEC5B66A3),
    'bl_R':       ('BRAKELIGHT', 'BRAKELIGHT_RIGHT', 0x4180, 0x0215BB65),
    'interior':   ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    # greys of the interior: patches of the interior texture
    'int_g08':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'int_g12':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'int_g30':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'int_g45':    ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'tyre':       ('RUBBER', '{car}_MX5_TYRE', 0x14080, 0x45043D7A),
    'rim':        ('MAGSILVER', '{car}_MX5_RIM', 0x4180, 0x0BA372C3),
    'logo':       ('CHROME', '{car}_MX5_LOGO', 0x14180, 0xC9ABEC7C),
    'disc':       ('BRAKEDISC', '{car}_MX5_DISC', 0x4180, 0x09768E11),
    # diagnostic squares only (MX5_SQUARES): the materials that were not drawn
    'sq_g05':     ('DULLPLASTIC', '{car}_MX5_G05', 0x14180, 0xFB3A7B77),
    # same plastic, only the texture changes: ours, ours under hashes of the Lexus pack, the Lexus' own
    'tx_white':   ('DULLPLASTIC', '{car}_MX5_WHITE', 0x14180, 0xFB3A7B77),
    'tx_white_e6': ('DULLPLASTIC', '#E6A7115A', 0x14180, 0xFB3A7B77),
    'tx_white_19': ('DULLPLASTIC', '#19F11092', 0x14180, 0xFB3A7B77),
    'tx_interior': ('DULLPLASTIC', '{car}_INTERIOR', 0x14180, 0xFB3A7B77),
    'tx_misc':    ('DULLPLASTIC', '{car}_MISC', 0x14180, 0xFB3A7B77),
    'tx_hl_on':   ('DULLPLASTIC', '{car}_KIT00_HEADLIGHT_ON', 0x14180, 0xFB3A7B77),
    'sq_moldings': ('MOLDINGS', '{car}_MX5_DETAILS', 0x14180, 0x99308649),
    'sq_interior': ('INTERIOR', '{car}_INTERIOR', 0x4080, 0xB1540568),
    'caliper':    ('CALIPER', '{car}_MX5_CALIPER', 0x4180, 0x4638230F),
}
# glass textures get the generic opacity map of the Elise headlight glass
OPACITY = {'hlg_L': '{car}_KIT00_HEADLIGHT_GLASS_OFF', 'hlg_R': '{car}_KIT00_HEADLIGHT_GLASS_OFF'}

DROP_MATS = {'EXT_RearLight_Beam', 'EXT_FrontLight_Beam', 'DAMAGE_GLASS', 'INT_Glass_REFLEX',
             'INT_Decals_Chrome_Aluminium'}


class Sub:
    """A piece of geometry with one NFS material."""

    def __init__(self, mat, pos, nrm, uv, col, tri):
        self.mat, self.pos, self.nrm, self.uv, self.col, self.tri = mat, pos, nrm, uv, col, tri

    def take(self, mask):
        """Sub with only the triangles where mask is true."""
        return Sub(self.mat, self.pos, self.nrm, self.uv, self.col, self.tri[mask])

    def take_tris(self, tri):
        return Sub(self.mat, self.pos, self.nrm, self.uv, self.col, tri)

    def centroids(self):
        return self.pos[self.tri].mean(1)


# Limits seen on every car of the game (31 cars): 18 shading groups, 9338 triangles, 11280 vertices
# and 589 KB per solid, 1000 triangles per group. A body with 59 groups and 38000 triangles crashes
# the game when the car loads, so every solid is kept under these:
MAX_SOLID_TRIS = 8500
MAX_GROUPS = 16
MAX_SOLID_VERTS = 11000
PART_TRIS = {'KIT00_FRONT_TIRE': 4500}  # drawn four times
LOD_SCALE = {'A': 1.0, 'B': 0.5, 'C': 0.3, 'D': 0.15, 'E': 0.08}
UNTEXTURED = {'paint', 'int_paint', 'roof_black', 'plastic', 'rubber', 'chrome', 'mirror',
              'int_g08', 'int_g12', 'int_g30', 'int_g45'}
# Plain textures. 256x128 like the textures that show: the game drew nothing with our 32x32 ones
# (in-game test, 11/10: the same white texture under three different names never showed, a
# 256x128 one of ours did). The game ignores the vertex colour, so the colour is in the texture.
PLAIN_SIZE = (256, 128)
GREYS = {}  # (plain textures of their own: none any more, the plain colours are patches of the atlas)
# interior texture: the cockpit picture on top (v 0..0.5), grey patches below (centre uv, grey)
# The shared texture (512x512, under the Lexus' IS300_INTERIOR name, the one texture of ours known to
# show in the game): cockpit picture top left, side skirt and details pictures top right, plain
# patches below (centre uv, grey). Every plain or textured part that is not paint, glass or a lamp
# goes through it.
ATLAS_SIZE = 512
ATLAS_IMAGES = {'interior': ((0.0, 0.0, 0.5, 0.5), 'INT_Cockpit_LR.dds'),
                'skirt': ((0.5, 0.0, 1.0, 0.25), 'EXT_Cup_Plastic.dds'),
                'details': ((0.5, 0.25, 1.0, 0.5), 'EXT_Details.dds')}
INTERIOR_PATCHES = {'int_g08': ((0.125, 0.625), 0.08), 'int_g12': ((0.375, 0.625), 0.12),
                    'int_g30': ((0.625, 0.625), 0.30), 'int_g45': ((0.875, 0.625), 0.45),
                    'plastic': ((0.125, 0.875), 0.05), 'chrome': ((0.375, 0.875), 0.60),
                    'mirror': ((0.625, 0.875), 0.40), 'white': ((0.875, 0.875), 1.0)}
PATCH_OF = {'roof_black': 'plastic', 'rubber': 'plastic'}


def grille_backing(pos, tri, nrm):
    """Black panels just behind the front grille, facing forward: three vertical strips, one in
    each of BODY, BASE and HOOD (in-game, the one in BODY alone did not show)."""
    c0 = pos[tri].mean(1) - SHIFT
    mouth = (np.abs(c0[:, 1]) < 0.45) & (c0[:, 2] > 0.15) & (c0[:, 2] < 0.48)
    p = pos[np.unique(tri[mouth])]
    x = p[:, 0].min() - 0.01
    (y0, z0), (y1, z1) = p[:, 1:].min(0), p[:, 1:].max(0)
    out = []
    for part, (a, b) in zip(('KIT00_BODY', 'BASE', 'KIT00_HOOD'), ((0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1))):
        ya, yb = y0 + (y1 - y0) * a, y0 + (y1 - y0) * b
        quad = np.array([[x, ya, z0], [x, yb, z0], [x, yb, z1], [x, ya, z1]], np.float32)
        n = np.tile(np.array([1, 0, 0], np.float32), (4, 1))
        out.append((part, Sub('plastic', quad, n, np.zeros((4, 2), np.float32), white(4, 0.03),
                              np.array([[0, 1, 2], [0, 2, 3]]))))
    return out


def atlas_uv(mat, uv):
    """UVs of a material in the shared texture (unchanged for the others)."""
    if mat in ATLAS_IMAGES:
        (u0, v0, u1, v1), _ = ATLAS_IMAGES[mat]
        c = np.clip(uv, 0, 1)
        return np.c_[u0 + (u1 - u0) * c[:, 0], v0 + (v1 - v0) * c[:, 1]].astype(uv.dtype)
    patch = PATCH_OF.get(mat, mat)
    if patch in INTERIOR_PATCHES:
        return np.tile(np.array(INTERIOR_PATCHES[patch][0], uv.dtype), (len(uv), 1))
    return uv


def merge(subs):
    """One Sub per material."""
    by = {}
    for sb in subs:
        by.setdefault(sb.mat, []).append(sb)
    out = []
    for mat, lst in by.items():
        base = 0
        pos, nrm, uv, col, tri = [], [], [], [], []
        for sb in lst:
            used = np.unique(sb.tri)
            remap = np.full(len(sb.pos), -1, np.int64)
            remap[used] = np.arange(len(used)) + base
            pos.append(sb.pos[used])
            nrm.append(sb.nrm[used])
            uv.append(sb.uv[used])
            col.append(sb.col[used])
            tri.append(remap[sb.tri])
            base += len(used)
        out.append(Sub(mat, np.concatenate(pos), np.concatenate(nrm), np.concatenate(uv),
                       np.concatenate(col), np.concatenate(tri)))
    return out


def reduce(sb, target):
    if len(sb.tri) <= target:
        return sb
    keys = np.c_[np.round(sb.pos, 5), np.round(sb.nrm, 1)]
    if sb.mat not in UNTEXTURED:
        keys = np.c_[keys, np.round(sb.uv, 4)]
    return sb.take_tris(qem.simplify(sb.pos, sb.tri, target, weld_keys=keys))


def budget(subs, total):
    """Triangle targets per material: at most `total` triangles and MAX_GROUPS groups."""
    n = np.array([len(sb.tri) for sb in subs], float)
    tgt = n.copy()
    if n.sum() > total:
        tgt = np.maximum(np.minimum(n, 40), np.floor(n * total / n.sum()))
    tgt = tgt.astype(int)
    while sum(-(-t // MAX_TRIS) for t in tgt) > MAX_GROUPS:
        i = int(np.argmax(tgt))
        tgt[i] = (-(-tgt[i] // MAX_TRIS) - 1) * MAX_TRIS
    return tgt


def make_lods(part, subs):
    """{LOD letter: [Sub]} within the limits."""
    a = merge(subs)
    cap = PART_TRIS.get(part, MAX_SOLID_TRIS)
    out = {}
    for lod, k in LOD_SCALE.items():
        src = a if lod == 'A' else out['A']
        total = int(cap * k) if lod == 'A' else max(12, int(sum(len(s.tri) for s in out['A']) * k))
        tg = budget(src, total)
        out[lod] = [r for r in (reduce(sb, t) for sb, t in zip(src, tg)) if len(r.tri)]
        nt = sum(len(r.tri) for r in out[lod])
        nv = sum(len(np.unique(r.tri)) for r in out[lod])
        ng = sum(-(-len(r.tri) // MAX_TRIS) for r in out[lod])
        assert nt <= 9000 and ng <= MAX_GROUPS and nv <= MAX_SOLID_VERTS, (part, lod, nt, ng, nv)
        if lod == 'A':
            print('%-28s %6d -> %5d tris, %2d groups, %5d verts' % (part, sum(len(s.tri) for s in subs), nt, ng, nv))
    return out


def to_nfs(p):
    return p[:, [2, 0, 1]] + SHIFT


class Sampler:
    def __init__(self, textures):
        self.t = textures
        self.cache = {}

    def img(self, name):
        if name not in self.cache:
            self.cache[name] = np.asarray(Image.open(io.BytesIO(self.t[name])).convert('RGBA'), np.float32)
        return self.cache[name]

    def ao(self, name, uv):
        a = self.img(name)
        hh, ww = a.shape[:2]
        x = np.clip((uv[:, 0] % 1.0) * ww, 0, ww - 1).astype(int)
        y = np.clip((uv[:, 1] % 1.0) * hh, 0, hh - 1).astype(int)
        rgb = a[y, x, :3]
        return rgb.mean(1) / 255.0


def gray(v, base=1.0, lo=0.0):
    v = np.clip(lo + (1 - lo) * v, 0, 1) * base
    c = (v * 255).astype(np.uint32)
    return (0xFF << 24) | (c << 16) | (c << 8) | c


def white(n, k=1.0):
    c = np.uint32(int(255 * k))
    return np.full(n, (0xFF << 24) | (c << 16) | (c << 8) | c, np.uint32)


# ---------------------------------------------------------------------------------------------
def collect(kn5_path):
    textures, materials, meshes, nodes = acmodel.load(kn5_path)
    S = Sampler(textures)
    parts = {}

    def add(part, sub):
        if len(sub.tri):
            parts.setdefault(part, []).append(sub)

    wheel_c = {k: to_nfs(nodes[k][3:4, :3])[0] for k in ('WHEEL_LF', 'WHEEL_RF', 'WHEEL_LR', 'WHEEL_RR')}

    for m in meshes:
        mat, path, name = m['mat']['name'], m['path'], m['name']
        if 'COCKPIT_HR' in path or mat in DROP_MATS or name.startswith('GEO_Shift'):
            continue
        pos, nrm, uv, tri = to_nfs(m['pos']), m['nrm'][:, [2, 0, 1]], m['uv'].copy(), m['tri']
        # AC stores V in [-1, 0]: shift by whole units into [0, 1] (the same texels with wrapping,
        # and right for clamped samplers too)
        uv -= np.floor(uv.min(0))
        n = len(pos)
        tx = m['mat']['tex'].get('txDiffuse', '')

        def sub(nm, col):
            return Sub(nm, pos, nrm, uv, col, tri)

        cent = pos[tri].mean(1)
        left = cent[:, 1] > 0
        # --- wheels and brakes (only the right-hand side models are used)
        if mat in ('EXT_Tyre', 'EXT_Rim', 'EXT_Loghi_CUP', 'EXT_Disc', 'EXT_Calipers', 'EXT_Details_CUP') \
                and ('WHEEL_' in path or 'DISC_' in path or 'SUSP_' in path):
            comp = next(c for c in path.split('/') if c.startswith(('WHEEL_', 'DISC_', 'SUSP_')))
            corner = comp.split('_')[1]
            if corner not in ('RF', 'RR'):
                continue
            c = wheel_c['WHEEL_' + corner]
            p = pos - c
            p[:, 1] += TIRE_Y
            if mat in ('EXT_Tyre', 'EXT_Rim', 'EXT_Loghi_CUP'):
                if corner != 'RF':
                    continue
                nm = {'EXT_Tyre': 'tyre', 'EXT_Rim': 'rim', 'EXT_Loghi_CUP': 'logo'}[mat]
                add('KIT00_FRONT_TIRE', Sub(nm, p, nrm, uv, white(n), tri))
            else:
                p[:, 1] -= BRAKE_MARKER_Y
                nm = {'EXT_Disc': 'disc', 'EXT_Calipers': 'caliper', 'EXT_Details_CUP': 'details'}[mat]
                col = white(n)
                add('KIT00_FRONT_BRAKE' if corner == 'RF' else 'KIT00_REAR_BRAKE',
                    Sub(nm, p, nrm, uv, col, tri))
            continue
        # --- interior
        if 'COCKPIT_LR' in path or mat in ('INT_SeatBelts', 'INT_Grid_Rear'):
            if mat == 'INT_LR_carpaint':
                add('KIT00_INTERIOR', sub('int_paint', gray(S.ao(tx, uv), lo=0.3)))
            elif mat == 'Mirror':
                add('KIT00_INTERIOR', sub('mirror', white(n, 0.2)))
            elif mat == 'INT_LR':
                add('KIT00_INTERIOR', sub('interior', white(n)))
            else:
                add('KIT00_INTERIOR', sub('int_g12', white(n)))
            continue
        if name.startswith('HardTop_'):
            if mat == 'EXT_Carpaint_Roof':
                ao = S.ao('AO_Roof.dds', uv)
                # black roof panels above the cabin, body-coloured buttresses behind
                c0 = cent - SHIFT  # thresholds in the model's own frame
                black = (c0[:, 0] > -0.80) & (c0[:, 2] > 1.08)
                add('BASE', sub('paint', gray(ao, lo=0.35)).take(~black))
                if not OPEN_TOP:  # open: the roof panels are stowed behind the seats
                    add('BASE', sub('roof_black', gray(ao, 0.06, lo=0.5)).take(black))
            elif OPEN_TOP:
                continue  # the roof panels' frame, details and lining go with them
            elif mat == 'EXT_Plastic_Black_Roof':
                add('BASE', sub('plastic', gray(S.ao('AO_Roof.dds', uv), 0.16, lo=0.4)))
            elif mat == 'EXT_Details':
                add('BASE', sub('details', white(n)))
            elif 'INT_OCC_Rubber' in name:
                continue  # roof seals, hidden when the roof is closed
            else:  # fabric, grey skin: inside the roof
                k = 0.45 if 'Fabric' in name else (0.3 if 'Skin' in name else 0.08)
                mat = 'int_g45' if 'Fabric' in name else ('int_g30' if 'Skin' in name else 'int_g08')
                add('KIT00_INTERIOR', sub(mat, gray(S.ao('AO_Roof.dds', uv), lo=0.4)))
            continue
        # --- exterior
        if mat == 'EXT_Carpaint':
            col = gray(S.ao('Skin_00.dds', uv), lo=0.3)
            if name == 'GEO_Hood_SUB0':
                add('KIT00_HOOD', sub('paint', col))
            elif 'BUMPER' in path:
                add('BASE', sub('paint', col))
            else:
                add('KIT00_BODY', sub('paint', col))
        elif mat in ('EXT_Plastic_Black',):
            col = gray(S.ao('Skin_00.dds', uv), 0.14, lo=0.4)
            if name == 'polymsh16_SUB1':
                # the grille is open mesh with nothing behind it (no radiator): close the mouth
                for part, sb in grille_backing(pos, tri, nrm):
                    add(part, sb)
            if name in ('GEO_Door_L_SUB1', 'GEO_Door_R_SUB1'):
                add('KIT00_LEFT_SIDE_MIRROR' if 'Door_L' in name else 'KIT00_RIGHT_SIDE_MIRROR', sub('plastic', col))
            else:
                add('KIT00_BODY', sub('plastic', col))
        elif mat == 'EXT_Rubber':
            add('KIT00_BODY', sub('rubber', gray(S.ao('Skin_00.dds', uv), 0.08, lo=0.4)))
        elif mat == 'EXT_Skirt_PLASTIC':
            add('KIT00_BODY', sub('skirt', white(n, 0.22)))
        elif mat == 'EXT_Details':
            add('KIT00_HOOD' if name == 'GEO_Hood_SUB1' else 'KIT00_BODY', sub('details', white(n)))
        elif mat == 'EXT_Chrome':
            add('KIT00_BODY', sub('chrome', white(n, 0.75)))
        elif mat == 'EXT_Calipers':  # duplicate calipers fixed to the body: the wheels have their own
            continue
        elif mat == 'EXT_PLATE_plastic':
            add('KIT00_BODY', sub('plate', white(n)))
        elif mat == 'Mirror':
            add('KIT00_LEFT_SIDE_MIRROR' if 'Door_L' in path else 'KIT00_RIGHT_SIDE_MIRROR', sub('mirror', white(n, 0.2)))
        elif mat in ('EXT_Lights_Chrome', 'EXT_Lights_Plastic'):
            s_ = sub('x', white(n))
            front = cent[:, 0] > 1.2
            rear = cent[:, 0] < -1.3
            mid = ~front & ~rear
            hl = 'hl' if mat == 'EXT_Lights_Chrome' else 'hlp'
            add('KIT00_LEFT_HEADLIGHT', Sub(hl + '_L', pos, nrm, uv, s_.col, tri[front & left]))
            add('KIT00_RIGHT_HEADLIGHT', Sub(hl + '_R', pos, nrm, uv, s_.col, tri[front & ~left]))
            add('KIT00_LEFT_BRAKELIGHT', Sub('bl_L', pos, nrm, uv, s_.col, tri[rear & left]))
            add('KIT00_RIGHT_BRAKELIGHT', Sub('bl_R', pos, nrm, uv, s_.col, tri[rear & ~left]))
            add('KIT00_BODY', Sub('lights_ext', pos, nrm, uv, s_.col, tri[mid]))
        elif mat in ('EXT_Glass', 'EXT_Glass_flat', 'EXT_Glass_rear_Light'):
            col = white(n)
            if mat == 'EXT_Glass_flat':
                add('KIT00_FRONT_WINDOW', sub('glass', col))
                continue
            if mat == 'EXT_Glass_rear_Light':
                continue  # the lamp texture already has the red lenses
            front = cent[:, 0] > 1.2
            rear = cent[:, 0] < -1.6
            side = ~front & ~rear & (np.abs(cent[:, 1]) > 0.5) & (cent[:, 0] > -0.75)
            back = ~front & ~rear & ~side
            if name.startswith('polymsh_extracted1'):  # door glass
                if not OPEN_TOP:  # open: the windows are down
                    add('KIT00_FRONT_LEFT_WINDOW' if 'Door_L' in path else 'KIT00_FRONT_RIGHT_WINDOW',
                        sub('glass', col))
                continue
            add('KIT00_LEFT_HEADLIGHT_GLASS', Sub('hlg_L', pos, nrm, uv, col, tri[front & left]))
            add('KIT00_RIGHT_HEADLIGHT_GLASS', Sub('hlg_R', pos, nrm, uv, col, tri[front & ~left]))
            if not OPEN_TOP:  # open: side windows down, rear window stowed with the roof
                add('KIT00_FRONT_LEFT_WINDOW', Sub('glass', pos, nrm, uv, col, tri[side & left]))
                add('KIT00_FRONT_RIGHT_WINDOW', Sub('glass', pos, nrm, uv, col, tri[side & ~left]))
                add('KIT00_REAR_WINDOW', Sub('glass', pos, nrm, uv, col, tri[back]))
        elif mat == 'INT_Grid_Rear':
            add('KIT00_INTERIOR', sub('int_g08', white(n)))
        else:
            print('unassigned', name, mat, len(tri))
    return textures, parts, wheel_c


# ---------------------------------------------------------------------------------------------
def build_textures(textures):
    """Our textures as (name, PIL image, fmt)."""
    def img(name):
        # alpha is gloss in Assetto Corsa, not transparency: drop it before any resize (Pillow
        # premultiplies, and an alpha of 0 turned the cockpit, skirt and rim pictures black)
        im = Image.open(io.BytesIO(textures[name])).convert('RGB').convert('RGBA')
        return im

    def fit(im, size):
        return im.resize(size, Image.LANCZOS)

    out = []
    for g, k in GREYS.items():
        v = int(round(255 * k))
        out.append(('{car}_MX5_' + g, Image.new('RGBA', PLAIN_SIZE, (v, v, v, 255)), 'DXT1'))
    lights = fit(img('EXT_Lights.dds'), (256, 128))
    out.append(('{car}_MX5_LIGHTS', lights, 'DXT1'))
    # generic light textures: HEADLIGHT_* -> <car>_KIT00_HEADLIGHT_OFF/ON, BRAKELIGHT_* -> _BRAKELIGHT_OFF/ON
    on_head = ImageEnhance.Brightness(lights).enhance(1.6)
    out.append((CAR + '_KIT00_HEADLIGHT_OFF', lights, 'DXT1'))
    out.append((CAR + '_KIT00_HEADLIGHT_ON', on_head, 'DXT1'))
    a = np.asarray(lights).astype(np.float32)
    red = a[..., 0] > a[..., 1] * 1.6
    b = a.copy()
    b[red, 0] = np.minimum(255, a[red, 0] * 1.5 + 60)
    b[red, 1] = np.minimum(255, a[red, 1] * 1.2 + 25)
    b[red, 2] = np.minimum(255, a[red, 2] * 1.2 + 25)
    out.append((CAR + '_KIT00_BRAKELIGHT_OFF', lights, 'DXT1'))
    out.append((CAR + '_KIT00_BRAKELIGHT_ON', Image.fromarray(b.clip(0, 255).astype(np.uint8)), 'DXT1'))
    glass = Image.new('RGBA', (32, 32), (235, 240, 250, 70))
    out.append((CAR + '_KIT00_HEADLIGHT_GLASS_OFF', glass, 'DXT5'))
    out.append((CAR + '_KIT00_HEADLIGHT_GLASS_ON', glass, 'DXT5'))
    tyre = img('Tyre_D.dds')
    out.append(('{car}_MX5_TYRE', fit(tyre, (256, 256)), 'DXT1'))
    rim = np.asarray(fit(img('EXT_Rims.dds'), (256, 128))).astype(np.float32)
    rim[..., :3] = rim[..., :3] * 0.30 + 8  # dark gunmetal like the photo
    out.append(('{car}_MX5_RIM', Image.fromarray(rim.clip(0, 255).astype(np.uint8)), 'DXT1'))
    out.append(('{car}_MX5_LOGO', fit(img('EXT_Loghi.dds'), (128, 128)), 'DXT1'))
    out.append(('{car}_MX5_DISC', fit(img('EXT_Disc.dds'), (128, 128)), 'DXT1'))
    out.append(('{car}_MX5_CALIPER', fit(img('EXT_Caliper.dds'), (256, 128)), 'DXT1'))
    n = ATLAS_SIZE
    atlas = Image.new('RGBA', (n, n), (0, 0, 0, 255))
    for (u0, v0, u1, v1), picture in ATLAS_IMAGES.values():
        box = (int(u0 * n), int(v0 * n), int(u1 * n), int(v1 * n))
        atlas.paste(fit(img(picture), (box[2] - box[0], box[3] - box[1])), box[:2])
    for (u, v), k in INTERIOR_PATCHES.values():
        g = int(round(255 * k))
        atlas.paste((g, g, g, 255), (int(u * n) - 60, int(v * n) - 60, int(u * n) + 60, int(v * n) + 60))
    out.append(('{car}_INTERIOR', atlas, 'DXT1'))
    return [(nm.format(car=CAR), im, fmt) for nm, im, fmt in out]


# ---------------------------------------------------------------------------------------------
def encode_group(pos, nrm, uv, col):
    n = len(pos)
    a = np.zeros(n, dtype=np.dtype([('p', '>f4', 3), ('uv', '>f4', 2), ('c', '>u4'), ('n', '>i2', 4)]))
    a['p'] = pos
    a['uv'] = uv
    a['c'] = col
    nn = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    a['n'][:, :3] = np.round(nn * 32767).astype(np.int16)
    a['n'][:, 3] = 32767
    return a.tobytes()


OPEN_TOP = False  # --top open: roof panels and rear window stowed, windows down
SQUARES = bool(os.environ.get('MX5_SQUARES'))
# diagnostic rows above the hood: row n has n dots, all in one group of its own material
TEST_ROWS = ['paint', 'tx_white', 'tx_white_e6', 'tx_white_19', 'plate', 'tx_interior', 'tx_misc', 'tx_hl_on']


def add_test_squares(hood_lods):
    """Diagnostic: a board standing 35 cm in front of the bumper, facing forward, rows of squares
    from the bottom (row 1 = 1 square) to the top (row 8 = 8 squares), one group per row."""
    subs = hood_lods['A']  # the garage shows LOD A
    p = np.concatenate([sb.pos for sb in subs])
    x = p[:, 0].max() + 0.35
    for row, mat in enumerate(TEST_ROWS):
        n_dots = row + 1
        z = 0.10 + 0.13 * row
        quads, tris = [], []
        for k in range(n_dots):
            y = (k - (n_dots - 1) / 2) * 0.12
            h = 0.045
            base = len(quads) * 4
            quads.append([[x, y - h, z - h], [x, y + h, z - h], [x, y + h, z + h], [x, y - h, z + h]])
            tris += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
        q = np.array(quads, np.float32).reshape(-1, 3)
        n = np.tile(np.array([1, 0, 0], np.float32), (len(q), 1))
        uv = np.tile(np.array([[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]], np.float32), (n_dots, 1))
        subs.append(Sub(mat, q, n, uv, white(len(q)), np.array(tris)))


DIAG = bool(os.environ.get('MX5_DIAG'))
DIAG_COLOURS = [('rouge', (255, 0, 0)), ('vert', (0, 220, 0)), ('jaune', (255, 230, 0)),
                ('cyan', (0, 230, 255)), ('magenta', (255, 0, 255)), ('orange', (255, 120, 0)),
                ('blanc', (255, 255, 255)), ('violet', (130, 0, 255)), ('rose', (255, 140, 200)),
                ('marron', (120, 60, 20)), ('bleuclair', (120, 160, 255)), ('kaki', (130, 140, 40))]
DIAG_LOG = []


def build_solid(tmpl, name, subs, markers=None):
    """Solid dict for geo360.write from a template solid (same name) and our geometry."""
    tex, lm, groups, vbseq, ib = [], [], [], [], []
    first = 0
    npolys = nverts = 0
    flags_or = 0
    allmin, allmax = np.full(3, 1e9), np.full(3, -1e9)
    for sb in subs:
        lmn, txn, flags, key = MATS[sb.mat]
        txn = txn.format(car=CAR)
        opn = OPACITY[sb.mat].format(car=CAR) if sb.mat in OPACITY else None
        if H(lmn) not in lm:
            lm.append(H(lmn))
        for nm in (txn, opn) if opn else (txn,):
            if TH(nm) not in tex:
                tex.append(TH(nm))
        li, ti = lm.index(H(lmn)), tex.index(TH(txn))
        oi = tex.index(TH(opn)) if opn else ti
        for k in range(0, len(sb.tri), MAX_TRIS):
            t = sb.tri[k:k + MAX_TRIS]
            used, inv = np.unique(t.reshape(-1), return_inverse=True)
            lt = inv.reshape(-1, 3).astype('>u2')
            p = sb.pos[used]
            col = sb.col[used]
            guv = atlas_uv(sb.mat, sb.uv[used])
            if DIAG and lmn == 'DULLPLASTIC':
                # diagnostic: one vivid colour per group, to see in the game which groups are drawn
                cname, rgb = DIAG_COLOURS[len(groups) % len(DIAG_COLOURS)]
                col = np.full(len(used), 0xFF000000 | (rgb[0] << 16) | (rgb[1] << 8) | rgb[2], np.uint32)
                DIAG_LOG.append('%-30s groupe %2d  %-8s %-10s %5d triangles  x %.2f..%.2f  z %.2f..%.2f'
                                % (name, len(groups), cname, sb.mat, len(t), p[:, 0].min(), p[:, 0].max(),
                                   p[:, 2].min(), p[:, 2].max()))
            vb = encode_group(p, sb.nrm[used], guv, col)
            mn, mx = p.min(0), p.max(0)
            allmin, allmax = np.minimum(allmin, mn), np.maximum(allmax, mx)
            raw = bytearray(256)
            struct.pack_into('<6f', raw, 0, *mn, *mx)
            struct.pack_into('<IIII', raw, 0x18, first, 7, key, flags)
            struct.pack_into('<H', raw, 0x28, len(t) * 3)
            raw[0x2A:0x30] = bytes([li, ti, ti, ti, ti, oi])
            struct.pack_into('<I', raw, 0x58, len(vb))
            raw[0x5C:0x60] = bytes([0, 0, 0x20, 0x80])
            groups.append({'raw': bytes(raw)})
            vbseq += [('C02', b''), ('B01', vb)]
            ib.append(lt.tobytes())
            first += len(t) * 3
            npolys += len(t)
            nverts += len(used)
            flags_or |= flags
    assert npolys < 65536, (name, npolys)
    hdr = bytearray(tmpl['header'])
    struct.pack_into('<H', hdr, 0x14, npolys)
    struct.pack_into('<H', hdr, 0x16, 0)
    hdr[0x18], hdr[0x19], hdr[0x1A], hdr[0x1B] = 0, len(tex), len(lm), 0
    struct.pack_into('<3f', hdr, 0x20, *allmin)
    struct.pack_into('<3f', hdr, 0x30, *allmax)
    desc = bytearray(tmpl['desc'])
    struct.pack_into('<I', desc, 3 * 4, flags_or)
    struct.pack_into('<I', desc, 4 * 4, len(groups))
    struct.pack_into('<I', desc, 13 * 4, npolys)
    struct.pack_into('<I', desc, 15 * 4, nverts)
    extra = [(cid, pl) for cid, pl in tmpl['extra'] if cid == 0x13401A]
    if markers is not None:
        extra = [(0x13401A, markers)] if markers else []
    return {'name': name, 'header': bytes(hdr), 'tex': tex, 'lm': lm, 'extra': extra, 'post': [],
            'desc': bytes(desc), 'groups': groups, 'vbseq': vbseq, 'ib': b''.join(ib), 'c02': []}


def degenerate(tmpl):
    """A solid with one zero-area triangle (keeps the slot valid, draws nothing)."""
    s = Sub('plastic', np.zeros((3, 3), np.float32), np.tile([0, 0, 1.0], (3, 1)), np.zeros((3, 2), np.float32),
            white(3), np.array([[0, 1, 2]]))
    return build_solid(tmpl, tmpl['name'], [s], markers=b'')


# the Elise driver moved into the MX-5 seat, measured with the Elise placement of the MX-5
DRIVER_OFFSET_ELISE = (-0.30, 0.06, 0.22)
ELISE_SHIFT = np.array([-0.0715, 0.0, 0.012])


def move_solid(s, off):
    """Copy of an original solid with every vertex moved by `off` (32-byte vertices only)."""
    groups = [g['raw'] for g in s['groups']]
    off = np.asarray(off, np.float32)
    vbseq = []
    gi = 0
    for kind, data in s['vbseq']:
        if kind == 'B01':
            typ, = struct.unpack_from('<I', groups[gi], 0x1C)
            size, = struct.unpack_from('<I', groups[gi], 0x58)
            assert typ == 7 and len(data) == size, (s['name'], typ, len(data), size)
            a = np.frombuffer(data, dtype=np.dtype([('p', '>f4', 3), ('rest', 'V20')])).copy()
            a['p'] += off
            data = a.tobytes()
            gi += 1
        vbseq.append((kind, data))
    hdr = bytearray(s['header'])
    for o in (0x20, 0x30):
        v = np.array(struct.unpack_from('<3f', hdr, o)) + off
        struct.pack_into('<3f', hdr, o, *v)
    new_groups = []
    for g in groups:
        r = bytearray(g)
        v = np.array(struct.unpack_from('<6f', r, 0)) + np.r_[off, off]
        struct.pack_into('<6f', r, 0, *v)
        new_groups.append({'raw': bytes(r)})
    return dict(s, header=bytes(hdr), vbseq=vbseq, groups=new_groups, post=[])


def pad_to(data, size, geometry=False):
    """Grow a chunk file to exactly `size` bytes with a trailing zero chunk."""
    if geometry:
        # the geometry pack already ends with a zero chunk: drop it, then add one of the right size
        top = struct.unpack_from('<I', data, 4)[0] + 8
        data = data[:top]
    if len(data) > size - 8:
        raise SystemExit('file is %d bytes, more than the %d of the original: reduce it' % (len(data), size))
    out = bytearray(data + struct.pack('<II', 0, size - len(data) - 8) + b'\0' * (size - len(data) - 8))
    if geometry:
        struct.pack_into('<I', out, 0x20 + 26 * 4, size)
    return bytes(out)


def marker_bytes(items):
    out = b''
    for nm, pos in items:
        M = np.eye(4, dtype=np.float32)
        M[3, :3] = pos
        out += struct.pack('<IiII', H(nm), 0, 0, 0) + M.astype('<f4').tobytes()
    return out


def patch_markers(payload, moves):
    """Move markers of an Elise payload: moves {name: new position}."""
    b = bytearray(payload)
    for o in range(0, len(b) - 0x4F, 0x50):
        h, = struct.unpack_from('<I', b, o)
        for nm, p in moves.items():
            if h == H(nm):
                struct.pack_into('<3f', b, o + 0x10 + 48, *p)
    return bytes(b)


class Source:
    """Game files: from `base_root` (an installed game_root with NFS/ZDIR.BIN, e.g. with the French
    dub) when it has them, else from the disc image."""

    def __init__(self, iso, base_root=None):
        self.disc = zzdata.Disc(iso)
        self.root = base_root
        self.zdir = {}
        if base_root and os.path.exists(os.path.join(base_root, 'NFS', 'ZDIR.BIN')):
            z = open(os.path.join(base_root, 'NFS', 'ZDIR.BIN'), 'rb').read()
            for i in range(0, len(z) - 23, 24):
                h, number, sector, _, length, _ = struct.unpack_from('<6I', z, i)
                self.zdir[h] = (number, sector, length)

    def read(self, name):
        e = self.zdir.get(zzdata.bstringhash(name))
        if e:
            number, sector, length = e
            arch = os.path.join(self.root, 'NFS', 'ZZDATA%d.BIN' % number)
            if os.path.exists(arch):
                with open(arch, 'rb') as f:
                    f.seek(sector * zzdata.SECTOR)
                    return f.read(length)
            _, base = self.disc.files['NFS/ZZDATA%d.BIN' % number]
            with open(self.disc.iso, 'rb') as f:
                f.seek(base + sector * zzdata.SECTOR)
                return f.read(length)
        return self.disc.read(name)


def tire_offsets(att, car):
    """(offset of ecar/<car> TireOffsets in ATTRIBUTES.BIN, 4 x (x, y, z, radius): FL, FR, RR, RL)"""
    cols = attrib360.Pack(att).collections()
    lay = cols.get((attrib360.key('ecar'), attrib360.key(car.lower())))
    if lay is None:
        raise SystemExit('no ecar collection for %s' % car)
    off = lay + 0x10  # after the 16-byte aligned array header
    v = np.array(struct.unpack_from('>16f', att, off)).reshape(4, 4)
    assert v[0, 0] > 0 and v[2, 0] < 0 and v[0, 3] > 0.2, v
    return off, v


# Performance of the MX-5 RF (ND2, 2.0 Skyactiv-G 184 ch, manual), in the game's units (fields of the
# replaced car's engine/transmission/pvehicle/chassis collections in ATTRIBUTES.BIN).
# - TORQUE: 9 points from IDLE to MAX_RPM. The game's torque is not the real one (IS300 235 for
#   294 Nm, Elise 149 for 172 Nm, RX-8 192 for 211 Nm): 205 Nm -> 176 at the peak, about the mean
#   of those ratios, with the shape of the real curve (205 Nm at 4000 rpm, 184 ch at 7000 rpm).
# - RED_LINE / MAX_RPM: 7500 rpm, the game's cars keep 1000 rpm above the red line.
# - GEAR_RATIO: reverse, neutral, then the six forward gears of the ND 2.0 SKYACTIV-MT; FINAL_GEAR.
# - DIFFERENTIAL: limited slip (the RF 2.0 has one), like the Elise's.
# - MASS: 1125 kg; DRAG_COEFFICIENT 0.33.
PERFORMANCE = {
    'rf184': {
        ('engine', 'TORQUE'): [121, 151, 166, 175, 176, 172, 164, 151, 129],
        ('engine', 'RED_LINE'): 7500.0,
        ('engine', 'MAX_RPM'): 8500.0,
        ('engine', 'FLYWHEEL_MASS'): 10.0,
        ('transmission', 'GEAR_RATIO'): [3.603, 0.0, 3.709, 2.190, 1.536, 1.177, 1.000, 0.832],
        ('transmission', 'FINAL_GEAR'): 3.454,
        ('transmission', 'DIFFERENTIAL'): [0.8, 0.8, 0.0],
        ('pvehicle', 'MASS'): 1125.0,
        ('chassis', 'DRAG_COEFFICIENT'): 0.33,
    },
}

# Engine sounds: engineaudio collections of ATTRIBUTES.BIN. 'miata' is the game's own Mazda Miata
# recording (GIN_Mazda_Miata.gin + _DCL, 1510-7158 rpm), which no car of the game uses.
ENGINE_SOUNDS = {'miata': 0x05725DDF}

MX5_ARCH_GAP = 0.029  # MX-5: wheel arch top - (wheel centre + radius), measured on the AC model


def wheel_centre_height(geo, offs):
    """Height of the wheel centres in the car's body frame, from its own wheel arches: lowest outer
    body point above each wheel, minus the radius and a 3 cm gap. (The game does not put them at
    z = radius: on the IS300 the arches are at 0.47 m for 0.32 m wheels.)"""
    body = next(s for s in solids.parse(geo) if s['name'] == '%s_KIT00_BODY_A' % CAR)
    P = np.concatenate([p for g, p, uv, c, n, t in sol360.decode(geo, body) if g['typ'] == 7])
    ymax = np.abs(P[:, 1]).max()
    tops = []
    for wx in (offs[0, 0], offs[2, 0]):
        m = (np.abs(P[:, 0] - wx) < 0.04) & (np.abs(P[:, 1]) > ymax - 0.12) & (P[:, 2] > 0.0)
        tops.append(P[m, 2].min())
    return float(np.mean(tops)) - offs[0, 3] - MX5_ARCH_GAP


def place_wheels(offs, tire_min_y, mode, centre_z):
    """Set SHIFT and TIRE_Y. Returns the TireOffsets (4x4) to write, or None to keep the car's."""
    global SHIFT, TIRE_Y
    fx, fy, rx, ry, r = offs[0, 0], abs(offs[0, 1]), offs[2, 0], abs(offs[2, 1]), offs[0, 3]
    wb_car, wb_mx5 = fx - rx, MX5_FRONT[0] - MX5_REAR[0]
    if mode == 'auto':
        mode = 'keep' if abs(wb_car - wb_mx5) < 0.03 else 'patch'
    mid_car, mid_mx5 = (fx + rx) / 2, (MX5_FRONT[0] + MX5_REAR[0]) / 2
    if mode == 'keep':
        # the MX-5 goes where the car's wheels are
        SHIFT = np.array([mid_car - mid_mx5, 0.0, centre_z - MX5_WHEEL_Z])
        TIRE_Y = ((fy - MX5_FRONT[1]) + (ry - MX5_REAR[1])) / 2
        print('wheels: kept (wheelbase %.3f m for %.3f m)' % (wb_car, wb_mx5))
        return None
    # the car's wheels move to the MX-5 ones; the MX-5 is centred on the car's axles
    SHIFT = np.array([mid_car - mid_mx5, 0.0, centre_z - MX5_WHEEL_Z])
    TIRE_Y = tire_min_y + MX5_TYRE_HALF_WIDTH
    new = offs.copy()
    for i, (x, y) in enumerate((MX5_FRONT, MX5_FRONT, MX5_REAR, MX5_REAR)):
        sign = 1 if i in (0, 3) else -1
        new[i] = (x + SHIFT[0], sign * (y + TIRE_Y), 0.0, MX5_RADIUS)
    print('wheels: moved, wheelbase %.3f -> %.3f m' % (wb_car, wb_mx5))
    return new


# texture classes (TextureInfo ClassNameHash) of the game's car packs
CLASS_DIFFUSE = 0x001A93CF  # interior, misc, badging, glass
CLASS_SWAP = 0x1B81E7B0     # tyre and the lamp textures the game swaps (headlight / brakelight on, off)
CLASS_NORMAL = 0x1DA6C8A6   # normal maps: never for ours


def texture_template(etex, name, fmt):
    """The car's own texture to copy a TextureInfo from: same format, and the class the game's cars
    give to that kind of texture."""
    comp = 0x22 if fmt == 'DXT1' else 0x26
    swap = any(k in name for k in ('_TYRE', '_RIM', 'HEADLIGHT_O', 'BRAKELIGHT_O', '_LOGO', '_DISC', '_CALIPER'))
    want = CLASS_SWAP if swap and fmt == 'DXT1' else CLASS_DIFFUSE
    for cls in (want, CLASS_DIFFUSE, CLASS_SWAP):
        for t in etex:
            if t['comp'] == comp and struct.unpack_from('<I', t['info'], 0x28)[0] == cls:
                return t
    raise SystemExit('no %s texture of class %08X in the car pack' % (fmt, want))


def rename_solid(s, name):
    hdr = bytearray(s['header'])
    struct.pack_into('<I', hdr, 0x10, H(name))
    return dict(s, name=name, header=bytes(hdr))


def main(iso, kn5_path, out, car='ELISE', base_root=None, wheels='auto', only=None, keep=(),
         mx5_wheels=False, perf='rf184', top='closed', sound='miata'):
    global CAR, BRAKE_MARKER_Y, OPEN_TOP
    OPEN_TOP = top == 'open'
    if not mx5_wheels:
        # the game does not draw the MX-5 rims and brakes yet: keep the car's own
        keep = tuple(keep) + ('KIT00_FRONT_TIRE', 'KIT00_FRONT_BRAKE', 'KIT00_REAR_BRAKE')
    CAR = car.upper()
    src = Source(iso, base_root)
    geo_name = zzdata.path('CARS', CAR, 'GEOMETRY.BIN')
    tex_name = zzdata.path('CARS', CAR, 'TEXTURES.BIN')
    ph, esols = geo360.read(src.read(geo_name))
    by = {s['name']: s for s in esols}
    # wheels: ecar TireOffsets of the car (in the preloaded GLOBALMEMORYFILE.BIN), its tyre model
    gm = src.read(zzdata.path('GLOBAL', 'GLOBALMEMORYFILE.BIN'))
    att_entry = None
    cnt, = struct.unpack_from('<I', gm, 12)
    for i in range(cnt):
        h, off, msize, ssize, flags = struct.unpack_from('<5I', gm, 16 + i * 20)
        if h == zzdata.bstringhash(zzdata.path('GLOBAL', 'ATTRIBUTES.BIN')):
            assert msize == ssize, 'ATTRIBUTES.BIN is compressed in the pack'
            att_entry = (off, ssize)
    att = gm[att_entry[0]:att_entry[0] + att_entry[1]]
    toff, offs = tire_offsets(att, CAR)
    tire = by['%s_KIT00_FRONT_TIRE_A' % CAR]
    tire_min_y = struct.unpack_from('<3f', tire['header'], 0x20)[1]
    for cid, pl in tire['extra']:
        if cid == 0x13401A:
            BRAKE_MARKER_Y = struct.unpack_from('<f', pl, 0x10 + 52)[0]
    centre_z = wheel_centre_height(src.read(geo_name), offs)
    new_offs = place_wheels(offs, tire_min_y, wheels, centre_z)
    print('wheel centres at z %.3f in the body frame' % centre_z)
    print('SHIFT', np.round(SHIFT, 4), 'TIRE_Y %.3f' % TIRE_Y, 'brake marker y %.3f' % BRAKE_MARKER_Y)

    textures, parts, wheel_c = collect(kn5_path)
    # position markers (lights, exhausts) on the MX-5, in the AC model's frame (NFS axes)
    base_moves = {nm: tuple(np.add(p, SHIFT)) for nm, p in {
        'LEFT_HEADLIGHT': (1.672, 0.62, 0.578), 'RIGHT_HEADLIGHT': (1.672, -0.62, 0.578),
        'LEFT_BRAKELIGHT': (-1.789, 0.60, 0.728), 'RIGHT_BRAKELIGHT': (-1.789, -0.60, 0.728),
        'LEFT_REVERSE': (-1.789, 0.45, 0.718), 'RIGHT_REVERSE': (-1.789, -0.45, 0.718),
        'ROOF_SCOOP': (-0.379, 0.0, 1.228), 'SPOILER': (-1.729, 0.0, 0.918),
        'SPOILER2': (-1.829, 0.0, 0.918)}.items()}
    exhaust = marker_bytes([(nm, tuple(np.add(p, SHIFT))) for nm, p in (
        ('LEFT_EXHAUST', (-1.909, 0.33, 0.238)), ('RIGHT_EXHAUST', (-1.909, -0.33, 0.238)),
        ('LEFT_REVERSE', (-1.789, 0.45, 0.718)), ('RIGHT_REVERSE', (-1.789, -0.45, 0.718)))])
    if only:
        parts = {k: v for k, v in parts.items() if k in only}
    parts = {k: v for k, v in parts.items() if k not in keep}
    lods = {part: make_lods(part, subs) for part, subs in parts.items()}
    clean = {part: {lod: list(subs) for lod, subs in d.items()} for part, d in lods.items()}
    if SQUARES and 'KIT00_HOOD' in lods:
        add_test_squares(lods['KIT00_HOOD'])  # the stock hood only
    new = {}
    for part in parts:
        for lod in 'ABCDE':
            nm = '%s_%s_%s' % (CAR, part, lod)
            if nm not in by:
                continue
            t = by[nm]
            mk = None
            ex = [pl for cid, pl in t['extra'] if cid == 0x13401A]
            if part == 'BASE' and ex:
                mk = patch_markers(ex[0], base_moves)
            elif part == 'KIT00_BODY':
                mk = exhaust
            new[nm] = build_solid(t, nm, lods[part][lod], markers=mk)
    if not only:
        # tuning parts the MX-5 does not have (body kits KIT01-04, hood styles): our own body and hood,
        # one level of detail lower to fit in the file. Left empty, the car lost its body or hood as
        # soon as one was bought (the hood went transparent in the shop).
        down = {'A': 'B', 'B': 'C', 'C': 'D', 'D': 'E', 'E': 'E'}
        for s in esols:
            nm = s['name']
            rest = nm[len(CAR) + 1:]
            lod = rest[-1]
            for ours, pattern in (('KIT00_BODY', ('KIT01_BODY_', 'KIT02_BODY_', 'KIT03_BODY_', 'KIT04_BODY_')),
                                  ('KIT00_HOOD', ('_HOOD_',))):
                if ours in clean and rest[:-1].endswith(pattern) and not rest.startswith('KIT00')                         and clean[ours].get(down[lod]):
                    if ours == 'KIT00_HOOD' and (SQUARES or not rest.startswith('STYLE')):
                        continue  # (the diagnostic build needs the room)
                    new[nm] = build_solid(s, nm, clean[ours][down[lod]],
                                          markers=exhaust if ours == 'KIT00_BODY' else None)
        # the driver: the Elise one (low seating, fits the roadster), moved into the MX-5 seat
        edisc = geo360.read(src.read(zzdata.path('CARS', 'ELISE', 'GEOMETRY.BIN')))[1]
        drivers = {s['name'][len('ELISE_'):]: s for s in edisc if 'DRIVER' in s['name']}
        doff = np.add(DRIVER_OFFSET_ELISE, SHIFT - ELISE_SHIFT)
        for s in esols:
            rest = s['name'][len(CAR) + 1:]
            if 'DRIVER' in rest and rest in drivers:
                new[s['name']] = rename_solid(move_solid(drivers[rest], doff), s['name'])
        # every other part (body kits, hood styles, damage pieces, rear windows...): empty
        for s in esols:
            nm = s['name']
            if nm not in new and 'DECAL' not in nm and not any('_%s_' % k in nm for k in keep):
                new[nm] = degenerate(s)
    sols = [new.get(s['name'], s) for s in esols]
    geo = geo360.write(ph, sols)
    # loose files are read with the size of the game's own file (ZDIR.BIN): give them exactly that size
    geo = pad_to(geo, len(src.read(geo_name)), geometry=True)
    cdir = os.path.join(out, 'CARS', CAR)
    os.makedirs(cdir, exist_ok=True)
    open(os.path.join(cdir, 'GEOMETRY.BIN'), 'wb').write(geo)

    ed = src.read(tex_name)
    etex = tpk.read(ed)
    ours = [tpk360.make_texture(nm, im, fmt, texture_template(etex, nm, fmt))
            for nm, im, fmt in build_textures(textures)]
    if SQUARES:
        # the white texture again under two hashes of the Lexus pack (its badging textures)
        white = next(t for t in ours if t['name'] == CAR + '_MX5_WHITE')
        for h in (0xE6A7115A, 0x19F11092):
            info = bytearray(white['info'])
            struct.pack_into('<I', info, 0x24, h)
            ours.append(dict(white, hash=h, info=bytes(info)))
    used = {h for sol in sols for h in sol['tex']}
    keep = [dict(hash=t['hash'], info=t['info'], plat=t['plat'], pixels=t['pixels']) for t in etex
            if t['hash'] not in {o['hash'] for o in ours} and t['hash'] in used]
    b, e = tpk.find(ed, 0x33310001)
    b2, e2 = tpk.find(ed, 0x33320001)
    # every texture our parts use must be in the pack, a shared one, or made by the game
    shared = {H(n) for n in ('WINDOW_FRONT', 'LICENSEPLATE', CAR + '_SKIN1')}
    shared |= {H(side % s_) for side in ('HEADLIGHT_%s', 'HEADLIGHT_GLASS_%s', 'BRAKELIGHT_%s')
               for s_ in ('LEFT', 'RIGHT')}
    have = {t['hash'] for t in keep + ours} | shared
    missing = {h for nm in new for h in new[nm]['tex']} - have - {h for s in esols for h in s['tex']}
    assert not missing, ['%08X' % h for h in missing]
    tex = pad_to(tpk360.write(keep + ours, ed[b:e], ed[b2:e2]), len(ed))
    open(os.path.join(cdir, 'TEXTURES.BIN'), 'wb').write(tex)
    print('CARS/%s: GEOMETRY.BIN %d, TEXTURES.BIN %d (%d textures)' % (CAR, len(geo), len(tex), len(keep) + len(ours)))

    if DIAG_LOG:
        open(os.path.join(out, 'diag_groupes.txt'), 'w', encoding='utf-8').write(chr(10).join(DIAG_LOG) + chr(10))
        print('diagnostic colours: %d groups, see diag_groupes.txt' % len(DIAG_LOG))
    if new_offs is not None or perf or sound:
        g = bytearray(gm)
        a0, asize = att_entry[0], att_entry[1]
        if new_offs is not None:
            struct.pack_into('>16f', g, a0 + toff, *new_offs.reshape(-1))
            print('GLOBAL/GLOBALMEMORYFILE.BIN: ecar/%s TireOffsets' % CAR.lower(), np.round(new_offs, 3).tolist())
        if perf or sound:
            att = bytearray(g[a0:a0 + asize])
            pack = attrib360.Pack(bytes(att))
            for (cls, name), v in (PERFORMANCE[perf].items() if perf else ()):
                attrib360.set_field(att, pack, cls, CAR.lower(), name, v)
            if sound:
                n = attrib360.set_refs(att, pack, 'pvehicle', CAR.lower(), 'engineaudio', 'engineaudio',
                                       [ENGINE_SOUNDS[sound]])
                print('GLOBAL/GLOBALMEMORYFILE.BIN: engine sound of %s -> %s (%d refs)' % (CAR.lower(), sound, n))
            g[a0:a0 + asize] = att
            if perf:
                print('GLOBAL/GLOBALMEMORYFILE.BIN: performance of %s set to %s' % (CAR.lower(), perf))
        gdir = os.path.join(out, 'GLOBAL')
        os.makedirs(gdir, exist_ok=True)
        open(os.path.join(gdir, 'GLOBALMEMORYFILE.BIN'), 'wb').write(g)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--iso', required=True, help='your Xbox 360 disc image of NFS Most Wanted')
    ap.add_argument('--kn5', required=True, help='mazda_mx5_rf.kn5 from the Assetto Corsa mod')
    ap.add_argument('--out', required=True, help='output game_root folder')
    ap.add_argument('--car', default='ELISE', help='car to replace (its folder in CARS, e.g. IS300)')
    ap.add_argument('--base-root', help='your installed game_root (read first, e.g. with the French dub), '
                                        'so that GLOBALMEMORYFILE.BIN keeps your changes')
    ap.add_argument('--wheels', default='auto', choices=('auto', 'keep', 'patch'),
                    help='keep the car wheel positions or move them to the MX-5 ones (auto: by wheelbase)')
    ap.add_argument('--only', nargs='*', help='diagnostic: convert only these parts (e.g. KIT00_HOOD), '
                                              'keep the original car for the others')
    ap.add_argument('--keep', nargs='*', default=(), help='diagnostic: parts kept from the original car '
                                                          '(e.g. KIT00_FRONT_TIRE KIT00_FRONT_BRAKE)')
    ap.add_argument('--mx5-wheels', action='store_true',
                    help='use the MX-5 rims and brakes (experimental: the game does not draw them yet)')
    ap.add_argument('--perf', default='rf184', choices=sorted(PERFORMANCE) + ['keep'],
                    help="performance written over the replaced car's (keep: leave the car's own)")
    ap.add_argument('--sound', default='miata', choices=sorted(ENGINE_SOUNDS) + ['keep'],
                    help="engine sound (keep: the replaced car's own)")
    ap.add_argument('--top', default='closed', choices=('closed', 'open'),
                    help='open: roof panels and rear window stowed, side windows down')
    a = ap.parse_args()
    main(a.iso, a.kn5, a.out, a.car, a.base_root, a.wheels, a.only, tuple(a.keep), a.mx5_wheels,
         None if a.perf == 'keep' else a.perf, a.top, None if a.sound == 'keep' else a.sound)
