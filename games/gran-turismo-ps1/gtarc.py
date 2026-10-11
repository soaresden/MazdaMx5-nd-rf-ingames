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


def compress(data, window=0x7FFF, max_len=258):
    """Greedy LZSS with a hash chain; output decodes with decompress()."""
    out = bytearray()
    n = len(data)
    heads = {}
    prev = [-1] * n
    i = 0

    def insert(p):
        if p + 3 <= n:
            k = data[p:p + 3]
            prev[p] = heads.get(k, -1)
            heads[k] = p

    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = 0
            best_d = 0
            if i + 3 <= n:
                p = heads.get(data[i:i + 3], -1)
                tries = 64
                limit = min(max_len, n - i)
                while p >= 0 and i - p <= window and tries:
                    l = 3
                    while l < limit and data[p + l] == data[i + l]:
                        l += 1
                    if l > best_len:
                        best_len, best_d = l, i - p
                        if l == limit:
                            break
                    p = prev[p]
                    tries -= 1
            if best_len >= 3 and not (best_len == 3 and best_d > 128):
                flags |= 1 << bit
                out.append(best_len - 3)
                d = best_d - 1
                if d < 0x80:
                    out.append(d)
                else:
                    out += bytes((0x80 | d >> 8, d & 0xFF))
                for k in range(best_len):
                    insert(i + k)
                i += best_len
            else:
                out.append(data[i])
                insert(i)
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
