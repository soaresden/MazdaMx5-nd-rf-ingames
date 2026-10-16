"""Gran Turismo 2's Simulation disc (or a combined disc) with GT2.VOL written again.

The new VOL stays where the old one starts. When it is bigger, the files after it (MUSIC.DAT,
STREAM.DAT or FAULTY.PSX) move down by the sectors it gained: their directory records and the
volume size in the primary volume descriptor follow, and their sectors get their new address in
the header (mode 2: the EDC and ECC do not cover the header, they stay valid). The game finds its
files by name: the combined discs, whose files are not where the Simulation disc has them, run the
same program. (The VOL cannot go after the last file instead: the console addresses sectors in
minutes up to 99, and a second VOL would take the disc past that.)
New VOL sectors: mode 2 form 1, the subheader of the old VOL's sectors, EDC and ECC computed.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'gran-turismo-ps1'), os.path.join(HERE, '..', '..', 'common')):
    if p not in sys.path:
        sys.path.insert(0, p)

import disc      # noqa: E402
import gt2vol    # noqa: E402

VOL = 'GT2.VOL'
CHUNK = 512      # sectors written at a time
MAX_FRAMES = 99 * 60 * 75 - 150   # the last address a disc can have (99:59:74)


def _bcd(n):
    return ((n // 10) << 4) | (n % 10)


def msf(lba):
    """Header address of sector lba: minute, second, frame of lba + 150, in BCD."""
    m, r = divmod(lba + 150, 75 * 60)
    s, f = divmod(r, 75)
    return bytes([_bcd(m), _bcd(s), _bcd(f)])


def sector_header(lba, subheader):
    """Sync, address, mode 2, subheader."""
    return b'\x00' + b'\xff' * 10 + b'\x00' + msf(lba) + b'\x02' + subheader


class Gt2Disc(disc.Disc):
    def __init__(self, image):
        super().__init__(image)
        if VOL not in self.files:
            raise ValueError("pas de GT2.VOL sur ce disque : ce n'est pas le disque Simulation de Gran Turismo 2")
        self.vol_lba, self.vol_size = self.files[VOL][:2]
        self.vol = gt2vol.Vol(self._vol_read)

    def _vol_read(self, offset, size):
        first, skip = divmod(offset, 2048)
        n = (skip + size + 2047) // 2048
        return self.c.read(self.vol_lba + first, n)[skip:skip + size]

    def plan(self, replace):
        """(new VOL size, sectors the files after it move down by)."""
        size = self.vol.new_size(replace)
        old = (self.vol_size + 2047) // 2048
        return size, max(0, size // 2048 - old) if size > self.room(VOL) else 0

    def bin_chunks(self, replace, progress=None):
        """The new image, raw 2352-byte sectors, a chunk at a time; replace: {VOL path: bytes}."""
        size, delta = self.plan(replace)
        n_vol = size // 2048
        vol_end = self.vol_lba + n_vol
        total = self.c.frames + delta
        if total > MAX_FRAMES:
            raise ValueError('image trop grande pour un CD (%d secteurs)' % total)
        old_end = self.vol_lba + (self.vol_size + 2047) // 2048
        first_sub = self.c.sector(self.vol_lba)[16:24]
        last_sub = self.c.sector(old_end - 1)[16:24]
        # directory records to change: GT2.VOL's size, the files after it moved down
        records = {}
        for name, (lba, fsize, dlba, doff) in self.files.items():
            if name == VOL:
                records.setdefault(dlba, []).append((doff, lba, size))
            elif delta and lba >= old_end:
                records.setdefault(dlba, []).append((doff, lba + delta, fsize))
        new_vol = self.vol.sectors(replace, CHUNK)
        pending = b''

        def vol_data(count):
            nonlocal pending
            while len(pending) < count * 2048:
                pending += next(new_vol)
            out, pending = pending[:count * 2048], pending[count * 2048:]
            return out

        for start in range(0, total, CHUNK):
            stop = min(total, start + CHUNK)
            raws, todo, datas = [], [], []
            n_new = 0
            for k, s in enumerate(range(start, stop)):
                if self.vol_lba <= s < vol_end:
                    # header from the sector's number, the old VOL's subheader (its last one, with
                    # the end of file flags, for the last sector)
                    raws.append(sector_header(s, last_sub if s == vol_end - 1 else first_sub).ljust(2352, b'\0'))
                    todo.append(k)
                    datas.append(None)
                    n_new += 1
                    continue
                if s >= vol_end:
                    raw = self.c.sector(s - delta)
                    if delta:
                        raw = raw[:12] + msf(s) + raw[15:]
                    raws.append(raw)
                    continue
                raw = self.c.sector(s)
                raws.append(raw)
                if s == 16 and delta:
                    d = bytearray(raw[24:24 + 2048])
                    struct.pack_into('<I', d, 80, total)
                    struct.pack_into('>I', d, 84, total)
                    todo.append(k)
                    datas.append(bytes(d))
                elif s in records:
                    d = bytearray(raw[24:24 + 2048])
                    for doff, lba, fsize in records[s]:
                        struct.pack_into('<I', d, doff + 2, lba)
                        struct.pack_into('>I', d, doff + 6, lba)
                        struct.pack_into('<I', d, doff + 10, fsize)
                        struct.pack_into('>I', d, doff + 14, fsize)
                    todo.append(k)
                    datas.append(bytes(d))
            if n_new:
                vd = vol_data(n_new)
                j = 0
                for i, x in enumerate(datas):
                    if x is None:
                        datas[i] = vd[j * 2048:(j + 1) * 2048]
                        j += 1
            if todo:
                for k, new in zip(todo, disc.make_sectors([raws[k] for k in todo], datas)):
                    raws[k] = new
            yield b''.join(raws)
            if progress:
                progress(stop, total)

    def write_bin(self, path, replace, progress=None):
        part = path + '.part'
        with open(part, 'wb') as f:
            for b in self.bin_chunks(replace, progress=progress):
                f.write(b)
        os.replace(part, path)
        with open(os.path.splitext(path)[0] + '.cue', 'w', newline='') as f:
            f.write(self.cue(os.path.basename(path)))
