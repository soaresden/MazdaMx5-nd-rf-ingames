"""EA HUFF (0x30FB, Huffman with runlength) decoder, from the 47PADO47/nfs-mw format notes."""
import struct


class Bits:
    def __init__(self, data):
        self.d = data
        self.p = 0  # bit position

    def bit(self):
        byte = self.p >> 3
        v = (self.d[byte] >> (7 - (self.p & 7))) & 1 if byte < len(self.d) else 0
        self.p += 1
        return v

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def num(self):
        z = 0
        while self.bit() == 0:
            z += 1
            if z > 15:
                raise ValueError('corrupt number')
        v = self.bits(z + 2)
        return v + (1 << (z + 2)) - 4


def decompress(blob):
    assert blob[:4] == b'HUFF'
    out_size, comp_size = struct.unpack_from('<II', blob, 8)
    b = Bits(blob[16:16 + comp_size])
    typ = b.bits(16)
    w = 32 if typ & 0x8000 else 24
    if typ & 0x0100:
        b.bits(w)
    size = b.bits(w)
    clue = b.bits(8)
    first, count, index = [0], [0], [0]
    L = nxt = total = 0
    while True:
        L += 1
        nxt <<= 1
        c = b.num()
        first.append(nxt)
        count.append(c)
        index.append(total)
        nxt += c
        total += c
        if nxt == 1 << L:
            break
        if L > 16:
            raise ValueError('bad code table')
    maxlen = L
    used = [False] * 256
    syms = []
    cur = 0xFF
    for i in range(total):
        k = b.num() % (256 - i)
        steps = k + 1
        while steps:
            cur = (cur + 1) & 0xFF
            if not used[cur]:
                steps -= 1
        used[cur] = True
        syms.append(cur)
    out = bytearray()
    while True:
        c = 0
        s = None
        for l in range(1, maxlen + 1):
            c = (c << 1) | b.bit()
            if c - first[l] < count[l]:
                s = syms[index[l] + c - first[l]]
                break
        if s is None:
            raise ValueError('bad code')
        if s != clue:
            out.append(s)
            continue
        n = b.num()
        if n > 0:
            out.extend(bytes([out[-1]]) * n)
        elif b.bit():
            break
        else:
            out.append(b.bits(8))
    if typ & 0x0200 or typ & 0x0400:
        raise NotImplementedError('delta filters')
    if len(out) != out_size or size != out_size:
        raise ValueError('HUFF size %d, expected %d' % (len(out), out_size))
    return bytes(out)
