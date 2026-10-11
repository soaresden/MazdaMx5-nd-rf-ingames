"""Decode a 360 car TEXTURES.BIN to PNG files: dump_tex.py <TEXTURES.BIN> <outdir>"""
import io
import os
import struct
import sys

from PIL import Image

import tpk
import xenos


def dds(w, h, fourcc, data):
    hdr = struct.pack('<4sIIIIIII44xII4sIIIIIIIIII', b'DDS ', 124, 0x81007, h, w, len(data), 0, 1,
                      32, 4, fourcc, 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    return hdr + data


d = open(sys.argv[1], 'rb').read()
os.makedirs(sys.argv[2], exist_ok=True)
for t in tpk.read(d):
    bpb = 8 if t['comp'] == 0x22 else 16
    fourcc = b'DXT1' if t['comp'] == 0x22 else b'DXT5'
    lin = xenos.untile(t['pixels'], t['w'], t['h'], bpb)
    im = Image.open(io.BytesIO(dds(t['w'], t['h'], fourcc, lin)))
    im.load()
    name = ''.join(c if c.isalnum() or c == '_' else '_' for c in t['name'])
    im.save(os.path.join(sys.argv[2], '%08X_%s.png' % (t['hash'], name)))
    print(t['name'].encode('ascii', 'replace').decode(), t['w'], t['h'], fourcc)
