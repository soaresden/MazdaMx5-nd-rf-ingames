"""Xbox disc images (XDVDFS) of NFS Underground 1 and 2 with the names' case kept: the ports read
the extracted disc from the SD card, whose file names are case-sensitive."""
import os
import struct

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'
PARTITIONS = (0, 0x18300000, 0xFD90000, 0x2080000)   # plain XISO, Xbox (redump), XGD2, XGD3


def _partition(f):
    for base in PARTITIONS:
        f.seek(base + 32 * SECTOR)
        if f.read(len(MAGIC)) == MAGIC:
            return base
    raise ValueError("pas une image de disque Xbox (XDVDFS)")


def tree(iso):
    """{path as on the disc: (size, offset in the image)}; directories end with '/' (size None)."""
    out = {}
    with open(iso, 'rb') as f:
        base = _partition(f)
        f.seek(base + 32 * SECTOR + 20)
        root, root_size = struct.unpack('<II', f.read(8))

        def walk(sector, size, prefix):
            f.seek(base + sector * SECTOR)
            data = f.read(size)
            stack, seen = [0], set()
            while stack:
                off = stack.pop()
                if off in seen or off + 14 > len(data):
                    continue
                seen.add(off)
                left, right, start, length, attr, n = struct.unpack_from('<HHIIBB', data, off)
                if left == 0xFFFF and right == 0xFFFF:
                    continue
                name = data[off + 14:off + 14 + n].decode('latin-1')
                if attr & 0x10:
                    out[prefix + name + '/'] = (None, None)
                    if length:
                        walk(start, length, prefix + name + '/')
                else:
                    out[prefix + name] = (length, base + start * SECTOR)
                for k in (left, right):
                    if k:
                        stack.append(k * 4)
        walk(root, root_size, '')
    return out


def find(t, path):
    """The disc's spelling of `path` (any case), or None."""
    up = path.replace('\\', '/').upper()
    for k in t:
        if k.upper() == up:
            return k
    return None


def read(iso, entry):
    size, off = entry
    with open(iso, 'rb') as f:
        f.seek(off)
        return f.read(size)


def copy(iso, entry, dst):
    size, off = entry
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(iso, 'rb') as f, open(dst, 'wb') as o:
        f.seek(off)
        left = size
        while left:
            b = f.read(min(left, 8 << 20))
            if not b:
                raise IOError('image tronquée : ' + dst)
            o.write(b)
            left -= len(b)


def extract(iso, dst, log=print):
    """The whole disc into dst, names as on the disc. Returns the tree."""
    t = tree(iso)
    files = sorted(k for k, (size, _) in t.items() if size is not None)
    total = sum(t[k][0] for k in files)
    done = 0
    for i, k in enumerate(files):
        copy(iso, t[k], os.path.join(dst, *k.split('/')))
        done += t[k][0]
        if i % 200 == 0 or i == len(files) - 1:
            log('  disque : %d/%d fichiers, %d Mo sur %d' % (i + 1, len(files), done >> 20, total >> 20))
    for k, (size, _) in t.items():
        if size is None:
            os.makedirs(os.path.join(dst, *k.rstrip('/').split('/')), exist_ok=True)
    return t
