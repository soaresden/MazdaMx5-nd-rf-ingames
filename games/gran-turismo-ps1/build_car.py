"""The MX-5 RF as a Gran Turismo (PS1) car: a .car model and a .tex texture made from the Assetto
Corsa model, on the template of the car it replaces (header, shadow and wheel picture kept).

- Shell: rings around the body (shell.py), three levels of detail.
- Texture: side, top, front and rear pictures of the detailed model (views.py) packed in the
  256x192 texels the faces can use; each face takes its texels from the view it faces (left side,
  left half of the top...: mirrored). 4 bits per texel, one 16-colour CLUT per face.
- CLUTs: 1-11 for the body (paint shades + fixed colours, chosen per group of faces), 14 for the
  faces of the rear lamps and 15 the same with the lamps lit (brakes), 0 (wheel) and 12, 13 kept
  from the template. Eight paints: the paint shades change, the rest stays.
"""
import struct

import numpy as np

import gt1car
import shell
import views as V

UNIT = 1024.0          # model units per metre (LOD scale 18)
WHEEL_UNIT = 4096.0    # wheel positions: units per metre
TEX_V0, TEX_V1 = 32, 224   # rows the faces can use
WHEEL_TEXELS = (0, 32, 48, 80)  # u0, v0, u1, v1: the wheel picture the game draws the wheels with

# MX-5 RF paints (sRGB), in the order of the template's eight paints
PAINTS = [
    ('Deep Crystal Blue', (24, 40, 84)),
    ('Soul Red Crystal', (150, 16, 26)),
    ('Machine Grey', (88, 90, 94)),
    ('Jet Black', (14, 14, 16)),
    ('Snowflake White Pearl', (226, 226, 220)),
    ('Ceramic', (184, 186, 182)),
    ('Polymetal Grey', (96, 108, 114)),
    ('Platinum Quartz', (156, 150, 140)),
]

# levels of detail: (stations, points per side of a ring)
LODS = [(15, 6), (9, 4), (6, 3)]


def paint_rgb(base, shade):
    """Colour of the paint for a shade (0 dark .. 1 lit), 0..1 floats."""
    b = np.asarray(base, np.float32) / 255
    s = np.asarray(shade, np.float32)[..., None]
    c = b * (0.25 + 1.05 * s) + 0.35 * np.clip(s - 0.8, 0, None) * 5 * (1 - b) * 0.4
    return np.clip(c, 0, 1)


def ps1(rgb):
    """0..1 RGB -> PS1 15-bit words (never 0, which is transparent)."""
    q = np.clip(np.round(np.asarray(rgb) * 31), 0, 31).astype(np.uint16)
    w = q[..., 0] | (q[..., 1] << 5) | (q[..., 2] << 10)
    return np.where(w == 0, 0x8000, w).astype(np.uint16)


# ---------------------------------------------------------------------------------------------
def make_shell(sp, st, stations, per_side):
    """Shell vertices (metres), faces (lists of 3 or 4 indices, outward winding as the game's),
    vertex normals."""
    z0, z1 = sp[:, 2].min(), sp[:, 2].max()
    u = np.linspace(0, 1, stations)
    u = u - 0.06 * np.sin(2 * np.pi * u)
    v, q, ring = shell.build(sp, st, z0 + 0.01 + (z1 - z0 - 0.02) * u, per_side)
    K = 2 * per_side + 2
    R = len(v) // K
    verts = [tuple(p) for p in v]
    faces = [list(f) for f in q[:(R - 1) * K]]
    # end caps, split on the centre line so that no face crosses it (the textures are mirrored)
    for r, front in ((0, False), (R - 1, True)):
        base = r * K
        cen = {}
        for k in range(per_side + 2):
            a, b = base + k, base + (K - k) % K
            if a == b:
                cen[k] = a
            else:
                p = (v[a] + v[b]) / 2
                p[0] = 0.0
                cen[k] = len(verts)
                verts.append(tuple(p))
        for k in range(per_side + 1):
            ra, rb = base + k, base + k + 1
            la, lb = base + (K - k) % K, base + (K - k - 1) % K
            for f in ([ra, rb, cen[k + 1], cen[k]], [cen[k], cen[k + 1], lb, la]):
                faces.append(f)
    verts = np.array(verts)
    # drop repeated corners (quads -> triangles), orient every face outwards
    centre = np.array([0.0, (verts[:, 1].min() + verts[:, 1].max()) / 2, 0.0])
    out = []
    for f in faces:
        g = []
        for i in f:
            if i not in g:
                g.append(i)
        if len(g) < 3:
            continue
        p = verts[g]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if len(g) == 4:
            n = n + np.cross(p[2] - p[0], p[3] - p[0])
        c = p.mean(0)
        outward = c - centre
        outward[2] *= 0.3
        # the game's faces: cross(p1 - p0, p2 - p0) points inwards
        if n @ outward > 0:
            g = g[::-1]
        out.append(g)
    # vertex normals: mean of the outward face normals around each vertex
    vn = np.zeros_like(verts)
    for g in out:
        p = verts[g]
        n = -np.cross(p[1] - p[0], p[2] - p[0])
        vn[g] += n / max(np.linalg.norm(n), 1e-9)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    return verts, out, vn


# ---------------------------------------------------------------------------------------------
class Atlas:
    """Where each view goes in the texture, and the pictures."""

    def __init__(self, scene, sp, hull):
        lo, hi = sp.min(0), sp.max(0)
        hw = np.abs(sp[:, 0]).max()
        L, Hh = hi[2] - lo[2], hi[1] - lo[1]
        rows = TEX_V1 - TEX_V0
        # front and rear pictures in a column on the right, side and top pictures to their left
        r_fr = 0.68 * (rows / 2) / Hh
        col = int(np.ceil(hw * r_fr))
        r_main = min((256 - col) / L, (rows - (WHEEL_TEXELS[3] - TEX_V0)) / (Hh + hw))
        self.boxes = {
            'side': ((lo[2], hi[2]), (-hi[1], -lo[1])),
            'top': ((lo[2], hi[2]), (0, hw)),
            'front': ((0, hw), (-hi[1], -lo[1])),
            'rear': ((0, hw), (-hi[1], -lo[1])),
        }
        side_h = int(np.ceil(Hh * r_main))
        self.place = {  # view: (u origin, v origin, texels per metre)
            'side': (0, WHEEL_TEXELS[3], r_main),
            'top': (0, WHEEL_TEXELS[3] + side_h, r_main),
            'front': (256 - col, TEX_V0, r_fr),
            'rear': (256 - col, TEX_V0 + int(np.ceil(Hh * r_fr)), r_fr),
        }
        # pictures at 4x the texel density, reduced later
        self.pics = {v: V.render(scene, v, self.place[v][2] * 4, self.boxes[v], hull=hull) for v in self.boxes}

    def uv(self, view, p):
        """Texel coordinates of points p (Nx3) in a view (|x| for the mirrored halves)."""
        (ua, us), (va, vs), _ = V.VIEWS[view]
        q = np.array(p, np.float64)
        q[:, 0] = np.abs(q[:, 0])
        (u0, _), (v0, _) = self.boxes[view]
        ou, ov, r = self.place[view]
        return np.stack([ou + (q[:, ua] * us - u0) * r, ov + (q[:, va] * vs - v0) * r], 1)

    def texels(self):
        """Per texel of the texture: class, rgb, shade (from the pictures, 4x4 reduced)."""
        cls = np.zeros((256, 256), np.int8)
        rgb = np.zeros((256, 256, 3), np.float32)
        shade = np.zeros((256, 256), np.float32)
        for v, pic in self.pics.items():
            W, H = pic['size']
            c = pic['cls'].reshape(H, W)
            col = pic['rgb'].reshape(H, W, 3)
            sh = pic['shade'].reshape(H, W)
            c, col, sh = _grow(c, col, sh)
            ou, ov, r = self.place[v]
            w, h = W // 4, H // 4
            blk = lambda a: a[:h * 4, :w * 4].reshape(h, 4, w, 4, *a.shape[2:])
            cb = blk(c)
            col4 = blk(col).mean((1, 3))
            # class of a texel: the most common of its 16 pixels; paint shade: mean over paint pixels
            flat = cb.transpose(0, 2, 1, 3).reshape(h, w, 16)
            counts = np.stack([(flat == k).sum(2) for k in range(7)], 2)
            tc = counts.argmax(2)
            pm = (flat == V.PAINT)
            shb = blk(sh).transpose(0, 2, 1, 3).reshape(h, w, 16)
            tsh = (shb * pm).sum(2) / np.maximum(pm.sum(2), 1)
            u1, v1 = min(256, ou + w), min(TEX_V1, ov + h)
            cls[ov:v1, ou:u1] = tc[:v1 - ov, :u1 - ou]
            rgb[ov:v1, ou:u1] = col4[:v1 - ov, :u1 - ou]
            shade[ov:v1, ou:u1] = tsh[:v1 - ov, :u1 - ou]
        return cls, rgb, shade


def _grow(cls, rgb, shade, steps=6):
    """Empty pixels take the values of a filled neighbour, a few pixels out from the car (faces
    of the shell stick out a little past the outline: no transparent holes)."""
    cls, rgb, shade = cls.copy(), rgb.copy(), shade.copy()
    for _ in range(steps * 4):
        empty = cls == V.EMPTY
        if not empty.any():
            break
        changed = False
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src_c = np.roll(np.roll(cls, dy, 0), dx, 1)
            take = empty & (src_c != V.EMPTY)
            if take.any():
                cls[take] = src_c[take]
                rgb[take] = np.roll(np.roll(rgb, dy, 0), dx, 1)[take]
                shade[take] = np.roll(np.roll(shade, dy, 0), dx, 1)[take]
                empty = cls == V.EMPTY
                changed = True
        if not changed:
            break
    return cls, rgb, shade


# ---------------------------------------------------------------------------------------------
def face_view(p, n):
    """The view a face takes its texels from (None: underside, plain black)."""
    ax = np.abs(n)
    k = ax.argmax()
    if k == 1:
        return 'top' if n[1] > 0 else None
    if k == 0:
        return 'side'
    return 'front' if n[2] > 0 else 'rear'


def raster_mask(uv, size=256):
    """Texels covered by the polygon uv (Kx2)."""
    from PIL import Image, ImageDraw
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).polygon([tuple(x) for x in uv], fill=1, outline=1)
    return np.array(m, bool)


def kmeans(x, k, iters=12, seed=0):
    x = np.asarray(x, np.float32)
    if len(x) <= k:
        return np.concatenate([x, np.repeat(x[-1:], k - len(x), 0)]) if len(x) else np.zeros((k,) + x.shape[1:], np.float32)
    rng = np.random.default_rng(seed)
    c = x[rng.choice(len(x), k, replace=False)]
    for _ in range(iters):
        d = ((x[:, None] - c[None]) ** 2).reshape(len(x), k, -1).sum(2)
        a = d.argmin(1)
        for j in range(k):
            if (a == j).any():
                c[j] = x[a == j].mean(0)
    return c


def build_texture(atlas, lods, template_tex, night=False):
    """(tex bytes, per LOD: per face (clut, uv list or None)). Faces: lists of (verts, faces, normals)."""
    cls, rgb, shade = atlas.texels()
    # every face of every LOD: its view, its uv, its texels
    info = []
    for li, (verts, faces, vn) in enumerate(lods):
        for fi, f in enumerate(faces):
            p = verts[f]
            n = -np.cross(p[1] - p[0], p[2] - p[0])
            view = face_view(p, n)
            if view is None:
                info.append((li, fi, None, None, None))
                continue
            uv = atlas.uv(view, p)
            uv = np.clip(np.round(uv), 0, 255)
            uv[:, 1] = np.clip(uv[:, 1], TEX_V0, TEX_V1 - 1)
            m = raster_mask(uv)
            info.append((li, fi, view, uv, m))
    # the CLUT of each face of LOD 0: rear lamp faces -> 14; the others in 11 groups by their
    # colours. A texel belongs to the group of the first LOD 0 face over it; the faces of the
    # other LODs take the group of most of their texels (same texture, same colours).
    groups = {}
    feats, body = [], []
    for idx, (li, fi, view, uv, m) in enumerate(info):
        if m is None or li != 0:
            continue
        c = cls[m]
        if not len(c):
            continue
        if (c == V.LAMP_R).mean() > 0.04:
            groups[idx] = 14
            continue
        non = rgb[m][c != V.PAINT]
        feats.append(np.r_[non.mean(0) if len(non) else [0.5, 0.5, 0.5], (c == V.PAINT).mean() * 0.6,
                           (c == V.LAMP_F).mean() * 0.8, (c == V.GLASS).mean() * 0.5])
        body.append(idx)
    if body:
        cent = kmeans(np.array(feats), min(11, len(body)))
        a_ = ((np.array(feats)[:, None] - cent[None]) ** 2).sum(2).argmin(1)
        for idx, g in zip(body, a_):
            groups[idx] = 1 + int(g)
    gmap = np.zeros((256, 256), np.int8)
    for idx in sorted(groups, reverse=True):
        gmap[info[idx][4]] = groups[idx]
    for idx, (li, fi, view, uv, m) in enumerate(info):
        if m is None or li == 0:
            continue
        g = gmap[m]
        g = g[g > 0]
        groups[idx] = int(np.bincount(g).argmax()) if len(g) else 1
        gmap[m & (gmap == 0)] = groups[idx]
    # palettes: per group, paint levels + fixed colours
    index = np.zeros((256, 256), np.uint8)
    cluts = np.zeros((len(PAINTS), 16, 16, 3), np.float32)
    paint_slots = {}
    for g in range(1, 16):
        sel = gmap == g
        if g == 15 or not sel.any():
            continue
        c, col, sh = cls[sel], rgb[sel], shade[sel]
        is_p = c == V.PAINT
        np_ = int(np.clip(round(is_p.mean() * 15), 0 if not is_p.any() else 2, 13))
        nf = 15 - np_
        levels = np.sort(kmeans(sh[is_p][:, None], np_)[:, 0]) if np_ else np.zeros(0)
        fixed = kmeans(col[~is_p], nf) if nf else np.zeros((0, 3))
        if g == 14:
            fixed = kmeans(col[~is_p], nf)
        # indices: 1..np_ paint levels, then the fixed colours
        ix = np.zeros(sel.sum(), np.uint8)
        if np_:
            ix[is_p] = 1 + np.abs(sh[is_p][:, None] - levels[None]).argmin(1)
        if nf:
            dd = ((col[~is_p][:, None] - fixed[None]) ** 2).sum(2)
            ix[~is_p] = 1 + np_ + dd.argmin(1)
        index[sel] = ix
        for p, (_, base) in enumerate(PAINTS):
            pal = np.zeros((16, 3), np.float32)
            if np_:
                pal[1:1 + np_] = paint_rgb(base, levels)
            pal[1 + np_:] = fixed
            cluts[p, g] = pal
        paint_slots[g] = np_
    # 15: the rear lamp CLUT with the lamps lit (red and amber brighter)
    lit = cluts[:, 14].copy()
    for p in range(len(PAINTS)):
        npl = paint_slots.get(14, 0)
        f = lit[p, 1 + npl:]
        red = (f[:, 0] > f[:, 1] * 1.4) & (f[:, 0] > 0.15)
        f[red] = np.clip(f[red] * 1.9 + [0.15, 0.02, 0.02], 0, 1)
        lit[p, 1 + npl:] = f
    cluts[:, 15] = lit
    if night:
        # front lamps glow at night: the bright texels of the lamp faces brighter still
        pass
    # bytes: template header, index image, CLUTs (CLUT 0, 12 and 13 from the template)
    t = bytearray(template_tex)
    old = np.frombuffer(bytes(t[0x8060:]), '<u2').reshape(-1, 16, 16)
    tidx = np.zeros((256, 256), np.uint8)
    o = np.frombuffer(bytes(t[0x60:0x8060]), np.uint8)
    tidx[:, 0::2] = (o & 15).reshape(256, 128)
    tidx[:, 1::2] = (o >> 4).reshape(256, 128)
    u0, v0, u1, v1 = WHEEL_TEXELS
    index[v0:v1, u0:u1] = tidx[v0:v1, u0:u1]
    packed = (index[:, 0::2] | (index[:, 1::2] << 4)).astype(np.uint8)
    t[0x60:0x8060] = packed.tobytes()
    words = ps1(cluts)
    words[:, :, 0] = 0               # colour 0: transparent (no texel uses it)
    n = min(len(old), len(PAINTS))
    for p in range(n):
        for k in (0, 12, 13):
            words[p, k] = old[p, k]
    t[0x8060:0x8060 + n * 0x200] = words[:n].astype('<u2').tobytes()
    faces_out = {}
    for idx, (li, fi, view, uv, m) in enumerate(info):
        faces_out[(li, fi)] = (groups.get(idx), uv)
    return bytes(t), faces_out, index, cluts


# ---------------------------------------------------------------------------------------------
def clut_word(k):
    """Palette word of CLUT k (as the disc's cars: (w >> 6) * 4 + (w & 3) = k)."""
    return ((k // 4) << 6) | (k % 4)


def build_car(template_car, lods, faces_tex, wheels, lo_y):
    """The .car bytes: template header and shadow, our LODs and wheel positions."""
    car = gt1car.Car.read(template_car)
    tmpl_face = {}
    for L in car.lods:
        for f in L.faces:
            tmpl_face.setdefault((f.quad, f.textured), f)
    new_lods = []
    for li, (verts, faces, vn) in enumerate(lods):
        T = car.lods[min(li, len(car.lods) - 1)]
        L = gt1car.Lod()
        L.head = T.head
        L.scale = 18
        q = np.round((verts - [0, lo_y, 0]) * UNIT).astype(int)
        L.verts = [(int(x), int(y), int(z), 0) for x, y, z in q]
        nn = np.round(vn * 4000).astype(int)
        L.normals = [(int(x), int(y), int(z), 0) for x, y, z in nn]
        for fi, f in enumerate(faces):
            clut, uv = faces_tex[(li, fi)]
            quad = len(f) == 4
            F = gt1car.Face()
            F.quad, F.textured = quad, clut is not None
            idx = [int(i) for i in f] + [0] * (4 - len(f))
            F.v = idx
            F.n = idx[:]
            # bits 27-31: 16 + 2 (lit, like most of the disc's faces)
            F.rest = (18 << 27)
            F.pad = b'\0\0'
            if F.textured:
                F.tail = b'\xff\xff\xff' + bytes([0x2D if quad else 0x25])
                uvl = [(int(a), int(b)) for a, b in uv] + [(0, 0)] * (4 - len(uv))
                F.uv = uvl
                F.pal = clut_word(clut)
            else:
                F.rest = 16 << 27  # unlit plain colour
                F.n = [0, 0, 0, 0]
                F.tail = b'\x10\x10\x10' + bytes([0x29 if quad else 0x21])
                F.uv = None
                F.pal = None
            L.faces.append(F)
        # header: counts are set on writing; bounding box and sphere here
        h = bytearray(L.head)
        mn, mx = q.min(0), q.max(0)
        struct.pack_into('<8h', h, 0x14, int(mn[0]), int(mn[1]), int(mn[2]), 0, int(mx[0]), int(mx[1]), int(mx[2]), 0)
        struct.pack_into('<H', h, 0x26, int(np.ceil(np.linalg.norm(q, axis=1).max())))
        L.head = bytes(h)
        new_lods.append(L)
    car.lods = new_lods
    # wheels: front left, front right, rear left, rear right
    car.wheels = [(int(round(x * WHEEL_UNIT)), int(round((y - lo_y) * WHEEL_UNIT)), int(round(z * WHEEL_UNIT)), 0)
                  for x, y, z in wheels]
    return car.write(), car
