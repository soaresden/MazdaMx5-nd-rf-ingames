"""Dump the bChunk tree of an EA Black Box file: chunks.py <file> <le|be> [maxdepth]"""
import struct
import sys


def walk(d, off, end, depth, fmt, maxdepth, out):
    while off + 8 <= end:
        cid, size = struct.unpack_from(fmt + 'II', d, off)
        body = off + 8
        if body + size > end:
            out.append('  ' * depth + 'BAD %08X size %d at %X' % (cid, size, off))
            return
        is_parent = cid & 0x80000000
        peek = d[body:body + 16].hex()
        out.append('  ' * depth + '%08X  %8d  @%08X  %s' % (cid, size, off, '' if is_parent else peek))
        if is_parent and depth < maxdepth:
            walk(d, body, body + size, depth + 1, fmt, maxdepth, out)
        off = body + size


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    fmt = '<' if sys.argv[2] == 'le' else '>'
    out = []
    walk(d, 0, len(d), 0, fmt, int(sys.argv[3]) if len(sys.argv) > 3 else 99, out)
    print('\n'.join(out))
