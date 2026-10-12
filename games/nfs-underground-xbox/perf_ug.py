"""Handling and performance of the MX-5 RF in Need for Speed Underground and Underground 2: the
Miata's CarTypeInfo (chunk 0x34600 of GLOBAL/GLOBALB.BUN, the same data JDLZ-compressed in
GLOBAL/GLOBALB.LZC) given the figures of a Mazda MX-5 RF ND2 2.0 184 ch (EU, manual).

Chunk 0x34600: 8 bytes of padding (0x11), then one record per car: 0xC90 bytes in Underground
(35 cars), 0x890 in Underground 2 (46 cars). Layout from SpeedReflect/Nikki (Support.Underground1
and Underground2 CarTypeInfo.Disassemble), checked against the data (record sizes, the Miata's
real gear ratios, and the inertia formula below). Offsets in a record, little-endian floats:

  0x000 name (32)  0x0C0 manufacturer (16)
  0x120 4 wheels of 48 bytes: +0 x (axle), +4 y (half track), +8 z (centre), +0x10 tyre radius,
        +0x14 tyre width (skid marks), +0x18 int id (0 FL, 1 FR, 2 RR, 3 RL)
  0x1E0 tyres: front (5 floats, 12 pad) then rear: +0 12, +4 1, +8 1, +0xC grip, +0x10 sliding
        grip (the stock Miata is the least grippy sports car of both games here)
  0x220 mass (t), length, width, height (m), then the inertia tensor (t.m2):
        0x230 roll = m (w2 + h2) / 12, 0x244 pitch = m (l2 + h2) / 12, 0x258 yaw = m (l2 + w2) / 12
  0x2C0 transmission: clutch slip, optimal shift, final drive (x2), torque split, burnout,
        int gear count, shift speed (2 stock, 4 / 6 / 8 upgraded), reverse (negative), neutral,
        gears 1..6
  0x300 idle, red line, limiter (rpm)
  0x30C engine: rev rate, 9 torque points (kN.m, about the real figures: RX-8 0.215, 350Z 0.37,
        GTO 0.495) evenly spaced from idle to the limiter (the game's peak powers then match the
        real ones: RX-8 177 kW, GTO 260 kW, Mustang GT 224 kW), 3 more
  0x340 turbo: 9 floats (6 + spool settings) for the stock car
  0x370 drag, front / rear downforce, bump, steering ratio, brakes, handbrake, brake bias
  0x3A0 stock top speed limiter (mph, Underground 2 only: Miata 125, RX-8 148, Audi TT 155)
Upgrades (absolute amounts):
  Underground: transmissions 0x3F0 / 0x430 / 0x470 (street, pro, top), engines 0x4B0 / 0x4F0 /
  0x530 (12 pad + engine block), rpm + ECU 0x570 / 0x5B0 / 0x5F0, turbos 0x630 / 0x660 / 0x690,
  tyres 0x6C0 / 0x700 / 0x740, drift yaw control 0x930.
  Underground 2: drift yaw control 0x3C0, street and pro engines 0x3E0 / 0x404, transmissions
  0x460 / 0x4A0 / 0x4E0, top engine 0x52C, ECUs 0x570 / 0x5A0 / 0x5F0, top turbo 0x620, top
  tyres 0x650.
The engine and ECU upgrades of the Miata are its stock torque curve times a constant (13.6 %,
27.2 %, 40 % in Underground): every such 9-float run is found and recomputed on the MX-5's curve.

Arcade balance: the real figures where the game has them (mass, inertia, torque curve, rpm, gear
ratios, tyres size, track, wheelbase), and for the rest the RX-8 / S2000 range of each game:
more grip than the Miata, more at the rear than at the front (stable, not a drift car), a little
less yaw help and a slightly slower steering, brakes and downforce like the RX-7 / RX-8.
"""
import struct

RECORD = {'ug1': (0xC90, 35), 'ug2': (0x890, 46)}
CHUNK = 0x34600
CAR = 'MIATA'

# --- the car -------------------------------------------------------------------------------
MASS = 1.125                       # t (kerb weight, as in the Gran Turismo version)
DIMS = (3.915, 1.735, 1.245)       # length, width, height of the RF (m)
IDLE, RED_LINE, LIMITER = 800.0, 7500.0, 8000.0
# ND 2.0 SKYACTIV-MT (the same ratios as the Most Wanted and Gran Turismo versions)
GEARS = (3.709, 2.190, 1.536, 1.177, 1.000, 0.832)
REVERSE, FINAL_DRIVE = 3.603, 3.454
# Skyactiv-G 2.0 ND2 (205 N.m at 4000 rpm, 184 ch at 7000 rpm): N.m every 500 rpm from 1000 to
# 8500, the curve of the Gran Turismo version (gran-turismo-ps1/carinf.py, kgf.m converted)
REAL_TORQUE = (142.2, 161.8, 176.5, 188.3, 196.1, 202.0, 205.0, 204.0, 202.0, 199.1, 195.2,
               190.2, 184.4, 172.6, 152.0, 127.5)
FRONT_AXLE, REAR_AXLE = 1.03, -1.279    # wheelbase 2.309 m: where build_ug puts the MX-5's axles
HALF_TRACK = (1.495 / 2, 1.505 / 2)     # front, rear
TYRE_RADIUS, TYRE_WIDTH = 0.308, 0.205  # 205/45 R17
TOP_SPEED_MPH = 137.0                   # 220 km/h (Underground 2 limiter of the stock car)

# per game: tyres (front grip, front sliding, rear grip, rear sliding), brakes, downforce
# (front, rear), steering ratio, drift yaw help (4th float of the drift block)
TUNING = {
    # Miata: 1.80 1.44 / 1.95 1.50, brakes 0.45, df 0.135 / 0.145, steering 1.15, yaw 0.08
    # S2000: 1.85 1.46 / 1.95 1.56, RX-7 brakes 0.49, df 0.156 / 0.16, S2000 yaw 0.06
    'ug1': dict(tyres=(1.90, 1.55, 2.00, 1.65), brakes=0.49, downforce=(0.140, 0.155),
                steering=1.10, yaw=0.06),
    # Miata: 1.65 1.45 / 1.675 1.45, brakes 0.45, df 0.14 / 0.15, steering 1.15, yaw 0.06
    # RX-8: 1.70 1.48 / 1.70 1.50, 350Z 1.68 1.58 / 1.70 1.59, RX-8 brakes 0.49, df 0.152 / 0.16,
    # steering 1.10, yaw 0.05
    'ug2': dict(tyres=(1.75, 1.55, 1.80, 1.62), brakes=0.49, downforce=(0.145, 0.160),
                steering=1.10, yaw=0.05),
}

OFF = {
    'wheels': 0x120, 'tyres': 0x1E0, 'mass': 0x220, 'trans': 0x2C0, 'rpm': 0x300,
    'engine': 0x30C, 'turbo': 0x340, 'drag': 0x370, 'downforce': 0x374, 'steering': 0x380,
    'brakes': 0x384, 'limiter': 0x3A0,
}
UPGRADES = {
    'ug1': dict(trans=(0x3F0, 0x430, 0x470), turbo=(0x630, 0x660, 0x690),
                tyres=(0x6C0, 0x700, 0x740), drift=0x930),
    'ug2': dict(trans=(0x460, 0x4A0, 0x4E0), turbo=(0x620,), tyres=(0x650,), drift=0x3C0),
}


def real_torque(rpm):
    """N.m of the ND2 2.0 at `rpm` (linear, extrapolated below 1000 rpm)."""
    x = (rpm - 1000.0) / 500.0
    i = min(max(int(x), 0), len(REAL_TORQUE) - 2)
    t = x - i
    return REAL_TORQUE[i] * (1 - t) + REAL_TORQUE[i + 1] * t


def torque_curve():
    """The game's 9 points (kN.m), idle to limiter."""
    return [round(real_torque(IDLE + (LIMITER - IDLE) * k / 8) / 1000.0, 4) for k in range(9)]


def inertia(m, l, w, h):
    return m * (w * w + h * h) / 12, m * (l * l + h * h) / 12, m * (l * l + w * w) / 12


# --- the file ------------------------------------------------------------------------------
def records(data, game):
    """{car name: offset of its record} in GLOBALB.BUN."""
    size, count = RECORD[game]
    off = 0
    while off + 8 <= len(data):
        cid, n = struct.unpack_from('<II', data, off)
        if cid == CHUNK:
            base = off + 8 + 8
            if n != 8 + size * count:
                raise ValueError('CarTypeInfo de %d octets, %d attendus' % (n, 8 + size * count))
            return {data[base + i * size:base + i * size + 32].split(b'\0')[0].decode():
                    base + i * size for i in range(count)}
        off += 8 + n
    raise ValueError('pas de CarTypeInfo (0x34600) dans GLOBALB')


def _f(r, o, n=1):
    return list(struct.unpack_from('<%df' % n, r, o))


def _put(r, o, *v):
    struct.pack_into('<%df' % len(v), r, o, *v)


def _proportional_runs(r, base, size):
    """Offsets of the 9-float runs equal to `base` x a constant (0 < k < 1): the upgrades."""
    out = []
    for o in range(0, size - 36 + 1, 4):
        if o == OFF['engine'] + 4:
            continue
        v = struct.unpack_from('<9f', r, o)
        if not all(x > 0 for x in v):
            continue
        k = [x / b for x, b in zip(v, base)]
        if 0.001 < k[0] < 1 and max(k) - min(k) < 0.01 * k[0]:
            out.append((o, sum(k) / 9))
    return out


def patch_record(rec, game, wheels=True):
    """New bytes of the Miata's record; [(field, old, new)] for the report."""
    r = bytearray(rec)
    size = RECORD[game][0]
    tune = TUNING[game]
    up = UPGRADES[game]
    log = []

    def setf(name, o, *v):
        old = _f(r, o, len(v))
        _put(r, o, *v)
        log.append((name, old if len(old) > 1 else old[0], list(v) if len(v) > 1 else v[0]))

    # wheels: the MX-5's wheelbase, tracks and 205/45 R17 tyres
    for k in range(4 if wheels else 0):
        o = OFF['wheels'] + 48 * k
        wid = struct.unpack_from('<i', r, o + 0x18)[0]
        front = wid in (0, 1)
        old = _f(r, o, 2) + _f(r, o + 0x10, 2)
        _put(r, o, FRONT_AXLE if front else REAR_AXLE)
        _put(r, o + 4, HALF_TRACK[0 if front else 1] * (1 if old[1] >= 0 else -1))
        _put(r, o + 0x10, TYRE_RADIUS, TYRE_WIDTH)
        log.append(('roue %s (x, y, rayon, largeur)' % ('AVG', 'AVD', 'ARD', 'ARG')[wid], old,
                    _f(r, o, 2) + _f(r, o + 0x10, 2)))
    # tyres, with the upgrades in the same proportion
    t = OFF['tyres']
    old_t = _f(r, t + 0xC, 2) + _f(r, t + 0x2C, 2)
    gf, sf, gr, sr = tune['tyres']
    ratio = [gf / old_t[0], sf / old_t[1], gr / old_t[2], sr / old_t[3]]
    setf('pneus avant (grip, glisse)', t + 0xC, gf, sf)
    setf('pneus arrière (grip, glisse)', t + 0x2C, gr, sr)
    for i, o in enumerate(up['tyres']):
        v = _f(r, o + 0xC, 2) + _f(r, o + 0x2C, 2)
        setf('pneus amélioration %d (av grip, glisse)' % (i + 1), o + 0xC, v[0] * ratio[0], v[1] * ratio[1])
        setf('pneus amélioration %d (ar grip, glisse)' % (i + 1), o + 0x2C, v[2] * ratio[2], v[3] * ratio[3])
    # mass and inertia
    setf('masse (t)', OFF['mass'], MASS)
    setf('dimensions (m)', OFF['mass'] + 4, *DIMS)
    ix, iy, iz = inertia(MASS, *DIMS)
    setf('inertie roulis', 0x230, ix)
    setf('inertie tangage', 0x244, iy)
    setf('inertie lacet', 0x258, iz)
    # engine: torque curve, rpm; upgrades recomputed on the new curve
    eo = OFF['engine'] + 4
    old_curve = _f(r, eo, 9)
    new_curve = torque_curve()
    runs = _proportional_runs(rec, old_curve, size)
    setf('régime ralenti, rupteur affiché, coupure', OFF['rpm'], IDLE, RED_LINE, LIMITER)
    setf('couple (9 points, kN.m)', eo, *new_curve)
    for o, k in runs:
        setf('amélioration moteur/ECU @0x%03X (x%.3f)' % (o, k), o, *[round(k * c, 5) for c in new_curve])
    for i, o in enumerate(up['turbo']):
        v = _f(r, o, 9)
        if any(v):
            setf('turbo amélioration %d' % (i + 1), o,
                 *[round(x * n / b, 5) if b else x for x, n, b in zip(v, new_curve, old_curve)])
    # transmissions: the ND's six gears everywhere (the upgrades keep their other settings)
    for name, o in [('boîte de série', OFF['trans'])] + [('boîte amélioration %d' % (i + 1), x)
                                                          for i, x in enumerate(up['trans'])]:
        old = _f(r, o + 8, 2) + [struct.unpack_from('<i', r, o + 0x18)[0]] + _f(r, o + 0x20, 8)
        _put(r, o + 8, FINAL_DRIVE, FINAL_DRIVE)
        struct.pack_into('<i', r, o + 0x18, len(GEARS))
        _put(r, o + 0x20, -REVERSE, 0.0, *GEARS)
        log.append((name + ' (pont x2, rapports, M.A., N, 1..6)', old,
                    [FINAL_DRIVE, FINAL_DRIVE, len(GEARS), -REVERSE, 0.0] + list(GEARS)))
    # chassis
    setf('appui avant, arrière', OFF['downforce'], *tune['downforce'])
    setf('direction', OFF['steering'], tune['steering'])
    setf('freins', OFF['brakes'], tune['brakes'])
    setf('aide au lacet (dérive)', up['drift'] + 12, tune['yaw'])
    if game == 'ug2':
        setf('vitesse max de série (mph)', OFF['limiter'], TOP_SPEED_MPH)
    return bytes(r), log


def patch_globalb(data, game, wheels=True, log=print):
    """GLOBALB.BUN bytes with the Miata made an MX-5 RF; (new bytes, changed range, report)."""
    recs = records(data, game)
    o = recs[CAR]
    size = RECORD[game][0]
    new_rec, report = patch_record(data[o:o + size], game, wheels)
    out = bytearray(data)
    out[o:o + size] = new_rec
    # read back
    again = records(bytes(out), game)
    assert again == recs and bytes(out[o:o + size]) == new_rec
    assert out[:o] == data[:o] and out[o + size:] == data[o + size:]
    log('  CarTypeInfo %s : %d champs modifiés' % (CAR, len(report)))
    return bytes(out), (o, o + size), report


def patch_lzc(blob, new_bun, changed):
    """GLOBALB.LZC (JDLZ) holding `new_bun`, re-encoded only around the changed record, no
    bigger than the original stream; checked with the game's own decoder."""
    import jdlz
    old = jdlz.decompress(blob)
    if len(old) != len(new_bun):
        raise ValueError('GLOBALB.LZC ne contient pas GLOBALB.BUN')
    new = jdlz.splice_to_fit(blob, new_bun, [changed], len(blob))
    if new is None:
        raise ValueError('GLOBALB.LZC ne tient pas dans sa taille')
    assert jdlz.game_decompress(new) == new_bun
    return new


def report_table(report):
    def fmt(v):
        if isinstance(v, list):
            return ' '.join('%.4g' % x for x in v)
        return '%.4g' % v
    return '\n'.join('  %-46s %s  ->  %s' % (n, fmt(a), fmt(b)) for n, a, b in report)
