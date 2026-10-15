"""A new Xbox 360 disc image of Most Wanted with folders laid over the disc's files: the French
dub of nfsmw-nx (tools/french-dub: NFS/ZDIR.BIN, ZZDATA0, ZZDATA9 and the French movies) and
the MX-5 RF (CARS/IS300, GLOBAL/GLOBALMEMORYFILE.BIN, FRONTEND/FRONTB.LZC), for Xenia.

python make_iso.py --iso "<X360 Most Wanted>.iso" --add <game_root> [--add <game_root> ...] --out <new>.iso
                   [--keep-pad]

Each --add folder is laid over the disc in order (the last one wins), names matched without case;
files that are not on the disc are added. The game opens a loose file before looking in the
ZZDATA archives, with the size ZDIR.BIN gives: the loose files are checked against it. The
NFS/PAD*.BIN files (filler that places the data on the real disc) are left out unless
--keep-pad. Written as a plain XDVDFS image (file system at sector 32 of the file), which Xenia
reads; nothing is written in the source image.
"""
import argparse
import hashlib
import os
import struct
import sys

import zzdata

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'
SKIP = ('.txt', '.png', '.md')                 # notes next to the data, not game files
SKIP_NAMES = {'COPSPEECH_IDX_ORIGINE.BIN'}      # the French dub's backup of the English index


class Node:
    def __init__(self, name, src=None, size=0):
        self.name, self.src, self.size = name, src, size      # src: ('iso', offset) or ('file', path)
        self.children = None if src else {}
        self.sector = 0


def disc_tree(iso):
    """Root Node of the image, names as on the disc, plus the volume's time stamp."""
    with open(iso, 'rb') as f:
        for base in (0, 0x18300000, 0xFD90000, 0x2080000):
            f.seek(base + 32 * SECTOR)
            if f.read(20) == MAGIC:
                break
        else:
            raise SystemExit("pas une image de disque Xbox / Xbox 360")
        root_sector, root_size, stamp = struct.unpack('<II8s', f.read(16))

        def walk(node, sector, size):
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
                    child = Node(name)
                    if length:
                        walk(child, start, length)
                else:
                    child = Node(name, ('iso', base + start * SECTOR), length)
                node.children[name.upper()] = child
                for k in (left, right):
                    if k:
                        stack.append(k * 4)
        root = Node('')
        walk(root, root_sector, root_size)
    return root, stamp


def lay_over(root, folder, log):
    n = 0
    for d, _, files in os.walk(folder):
        rel = os.path.relpath(d, folder)
        parts = [] if rel == '.' else rel.split(os.sep)
        for f in files:
            if f.lower().endswith(SKIP) or f.upper() in SKIP_NAMES:
                continue
            node = root
            for p in parts:
                node = node.children.setdefault(p.upper(), Node(p.upper()))
            path = os.path.join(d, f)
            old = node.children.get(f.upper())
            node.children[f.upper()] = Node(old.name if old else f.upper(), ('file', path), os.path.getsize(path))
            n += 1
    log('  %s : %d fichiers' % (folder, n))


def files_of(node, prefix=''):
    for k in sorted(node.children):
        c = node.children[k]
        if c.children is None:
            yield prefix + c.name, c
        else:
            yield from files_of(c, prefix + c.name + '/')


def dirs_of(node):
    yield node
    for k in sorted(node.children):
        if node.children[k].children is not None:
            yield from dirs_of(node.children[k])


def _entry_len(name):
    return (14 + len(name.encode('latin-1')) + 3) & ~3


def _layout(node):
    """Entries of a directory as a balanced tree sorted by upper-case name (how the Xbox looks a
    name up): [(child, offset, left index, right index)] in pre-order; none crosses a sector."""
    kids = [node.children[k] for k in sorted(node.children, key=lambda k: k.upper())]
    order = []

    def build(lo, hi):
        if lo >= hi:
            return None
        mid = (lo + hi) // 2
        i = len(order)
        order.append([kids[mid], 0, None, None])
        order[i][2] = build(lo, mid)
        order[i][3] = build(mid + 1, hi)
        return i
    build(0, len(kids))
    off = 0
    for e in order:
        n = _entry_len(e[0].name)
        if off // SECTOR != (off + n - 1) // SECTOR:
            off = (off // SECTOR + 1) * SECTOR
        e[1] = off
        off += n
    size = max(SECTOR, (off + SECTOR - 1) // SECTOR * SECTOR)
    return order, size


def _dir_bytes(order, size):
    b = bytearray(b'\xff' * size)
    for child, off, left, right in order:
        name = child.name.encode('latin-1')
        lo = order[left][1] // 4 if left is not None else 0
        ro = order[right][1] // 4 if right is not None else 0
        attr = 0x10 if child.children is not None else 0x80
        length = child.dir_size if child.children is not None else child.size
        struct.pack_into('<HHIIBB', b, off, lo, ro, child.sector, length, attr, len(name))
        b[off + 14:off + 14 + len(name)] = name
        pad = _entry_len(child.name) - 14 - len(name)
        b[off + 14 + len(name):off + 14 + len(name) + pad] = b'\xff' * pad
    return bytes(b)


def write_image(root, stamp, src_iso, out, log):
    layouts = {}
    sector = 33
    for d in dirs_of(root):
        layouts[id(d)] = _layout(d)
        d.dir_size = layouts[id(d)][1]
        d.sector = sector
        sector += d.dir_size // SECTOR
    files = list(files_of(root))
    for _, f in files:
        f.sector = sector
        sector += max(1, (f.size + SECTOR - 1) // SECTOR)
    total = sector * SECTOR
    log('  image : %d fichiers, %.2f Go' % (len(files), total / 1e9))
    tmp = out + '.part'
    with open(src_iso, 'rb') as src, open(tmp, 'wb') as o:
        o.write(bytes(32 * SECTOR))
        vd = bytearray(SECTOR)
        vd[0:20] = MAGIC
        struct.pack_into('<II8s', vd, 20, root.sector, root.dir_size, stamp)
        vd[0x7EC:0x800] = MAGIC
        o.write(vd)
        for d in dirs_of(root):
            o.write(_dir_bytes(*layouts[id(d)]))
        done = 0
        for i, (path, f) in enumerate(files):
            assert o.tell() == f.sector * SECTOR, path
            if f.src[0] == 'iso':
                src.seek(f.src[1])
                left = f.size
                while left:
                    b = src.read(min(left, 8 << 20))
                    o.write(b)
                    left -= len(b)
            else:
                with open(f.src[1], 'rb') as g:
                    while True:
                        b = g.read(8 << 20)
                        if not b:
                            break
                        o.write(b)
            o.write(bytes(-o.tell() % SECTOR or (0 if f.size else SECTOR)))
            done += f.size
            if i % 10 == 0 or i == len(files) - 1:
                log('  écrit %d/%d (%d Mo)' % (i + 1, len(files), done >> 20))
    os.replace(tmp, out)
    return files


def check_loose(root, log):
    """Loose files that are also in ZDIR.BIN must have the size it gives."""
    nfs = root.children['NFS'].children
    z = nfs['ZDIR.BIN']
    if z.src[0] == 'file':
        zdir = open(z.src[1], 'rb').read()
    else:
        return
    sizes = {}
    for i in range(0, len(zdir) - 23, 24):
        h, _, _, _, size, _ = struct.unpack_from('<6I', zdir, i)
        sizes.setdefault(h, set()).add(size)
    bad = []
    for path, f in files_of(root):
        if f.src[0] != 'file' or path.upper().startswith(('NFS/', 'MOVIES/')):
            continue
        h = zzdata.bstringhash(path.upper().replace('/', '\\'))
        if h in sizes and f.size not in sizes[h]:
            bad.append('%s : %d octets, ZDIR.BIN dit %s' % (path, f.size, sorted(sizes[h])))
        log('  %-40s %d octets %s' % (path, f.size, 'OK (taille du ZDIR)' if h in sizes and f.size in sizes[h]
                                                 else ('absent du ZDIR' if h not in sizes else 'TAILLE DIFFÉRENTE')))
    if bad:
        raise SystemExit('\n'.join(bad))


def verify(out, files, log):
    """Read the new image back with the disc reader and compare every laid-over file."""
    import xdvdfs
    listed = xdvdfs.list_files(out)
    with open(out, 'rb') as o:
        for path, f in files:
            size, off = listed[path.upper()]
            assert size == f.size, path
            if f.src[0] == 'file':
                o.seek(off)
                a = hashlib.sha1(o.read(size)).hexdigest()
                b = hashlib.sha1(open(f.src[1], 'rb').read()).hexdigest()
                assert a == b, path
    log('  relu : %d fichiers, les fichiers ajoutés identiques à leur source' % len(listed))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--iso', required=True)
    ap.add_argument('--add', action='append', default=[], help='dossier posé par-dessus (game_root)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--keep-pad', action='store_true')
    a = ap.parse_args()
    if os.path.abspath(a.out) == os.path.abspath(a.iso):
        raise SystemExit("l'image de sortie ne doit pas être celle de départ")
    root, stamp = disc_tree(a.iso)
    if 'DEFAULT.XEX' not in root.children:
        raise SystemExit("pas de default.xex : ce n'est pas une image Xbox 360")
    if not a.keep_pad:
        for k in [k for k in root.children['NFS'].children if k.startswith('PAD')]:
            del root.children['NFS'].children[k]
    for folder in a.add:
        lay_over(root, folder, print)
    check_loose(root, print)
    files = write_image(root, stamp, a.iso, a.out, print)
    verify(a.out, files, print)
    print('fini :', a.out)


if __name__ == '__main__':
    sys.exit(main())
