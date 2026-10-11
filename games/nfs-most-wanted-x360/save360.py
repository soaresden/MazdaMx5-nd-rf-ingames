"""Edit an Xbox 360 NFS Most Wanted career save (also on the Switch port nfsmw-nx).

python save360.py <save> [--money N] [--unlock-all] [--out <file>]

The save (`MC02`, 62,688 bytes) has the PC layout with big-endian values. Two checks must be
rewritten after any change, in this order:
- MD5 of [0x34, end - 16) in the last 16 bytes;
- three EA CRC32s, big-endian: 0x10 over [0x1C, 0x24), 0x14 over [0x24, end), then 0x18 over
  [0x00, 0x18) (it covers the first two). Without them the game says the save is damaged.

--unlock-all sets CareerModeHasBeenCompletedAtLeastOnce (0xE895, PC 0xE88D). The unlock checks
(CareerUnlocker, from the NFS MW decompilation) treat every part, performance level and decal
location as unlocked when it is set; career progress, cars and markers are not changed.
"""
import argparse
import hashlib
import struct

SIZE = 62688
MONEY = 0x4039
CAREER_COMPLETED_ONCE = 0xE895

_T = []
for _i in range(256):
    _c = _i << 24
    for _ in range(8):
        _c = ((_c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if _c & 0x80000000 else (_c << 1) & 0xFFFFFFFF
    _T.append(_c)


def ea_crc32(d):
    crc = ~int.from_bytes(d[:4], 'big') & 0xFFFFFFFF
    for b in d[4:]:
        crc = ((((crc << 8) & 0xFFFFFFFF) | b) ^ _T[crc >> 24]) & 0xFFFFFFFF
    return ~crc & 0xFFFFFFFF


def fix(d):
    d = bytearray(d)
    d[-16:] = hashlib.md5(d[0x34:-16]).digest()
    struct.pack_into('>I', d, 0x10, ea_crc32(d[0x1C:0x24]))
    struct.pack_into('>I', d, 0x14, ea_crc32(d[0x24:]))
    struct.pack_into('>I', d, 0x18, ea_crc32(d[0x00:0x18]))
    return bytes(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('save')
    ap.add_argument('--money', type=int)
    ap.add_argument('--unlock-all', action='store_true')
    ap.add_argument('--out', help='output file (default: overwrite the save)')
    a = ap.parse_args()
    d = bytearray(open(a.save, 'rb').read())
    if d[:4] != b'MC02' or len(d) != SIZE:
        raise SystemExit('not an Xbox 360 NFS MW save (MC02, %d bytes)' % SIZE)
    if fix(d) != bytes(d):
        print('warning: the checksums of the input do not match (already edited?)')
    print('money %d, unlock-all flag %d' % (struct.unpack_from('>I', d, MONEY)[0], d[CAREER_COMPLETED_ONCE]))
    if a.money is not None:
        struct.pack_into('>I', d, MONEY, a.money)
    if a.unlock_all:
        d[CAREER_COMPLETED_ONCE] = 1
    out = fix(d)
    open(a.out or a.save, 'wb').write(out)
    print('written %s: money %d, unlock-all flag %d' % (a.out or a.save, struct.unpack_from('>I', out, MONEY)[0],
                                                       out[CAREER_COMPLETED_ONCE]))


if __name__ == '__main__':
    main()
