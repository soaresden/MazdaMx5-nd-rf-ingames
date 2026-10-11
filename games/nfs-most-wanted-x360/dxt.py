"""Small DXT1 / DXT5 (BC1 / BC3) encoder in numpy, for when Pillow cannot write DDS (the browser).

Endpoints: the ends of each 4x4 block's colour range along its main axis; always the 4-colour
mode of DXT1 (colour0 > colour1, or a single colour with every index 0), so that no texel is ever
the transparent black of the 3-colour mode.
"""
import numpy as np


def _blocks(a):
    """(h, w, c) -> (h/4 * w/4, 16, c), rows of blocks."""
    h, w, c = a.shape
    return a.reshape(h // 4, 4, w // 4, 4, c).transpose(0, 2, 1, 3, 4).reshape(-1, 16, c)


def _rgb565(c):
    c = np.clip(np.round(c), 0, 255).astype(np.uint32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)


def _unpack565(v):
    r = ((v >> 11) & 31) * 255 // 31
    g = ((v >> 5) & 63) * 255 // 63
    b = (v & 31) * 255 // 31
    return np.stack([r, g, b], -1).astype(np.float32)


def _colour_blocks(rgb):
    """rgb: (n, 16, 3) float -> (n, 8) uint8 DXT1 colour blocks."""
    mean = rgb.mean(1, keepdims=True)
    d = rgb - mean
    # main axis by a few power iterations on the 3x3 covariance
    cov = np.einsum('nki,nkj->nij', d, d)
    axis = np.ones((len(rgb), 3), np.float32)
    for _ in range(4):
        axis = np.einsum('nij,nj->ni', cov, axis)
        axis /= np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-9)
    t = np.einsum('nki,ni->nk', d, axis)
    lo = mean[:, 0] + axis * t.min(1, keepdims=True)
    hi = mean[:, 0] + axis * t.max(1, keepdims=True)
    c0, c1 = _rgb565(hi), _rgb565(lo)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    p0, p1 = _unpack565(c0), _unpack565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)  # (n, 4, 3)
    dist = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
    idx = dist.argmin(2).astype(np.uint32)
    idx[c0 == c1] = 0
    bits = (idx << (2 * np.arange(16, dtype=np.uint32))).sum(1).astype(np.uint32)
    out = np.zeros((len(rgb), 8), np.uint8)
    out[:, 0], out[:, 1] = c0 & 255, c0 >> 8
    out[:, 2], out[:, 3] = c1 & 255, c1 >> 8
    for k in range(4):
        out[:, 4 + k] = (bits >> (8 * k)) & 255
    return out


def _alpha_blocks(a):
    """a: (n, 16) float -> (n, 8) uint8 DXT5 alpha blocks (8-value mode)."""
    a0 = np.clip(np.round(a.max(1)), 0, 255).astype(np.int32)
    a1 = np.clip(np.round(a.min(1)), 0, 255).astype(np.int32)
    k = np.arange(8)
    w = np.array([0, 7, 1, 2, 3, 4, 5, 6])  # palette index -> weight of a1 over 7
    pal = (a0[:, None] * (7 - w) + a1[:, None] * w) / 7.0  # index 0 = a0, 1 = a1, 2..7 between
    pal[a0 == a1] = a0[a0 == a1, None]
    idx = np.abs(a[:, :, None] - pal[:, None, :]).argmin(2).astype(np.uint64)
    bits = (idx << (3 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.zeros((len(a), 8), np.uint8)
    out[:, 0], out[:, 1] = a0, a1
    for i in range(6):
        out[:, 2 + i] = ((bits >> np.uint64(8 * i)) & np.uint64(255)).astype(np.uint8)
    return out


def encode(img, fmt):
    """PIL image (w, h multiples of 4) -> linear DXT1 or DXT5 blocks, little endian."""
    a = np.asarray(img.convert('RGBA'), np.float32)
    b = _blocks(a)
    colour = _colour_blocks(b[..., :3])
    if fmt == 'DXT1':
        return colour.tobytes()
    return np.concatenate([_alpha_blocks(b[..., 3]), colour], 1).tobytes()
