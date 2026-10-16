"""Gran Turismo 2's menus for the MX-5 RF: its description (two pages of text per language), its
title pictures, which car the used car dealer sells.

gtmenu/<lang>/gtmenudat.idx / .dat: u32 count, a u32 per screen (start | bytes of padding after
  it, low 2 bits) and one more (the end), the screens gzipped one after the other, each on 4
  bytes (GT2MenuSplitter).
A screen (GTMP, "GM\\x03"): u32 0, u32 count of 80-byte records (zones the game fills: the car,
  buttons...), the records, "GMLL", u32 count, per tile drawn (x, y in tiles of 16 x 8, u16 tile
  | palette << 12), 1024 bytes of palettes (16 colours each), u32 tile count, the tiles: a sheet
  512 pixels (256 bytes) wide, 32 tiles per row of tiles, 4 bits per pixel, low nibble first.
  Tiles left out of the list are not drawn (the black of the screen shows).
gtmenu/<lang>/solodata.dat.gz: u32 n, n u16, u32 count, per car (u32 car ID, u32 screen of the
  first page of its description; the second page follows).
  The description pages: two columns of 224 pixels at x 29 and 262, lines every 20 pixels from
  y 111, 15 lines on the left and 9 on the right (under them the game draws the car).
carlogo/<car><l|m|n|o|p|q>--.tim: the car's name, large (dealer) and small (description): l, m
  Japanese, n, o American, p, q European. 4-bit TIM, 16-colour CLUT (a black 0x0000: transparent).
.usedcar (gzipped): "UCAR", per week records of (u32 car ID, 3-byte price, letter of the paint).
"""
import gzip
import os
import re
import struct
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WINFONTS = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts') + os.sep
FONTS = [r'C:\Windows\Fonts\arial.ttf', os.path.join(HERE, '..', 'gran-turismo-ps1', 'fonts', 'LiberationSans-Bold.ttf')]
TITLE_FONTS = {'narrow': [r'C:\Windows\Fonts\ARIALNB.TTF', r'C:\Windows\Fonts\arialbd.ttf', FONTS[1]],
               'wide': [r'C:\Windows\Fonts\arialbd.ttf', FONTS[1]]}
TEXT_LEFT, TEXT_RIGHT, TEXT_WIDTH = 29, 262, 224
FIRST, PITCH, LEFT_LINES, RIGHT_LINES = 111, 20, 15, 9
TEXT_HEIGHT = 14          # from the top of an accented capital to the bottom of a 'p'
CONDENSE = 0.97           # the game's letters are a little narrower than Arial's
LANGS = ('eng', 'fra', 'ger', 'ita', 'spa')

TEXTS = {
    'fra': (
        "Présentée en 2016, la Mazda MX-5 RF est la version à toit rigide rétractable de la quatrième "
        "génération du roadster de Mazda, la ND. RF signifie Retractable Fastback : en treize secondes "
        "environ, et jusqu'à 10 km/h, le toit en trois parties s'escamote derrière les sièges, tandis que "
        "les arcs-boutants arrière restent en place et donnent à la voiture sa silhouette de coupé. "
        "Fermée, c'est un petit coupé silencieux ; ouverte, une targa qui laisse entrer le vent et le "
        "chant du moteur.\n"
        "En 2018, la version ND2 reçoit un 2.0 SKYACTIV-G profondément revu : pistons et bielles allégés, "
        "papillon des gaz agrandi, nouvel échappement. Il développe 184 ch à 7 000 tr/mn et 20,9 mkg à "
        "4 000 tr/mn, et monte désormais jusqu'à 7 500 tr/mn. La puissance passe aux roues arrière par "
        "une boîte manuelle à six rapports courte et précise.\n"
        "Avec à peine plus de 1 100 kg et une répartition des masses de 50/50, la RF reste fidèle à la "
        "recette du roadster : légèreté, moteur à l'avant, propulsion. Ses doubles triangles à l'avant et "
        "son essieu multibras à l'arrière la rendent vive et communicative en virage, sans jamais la "
        "rendre piégeuse. Ce n'est pas la plus puissante de sa catégorie, mais c'est l'une des voitures "
        "les plus amusantes à conduire, du premier virage jusqu'au circuit."),
    'eng': (
        "Unveiled in 2016, the Mazda MX-5 RF is the retractable hardtop version of the fourth-generation "
        "Mazda roadster, the ND. RF stands for Retractable Fastback: in around thirteen seconds, and at up "
        "to 10 km/h, the three-piece roof stows behind the seats, while the rear buttresses stay in place "
        "and give the car its coupe silhouette. Closed, it is a quiet little coupe; open, a targa that "
        "lets in the wind and the sound of the engine.\n"
        "In 2018 the ND2 update brought a thoroughly revised 2.0-litre SKYACTIV-G engine: lighter pistons "
        "and connecting rods, a larger throttle body and a new exhaust. It produces 184 PS at 7000 rpm "
        "and 20.9 kgm at 4000 rpm, and now revs to 7500 rpm. The power goes to the rear wheels through a "
        "short and precise six-speed manual gearbox.\n"
        "Weighing just over 1100 kg with a 50/50 weight distribution, the RF stays true to the roadster "
        "recipe: light weight, engine at the front, rear-wheel drive. Double wishbones at the front and "
        "a multi-link rear axle make it lively and communicative through the corners, without ever "
        "catching you out. It is not the most powerful car of its kind, but it is one of the most "
        "enjoyable to drive, from the very first corner to the race track."),
    'ger': (
        "Der 2016 vorgestellte Mazda MX-5 RF ist die Version mit versenkbarem Hardtop der vierten "
        "Generation des Mazda Roadsters, des ND. RF steht für Retractable Fastback: In rund dreizehn "
        "Sekunden und bis 10 km/h verschwindet das dreiteilige Dach hinter den Sitzen, während die "
        "hinteren Dachpfosten stehen bleiben und dem Wagen seine Coupé-Silhouette geben. Geschlossen ist "
        "er ein leises kleines Coupé, offen ein Targa, der Fahrtwind und Motorklang hereinlässt.\n"
        "2018 erhielt der ND2 einen gründlich überarbeiteten 2,0-Liter-SKYACTIV-G-Motor: leichtere "
        "Kolben und Pleuel, eine größere Drosselklappe und eine neue Abgasanlage. Er leistet 184 PS bei "
        "7000/min und 20,9 mkg bei 4000/min und dreht nun bis 7500/min. Die Kraft gelangt über ein kurz "
        "und präzise geschaltetes Sechsgang-Schaltgetriebe an die Hinterräder.\n"
        "Mit knapp über 1100 kg und einer Gewichtsverteilung von 50:50 bleibt der RF dem Roadster-Rezept "
        "treu: wenig Gewicht, Frontmotor, Hinterradantrieb. Doppelquerlenker vorn und eine "
        "Mehrlenkerachse hinten machen ihn in Kurven lebendig und mitteilsam, ohne je tückisch zu "
        "werden. Er ist nicht der stärkste seiner Klasse, aber einer der Wagen, die am meisten Spaß "
        "machen, von der ersten Kurve bis zur Rennstrecke."),
    'ita': (
        "Presentata nel 2016, la Mazda MX-5 RF è la versione con tetto rigido retrattile della quarta "
        "generazione della roadster Mazda, la ND. RF significa Retractable Fastback: in circa tredici "
        "secondi, e fino a 10 km/h, il tetto in tre parti scompare dietro i sedili, mentre i montanti "
        "posteriori restano al loro posto e danno all'auto la sua silhouette da coupé. Chiusa è una "
        "piccola coupé silenziosa; aperta, una targa che lascia entrare il vento e il canto del motore.\n"
        "Nel 2018 la ND2 riceve un 2.0 SKYACTIV-G profondamente rivisto: pistoni e bielle alleggeriti, "
        "corpo farfallato più grande, nuovo scarico. Eroga 184 CV a 7000 giri/min e 20,9 kgm a 4000 "
        "giri/min, e ora sale fino a 7500 giri/min. La potenza arriva alle ruote posteriori attraverso "
        "un cambio manuale a sei marce corto e preciso.\n"
        "Con poco più di 1100 kg e una distribuzione dei pesi di 50/50, la RF resta fedele alla ricetta "
        "della roadster: leggerezza, motore anteriore, trazione posteriore. I doppi bracci oscillanti "
        "all'anteriore e il multilink al posteriore la rendono viva e comunicativa in curva, senza mai "
        "diventare insidiosa. Non è la più potente della sua categoria, ma è una delle auto più "
        "divertenti da guidare, dalla prima curva fino alla pista."),
    'spa': (
        "Presentado en 2016, el Mazda MX-5 RF es la versión con techo rígido retráctil de la cuarta "
        "generación del roadster de Mazda, el ND. RF significa Retractable Fastback: en unos trece "
        "segundos, y hasta 10 km/h, el techo de tres piezas se esconde detrás de los asientos, mientras "
        "los arbotantes traseros permanecen en su sitio y dan al coche su silueta de cupé. Cerrado es un "
        "pequeño cupé silencioso; abierto, un targa que deja entrar el viento y el sonido del motor.\n"
        "En 2018 la versión ND2 recibe un 2.0 SKYACTIV-G muy revisado: pistones y bielas aligerados, "
        "mariposa de admisión más grande y nuevo escape. Rinde 184 CV a 7.000 rpm y 20,9 kgm a 4.000 "
        "rpm, y ahora sube hasta 7.500 rpm. La potencia llega a las ruedas traseras a través de una caja "
        "manual de seis marchas corta y precisa.\n"
        "Con poco más de 1.100 kg y un reparto de pesos de 50/50, el RF sigue fiel a la receta del "
        "roadster: ligereza, motor delantero, propulsión. La doble horquilla delantera y el eje trasero "
        "multibrazo lo hacen vivo y comunicativo en las curvas, sin volverse nunca traicionero. No es el "
        "más potente de su categoría, pero es uno de los coches más divertidos de conducir, desde la "
        "primera curva hasta el circuito."),
}


def _font_path(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError('aucune police trouvée (%s)' % ', '.join(paths))


# ---------------------------------------------------------------------------------------------
class MenuData:
    """gtmenudat.idx + .dat: the screens, gzipped."""
    def __init__(self, idx, dat):
        n, = struct.unpack_from('<I', idx, 0)
        offs = list(struct.unpack_from('<%dI' % (n + 1), idx, 4))   # and the end
        self.gz = []
        for i in range(n):
            pad = offs[i] & 3
            start = offs[i] - pad
            self.gz.append(dat[start:(offs[i + 1] & ~3) - pad])

    def screen(self, i):
        return gzip.decompress(self.gz[i])

    def set(self, i, data):
        self.gz[i] = regz(self.gz[i], data)

    def bytes(self):
        idx, dat = [struct.pack('<I', len(self.gz))], bytearray()
        for g in self.gz:
            pad = -len(g) % 4
            idx.append(struct.pack('<I', len(dat) | pad))
            dat += g + b'\0' * pad
        idx.append(struct.pack('<I', len(dat)))
        return b''.join(idx), bytes(dat)


def regz(original, data):
    """data gzipped with the original's header (name, time), as the disc's files are."""
    flg = original[3]
    end = 10
    if flg & 4:
        end += 2 + struct.unpack_from('<H', original, 10)[0]
    if flg & 8:
        end = original.index(b'\0', end) + 1
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    body = c.compress(data) + c.flush()
    head = bytearray(original[:end])
    head[3] = flg & 8
    return bytes(head) + body + struct.pack('<II', zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)


# ---------------------------------------------------------------------------------------------
class Solo:
    """solodata: car ID -> first screen of its description."""
    def __init__(self, d):
        n, = struct.unpack_from('<I', d, 0)
        self.head = d[:4 + 2 * n]
        o = 4 + 2 * n
        count, = struct.unpack_from('<I', d, o)
        self.rows = [list(struct.unpack_from('<II', d, o + 4 + 8 * k)) for k in range(count)]
        self.tail = d[o + 4 + 8 * count:]

    def page(self, cid):
        for c, p in self.rows:
            if c == cid:
                return p
        return None

    def set_page(self, cid, page):
        for r in self.rows:
            if r[0] == cid:
                r[1] = page

    def bytes(self):
        return self.head + struct.pack('<I', len(self.rows)) + b''.join(struct.pack('<II', *r) for r in self.rows) + self.tail


# ---------------------------------------------------------------------------------------------
class Screen:
    """A GTMP screen as an index image (512 wide), and back."""
    def __init__(self, d):
        k = d.find(b'GMLL')
        self.head = d[:k]
        cnt, = struct.unpack_from('<I', d, k + 4)
        ents = [struct.unpack_from('<BBH', d, k + 8 + 4 * i) for i in range(cnt)]
        p = k + 8 + 4 * cnt
        for o in range(p, len(d) - 4, 4):
            n, = struct.unpack_from('<I', d, o)
            if 0 < n < 0x1000 and len(d) - (o + 4) == ((n + 31) // 32) * 2048:
                break
        else:
            raise ValueError('écran GTMP illisible')
        self.palettes = d[p:o]
        pal = np.frombuffer(self.palettes[:32], '<u2')
        self.transparent = int(np.nonzero(pal == 0)[0][0])
        sheet = np.frombuffer(d[o + 4:], np.uint8).reshape(-1, 256)
        ix = np.empty((sheet.shape[0], 512), np.uint8)
        ix[:, 0::2], ix[:, 1::2] = sheet & 15, sheet >> 4
        h = (max(e[1] for e in ents) + 1) * 8
        self.index = np.full((max(h, 8), 512), self.transparent, np.uint8)
        for x, y, t in ents:
            if t >> 12:
                raise ValueError('écran à plusieurs palettes')
            t &= 0xFFF
            self.index[y * 8:y * 8 + 8, x * 16:x * 16 + 16] = ix[(t // 32) * 8:(t // 32) * 8 + 8, (t % 32) * 16:(t % 32) * 16 + 16]
        self.pal = pal

    def bytes(self):
        tiles, ents, seen = [], [], {}
        H = self.index.shape[0] // 8
        for y in range(H):
            for x in range(32):
                t = self.index[y * 8:y * 8 + 8, x * 16:x * 16 + 16]
                if (t == self.transparent).all():
                    continue
                key = t.tobytes()
                if key not in seen:
                    seen[key] = len(tiles)
                    tiles.append(t)
                ents.append((x, y, seen[key]))
        if len(tiles) >= 0x1000:
            raise ValueError('trop de tuiles')
        rows = (len(tiles) + 31) // 32
        sheet = np.zeros((rows * 8, 512), np.uint8)
        for i, t in enumerate(tiles):
            sheet[(i // 32) * 8:(i // 32) * 8 + 8, (i % 32) * 16:(i % 32) * 16 + 16] = t
        packed = (sheet[:, 0::2] | (sheet[:, 1::2] << 4)).astype(np.uint8)
        return (self.head + b'GMLL' + struct.pack('<I', len(ents)) +
                b''.join(struct.pack('<BBH', *e) for e in ents) + self.palettes +
                struct.pack('<I', len(tiles)) + packed.tobytes())


UNITS = r'(?:ch|CV|PS|kg|mkg|kgm|km/h|tr/mn|rpm|U/min|giri/min|secondes|Sekunden|secondi|segundos|seconds)'


def _keep_together(text):
    """No line break between a number and its unit or its next group of digits, nor before the
    French : ; ! ? and inside the French quotes."""
    nbsp = '\u00a0'
    text = re.sub(r'(?<![\w.,-])(\d[\d.,]*) (?=%s(?![\w/])|\d{3}\b)' % UNITS, r'\1' + nbsp, text)
    text = re.sub(r' ([:;!?\u00bb])', nbsp + r'\1', text)
    return text.replace('\u00ab ', '\u00ab' + nbsp)


VOWELS = set('aeiouyàâäéèêëîïôöùûüAEIOUYÀÂÉÈÊÎÔÛ')


DIGRAPHS = {'ch', 'ck', 'ph', 'qu', 'th', 'gn', 'sc', 'gl', 'tz', 'sh'}


def _cuts(word):
    """Where a word can be cut, as the game's texts do (L'Eunos em-ployait): (position, keeps a
    hyphen of its own): after a hyphen; between a vowel and a consonant followed by a vowel; between
    two consonants followed by a vowel (not ch, ck, ph, qu, th...); 3 letters at least on each side,
    never in a number."""
    out = []
    for k in range(3, len(word) - 2):
        if word[k - 1] == '-' and not word[k].isdigit():
            out.append((k, True))
    if len(word) < 7:
        return out
    for k in range(3, len(word) - 3):
        a, b, c = word[k - 1], word[k], word[k + 1]
        if not (a.isalpha() and b.isalpha() and c.isalpha()) or any(x.isdigit() for x in word[max(0, k - 3):k + 3]):
            continue
        if a in VOWELS and b not in VOWELS and c in VOWELS:
            out.append((k, False))
        elif a not in VOWELS and b not in VOWELS and c in VOWELS and (a + b).lower() not in DIGRAPHS:
            out.append((k, False))
    return sorted(set(out))


def _wrap(text, font, width):
    """Lines: (words, last of its paragraph); a long word is cut when the line would be loose."""
    size = lambda ws: font.getlength(' '.join(ws).replace('\u00a0', ' ')) * CONDENSE
    out = []
    for para in text.split('\n'):
        words, cur = _keep_together(para).split(' '), []
        k = 0
        while k < len(words):
            w = words[k]
            if not cur or size(cur + [w]) <= width:
                cur.append(w)
                k += 1
                continue
            # the line is full: cut the next word if what is left on the line is loose
            if size(cur) < 0.9 * width:
                for c, own in reversed(_cuts(w)):
                    head = w[:c] if own else w[:c] + '-'
                    if size(cur + [head]) <= width:
                        cur.append(head)
                        words[k] = w[c:]
                        break
            out.append((cur, False))
            cur = []
        out.append((cur, True))
    return out


def text_font(size=None):
    from PIL import ImageFont
    path = _font_path(FONTS)
    if size:
        return ImageFont.truetype(path, size)
    # the size whose accented capitals to descenders are TEXT_HEIGHT pixels, as the game's
    for s in range(10, 18):
        f = ImageFont.truetype(path, s)
        b = f.getbbox('Ép')
        if b[3] - b[1] >= TEXT_HEIGHT:
            return f
    return f


def _greys(scr):
    """(palette indices from dark to light, their levels 0..255) of the screen's grey ramp."""
    c = scr.pal.astype(np.int64)
    lv = {}
    for k, w in enumerate(c):
        r, g, b = w & 31, w >> 5 & 31, w >> 10 & 31
        if r == g == b and (w or k == scr.transparent):
            lv[k] = r * 255 // 31 if k != scr.transparent else 0
    keys = sorted(lv, key=lv.get)
    return np.array(keys), np.array([lv[k] for k in keys], np.float32)


def _draw_line(scr, x, top, words, last, font, keys, levels):
    from PIL import Image, ImageDraw
    if not words:
        return
    # drawn wider by 1 / CONDENSE, then narrowed to the column
    full = TEXT_WIDTH / CONDENSE
    im = Image.new('L', (int(full) + 8, PITCH + 8), 0)
    d = ImageDraw.Draw(im)
    a = font.getbbox('É')[1]       # top of the accents (may be above the font's origin)
    texts = [w.replace('\u00a0', ' ') for w in words]
    widths = [font.getlength(t) for t in texts]
    gap = font.getlength(' ')
    if not last and len(words) > 1:
        gap = (full - sum(widths)) / (len(words) - 1)
    px = 0.0
    for t, wd in zip(texts, widths):
        d.text((px, -a), t, font=font, fill=255)
        px += wd + gap
    im = im.resize((TEXT_WIDTH + 8, im.height), Image.LANCZOS)
    cov = np.asarray(im, np.float32)
    want = cov * (levels[-1] / 255)
    pick = keys[np.abs(want[..., None] - levels).argmin(-1)]
    sub = scr.index[top:top + cov.shape[0], x:x + cov.shape[1]]
    m = cov[:sub.shape[0], :sub.shape[1]] > 6
    sub[m] = pick[:sub.shape[0], :sub.shape[1]][m]


def description_pages(page1, page2, text):
    """The two description screens (bytes) with `text` in place of the original's (ValueError if
    it does not fit)."""
    font = text_font()
    lines = _wrap(text, font, TEXT_WIDTH)
    room = 2 * (LEFT_LINES + RIGHT_LINES)
    if len(lines) > room:
        raise ValueError('description : %d lignes, place pour %d' % (len(lines), room))
    out = []
    for p, data in enumerate((page1, page2)):
        scr = Screen(data)
        keys, levels = _greys(scr)
        scr.index[FIRST - 8:, :] = scr.transparent
        chunk = lines[p * (LEFT_LINES + RIGHT_LINES):(p + 1) * (LEFT_LINES + RIGHT_LINES)]
        for k, (words, last) in enumerate(chunk):
            x, row = (TEXT_LEFT, k) if k < LEFT_LINES else (TEXT_RIGHT, k - LEFT_LINES)
            _draw_line(scr, x, FIRST + row * PITCH, words, last, font, keys, levels)
        out.append(scr.bytes())
    return out


# ---------------------------------------------------------------------------------------------
def title_tim(original, small=False, suffix=''):
    """A carlogo TIM of the same size with 'Mazda MX-5 RF' (+ a small suffix) in white."""
    from PIL import Image, ImageDraw, ImageFont
    tag, flags = struct.unpack_from('<II', original, 0)
    if flags & 7 != 0 or not flags & 8:
        raise ValueError('titre : TIM 4 bits attendu')
    clen, = struct.unpack_from('<I', original, 8)
    clut = np.frombuffer(original[20:20 + 32], '<u2')
    o = 8 + clen
    blen, x, y, wh, h = struct.unpack_from('<IHHHH', original, o)
    w = wh * 4
    lum = np.array([((c & 31) + (c >> 5 & 31) + (c >> 10 & 31)) * 255 // 93 for c in clut], np.float32)
    clear = [k for k in range(16) if clut[k] == 0]
    if not clear:
        raise ValueError('titre : pas de couleur transparente dans la palette')
    opaque = [k for k in range(16) if clut[k] != 0]
    ss = 4
    im = Image.new('L', (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    narrow = _font_path(TITLE_FONTS['narrow'])
    wide = _font_path(TITLE_FONTS['wide'])
    # two lines, as the Japanese titles (EUNOS over ROADSTER): "Mazda" condensed above, then
    # "MX-5" bold and wide and "RF"; a suffix small at the end of the second line
    big = ImageFont.truetype(wide, int(h * ss * 0.56))
    top = ImageFont.truetype(narrow, int(h * ss * 0.40))
    sml = ImageFont.truetype(narrow, int(h * ss * 0.22))
    line2 = [('MX-5', big, 1.2), (' RF', big, 1.0)] + ([(' ' + suffix, sml, 1.0)] if suffix else [])

    def piece(t, f, sx, scale):
        tmp = Image.new('L', (int(f.getlength(t) + 8 * ss), h * ss * 2), 0)
        ImageDraw.Draw(tmp).text((0, 0), t, font=f, fill=255)
        return tmp.resize((max(1, int(tmp.width * sx * scale)), max(1, int(tmp.height * scale))), Image.LANCZOS), f.getmetrics()[0] * scale

    widths = [f.getlength(t) * sx for t, f, sx in line2]
    scale = min(1.0, (w * ss - 6 * ss) / sum(widths))
    x0 = (w * ss - sum(widths) * scale) / 2
    base2 = h * ss * 0.97
    px = x0
    for (t, f, sx), wd in zip(line2, widths):
        img, asc = piece(t, f, sx, scale)
        im.paste(img, (int(px), int(base2 - asc)), img)
        px += wd * scale
    img, asc = piece('Mazda', top, 1.0, scale)
    im.paste(img, (int(x0 + 2 * ss), int(h * ss * 0.40 - asc)), img)
    cov = np.asarray(im.resize((w, h), Image.LANCZOS), np.float32)
    idx = np.full((h, w), clear[0], np.uint8)
    keys = np.array(opaque)
    vals = lum[keys]
    near = keys[np.abs(cov[..., None] - vals).argmin(-1)]
    idx[cov > 24] = near[cov > 24]
    packed = (idx[:, 0::2] | (idx[:, 1::2] << 4)).astype(np.uint8)
    return original[:o + 12] + packed.tobytes()


# ---------------------------------------------------------------------------------------------
def move_used_car(d, car, price, new_car, letter):
    """.usedcar (raw, not gzipped) with the records of `car` at `price` given to `new_car` and the
    paint `letter`. Returns (data, records changed)."""
    d = bytearray(d)
    a = struct.pack('<I', car) + int(price).to_bytes(3, 'little')
    n = 0
    k = d.find(a)
    while k >= 0:
        if k % 4 == 0:
            struct.pack_into('<I', d, k, new_car)
            d[k + 7] = ord(letter)
            n += 1
        k = d.find(a, k + 1)
    return bytes(d), n


# ---------------------------------------------------------------------------------------------
# the version on the start screens (8-bit TIMs, 352 x 480): a badge in the style of the GT logo
# (its blue and red blocks), "HD PLUS" in white bold italic and the version under it.
# Per screen: (left x, or the centre when the width is None, top y, width, height of the title
# letters, dark panel behind)
VERSION_PLACES = {
    'arcade/l-sel.tim.gz': (22, 196, 164, 22, True),         # under "Select Language"
    'arcade/title_gtmode.tim.gz': (176, 443, None, 18, False),  # the title screens: under the copyright (the game
                                                             # scrolls its mode list under the logo)
    'arcade/title_gtmode_jp.tim.gz': (176, 443, None, 18, False),
    'arcade/title_gtmode_us.tim.gz': (176, 443, None, 18, False),
    'arcade/title_arcade.tim.gz': (176, 443, None, 18, False),
    'arcade/title_arcade_jp.tim.gz': (176, 443, None, 18, False),
    'arcade/title_arcade_us.tim.gz': (176, 443, None, 18, False),
}
GT_BLUE, GT_RED = (40, 72, 168), (214, 30, 42)


def version_screen(tim, text, place, sub=''):
    """An 8-bit TIM (with its 256-colour CLUT) with the version badge drawn on it, in the CLUT's
    nearest colours."""
    from PIL import Image, ImageDraw, ImageFont
    tag, flags = struct.unpack_from('<II', tim, 0)
    if flags & 7 != 1 or not flags & 8:
        raise ValueError('écran : TIM 8 bits attendu')
    clen, = struct.unpack_from('<I', tim, 8)
    clut = np.frombuffer(tim[20:20 + 512], '<u2').astype(np.int64)
    o = 8 + clen
    blen, x, y, wh, h = struct.unpack_from('<IHHHH', tim, o)
    w = wh * 2
    idx = np.frombuffer(tim[o + 12:o + 12 + w * h], np.uint8).reshape(h, w).copy()
    pal = np.stack([(clut & 31), (clut >> 5) & 31, (clut >> 10) & 31], -1).astype(np.float32) * 255 / 31
    left, top, width, size, panel = place
    ss = 4
    bold = ImageFont.truetype(_font_path([WINFONTS + 'arialbi.ttf', WINFONTS + 'arialbd.ttf', FONTS[1]]), size * ss)
    light = ImageFont.truetype(_font_path([WINFONTS + 'ariali.ttf', FONTS[0]]), max(9, int(size * 0.5)) * ss)
    bh = int(size * (1.95 if sub else 1.35))
    need = int((6 + 2 * (0.55 * size + 1) + 4 + 6) + bold.getlength(text) / ss + 0.18 * size) + 2
    if width is None:
        width = need
        left = int(left - width / 2)
    width = max(width, need) if not panel else width
    over = Image.new('RGBA', (width * ss, bh * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    W, H = over.size
    if panel:
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=4 * ss, fill=(12, 12, 16, 200))
    # the two blocks of the GT logo, slanted as its letters
    bx, by, bw, bhh, slant = 6 * ss, int(0.18 * size * ss), int(0.55 * size * ss), int(0.62 * size * ss), int(0.18 * size * ss)
    for k, col in enumerate((GT_BLUE, GT_RED)):
        x0 = bx + k * (bw + ss)
        d.polygon([(x0 + slant, by), (x0 + bw + slant, by), (x0 + bw, by + bhh), (x0, by + bhh)], fill=col + (255,))
    tx = bx + 2 * (bw + ss) + 4 * ss
    t0 = -bold.getbbox(text)[1]
    d.text((tx + ss, t0 + by - 2 * ss + ss), text, font=bold, fill=(0, 0, 0, 170))     # shadow
    d.text((tx, t0 + by - 2 * ss), text, font=bold, fill=(255, 255, 255, 255))
    if sub:
        sy = by + int(size * 1.0 * ss)
        d.line((bx, sy, W - 6 * ss, sy), fill=(190, 190, 200, 160), width=ss)
        ty = sy + 2 * ss - light.getbbox(sub)[1]
        d.text((bx + ss, ty + ss), sub, font=light, fill=(0, 0, 0, 190))
        d.text((bx, ty), sub, font=light, fill=(232, 232, 238, 255))
    small = np.asarray(over.resize((width, bh), Image.LANCZOS), np.float32) / 255
    region = (slice(top, top + bh), slice(left, left + width))
    base = pal[idx[region]]
    a = small[..., 3:4]
    col = base * (1 - a) + small[..., :3] * 255 * a
    changed = a[..., 0] > 0.02
    usable = np.nonzero(clut != 0)[0]          # 0x0000 is transparent on the PlayStation
    dist = ((col[changed][:, None, :] - pal[usable][None]) ** 2).sum(-1)
    sub_idx = idx[region]
    sub_idx[changed] = usable[dist.argmin(1)]
    idx[region] = sub_idx
    return tim[:o + 12] + idx.tobytes() + tim[o + 12 + w * h:]
