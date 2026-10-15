"""Gran Turismo 2 car textures (carobj/<car>.cdp, .cnp for the night version): 45984 bytes.

From pez2k's CDP2TIM: byte 0 the number of paints; from 0x20, per paint 0x240 bytes: 16 palettes
(CLUTs) of 16 PlayStation colours (15-bit BGR + the transparency bit), each polygon picking one; from
0x43A0 the image, 256 x 224 pixels at 4 bits (low nibble first), shared by every paint.
"""
import numpy as np

SIZE = 45984
PALETTES = 0x20
PAINT = 0x240
IMAGE = 0x43A0
W, H = 256, 224


class Texture:
    def __init__(self, d):
        if len(d) != SIZE:
            raise ValueError('texture de %d octets (%d attendus)' % (len(d), SIZE))
        self.d = bytearray(d)
        self.paints = d[0]

    def index_image(self):
        b = np.frombuffer(bytes(self.d[IMAGE:IMAGE + W * H // 2]), np.uint8)
        out = np.empty(W * H, np.uint8)
        out[0::2], out[1::2] = b & 15, b >> 4
        return out.reshape(H, W)

    def cluts(self, paint=0):
        """(16, 16, 4) RGBA uint8 of a paint's 16 palettes (alpha 0 for the transparent black 0x0000)."""
        o = PALETTES + paint * PAINT
        c = np.frombuffer(bytes(self.d[o:o + 512]), '<u2').reshape(16, 16)
        rgb = np.stack([(c & 31), (c >> 5) & 31, (c >> 10) & 31], -1).astype(np.uint16) * 255 // 31
        a = np.where(c == 0, 0, 255)[..., None]
        return np.concatenate([rgb, a], -1).astype(np.uint8)

    def rgba(self, clut, paint=0):
        """The whole image seen through one palette."""
        return self.cluts(paint)[clut][self.index_image()]

    def set_image(self, idx):
        idx = np.asarray(idx, np.uint8).reshape(-1)
        self.d[IMAGE:IMAGE + W * H // 2] = (idx[0::2] | (idx[1::2] << 4)).tobytes()

    def set_clut(self, paint, clut, colours):
        """colours: 16 PlayStation words."""
        o = PALETTES + paint * PAINT + clut * 32
        self.d[o:o + 32] = np.asarray(colours, '<u2').tobytes()

    def bytes(self):
        return bytes(self.d)


def ps_colour(r, g, b, stp=False):
    """A 15-bit PlayStation colour; pure black is 0x0000 = transparent, so it becomes 1/31 dark."""
    v = (r * 31 // 255) | ((g * 31 // 255) << 5) | ((b * 31 // 255) << 10) | (0x8000 if stp else 0)
    return v or 0x0421
