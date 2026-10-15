"""Ready-to-copy SD card folder for the Switch ports of NFS Underground (nfsu1-sw) and Underground 2
(nfsu2-sw): the port's release zip, the extracted USA disc, and as options the French version
(from the Europe disc), the MX-5 RF in place of the Miata, its handling and its name.

python make_sd.py --game ug1|ug2 --usa <USA ISO> --release <nfsu1x.zip|nfsu2x.zip> --out <folder>
                  [--europe <Europe ISO> [--langue fr|de|it|es]] [--nro <other NRO>] [--env <port>_env.txt] [--kn5 mazda_mx5_rf.kn5 --top closed|open]
                  [--perf] [--names] [--no-autoload]

Writes <folder>/switch/nfsu1x/ (or nfsu2x/): the NRO, <port>_env.txt, game/. Nothing is written
in the images. The folder must not hold a game already (a card's saves live in game/UDATA).

French version: Underground 2 needs no port change (ZZDATA10/11 + ZDIR, vf_ug2). Underground
uses NFSU1_LANGUAGE=fr when the NRO knows it (antoxa2584x/nfsu1-sw#8, or --nro), else plan B,
the USA default.xbe with French as language 0 (vf_ug1). Underground's NFSU1_AUTOLOAD (#9) is
set when the NRO knows it; Underground 2's port loads the save by itself.
"""
import argparse
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(HERE, '..', 'nfs-most-wanted-x360'))
import make_car    # noqa: E402  (this folder's, before Most Wanted's make_car.py is on the path)
import build_ug    # noqa: E402
import disc_ug     # noqa: E402
import vf_ug1      # noqa: E402
import vf_ug2      # noqa: E402
import zdir_ug2    # noqa: E402

PORT = {'ug1': 'nfsu1x', 'ug2': 'nfsu2x'}
LANG_NAME = {'fr': 'français', 'de': 'allemand', 'it': 'italien', 'es': 'espagnol'}
TITLE = {'ug1': 'Need for Speed Underground', 'ug2': 'Need for Speed Underground 2'}


def unzip_release(zpath, dest, port, nro, env, log):
    """The release's NRO and env file (not its empty save/ images: copied over a card, they would
    replace the ones there; the port makes them on its first run)."""
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if port + '.nro' not in names:
            raise SystemExit("%s n'est pas le zip de %s (pas de %s.nro dedans)" % (zpath, port, port))
        for i in z.infolist():
            if i.filename.startswith('save/'):
                continue
            dst = os.path.join(dest, *i.filename.rstrip('/').split('/'))
            if i.is_dir():
                os.makedirs(dst, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as o:
                o.write(z.read(i))
    log('portage : %s' % os.path.basename(zpath))
    if nro:
        shutil.copyfile(nro, os.path.join(dest, port + '.nro'))
        log('  NRO remplacé par %s' % nro)
    if env:
        shutil.copyfile(env, os.path.join(dest, port + '_env.txt'))
        log('  réglages : %s' % env)
    with open(os.path.join(dest, port + '.nro'), 'rb') as f:
        return f.read()


def add_env(path, lines, log):
    with open(path, encoding='utf-8', errors='replace') as f:
        text = f.read()
    keys = {l.split('=')[0] for l in lines}
    kept = [l for l in text.splitlines() if l.split('=')[0].strip() not in keys]
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(kept).rstrip('\n') + '\n\n# make_sd.py\n' + '\n'.join(lines) + '\n')
    log('  %s : %s' % (os.path.basename(path), ', '.join(lines)))


def on_disc(game_dir, t, path):
    """The extracted file for a disc path in any case."""
    k = disc_ug.find(t, path)
    if not k:
        raise SystemExit('%s absent du disque' % path)
    return os.path.join(game_dir, *k.split('/'))


def write(path, data):
    if os.path.exists(path):
        os.remove(path)             # a fresh file, never through a link
    with open(path, 'wb') as f:
        f.write(data)


def mx5_ug1(a, game_dir, t, log):
    read = lambda p: open(on_disc(game_dir, t, p), 'rb').read()   # noqa: E731
    geo, tex = (read(n) for n in make_car.FILES)
    log('MX-5 RF (%s)' % ('décapotée' if a.top == 'open' else 'capotée'))
    new = build_ug.build(geo, tex, a.kn5, a.top, 'ug1', log=lambda *x: None)
    for n, data in zip(make_car.FILES, new):
        write(on_disc(game_dir, t, n), data)
    for n, data in make_car.extras(read, 'ug1', a.perf, True, a.names, log=log).items():
        write(on_disc(game_dir, t, n), data)


def mx5_ug2(a, game_dir, log):
    """Plan B (the MX-5 over the Miata in ZZDATA2) and, for handling and name, ZZDATA12; the car's
    ZDIR entries go into the ZDIR.BIN in place (the French one too)."""
    nfs = os.path.join(game_dir, 'NFSUNDER')
    packs = make_car.Packs(a.usa)
    geo, tex = (packs.read(n) for n in make_car.FILES)
    log('MX-5 RF (%s)' % ('décapotée' if a.top == 'open' else 'capotée'))
    new_geo, new_tex = build_ug.build(geo, tex, a.kn5, a.top, 'ug2', log=lambda *x: None)
    zz, car_zdir = packs.replaced({make_car.FILES[0]: new_geo, make_car.FILES[1]: new_tex})
    for name, data in zz.items():
        write(os.path.join(nfs, name), data)
    with open(os.path.join(nfs, 'ZDIR.BIN'), 'rb') as f:
        zdir = bytearray(f.read())
    stock = bytes(packs.zdir)
    for i in range(0, len(stock) - 23, 24):
        if car_zdir[i:i + 24] != stock[i:i + 24]:
            if zdir[i:i + 24] != stock[i:i + 24]:
                raise SystemExit('entrée %d du ZDIR.BIN déjà changée par autre chose' % (i // 24))
            zdir[i:i + 24] = car_zdir[i:i + 24]
    more = make_car.extras(packs.read_all, 'ug2', a.perf, True, a.names, log=log)
    if more:
        zz10 = os.path.join(nfs, 'ZZDATA10.BIN') if a.europe else None
        pack, manifest = make_car.ug2_pack(packs, more, zz10, log)
        zdir, _ = zdir_ug2.apply(bytes(zdir), manifest, log=log)
        left = zdir_ug2.check_untouched(zdir, manifest)
        if left:
            raise SystemExit('entrées non redirigées : %r' % left)
        write(os.path.join(nfs, 'ZZDATA12.BIN'), pack)
        with open(os.path.join(nfs, 'ZZDATA12.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=1)
    write(os.path.join(nfs, 'ZDIR.BIN'), bytes(zdir))


README = """{title} sur Switch ({port}) - dossier fait par make_sd.py
==========================================================================

{lines}

Installer (jeu fermé) : si le jeu est déjà sur ta carte, copie d'abord
sdmc:/switch/{port}/game/UDATA (tes sauvegardes) ailleurs. Puis copie le dossier switch d'ici
à la racine de la carte, PAR-DESSUS (fusionner, remplacer les fichiers), sans jamais supprimer
ni remplacer tout le dossier game/ de la carte.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', required=True, choices=('ug1', 'ug2'))
    ap.add_argument('--usa', required=True, help='image du disque Xbox USA')
    ap.add_argument('--release', required=True, help='zip de la release du portage')
    ap.add_argument('--out', required=True, help='dossier de sortie (la racine de la carte SD)')
    ap.add_argument('--europe', help='image du disque Xbox Europe : jeu dans la langue de --langue')
    ap.add_argument('--langue', default='fr', choices=('fr', 'de', 'it', 'es'),
                    help='avec --europe : fr, de, it (Underground 2 : pas es, sans voix espagnoles)')
    ap.add_argument('--nro', help='un autre NRO que celui du zip')
    ap.add_argument('--env', help='ton fichier de réglages (<port>_env.txt) à la place de celui du zip')
    ap.add_argument('--kn5', help='modèle Assetto Corsa de la MX-5 RF : la MX-5 à la place de la Miata')
    ap.add_argument('--top', default='closed', choices=('closed', 'open'))
    ap.add_argument('--perf', action='store_true', help='conduite et performances de la MX-5 RF 184 ch')
    ap.add_argument('--names', action='store_true', help='« MX-5 RF » dans les menus')
    ap.add_argument('--no-autoload', action='store_true', help='pas de chargement automatique (Underground)')
    a = ap.parse_args()
    if (a.perf or a.names) and not a.kn5:
        ap.error('--perf et --names vont avec --kn5')
    if a.game == 'ug2' and a.langue not in vf_ug2.LANGS:
        ap.error("Underground 2 : --langue fr, de ou it (le disque Europe n'a pas de voix espagnoles)")
    port = PORT[a.game]
    dest = os.path.join(a.out, 'switch', port)
    game_dir = os.path.join(dest, 'game')
    if os.path.isdir(game_dir) and os.listdir(game_dir):
        raise SystemExit('%s contient déjà un jeu : choisis un dossier vide (tes sauvegardes sont dans '
                         'game/UDATA, je ne veux pas risquer de les écraser)' % game_dir)
    lines = []
    nro = unzip_release(a.release, dest, port, a.nro, a.env, print)
    print('disque USA : %s' % a.usa)
    t = disc_ug.extract(a.usa, game_dir)
    lines.append('- le portage (%s) et le disque USA extrait dans game/' % os.path.basename(a.release))
    env = os.path.join(dest, port + '_env.txt')
    settings = []
    if a.europe:
        name = LANG_NAME[a.langue]
        print('langue %s : %s' % (name, a.europe))
        if a.game == 'ug1':
            vf_ug1.dubbed_movies(a.europe, a.usa, game_dir, a.langue)
            if b'NFSU1_LANGUAGE' in nro:
                settings.append('NFSU1_LANGUAGE=' + a.langue)
                lines.append('- en %s : NFSU1_LANGUAGE=%s + les cinématiques doublées du disque Europe' % (name, a.langue))
            elif a.langue == 'fr':
                xbe = on_disc(game_dir, t, 'default.xbe')
                write(xbe, vf_ug1.patch_xbe(open(xbe, 'rb').read()))
                lines.append('- en français : ce NRO ne connaît pas NFSU1_LANGUAGE, donc default.xbe USA '
                             'corrigé (plan B) + les cinématiques françaises du disque Europe')
            else:
                raise SystemExit("ce NRO ne connaît pas NFSU1_LANGUAGE (antoxa2584x/nfsu1-sw#8) : sans lui, "
                                 "seul le français est possible (--nro pour en donner un autre)")
        else:
            vf_ug2.build(game_dir, a.europe, a.langue)
            lines.append('- en %s : NFSUNDER/ZZDATA10.BIN, ZZDATA11.BIN et ZDIR.BIN '
                         "(retour à l'anglais : remettre ZDIR_anglais.BIN à la place de ZDIR.BIN)" % name)
    if a.game == 'ug1' and not a.no_autoload:
        if b'NFSU1_AUTOLOAD' in nro:
            settings.append('NFSU1_AUTOLOAD=1')
            lines.append('- chargement automatique de la sauvegarde au démarrage (NFSU1_AUTOLOAD=1)')
        else:
            print('  ce NRO ne connaît pas NFSU1_AUTOLOAD : pas de chargement automatique')
    if settings:
        add_env(env, settings, print)
    if a.kn5:
        if a.game == 'ug1':
            mx5_ug1(a, game_dir, t, print)
        else:
            mx5_ug2(a, game_dir, print)
        lines.append('- la MX-5 RF %s à la place de la Miata%s%s' % (
            'décapotée' if a.top == 'open' else 'capotée',
            ', conduite MX-5 RF 184 ch' if a.perf else '', ', nom « MX-5 RF » dans les menus' if a.names else ''))
    with open(os.path.join(a.out, 'LISEZMOI_%s.txt' % port), 'w', encoding='utf-8') as f:
        f.write(README.format(title=TITLE[a.game], port=port, lines='\n'.join(lines)))
    print('fini :', dest)


if __name__ == '__main__':
    main()
