"""Tiny numpy z-buffer rasterizer for previews (Z up, X forward, Y left)."""
import numpy as np
from PIL import Image


def look(yaw_deg, pitch_deg):
    y, p = np.radians(yaw_deg), np.radians(pitch_deg)
    # camera looks along -forward; build rotation so that world -> camera (x right, y up, z depth)
    fwd = np.array([np.cos(p) * np.cos(y), np.cos(p) * np.sin(y), np.sin(p)])
    right = np.cross(fwd, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return np.stack([right, up, -fwd])


def render(meshes, size=(900, 500), yaw=-35, pitch=-12, scale=None, bg=(235, 235, 240), center=None,
           cull=0):
    """meshes: list of (pos Nx3, tris Mx3, rgb tuple or Nx3 per-vertex colors).
    cull: 0 draws both sides; 1 or -1 drops the triangles whose screen winding has the other sign."""
    W, H = size
    R = look(yaw, pitch)
    allp = np.concatenate([m[0] for m in meshes])
    c = allp.mean(0) if center is None else np.asarray(center)
    cam = [(m[0] - c) @ R.T for m in meshes]
    allc = np.concatenate(cam)
    if scale is None:
        ext = np.maximum(np.ptp(allc[:, 0]), np.ptp(allc[:, 1]) * W / H)
        scale = 0.9 * W / ext
    img = np.zeros((H, W, 3), np.float32) + np.array(bg, np.float32)
    zb = np.full((H, W), -1e9, np.float32)
    light = np.array([0.4, 0.5, 0.75])
    light /= np.linalg.norm(light)
    for (pos, tris, col), pc in zip(meshes, cam):
        if len(tris) == 0:
            continue
        sx = pc[:, 0] * scale + W / 2
        sy = H / 2 - pc[:, 1] * scale
        sz = pc[:, 2]
        wp = pos[tris]
        nrm = np.cross(wp[:, 1] - wp[:, 0], wp[:, 2] - wp[:, 0])
        nl = np.linalg.norm(nrm, axis=1, keepdims=True)
        nrm = nrm / np.maximum(nl, 1e-12)
        shade = 0.35 + 0.65 * np.abs(nrm @ light)
        pcol = np.asarray(col, np.float32)
        for k, t in enumerate(tris):
            x = sx[t]
            y = sy[t]
            z = sz[t]
            x0, x1 = int(max(0, np.floor(x.min()))), int(min(W - 1, np.ceil(x.max())))
            y0, y1 = int(max(0, np.floor(y.min()))), int(min(H - 1, np.ceil(y.max())))
            if x0 > x1 or y0 > y1:
                continue
            d = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
            if abs(d) < 1e-9 or (cull and np.sign(d) != cull):
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            w1 = ((gx - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (gy - y[0])) / d
            w2 = ((x[1] - x[0]) * (gy - y[0]) - (gx - x[0]) * (y[1] - y[0])) / d
            w0 = 1 - w1 - w2
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not m.any():
                continue
            zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            m &= zz > sub
            if not m.any():
                continue
            sub[m] = zz[m]
            if pcol.ndim == 2:
                cc = (pcol[t[0]] + pcol[t[1]] + pcol[t[2]]) / 3
            else:
                cc = pcol
            img[y0:y1 + 1, x0:x1 + 1][m] = cc * shade[k]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
