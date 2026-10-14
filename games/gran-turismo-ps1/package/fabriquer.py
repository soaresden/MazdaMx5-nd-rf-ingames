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
    codes = list(make_car.ROADSTERS)
    print(T('Quelles Roadster remplacer par la MX-5 ?', 'Which Roadsters should the MX-5 replace?'))
    for i, c in enumerate(codes, 1):
        print('  %2d. %s' % (i, make_car.ROADSTERS[c][1]))
    a = ask(T('Numéros séparés par des virgules, ou Entrée pour toutes', 'Numbers separated by commas, or Enter for all'))
    if a:
        sel = [codes[int(x) - 1] for x in a.replace(' ', '').split(',') if x.isdigit() and 1 <= int(x) <= len(codes)]
        codes = sel or codes
    a = ask(T('Toit : 1 = capotée (fermé), 2 = décapotée', 'Roof: 1 = closed, 2 = open top'), '1')
    top = 'open' if a.strip() == '2' else 'closed'
    print(T('Prix chez Mazda, en crédits. Le prix réaliste est 29900 ; mets 100 pour l\'avoir dès le début du jeu.',
            'Price at the Mazda dealer, in credits. The realistic price is 29900; put 100 to have it from the start.'))
    a = ask(T('Prix', 'Price'), '29900')
    price = int(a) if a.isdigit() else 29900
    cheat = False
    if os.path.isdir(os.path.join(HERE, 'gt1cheat')):
        a = ask(T('Ajouter le cheat (maintenir SELECT : figer le chrono des permis, changer les crédits) ? o/n',
                  'Add the cheat (hold SELECT: freeze the licence timer, change the credits)? y/n'), 'n')
        cheat = a.strip().lower() in ('o', 'y', 'oui', 'yes')
    out_dir = os.path.join(ROOT, 'MX5_RF_' + (T('decapotee', 'open') if top == 'open' else T('capotee', 'closed')))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'Gran Turismo MX-5 RF.bin')
    src = make_car.binimage.cue_bin(disc_in) if disc_in.lower().endswith('.cue') else disc_in
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(out)):
        raise SystemExit(T('Le résultat écraserait ton image du jeu : déplace-la.', 'The result would overwrite your game image: move it.'))
    print()
    t0 = time.time()
    files, d = make_car.generate(disc_in, kn5, codes, top, price, cheat=cheat)
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
