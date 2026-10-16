"""The MX-5 RF as a Gran Turismo 2 car: carobj/<car>.cdo / .cno (model, day and night) and .cdp /
.cnp (texture), made from the Assetto Corsa model on the template of the car it replaces.

The shell, the pictures and the texture are those of the GT1 version (../gran-turismo-ps1:
build_car.py, shell.py, views.py), with what GT2 gives more: 224 rows of texture (GT1: 192) and
more vertices. As in GT1 the game draws the wheels with a picture in the car's texture (the
top-left 48 x 48, CLUT 0): kept from the car replaced.
GT2 against GT1: z towards the rear (the faces' winding then comes out right: their cross product
points outwards in GT2), vertices at 2048 per metre (LOD scale 17), wheels at 4096 per metre with
their x at the edge of the body (0.98 x its half width at the axle, measured on the disc's cars),
in the menus 0.875 x that. Faces: lit (0x8000), the rear lamps 0xC000 (CLUT 14, 15 when braking),
the underside plain black.
CLUTs: 0 the wheel (the template's), 1..12 the body, 13 the front lamps (lit in the night
texture), 14 / 15 the rear lamps.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GT1 = os.path.join(HERE, '..', 'gran-turismo-ps1')
for p in (GT1, os.path.join(HERE, '..', '..', 'common')):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_car as B   # noqa: E402
import gt2data          # noqa: E402
import gt2model         # noqa: E402
import gt2texture       # noqa: E402
import mx5scene         # noqa: E402

SCALE = 17
UNIT = 2.0 ** (SCALE - 6)     # 2048 per metre
WHEEL_UNIT = 4096.0
ROWS = 224                    # rows of the GT2 texture
WHEEL = (0, 0, 48, 48)        # u0, v0, u1, v1: the wheel picture the game draws the wheels with
                              # (CLUT 0), kept from the template
LODS = [240, 110, 44]         # vertices wanted per LOD (256 at most); fewer if the file is too big
BODY_GROUPS, FRONT_LAMPS = 12, 13
TYRE = (0.308, 0.205)         # 205/45 R17: radius, width (m)
ARCH_R = TYRE[0] + 0.05       # radius of the wheel arches cut in the side picture (m)
ARCH_OUT = TYRE[0] + 0.16     # how far the dark of a real arch can go past that circle
CLEAR = (98, 18, 106, 26)     # a corner of the texture left transparent (u0, v0, u1, v1): the faces
                              # of the arches that are not on the side picture point there
WALL_X = 0.45                 # the black wheel well walls, inside the arches (the disc's cars: 0.35)
ORDER = 16                    # render order of the disc's ordinary faces
ARCH_ORDER = 23               # the faces in the wheel arches: drawn before the wheels (the disc's
                              # cars have their wheel wells at 23 and open arches)
LIT, BRAKE = 0x8000, 0xC000


def scene(kn5, top):
    """Model points and the scene, centred between the axles; wheel centres FL, FR, RL, RR."""
    sp, st, sc, wheels = mx5scene.load(kn5, top)
    zc = (wheels['LF'][2] + wheels['LR'][2]) / 2
    sp = sp - [0, 0, zc]
    for P in sc.parts:
        P['pos'] = P['pos'] - np.float32([0, 0, zc])
    return sp, st, sc, [wheels[k] - [0, 0, zc] for k in ('LF', 'RF', 'LR', 'RR')]


def fill_arches(sp, st, W, lo_y):
    """The shell's points with a flat panel across each wheel arch, flush with the side: the
    shell then goes straight down there, as the disc's cars (a flat side, the arch cut round in
    the texture), instead of tucking into the wheel well (corners that stick out around the
    wheels). Only the shell sees them; the pictures show the real arches."""
    extra_p, extra_t = [], []
    n = len(sp)
    for x, y, z in W:
        sx = 1.0 if x > 0 else -1.0
        band = sp[(np.abs(np.abs(sp[:, 2] - z) - (B.ARCH + 0.08)) < 0.07) & (sp[:, 1] < y + 0.05) & (sp[:, 0] * sx > 0)]
        xw = 0.995 * np.abs(band[:, 0]).max() if len(band) else 0.85
        z0, z1 = z - B.ARCH - 0.06, z + B.ARCH + 0.06
        y0, y1 = lo_y - 0.01, y + ARCH_R + 0.03
        gz, gy = np.meshgrid(np.linspace(z0, z1, 9), np.linspace(y0, y1, 6))
        pts = np.stack([np.full(gz.size, sx * xw), gy.ravel(), gz.ravel()], 1)
        base = n + sum(len(a) for a in extra_p)
        extra_p.append(pts)
        cols = 9
        for r in range(5):
            for c in range(8):
                a = base + r * cols + c
                extra_t += [(a, a + 1, a + cols + 1), (a, a + cols + 1, a + cols)]
    return np.vstack([sp] + extra_p), np.vstack([st, np.array(extra_t)])


def normal_word(n):
    """A unit vector as GT2 stores it: x, y, z x 500 in 10 signed bits from bits 2, 12, 22."""
    q = [int(round(c * 500)) & 0x3FF for c in n]
    return (q[0] << 2) | (q[1] << 12) | (q[2] << 22)


def clut_word(k):
    return ((k // 4) << 6) | (k % 4)


def to_gt2(p, lo_y):
    """GT1-axes metres (z forward) -> GT2 units (z backward), y from the lowest point."""
    q = np.asarray(p, np.float64) * [1, 1, -1]
    q[..., 1] -= lo_y
    return q


def in_arch(p, wheels):
    """A face (GT1-axes metres) in a wheel arch: its centre, seen from the side, in the arch cut
    in the texture (the half circle over the wheel and the opening under it). Those of its faces
    that are not on the side picture go behind the wheels, transparent; outside it, a face so
    hidden would leave a hole (the black of the underside through it)."""
    c = np.asarray(p).mean(0)
    for _, y, z in wheels:
        dz, dy = c[2] - z, c[1] - y
        r = ARCH_R + 0.02
        if dz * dz + dy * dy < r * r or (dy < 0 and abs(dz) < r):
            return True
    return False


def _in_rect(uv, rect):
    if uv is None or rect is None:
        return False
    uv = np.asarray(uv, float)
    u0, v0, u1, v1 = rect
    return bool(((uv[:, 0] >= u0) & (uv[:, 0] < u1) & (uv[:, 1] >= v0) & (uv[:, 1] < v1)).all())


def _wheel_wells(L, wheels, lo_y):
    """A black wall behind each arch, facing out (seen through the arch, as the disc's cars have)."""
    for x, y, z in wheels:
        sx = 1.0 if x > 0 else -1.0
        c = np.array([[sx * WALL_X, lo_y - 0.02, z - ARCH_R], [sx * WALL_X, y + ARCH_R, z - ARCH_R],
                      [sx * WALL_X, y + ARCH_R, z + ARCH_R], [sx * WALL_X, lo_y - 0.02, z + ARCH_R]])
        g = to_gt2(c, lo_y)
        if np.cross(g[1] - g[0], g[2] - g[0])[0] * sx < 0:      # GT2: the cross product points out
            g = g[::-1]
        k = len(L.verts)
        for v in np.round(g * UNIT).astype(int):
            L.verts.append((int(v[0]), int(v[1]), int(v[2]), 0))
        L.quads.append(gt2model.Poly([k, k + 1, k + 2, k + 3], (0, 0, 0, 0), ARCH_ORDER, 0, 40, 0))


def arch_holes(atlas, wheels, lo_y):
    """Texels of the side picture inside the wheel arches (made transparent: the wheels show
    through them, with a round edge, as on the disc's cars): a half circle over each wheel, down
    to below the car."""
    from PIL import Image, ImageDraw
    ou, ov, r = atlas.place['side']
    W, H = atlas.pics['side']['size']
    rect = (ou, ov, ou + W // 4, min(ROWS, ov + H // 4))
    img = Image.new('L', (256, 256), 0)
    d = ImageDraw.Draw(img)
    # the left and right sides share the picture: one arch per axle
    for _, y, z in (wheels[0], wheels[2]):
        t = np.linspace(0, np.pi, 33)
        pts = [[0.8, y + ARCH_R * np.sin(a), z + ARCH_R * np.cos(a)] for a in t]
        pts += [[0.8, lo_y - 0.2, z - ARCH_R], [0.8, lo_y - 0.2, z + ARCH_R]]
        uv = atlas.uv('side', np.array(pts))
        d.polygon([tuple(p) for p in uv], fill=1)
    m = np.array(img, bool)
    keep = np.zeros_like(m)
    keep[rect[1]:rect[3], rect[0]:rect[2]] = True
    # the real arch of the car is not quite that circle (the ND's front one is larger): from the
    # circle, the dark of the wheel well around it (what is not paint, lamp or glass) within a
    # wider circle goes too, as long as it touches it
    V = atlas.V
    cls = atlas.texels()[0]
    big = Image.new('L', (256, 256), 0)
    db = ImageDraw.Draw(big)
    for _, y, z in (wheels[0], wheels[2]):
        t = np.linspace(0, np.pi, 33)
        pts = [[0.8, y + ARCH_OUT * np.sin(a), z + ARCH_OUT * np.cos(a)] for a in t]
        pts += [[0.8, lo_y - 0.2, z - ARCH_OUT], [0.8, lo_y - 0.2, z + ARCH_OUT]]
        db.polygon([tuple(q) for q in atlas.uv('side', np.array(pts))], fill=1)
    dark = np.array(big, bool) & ~np.isin(cls, (V.PAINT, V.LAMP_F, V.LAMP_R, V.GLASS))
    grow = m & keep
    for _ in range(64):
        g = grow.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            g |= np.roll(np.roll(grow, dy, 0), dx, 1)
        g &= (dark | m) & keep
        if (g == grow).all():
            break
        grow = g
    return grow, rect


def near_wheel(p, wheels):
    c = np.asarray(p).mean(0)
    return any(abs(c[2] - z) < B.ARCH + 0.2 and c[1] < y + ARCH_OUT for _, y, z in wheels)


def make_lod(verts, faces, vn, faces_tex, li, lo_y, wheels=(), side=None, dark=None):
    """side: (u0, v0, u1, v1) of the side picture: its faces show the arches (transparent texels)
    and stay at the ordinary order; the other faces of the arches go behind the wheels, and so do
    the faces near a wheel whose texels are mostly the dark of the wheel well (dark: per texel)."""
    L = gt2model.LOD()
    L.scale = SCALE
    q = np.round(to_gt2(verts, lo_y) * UNIT).astype(int)
    if np.abs(q).max() > 32767:
        raise ValueError('modèle trop grand pour l\'échelle %d' % SCALE)
    L.verts = [(int(x), int(y), int(z), 0) for x, y, z in q]
    n = to_gt2(vn, 0)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    L.normals = [normal_word(v) for v in n]
    for fi, f in enumerate(faces):
        clut, uv = faces_tex[(li, fi)]
        quad = len(f) == 4
        idx = [int(i) for i in f]
        hidden = in_arch(verts[idx], wheels) and not _in_rect(uv, side)
        if not hidden and dark is not None and uv is not None and not _in_rect(uv, side) and near_wheel(verts[idx], wheels):
            m = B.raster_mask(np.asarray(uv))
            hidden = m.any() and dark[m].mean() > 0.6
        order = ARCH_ORDER if hidden else ORDER
        if clut is None and wheels and near_wheel(verts[idx], wheels):
            # a face turned to the ground at a wheel (under the edge of a wing): transparent too
            clut, hidden, order = 1, True, ARCH_ORDER
        if clut is None:
            # underside: plain black, unlit, behind the wheels (the disc's cars have theirs at 17):
            # at ordinary order it covered them, seen through the arches
            p = gt2model.Poly(idx, (0, 0, 0, 0), ARCH_ORDER, 0, 40 if quad else 32, 0)
            (L.quads if quad else L.tris).append(p)
            continue
        uvl = [(int(a), int(min(b, ROWS - 1))) for a, b in uv] if uv is not None else []
        if hidden:
            # the arch's own faces (the shell tucking in under it): transparent, as the open
            # arches of the disc's cars; the wheel and the black wall behind show
            u0, v0, u1, v1 = CLEAR
            uvl = [(u0 + 1, v0 + 1), (u1 - 2, v0 + 1), (u1 - 2, v1 - 2), (u0 + 1, v1 - 2)][:len(idx)]
        p = gt2model.Poly(idx, idx + [0] * (4 - len(idx)), order, BRAKE if clut == 14 else LIT,
                          45 if quad else 37, 0, uvl + [(0, 0)] * (4 - len(uvl)), clut, clut_word(clut))
        (L.uv_quads if quad else L.uv_tris).append(p)
    if wheels and li < 2:
        _wheel_wells(L, wheels, lo_y)
        q = np.array([v[:3] for v in L.verts])
    mn, mx = q.min(0), q.max(0)
    L.bounds = (int(mn[0]), int(mn[1]), int(mn[2]), 0, int(mx[0]), int(mx[1]), int(mx[2]), 0)
    L.scale2 = int(math.ceil(np.linalg.norm(q, axis=1).max()))
    return L


class Atlas(B.Atlas):
    """The GT1 atlas, with the front lamps found under their glass: the pictures see the lens in
    front of them (glass), so the texels where the lamps' own triangles fall are made lamps."""

    def __init__(self, sc, sp, hull, **kw):
        super().__init__(sc, sp, hull, **kw)
        from PIL import Image, ImageDraw
        import views as V
        self.V = V
        img = Image.new('L', (256, 256), 0)
        draw = ImageDraw.Draw(img)
        for P in sc.parts:
            if P['cls'] != V.LAMP_F:
                continue
            for view in ('front', 'side', 'top'):
                tri = P['tri']
                pos = P['pos']
                # only the lamp triangles that the view sees (nothing in front of them)
                cen = pos[tri].mean(1)
                seen = self.miss(view, cen) < 0.06
                uv = self.uv(view, pos.reshape(-1, 3))
                for t in tri[seen]:
                    draw.polygon([tuple(uv[i]) for i in t], fill=1, outline=1)
        self.lamps = np.array(img, bool)

    def texels(self):
        cls, rgb, shade = super().texels()
        V = self.V
        cls[self.lamps & np.isin(cls, (V.GLASS, V.OTHER, V.LAMP_F))] = V.LAMP_F
        return cls, rgb, shade


def wheels_of(sp, W, lo_y):
    """GT2 wheel positions (x, y, z, menu x) and the menu wheel size, from the detailed model's
    width at the axles."""
    out = []
    for x, y, z in W:
        near = sp[np.abs(sp[:, 2] - z) < 0.25]
        hw = np.abs(near[:, 0]).max()
        X = 0.98 * hw * np.sign(x) * WHEEL_UNIT
        out.append((int(round(X)), int(round((y - lo_y) * WHEEL_UNIT)), int(round(-z * WHEEL_UNIT)),
                    int(round(0.875 * X))))
    r, w = (int(round(c * WHEEL_UNIT)) for c in TYRE)
    return out, (r, w, r, w)


def shadow_of(template, verts, lo_y):
    """The template's shadow stretched over the new car's footprint."""
    S = template.shadow
    q = to_gt2(verts, lo_y) * UNIT
    x0, x1, z0, z1 = q[:, 0].min(), q[:, 0].max(), q[:, 2].min(), q[:, 2].max()
    sv = np.array(S.verts, float)
    sx0, sx1, sz0, sz1 = sv[:, 0].min(), sv[:, 0].max(), sv[:, 1].min(), sv[:, 1].max()
    nx = x0 + (sv[:, 0] - sx0) * (x1 - x0) / max(sx1 - sx0, 1)
    nz = z0 + (sv[:, 1] - sz0) * (z1 - z0) / max(sz1 - sz0, 1)
    out = gt2model.Shadow()
    out.verts = [(int(round(a)), int(round(b))) for a, b in zip(nx, nz)]
    out.tris, out.quads, out.unknown = S.tris, S.quads, S.unknown
    out.scale, out.scale2 = S.scale, S.scale2
    out.bounds = (int(nx.min()), 0, int(nz.min()), 0, int(nx.max()), 0, int(nz.max()), 0)
    return out


def texture_bytes(template, index, cluts, night=False, holes=None):
    """The .cdp / .cnp: the template's header (paint count and codes) and per-paint tail, our image
    and CLUTs (the RF's paints, gt2data.PAINTS, in the order of the car's colours)."""
    t = gt2texture.Texture(template)
    # colour 0 is transparent: the texels no face was given (between faces) take a neighbour's
    # index, so that the edges of the faces, drawn a little wider by the console, have no holes
    idx = index[:ROWS].copy()
    for _ in range(4):
        empty = idx == 0
        if not empty.any():
            break
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(idx, dy, 0), dx, 1)
            take = empty & (src != 0)
            idx[take] = src[take]
            empty = idx == 0
    if holes is not None:
        idx[holes[:ROWS]] = 0          # the arches: transparent
    u0, v0, u1, v1 = CLEAR
    idx[v0:v1, u0:u1] = 0
    u0, v0, u1, v1 = WHEEL
    idx[v0:v1, u0:u1] = t.index_image()[v0:v1, u0:u1]
    t.set_image(idx)
    pal = np.array(cluts, np.float32)
    if night:
        pal = pal.copy()
        # front lamps on: their fixed colours (the same in every paint; not the paint) that are
        # not dark go towards a warm white; rear lamps on (between off and braking)
        f = pal[:, FRONT_LAMPS]
        fixed = (np.abs(f - f[:1]).max((0, 2)) < 1e-6)[None, :, None]
        lum = f.mean(2, keepdims=True)
        on = fixed & (lum > 0.2)
        pal[:, FRONT_LAMPS] = np.where(on, np.clip(0.3 * f + 0.8 * np.array([1.0, 0.97, 0.88]), 0, 1), f)
        pal[:, 14] = 0.5 * (pal[:, 14] + pal[:, 15])
    words = B.ps1(pal)
    words[:, :, 0] = 0
    for p in range(t.paints):
        for k in range(1, 16):     # CLUT 0: the wheel's, the template's
            t.set_clut(p, k, words[p % len(gt2data.PAINTS), k])
    return t.bytes()


def build(kn5, top, template_cdo, template_cdp, template_cnp, lods=LODS, log=print):
    """(cdo, cno, cdp, cnp) bytes of the RF ('closed' / 'open') on the template car's files."""
    sp, st, sc, W = scene(kn5, top)
    lo_y = sp[:, 1].min()
    wheel_sp = sp
    sp, st = fill_arches(sp, st, W, lo_y)
    tmpl = gt2model.read(template_cdo)
    targets = list(lods)
    while True:
        shells = [B.make_shell(sp, st, n, (W[0][2], W[2][2]), smooth=top == 'open', log=log) for n in targets]
        if max(len(v) for v, _, _ in shells) <= 256:
            break
        targets[0] -= 8
    hv, hf, _ = shells[0]
    ht = np.array([q for f in hf for q in ([(f[0], f[1], f[2]), (f[0], f[2], f[3])] if len(f) == 4 else [tuple(f)])])
    atlas = Atlas(sc, sp, (hv, ht), v0=0, v1=ROWS, side_v=WHEEL[3])
    while True:
        index, cluts, ftex = B.texture_layout(atlas, shells, BODY_GROUPS, FRONT_LAMPS, gt2data.PAINTS)
        M = gt2model.Model()
        M.distances = list(tmpl.distances)
        M.wheels, M.menu_wheels = wheels_of(wheel_sp, W, lo_y)
        holes, side = arch_holes(atlas, W, lo_y)
        V = atlas.V
        dark = ~np.isin(atlas.texels()[0], (V.PAINT, V.LAMP_F, V.LAMP_R, V.GLASS))
        M.lods = [make_lod(v, f, n, ftex, li, lo_y, W, side, dark) for li, (v, f, n) in enumerate(shells)]
        M.shadow = shadow_of(tmpl, shells[0][0], lo_y)
        try:
            cdo = gt2model.write(M)
            break
        except ValueError:
            # too big for what the game reserves: fewer vertices in the detailed LOD
            targets[0] -= 12
            log('    trop gros (%d octets max), LOD 0 ramené à %d sommets' % (gt2model.MAX_SIZE, targets[0]))
            shells[0] = B.make_shell(sp, st, targets[0], (W[0][2], W[2][2]), smooth=top == 'open', log=log)
            hv, hf, _ = shells[0]
            ht = np.array([q for f in hf for q in ([(f[0], f[1], f[2]), (f[0], f[2], f[3])] if len(f) == 4 else [tuple(f)])])
            atlas = Atlas(sc, sp, (hv, ht), v0=0, v1=ROWS, side_v=WHEEL[3])
    log('    modèle GT2 : %s, %d octets' % (gt2model.stats(M), len(cdo)))
    cdp = texture_bytes(template_cdp, index, cluts, holes=holes)
    cnp = texture_bytes(template_cnp, index, cluts, night=True, holes=holes)
    return cdo, cdo, cdp, cnp, (M, index, cluts)
