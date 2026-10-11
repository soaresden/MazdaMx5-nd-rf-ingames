"""Xbox 360 (Xenos) texture tiling for block-compressed formats."""
import numpy as np


def tiled_offset(x, y, aligned_w, texel_pitch):
    log_bpp = (texel_pitch >> 2) + ((texel_pitch >> 1) >> (texel_pitch >> 2))
    macro = ((x >> 5) + (y >> 5) * (aligned_w >> 5)) << (log_bpp + 7)
    micro = ((x & 7) + ((y & 6) << 2)) << log_bpp
    off = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 8) << (3 + log_bpp)) + ((y & 1) << 4)
    return (((off & ~511) << 3) + ((off & 448) << 2) + (off & 63) + ((y & 16) << 7)
            + (((((y & 8) >> 2) + (x >> 3)) & 3) << 6)) >> log_bpp


def _map(wb, hb, bpb):
    aw = (wb + 31) & ~31
    ah = (hb + 31) & ~31
    idx = np.empty((hb, wb), dtype=np.int64)
    for y in range(hb):
        for x in range(wb):
            idx[y, x] = tiled_offset(x, y, aw, bpb)
    return idx, aw * ah


def untile(data, w, h, bpb):
    """360 tiled, 16-bit big-endian blocks -> linear little-endian blocks (DXT)."""
    wb, hb = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    idx, total = _map(wb, hb, bpb)
    a = np.frombuffer(data[:total * bpb], dtype=np.uint8).reshape(total, bpb)
    lin = a[idx.reshape(-1)]
    lin = lin.reshape(-1, 2)[:, ::-1].reshape(-1)  # swap bytes of each 16-bit word
    return lin.tobytes()


def tile(data, w, h, bpb):
    """Linear little-endian DXT blocks -> 360 tiled, 16-bit swapped, padded to 32x32 blocks."""
    wb, hb = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    idx, total = _map(wb, hb, bpb)
    lin = np.frombuffer(data, dtype=np.uint8).reshape(-1, 2)[:, ::-1].reshape(-1, bpb)
    out = np.zeros((total, bpb), dtype=np.uint8)
    out[idx.reshape(-1)] = lin[:wb * hb]
    return out.tobytes()
