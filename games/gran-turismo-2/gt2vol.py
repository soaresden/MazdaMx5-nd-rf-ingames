"""GT2.VOL, the archive of Gran Turismo 2's Simulation disc: read files by path, and write it again
with some files replaced (streamed: the VOL is about 490 MB).

  0x00 "GTFS", 4 zero bytes, u16 offset count, u16 directory entry count, 4 zero bytes
  0x10 u32 per file: start (a multiple of 2048) | bytes of padding after the file (low 11 bits);
       the last one is the end of the VOL. File 0 is this header, file 1 the directory.
  directory: 32 bytes per entry: u32 time, u16 index, u8 flags, 25 bytes of name. A file's index
       is its offset index; a directory's (flags & 1) the entry its list starts at (with ".." first);
       flags & 0x80: the last entry of its directory. The root's list starts at entry 0.
A file's size is the next file's start - its start - its padding.
"""
import struct

SECTOR = 2048


class Vol:
    def __init__(self, read):
        """read(offset, size) -> bytes of the VOL."""
        self._read = read
        h = read(0, 16)
        if h[:4] != b'GTFS':
            raise ValueError("ce n'est pas un GT2.VOL (en-tête %r)" % h[:4])
        n, self.entries = struct.unpack_from('<HH', h, 8)
        self.offsets = list(struct.unpack_from('<%dI' % n, read(16, 4 * n)))
        toc = read(self.start(1), self.size(1))
        self.toc = toc
        self.paths = {}
        self._walk(toc, 0, '')

    def start(self, i):
        return self.offsets[i] & ~(SECTOR - 1)

    def size(self, i):
        return self.start(i + 1) - self.start(i) - (self.offsets[i] & (SECTOR - 1))

    @property
    def end(self):
        return self.start(len(self.offsets) - 1)

    def _walk(self, toc, first, path):
        k = first
        while True:
            _, idx, flags = struct.unpack_from('<IHB', toc, 32 * k)
            name = toc[32 * k + 7:32 * k + 32].split(b'\0')[0].decode('latin-1')
            if name != '..':
                full = path + name
                if flags & 1:
                    self._walk(toc, idx, full + '/')
                else:
                    self.paths[full] = idx
            if flags & 0x80:
                break
            k += 1

    def read(self, path):
        i = self.paths[path]
        return self._read(self.start(i), self.size(i))

    def layout(self, replace):
        """New offsets for the files of `replace` ({path: bytes}) put in place of the old ones."""
        new = {self.paths[p]: d for p, d in replace.items()}
        offs, pos = [], 0
        for i in range(len(self.offsets) - 1):
            size = len(new[i]) if i in new else self.size(i)
            sectors = (size + SECTOR - 1) // SECTOR
            offs.append(pos | (sectors * SECTOR - size))
            pos += sectors * SECTOR
        offs.append(pos)
        return offs, new

    def sectors(self, replace, chunk=256):
        """The new VOL, `chunk` sectors (or fewer) at a time."""
        offs, new = self.layout(replace)
        head = bytearray(self._read(0, self.size(0)))
        struct.pack_into('<%dI' % len(offs), head, 16, *offs)
        new[0] = bytes(head)
        for i in range(len(offs) - 1):
            if i in new:
                d = new[i]
                d += b'\0' * (-len(d) % SECTOR)
                for o in range(0, len(d), chunk * SECTOR):
                    yield d[o:o + chunk * SECTOR]
                continue
            start, size = self.start(i), self.size(i)
            total = (size + SECTOR - 1) // SECTOR * SECTOR
            # the old padding bytes are copied as they were
            for o in range(0, total, chunk * SECTOR):
                yield self._read(start + o, min(chunk * SECTOR, total - o))

    def new_size(self, replace):
        return self.layout(replace)[0][-1]
