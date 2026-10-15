"""A CD image in CHD into .bin + .cue (raw 2352-byte sectors), for tools that only read .bin.

python chd2bin.py <disc.chd> <out.bin>     writes out.bin and out.cue; prints the CRC32 of the .bin

Discs with a single data track (PlayStation games such as Gran Turismo 1 and 2); several tracks
are refused rather than written wrong.
"""
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chd  # noqa: E402

CUE_TYPE = {'MODE2_RAW': 'MODE2/2352', 'MODE1_RAW': 'MODE1/2352'}


def convert(src, out, log=print):
    c = chd.Chd(src)
    if len(c.tracks) != 1 or c.tracks[0].get('TYPE') not in CUE_TYPE:
        raise SystemExit('%s : %d pistes (%s), seulement une piste de données est gérée'
                         % (src, len(c.tracks), [t.get('TYPE') for t in c.tracks]))
    frames = c.frames
    crc = 0
    tmp = out + '.part'
    with open(tmp, 'wb') as f:
        for h in range((frames + c.frames_per_hunk - 1) // c.frames_per_hunk):
            b = c.hunk(h)
            n = min(c.frames_per_hunk, frames - h * c.frames_per_hunk)
            for i in range(n):
                s = b[i * chd.FRAME:i * chd.FRAME + chd.SECTOR]
                f.write(s)
                crc = zlib.crc32(s, crc)
            if h % 2000 == 0:
                log('  %s : %d %%' % (os.path.basename(out), 100 * h * c.frames_per_hunk // frames))
    os.replace(tmp, out)
    with open(os.path.splitext(out)[0] + '.cue', 'w', encoding='ascii') as f:
        f.write('FILE "%s" BINARY\n  TRACK 01 %s\n    INDEX 01 00:00:00\n' % (os.path.basename(out), CUE_TYPE[c.tracks[0]['TYPE']]))
    log('  %s : %d secteurs, CRC32 %08X' % (os.path.basename(out), frames, crc & 0xFFFFFFFF))
    return crc & 0xFFFFFFFF


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
