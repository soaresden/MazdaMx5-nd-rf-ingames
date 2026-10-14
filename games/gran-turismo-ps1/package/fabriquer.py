"""Assistant of the Windows package: asks the questions (French or English), finds the player's
files next to it and makes the disc with make_car.generate. Run by FABRIQUER.bat.

Files looked for in the package folder (or given on the command line):
  the game: Gran Turismo, Europe multi-language (PAL, SCES-00984): .chd, .cue (+ .bin) or .bin
  the model: mazda_mx5_rf.kn5 (Assetto Corsa mod)
"""
import glob
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # the package folder (where the player's files go)
TOOLS = os.path.join(HERE, 'games', 'gran-turismo-ps1')
sys.path[:0] = [TOOLS, os.path.join(HERE, 'common')]

import make_car  # noqa: E402

LANG = 'fr'


def T(fr, en):
    return fr if LANG == 'fr' else en


def ask(prompt, default=''):
    try:
        a = input(prompt + (' [%s]' % default if default != '' else '') + ' : ').strip()
    except EOFError:
        a = ''
    return a or default


def pick(kind_fr, kind_en, patterns, also=()):
    found = []
    for p in patterns:
        found += glob.glob(os.path.join(ROOT, p))
    found = [f for f in sorted(set(found)) if not os.path.basename(os.path.dirname(f)).startswith('MX5_RF')]
    found += [f for f in also if f and os.path.exists(f)]
    # a .bin named by a .cue next to it: only the .cue is listed
    cues = [f for f in found if f.lower().endswith('.cue')]
    named = set()
    for c in cues:
        try:
            named.add(os.path.normcase(make_car.binimage.cue_bin(c)))
        except ValueError:
            pass
    found = [f for f in found if os.path.normcase(f) not in named]
    while True:
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            print(T('Plusieurs fichiers trouvés pour %s :', 'Several files found for %s:') % T(kind_fr, kind_en))
            for i, f in enumerate(found, 1):
                print('  %d. %s' % (i, os.path.basename(f)))
            a = ask(T('Numéro', 'Number'), '1')
            if a.isdigit() and 1 <= int(a) <= len(found):
                return found[int(a) - 1]
            continue
        print(T('Je ne trouve pas %s dans ce dossier.', 'I cannot find %s in this folder.') % T(kind_fr, kind_en))
        a = ask(T('Glisse le fichier ici (ou tape son chemin)', 'Drag the file here (or type its path)')).strip('"')
        if a and os.path.exists(a):
            return a


def main():
    global LANG
    print('=' * 70)
    print(' MX-5 RF -> Gran Turismo (PlayStation, Europe multi / PAL, SCES-00984)')
    print('=' * 70)
    a = ask('Langue / Language : 1 = Français, 2 = English', '1')
    LANG = 'en' if a.strip() == '2' else 'fr'
    args = [x for x in sys.argv[1:] if os.path.exists(x)]
    disc_in = pick('ton image du jeu (.chd, .cue ou .bin)', 'your game image (.chd, .cue or .bin)',
                   ['*.chd', '*.cue', '*.bin'], [x for x in args if not x.lower().endswith('.kn5')])
    kn5 = pick('le modèle mazda_mx5_rf.kn5', 'the model mazda_mx5_rf.kn5', ['*.kn5', '*/*.kn5'],
               [x for x in args if x.lower().endswith('.kn5')])
    print()
    print(T('Jeu    : ', 'Game   : ') + disc_in)
    print(T('Modèle : ', 'Model  : ') + kn5)
    print()
    # the Roadsters of the game, each with its race version (it gets the same roof)
    base = [c for c in make_car.ROADSTERS if not c.endswith('r') or c == 'arodn']
    twin = {c: c[:-1] + 'r' for c in base if c[:-1] + 'r' in make_car.ROADSTERS}
    print(T('Chaque Eunos Roadster peut devenir la MX-5 RF capotée ou décapotée (sa version course suit) :',
            'Each Eunos Roadster can become the MX-5 RF closed or open (its race version follows):'))
    print(T('  1 = toutes capotées   2 = toutes décapotées   3 = voiture par voiture',
            '  1 = all closed   2 = all open   3 = car by car'))
    a = ask(T('Choix', 'Choice'), '1').strip()
    roof = {}
    if a == '3':
        print(T('Pour chaque voiture : C = capotée, D = décapotée, R = garder la Roadster.',
                'For each car: C = closed, O = open, R = keep the Roadster.'))
        for c in base:
            r = ask('  ' + make_car.ROADSTERS[c][1], 'C').strip().upper()[:1]
            if r in ('D', 'O'):
                roof[c] = 'open'
            elif r != 'R':
                roof[c] = 'closed'
    else:
        roof = {c: 'open' if a == '2' else 'closed' for c in base}
    for c in list(roof):
        if c in twin:
            roof[twin[c]] = roof[c]
    if not roof:
        raise SystemExit(T('Aucune Roadster à remplacer.', 'No Roadster to replace.'))
    tops = set(roof.values())
    top = tops.pop() if len(tops) == 1 else 'mixed'
    print(T('Prix chez Mazda, en crédits. Le prix réaliste est 29900 ; mets 100 pour l\'avoir dès le début du jeu.',
            'Price at the Mazda dealer, in credits. The realistic price is 29900; put 100 to have it from the start.'))
    a = ask(T('Prix', 'Price'), '29900')
    price = int(a) if a.isdigit() else 29900
    cheat = False
    if os.path.isdir(os.path.join(HERE, 'gt1cheat')):
        a = ask(T('Ajouter le cheat (maintenir SELECT : figer le chrono des permis, changer les crédits) ? o/n',
                  'Add the cheat (hold SELECT: freeze the licence timer, change the credits)? y/n'), 'n')
        cheat = a.strip().lower() in ('o', 'y', 'oui', 'yes')
    out_dir = os.path.join(ROOT, 'MX5_RF_' + {'open': T('decapotee', 'open'), 'closed': T('capotee', 'closed'),
                                             'mixed': T('capotee_et_decapotee', 'closed_and_open')}[top])
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'Gran Turismo MX-5 RF.bin')
    src = make_car.binimage.cue_bin(disc_in) if disc_in.lower().endswith('.cue') else disc_in
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(out)):
        raise SystemExit(T('Le résultat écraserait ton image du jeu : déplace-la.', 'The result would overwrite your game image: move it.'))
    print()
    t0 = time.time()
    files, d = make_car.generate(disc_in, kn5, roof, price=price, cheat=cheat)
    print(T("L'image disque", 'The disc image'))
    d.write_bin(out, files, progress=lambda i, n: print('  %d%%' % (100 * i // n), end='\r'))
    print()
    print(T('Terminé en %d s :', 'Done in %d s:') % (time.time() - t0))
    print('  ' + out)
    print('  ' + os.path.splitext(out)[0] + '.cue')
    print(T("Ouvre le .cue dans DuckStation (ou un autre émulateur PlayStation).",
            'Open the .cue in DuckStation (or another PlayStation emulator).'))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # shown to the player, the window stays open (pause in the .bat)
        print()
        print('ERREUR / ERROR :', e)
        sys.exit(1)
