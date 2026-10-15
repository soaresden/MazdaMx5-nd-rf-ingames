"""Apply an xdelta3 patch (VCDIFF, RFC 3284) to a file, in pure Python: the window loop, the default
code table, the near/same address caches and xdelta3's application header and Adler-32 checksum.

python vcdiff.py <source> <patch.xdelta> <target>

Not supported (refused with a message): secondary compression (xdelta3 -S djw / lzma / fgk) and
custom code tables. Patches made with xdelta3 -S none, as Gran Turismo 2 plus's, use neither.
"""
import os
import struct
import sys
import zlib

VCD_SOURCE, VCD_TARGET, VCD_ADLER32 = 0x01, 0x02, 0x04
NEAR, SAME = 4, 3


def _varint(b, p):
    v = 0
    while True:
        c = b[p]
        p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def _code_table():
    """RFC 3284 section 5.6: [(type1, size1, mode1, type2, size2, mode2)] for the 256 codes;
    types: 0 NOOP, 1 ADD, 2 RUN, 3 COPY."""
    t = [(2, 0, 0, 0, 0, 0)]                                   # 0: RUN size 0
    t += [(1, s, 0, 0, 0, 0) for s in [0] + list(range(1, 18))]  # 1-18: ADD 0, 1..17
    for mode in range(9):
        t.append((3, 0, mode, 0, 0, 0))                        # COPY size 0
        t += [(3, s, mode, 0, 0, 0) for s in range(4, 19)]     # COPY 4..18
    for mode in range(6):                                      # ADD + COPY, near/self modes
        for a in range(1, 5):
            t += [(1, a, 0, 3, c, mode) for c in range(4, 7)]
    for mode in range(6, 9):                                   # ADD + COPY, same modes
        for a in range(1, 5):
            t.append((1, a, 0, 3, 4, mode))
    for mode in range(9):                                      # COPY 4 + ADD 1
        t.append((3, 4, mode, 1, 1, 0))
    assert len(t) == 256, len(t)
    return t


TABLE = _code_table()


class _Addr:
    def __init__(self):
        self.near = [0] * NEAR
        self.next = 0
        self.same = [0] * (SAME * 256)

    def update(self, addr):
        self.near[self.next] = addr
        self.next = (self.next + 1) % NEAR
        self.same[addr % (SAME * 256)] = addr

    def decode(self, here, mode, data, p):
        if mode == 0:
            addr, p = _varint(data, p)
        elif mode == 1:
            v, p = _varint(data, p)
            addr = here - v
        elif mode < 2 + NEAR:
            v, p = _varint(data, p)
            addr = self.near[mode - 2] + v
        else:
            m = mode - (2 + NEAR)
            addr = self.same[m * 256 + data[p]]
            p += 1
        self.update(addr)
        return addr, p


def apply(source, patch, out, log=print):
    with open(patch, 'rb') as f:
        d = f.read()
    if d[:3] != b'\xd6\xc3\xc4':
        raise SystemExit("ce n'est pas un patch xdelta (VCDIFF)")
    hdr = d[4]
    p = 5
    if hdr & 0x01:
        raise SystemExit('compression secondaire (xdelta3 -S) : non gérée')
    if hdr & 0x02:
        raise SystemExit('table de codes personnalisée : non gérée')
    if hdr & 0x04:                                   # application header (xdelta3: file names)
        n, p = _varint(d, p)
        p += n
    src = open(source, 'rb')
    written = 0
    with open(out + '.part', 'wb') as o:
        while p < len(d):
            win = d[p]
            p += 1
            seg = b''
            if win & (VCD_SOURCE | VCD_TARGET):
                slen, p = _varint(d, p)
                spos, p = _varint(d, p)
                if win & VCD_SOURCE:
                    src.seek(spos)
                    seg = src.read(slen)
                else:
                    o.flush()
                    with open(out + '.part', 'rb') as t:
                        t.seek(spos)
                        seg = t.read(slen)
            dlen, p = _varint(d, p)
            dend = p + dlen
            tlen, p = _varint(d, p)
            ind = d[p]
            p += 1
            if ind:
                raise SystemExit('fenêtre compressée (compression secondaire) : non gérée')
            alen, p = _varint(d, p)
            ilen, p = _varint(d, p)
            clen, p = _varint(d, p)
            adler = None
            if win & VCD_ADLER32:
                adler, = struct.unpack_from('>I', d, p)
                p += 4
            data, inst, addr = d[p:p + alen], d[p + alen:p + alen + ilen], d[p + alen + ilen:p + alen + ilen + clen]
            p = dend
            target = bytearray()
            cache = _Addr()
            dp = ip = ap = 0
            slen = len(seg)
            while ip < len(inst):
                code = inst[ip]
                ip += 1
                ent = TABLE[code]
                for typ, size, mode in ((ent[0], ent[1], ent[2]), (ent[3], ent[4], ent[5])):
                    if typ == 0:
                        continue
                    if size == 0:
                        size, ip = _varint(inst, ip)
                    if typ == 1:                         # ADD
                        target += data[dp:dp + size]
                        dp += size
                    elif typ == 2:                       # RUN
                        target += data[dp:dp + 1] * size
                        dp += 1
                    else:                                # COPY from source segment or target so far
                        here = slen + len(target)
                        a, ap = cache.decode(here, mode, addr, ap)
                        if a + size <= slen:
                            target += seg[a:a + size]
                        else:
                            for k in range(size):        # may overlap what it writes
                                x = a + k
                                target.append(seg[x] if x < slen else target[x - slen])
            if len(target) != tlen:
                raise SystemExit('fenêtre de %d octets au lieu de %d' % (len(target), tlen))
            if adler is not None and zlib.adler32(bytes(target)) & 0xFFFFFFFF != adler:
                raise SystemExit('somme Adler-32 fausse : ce patch ne va pas avec ce fichier source')
            o.write(target)
            written += len(target)
            if written >> 26 != (written - len(target)) >> 26:
                log('  %s : %d Mo' % (os.path.basename(out), written >> 20))
    src.close()
    os.replace(out + '.part', out)
    log('  %s : %d octets' % (os.path.basename(out), written))
    return written


if __name__ == '__main__':
    apply(*sys.argv[1:4])
