"""The MX-5 RF in Gran Turismo 2's data: specifications, names and engine sound of the cars it replaces.

carparam/<lang>_gtmode_data.dat.gz (GTDT, layout from pez2k's GT2DataSplitterRewrite): after the
6-byte "GTDTl\\0" and a u16, one (u32 start, u32 size) pair per table at 8 * (i + 1), the tables in
the order of TABLES. Every row starts with the car's u32 ID; the Car row (0x48 bytes) holds the
index of the car's row in each part table. Only rows of a fixed size are rewritten in place.
  Engine (0x4C): 0x04 layout, valvetrain, aspiration (strings), 0x0A sound, 0x0C 16 x s16 torque
    (kgf.m x 100), 0x2C displacement, power (PS), power rpm / 10, torque (kgf.m x 10), torque rpm
    (string), 0x36 power multiplier, ?, ?, 0x39 rev limit, 0x3A redline (x 100 rpm), 0x3B 16 x u8
    rpm of the torque points (x 100), 0x4B point count
  Chassis (0x14): 0x04 front weight, ?, front grip, rear grip, 0x08 length, height, wheelbase,
    weight (u16)
  Gear (0x24): 0x08 stage, gear count, 0x0A 8 x s16 ratios x 1000 (reverse, 1st..7th, -1 unused),
    0x1A final drive default, max, min; one row per stage (stock, close, super close, custom), the
    bought stages with every ratio at -1 (worked out by the game)
  Car (0x48): 0x3C first and second line of the name (strings), 0x41 year
The tuning parts (NA tune, turbo, port polish...) are multipliers and rpm offsets: they apply to
the new engine as they did to the old one.
carparam/<lang>_unistrdb.dat.gz: u32 size, "WSDB", u16 count, per string u16 length + UTF-16 + 0
(the game refuses more than 0x6000 bytes).
.carinfoj/a/e (Japan, USA, Europe): "CAR\\0", u32 count, per car (u32 ID, u16 offset, u16 colour
count and region flags); at the offset 3 bytes per colour, then the name (u8 length, latin-1, 0x7F
the racing mark), so a new name is a copy of that block at the end of the file.
"""
import gzip
import struct

TABLES = ('Brake BrakeController Steer Chassis Lightweight RacingModify Engine PortPolish EngineBalance '
          'Displacement Computer NATune TurbineKit Drivetrain Flywheel Clutch PropellerShaft Gear Suspension '
          'Intercooler Muffler LSD TiresFront TiresRear TireSize TireCompound TireForceVol '
          'ActiveStabilityControl TractionControlSystem Wheel Car').split()
ROW = {'Chassis': 0x14, 'Engine': 0x4C, 'Gear': 0x24, 'Car': 0x48}
CAR_PART = {'Chassis': 0x0A, 'Engine': 0x10, 'Gear': 0x28}
CHARS = '-0123456789abcdefghijklmnopqrstuvwxyz'
LANGS = ('eng', 'fra', 'ger', 'ita', 'spa', 'usa', 'jpn', '')

# Skyactiv-G 2.0 (ND2), the curve of the GT1 version with the top end set so that the garage,
# which computes the power from it, shows 184 PS at 7000 rpm (points every 500 rpm, 1000..8500)
RF = {
    'torque': (1450, 1650, 1800, 1920, 2000, 2060, 2090, 2080, 2060, 2040, 2010, 1980, 1920, 1790, 1560, 1300),
    'displacement': 1997, 'power': 184, 'power_rpm': 700, 'torque_display': 209, 'torque_rpm': '4000rpm',
    'rev_limit': 80, 'redline': 75,
    'length': 3915, 'height': 1245, 'wheelbase': 2310, 'weight': 1125,
    # 6-speed: reverse, 1st..6th, final drive
    'gears': (3603, 3709, 2190, 1536, 1177, 1000, 832), 'final': 3454,
    'year': 18,
}
# the name in the lists and the garage: the first line (one for every MX-5 of the disc; GT2 Plus
# calls them Eunos Roadster) and the second, per language of the menus: hardtop closed, top down
# (short: the used car list has room for about 27 letters before the price)
NAME1 = 'Mazda MX-5'
NAME2 = {
    'fra': ("RF ND2 '18", "RF décapotée '18"),
    'eng': ("RF ND2 '18", "RF ND2 Open '18"),
    'usa': ("RF ND2 '18", "RF ND2 Open '18"),
    'ger': ("RF ND2 '18", "RF ND2 offen '18"),
    'ita': ("RF ND2 '18", "RF scoperta '18"),
    'spa': ("RF ND2 '18", "RF abierto '18"),
    'jpn': ("RF ND2 '18", "RF ND2 Open '18"),
    '': ("RF ND2 '18", "RF ND2 Open '18"),
}
# the RF's paints (Mazda's names; sRGB of the GT1 version), in the order of the car's colours: the
# '93 has nine, the V-Special six
PAINTS = [
    ('Deep Crystal Blue Mica', (24, 40, 84)),
    ('Soul Red Crystal Metallic', (150, 16, 26)),
    ('Machine Grey Metallic', (88, 90, 94)),
    ('Jet Black Mica', (14, 14, 16)),
    ('Snowflake White Pearl Mica', (226, 226, 220)),
    ('Ceramic Metallic', (184, 186, 182)),
    ('Polymetal Grey Metallic', (96, 108, 114)),
    ('Platinum Quartz Metallic', (156, 150, 140)),
    ('Arctic White', (236, 236, 232)),
]
# the lists (.carinfo): one name for every language of a region
LIST_NAME = {'j': ("MX-5 RF ND2 '18", "MX-5 RF ND2 Open '18"),
             'a': ("Mazda MX-5 RF ND2 '18", "Mazda MX-5 RF Open '18"),
             'e': ("Mazda MX-5 RF ND2 '18", "Mazda MX-5 RF Open '18")}


def car_id(code):
    v = 0
    for c in code:
        v = (v << 6) | CHARS.index(c)
    return v


def car_code(v):
    return ''.join(CHARS[(v >> (k * 6)) & 0x3F] for k in range(4, -1, -1))


class Strings:
    """A unistrdb: the list of strings, add() appends one (or finds it)."""
    def __init__(self, d):
        if d[4:8] != b'WSDB':
            raise ValueError('pas une table de textes WSDB')
        n, = struct.unpack_from('<H', d, 8)
        o, self.items = 10, []
        for _ in range(n):
            k, = struct.unpack_from('<H', d, o)
            self.items.append(d[o + 2:o + 2 + 2 * k].decode('utf-16-le'))
            o += 2 + 2 * (k + 1)

    def add(self, s):
        if s not in self.items:
            self.items.append(s)
        return self.items.index(s)

    def bytes(self):
        body = b''.join(struct.pack('<H', len(s)) + (s + '\0').encode('utf-16-le') for s in self.items)
        d = b'WSDB' + struct.pack('<H', len(self.items)) + body
        d = struct.pack('<I', len(d) + 4) + d
        if len(d) > 0x6000:
            raise ValueError('table de textes trop grande pour le jeu (%d octets, 24576 au plus)' % len(d))
        return d


def tables(d):
    if d[:5] != b'GTDTl':
        raise ValueError('pas un fichier GTDT')
    return {name: struct.unpack_from('<II', d, 8 * (i + 1)) for i, name in enumerate(TABLES)}


def rows(d, t, table):
    """(offset, car code) of every row of a table."""
    start, size = t[table]
    n = ROW[table]
    return [(start + i * n, car_code(struct.unpack_from('<I', d, start + i * n)[0])) for i in range(size // n)]


def patch_gtmode(d, variants, strings, lang):
    """A gtmode_data with the cars of `variants` ({code: 0 closed, 1 top down}) made into the RF;
    strings: the language's Strings (new names added to it). Returns (data, codes done)."""
    d = bytearray(d)
    t = tables(d)
    car_rows = {code: o for o, code in rows(d, t, 'Car')}
    gear_rows = rows(d, t, 'Gear')
    done = []
    names = NAME2.get(lang, NAME2['eng'])
    tq_rpm = strings.add(RF['torque_rpm'])
    for code, variant in variants.items():
        if code not in car_rows:
            continue
        c = car_rows[code]
        part = {k: struct.unpack_from('<H', d, c + o)[0] for k, o in CAR_PART.items()}
        e = t['Engine'][0] + part['Engine'] * ROW['Engine']
        struct.pack_into('<16h', d, e + 0x0C, *RF['torque'])
        struct.pack_into('<4HH', d, e + 0x2C, RF['displacement'], RF['power'], RF['power_rpm'],
                         RF['torque_display'], tq_rpm)
        d[e + 0x39], d[e + 0x3A] = RF['rev_limit'], RF['redline']
        d[e + 0x3B:e + 0x4B] = bytes(range(10, 90, 5))
        d[e + 0x4B] = 16
        ch = t['Chassis'][0] + part['Chassis'] * ROW['Chassis']
        struct.pack_into('<4H', d, ch + 0x08, RF['length'], RF['height'], RF['wheelbase'], RF['weight'])
        stock = t['Gear'][0] + part['Gear'] * ROW['Gear']
        base_final, = struct.unpack_from('<h', d, stock + 0x1A)
        for g, gcode in gear_rows:
            if gcode != code:
                continue
            # the stock box has its ratios; the bought ones (close, super close, custom) have -1,
            # the game works them out, so only their gear count and final drive change
            old = struct.unpack_from('<8h', d, g + 0x0A)
            d[g + 0x09] = 6
            if old[1] > 0:
                struct.pack_into('<8h', d, g + 0x0A, *RF['gears'], -1)
            finals = struct.unpack_from('<3h', d, g + 0x1A)
            struct.pack_into('<3h', d, g + 0x1A, *(round(RF['final'] * f / base_final) for f in finals))
        struct.pack_into('<HH', d, c + 0x3C, strings.add(NAME1), strings.add(names[variant]))
        d[c + 0x41] = RF['year']
        done.append(code)
    return bytes(d), done


def thumbnail(rgb):
    """The colour of a paint's square in the menus (15 bits, as pez2k's editor writes it)."""
    r, g, b = (c // 8 for c in rgb)
    return r | (g << 5) | (b << 10)


def rename_carinfo(d, region, variants):
    """A .carinfo<region> with the cars of `variants` renamed and their colour squares those of
    the RF's paints (the block copied at the end: per colour a u16 square colour, then per colour
    the letter of its paint in the texture, then the name)."""
    d = bytearray(d)
    n, = struct.unpack_from('<I', d, 4)
    for i in range(n):
        cid, off, misc = struct.unpack_from('<IHH', d, (i + 1) * 8)
        code = car_code(cid)
        base = code[:-1] + 'n'
        if base not in variants:
            continue
        colours = ((misc & 0x3C) >> 2) + 1
        racing = code.endswith('r')
        name = LIST_NAME[region][variants[base]]
        raw = (b'\x7f' if racing else b'') + name.encode('latin-1')
        new = len(d)
        if new + colours * 3 + len(raw) + 2 > 0xFFFF:
            raise ValueError('.carinfo%s : plus de place pour les noms' % region)
        block = bytearray(d[off:off + colours * 3])
        if not racing:
            for k in range(colours):
                struct.pack_into('<H', block, 2 * k, thumbnail(PAINTS[k % len(PAINTS)][1]))
        d += block + bytes([len(raw)]) + raw + b'\0'
        if len(d) % 2:
            d += b'\0'
        struct.pack_into('<H', d, (i + 1) * 8 + 4, new)
    return bytes(d)


class ColourNames:
    """.cclatain (latin-1) or .ccjapanese (UTF-16): a u16 offset per name, then the names."""
    def __init__(self, d, wide):
        self.wide = wide
        first, = struct.unpack_from('<H', d, 0)
        offs = list(struct.unpack_from('<%dH' % (first // 2), d, 0)) + [len(d)]
        self.raw = [d[offs[k]:offs[k + 1]] for k in range(first // 2)]

    def add(self, name):
        b = name.encode('utf-16-le') + b'\0\0' if self.wide else name.encode('latin-1') + b'\0'
        if b in self.raw:
            return self.raw.index(b)
        self.raw.append(b)
        return len(self.raw) - 1

    def bytes(self):
        pos = 2 * len(self.raw)
        offs = []
        for b in self.raw:
            offs.append(pos)
            pos += len(b)
        if pos > 0xFFFF:
            raise ValueError('noms de couleurs : plus de place')
        return struct.pack('<%dH' % len(offs), *offs) + b''.join(self.raw)


def name_colours(carcolor, latin, japanese, carinfo_j, variants):
    """(.carcolor, .cclatain, .ccjapanese) with the paint names of the RF for the road cars of
    `variants`. .carcolor: "CCOL00\\0\\0", per car (in the order of .carinfoj) the offset of the
    list of its colours' name numbers; a new list goes at the end."""
    cc = bytearray(carcolor)
    la, jp = ColourNames(latin, False), ColourNames(japanese, True)
    ids = [(la.add(name), jp.add(name)) for name, _ in PAINTS]
    if any(a != b for a, b in ids):
        # the two tables share the numbers: add to both until they line up
        raise ValueError('noms de couleurs : les deux tables ne correspondent pas')
    n, = struct.unpack_from('<I', carinfo_j, 4)
    for i in range(n):
        cid, _, misc = struct.unpack_from('<IHH', carinfo_j, (i + 1) * 8)
        if car_code(cid) not in variants:
            continue
        colours = ((misc & 0x3C) >> 2) + 1
        new = len(cc)
        cc += struct.pack('<%dH' % colours, *(ids[k % len(ids)][0] for k in range(colours)))
        struct.pack_into('<H', cc, 8 + 2 * i, new)
    return bytes(cc), la.bytes(), jp.bytes()


def gz(d):
    return gzip.compress(d, 9, mtime=0)
