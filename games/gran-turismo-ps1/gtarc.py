"""Gran Turismo (PS1) archives: "@(#)GT-ARC" containers and their LZSS compression.

GT-ARC layout:
  0x00  "@(#)GT-ARC" + u16 0
  0x0C  u8 1, u8 flags (0x80: some entries are compressed), u16 entry count
  0x10  entries of 12 bytes: u32 offset, u32 stored size, u32 size (compressed when they differ)
No names: entries are known by their index. A whole file (CARINF.DAT) may itself be compressed.

LZSS: a flag byte for each 8 items, low bit first; 0 = a literal byte, 1 = a reference made of a
length byte (+3) and a distance (one byte + 1, or, if its top bit is set, 15 bits on two bytes,
+ 1) back into what was already written.
"""
import struct

MAGIC = b'@(#)GT-ARC'


def decompress(src, size=None):
    out = bytearray()
    i = 0
    n = len(src)
    while i < n and (size is None or len(out) < size):
        flags = src[i]
        i += 1
        for bit in range(8):
            if i >= n or (size is not None and len(out) >= size):
                break
            if flags >> bit & 1:
                length = src[i] + 3
                d = src[i + 1]
                if d & 0x80:
                    d = ((d & 0x7F) << 8 | src[i + 2]) + 1
                    i += 3
                else:
                    d += 1
                    i += 2
                start = len(out) - d
                for k in range(length):
                    out.append(out[start + k])
            else:
                out.append(src[i])
                i += 1
    return bytes(out)


def literal(data):
    """'Compression' with literals only (9/8 of the size): always accepted by the game's decoder."""
    out = bytearray()
    for i in range(0, len(data), 8):
        out.append(0)
        out += data[i:i + 8]
    return bytes(out)


def _matches(data, window, max_len, tries):
    """For each position: (longest match length, its distance, longest match length within 128
    bytes, its distance), by hash chains."""
    n = len(data)
    heads = {}
    prev = [-1] * n
    ml = [0] * n
    md = [0] * n
    sl = [0] * n
    sd = [0] * n
    for i in range(n - 2):
        k = data[i:i + 3]
        p = heads.get(k, -1)
        prev[i] = p
        heads[k] = i
        limit = min(max_len, n - i)
        bl = bd = 0
        sbl = sbd = 0
        t = tries
        while p >= 0 and i - p <= window and t:
            l = 3
            while l < limit and data[p + l] == data[i + l]:
                l += 1
            d = i - p
            if l > bl:
                bl, bd = l, d
            if d <= 128 and l > sbl:
                sbl, sbd = l, d
            if bl == limit:
                break
            p = prev[p]
            t -= 1
        ml[i], md[i], sl[i], sd[i] = bl, bd, sbl, sbd
    return ml, md, sl, sd


def compress(data, window=0x7FFF, max_len=258, tries=48):
    """LZSS with an optimal parse of the matches found (costs in bits: literal 9, match within
    128 bytes 17, farther 25, flag bits included); output decodes with decompress()."""
    data = bytes(data)
    n = len(data)
    ml, md, sl, sd = _matches(data, window, max_len, tries)
    INF = 1 << 60
    cost = [0] * (n + 1)
    choice = [0] * n   # 0: literal, else (length << 1) | short
    for i in range(n - 1, -1, -1):
        best = 9 + cost[i + 1]
        ch = 0
        L = ml[i]
        if L >= 3:
            S = sl[i]
            for l in range(3, L + 1):
                c = (17 if l <= S else 25) + cost[i + l]
                if c < best:
                    best, ch = c, (l << 1) | (l <= S)
        cost[i] = best
        choice[i] = ch
    out = bytearray()
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            ch = choice[i]
            if ch:
                l, short = ch >> 1, ch & 1
                d = (sd[i] if short else md[i]) - 1
                flags |= 1 << bit
                out.append(l - 3)
                if d < 0x80:
                    out.append(d)
                else:
                    out += bytes((0x80 | d >> 8, d & 0xFF))
                i += l
            else:
                out.append(data[i])
                i += 1
        out[flag_pos] = flags
    return bytes(out)


class Arc:
    def __init__(self, data):
        if data[1:9] == MAGIC[:8] and data[:1] == b'\0':
            data = decompress(data)  # the whole archive is compressed
        if data[:10] != MAGIC:
            raise ValueError('not a GT-ARC')
        self.data = data
        self.version, self.flags, count = struct.unpack_from('<BBH', data, 12)
        self.entries = [struct.unpack_from('<III', data, 16 + 12 * i) for i in range(count)]

    def __len__(self):
        return len(self.entries)

    def raw(self, i):
        off, stored, _ = self.entries[i]
        return self.data[off:off + stored]

    def __getitem__(self, i):
        off, stored, size = self.entries[i]
        b = self.data[off:off + stored]
        return b if stored == size else decompress(b, size)

    def compressed(self, i):
        return self.entries[i][1] != self.entries[i][2]


def replace(arc, new, align=0x800):
    """The archive with some entries replaced ({index: uncompressed bytes}, stored compressed);
    the other entries are copied as they are stored. Entries start on `align` boundaries."""
    count = len(arc)
    off = (16 + 12 * count + align - 1) // align * align
    table = bytearray()
    body = bytearray()
    for i in range(count):
        if i in new:
            size = len(new[i])
            # compressed if the entry was: the game decompresses some files whatever the sizes
            # say (a menu page stored 21102 bytes compressed for 20276); stored raw only if it was
            stored = compress(new[i]) if arc.compressed(i) else new[i]
            if len(stored) == size and arc.compressed(i):
                stored += b'\0'          # stored == size would read as "not compressed"
        else:
            stored, size = arc.raw(i), arc.entries[i][2]
        table += struct.pack('<III', off + len(body), len(stored), size)
        body += stored
        body += b'\0' * (-len(body) % align)
    head = bytearray(arc.data[:16]) + table
    head += b'\0' * (off - len(head))
    return bytes(head + body)


def build(files, compressed, align=0x800, version=1):
    """A GT-ARC from a list of (uncompressed) files; compressed[i] says which ones to compress."""
    count = len(files)
    off = 16 + 12 * count
    off = (off + align - 1) // align * align
    table = bytearray()
    body = bytearray()
    flags = 0
    for f, c in zip(files, compressed):
        stored = compress(f) if c else f
        if c:
            flags = 0x80
        table += struct.pack('<III', off + len(body), len(stored), len(f))
        body += stored
        body += b'\0' * (-len(body) % align)
    head = MAGIC + b'\0\0' + struct.pack('<BBH', version, flags, count) + table
    head += b'\0' * ((16 + 12 * count + align - 1) // align * align - len(head))
    return bytes(head + body)
