"""Questions, then make_sd.py: the SD card folder of NFS Underground 1 or 2 for Switch.

python fabriquer_sd.py ug1|ug2 [--usa ISO] [--europe ISO] [--release ZIP] [--nro NRO] [--env FILE]
                       [--kn5 KN5] [--out FOLDER]
The paths given are the defaults offered; each question can be answered with Enter.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def ask(q, default=''):
    a = input('%s%s : ' % (q, ' [%s]' % default if default else '')).strip().strip('"')
    return a or default


def ask_file(q, default=''):
    while True:
        a = ask(q, default)
        if os.path.isfile(a):
            return a
        print('  introuvable : %s' % (a or '(rien)'))


def guess(folder, game):
    """Defaults from the files put next to FABRIQUER.bat: the game's discs (USA / Europe by name),
    the port's release zip, the model; the output folder SD_<port>."""
    port = {'ug1': 'nfsu1x', 'ug2': 'nfsu2x'}[game]
    out = {'--out': os.path.join(folder, 'SD_' + port)}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for n in names:
        low = n.lower()
        two = 'underground 2' in low or 'underground2' in low or 'nfsu2' in low
        if low.endswith('.iso') and ('underground' in low or 'nfsu' in low) and two == (game == 'ug2'):
            if '(usa)' in low or 'ntsc' in low:
                out.setdefault('--usa', os.path.join(folder, n))
            elif 'europe' in low or 'pal' in low or '(fr' in low or 'fr,' in low:
                out.setdefault('--europe', os.path.join(folder, n))
        elif low == port + '.zip' or (low.startswith(port) and low.endswith('.zip')):
            out.setdefault('--release', os.path.join(folder, n))
        elif low.endswith('.kn5') and 'mx5' in low and 'collider' not in low:
            out.setdefault('--kn5', os.path.join(folder, n))
    return out


def yes(q, default='o'):
    return ask(q + ' (o/n)', default).lower().startswith(('o', 'y'))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('ug1', 'ug2'):
        game, rest = sys.argv[1], sys.argv[2:]
    else:
        rest = sys.argv[1:]
        game = ''
        while game not in ('1', '2'):
            game = ask('Quel jeu ? 1 = Need for Speed Underground, 2 = Underground 2')
        game = 'ug' + game
    opts = dict(zip(rest[0::2], rest[1::2]))
    if '--dossier' in opts:
        for k, v in guess(opts.pop('--dossier'), game).items():
            opts.setdefault(k, v)
    title = 'Need for Speed Underground' + (' 2' if game == 'ug2' else '')
    print('=' * 60)
    print(' %s : dossier pour la carte SD de la Switch' % title)
    print('=' * 60)
    args = [sys.executable, os.path.join(HERE, 'make_sd.py'), '--game', game]
    usa = ask_file('Disque Xbox USA (.iso)', opts.get('--usa', ''))
    rel = ask_file('Zip de la release du portage', opts.get('--release', ''))
    args += ['--usa', usa, '--release', rel]
    if opts.get('--nro') and yes('Utiliser ce NRO à la place de celui du zip : %s' % opts['--nro']):
        args += ['--nro', opts['--nro']]
    if opts.get('--env') and yes('Reprendre tes réglages : %s' % opts['--env']):
        args += ['--env', opts['--env']]
    langs = 'fr, de, it' + (', es' if game == 'ug1' else '')
    lang = ask('Langue : en = anglais (disque USA seul), ou %s (il faut le disque Europe)' % langs, 'fr').lower()
    if lang in langs.split(', '):
        args += ['--europe', ask_file('Disque Xbox Europe (.iso)', opts.get('--europe', '')), '--langue', lang]
    top = ask('La MX-5 RF à la place de la Miata : C = capotée, D = décapotée, N = non', 'D').upper()
    if top in ('C', 'D'):
        args += ['--kn5', ask_file('Modèle de la MX-5 (mazda_mx5_rf.kn5)', opts.get('--kn5', '')),
                 '--top', 'closed' if top == 'C' else 'open']
        if yes('Conduite et performances de la MX-5 RF 184 ch ? (à essayer)', 'n'):
            args.append('--perf')
        if yes('« MX-5 RF » dans les menus ? (à essayer)', 'n'):
            args.append('--names')
    if game == 'ug1' and not yes('Charger la sauvegarde tout seul au démarrage ?'):
        args.append('--no-autoload')
    out = ask('Dossier à créer (vide)', opts.get('--out', ''))
    args += ['--out', out]
    print()
    r = subprocess.call(args)
    print()
    print('Terminé.' if r == 0 else 'Erreur (voir ci-dessus).')
    if r == 0:
        print('À copier : %s\\switch  ->  la racine de la carte SD, PAR-DESSUS.' % out)
        print('Tes sauvegardes (game\\UDATA) : copie-les ailleurs avant, par sécurité.')
    return r


if __name__ == '__main__':
    sys.exit(main())
