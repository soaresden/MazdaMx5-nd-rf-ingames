"""Builds the Windows package MX5-RF_GranTurismo1.zip: FABRIQUER.bat, LISEZMOI.txt / README.txt
and outils/ (the Python tools of this repository, the font, the badge). No game data.

python make_package.py [output.zip]   (default: ../../../dist/MX5-RF_GranTurismo1.zip)
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
TOOLS = [
    ('games/gran-turismo-ps1', '*.py'),
    ('common', '*.py'),
]
EXTRA = [
    'games/gran-turismo-ps1/fonts/LiberationSans-Bold.ttf',
    'games/gran-turismo-ps1/fonts/LICENSE-LiberationSans.txt',
    'games/nfs-most-wanted-x360/assets/badge_mx5_miata_1024.png',
    'LICENSE',
]
TEXT = ('.bat', '.txt')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'dist', 'MX5-RF_GranTurismo1.zip')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    top = 'MX5-RF_GranTurismo1/'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('FABRIQUER.bat', 'LISEZMOI.txt', 'README.txt'):
            data = open(os.path.join(HERE, name), 'rb').read().replace(b'\r\n', b'\n')
            z.writestr(top + name, data.replace(b'\n', b'\r\n'))   # Windows line ends (cmd needs them)
        z.write(os.path.join(HERE, 'fabriquer.py'), top + 'outils/fabriquer.py')
        for d, pat in TOOLS:
            for f in sorted(os.listdir(os.path.join(REPO, d))):
                if f.endswith('.py'):
                    z.write(os.path.join(REPO, d, f), top + 'outils/' + d + '/' + f)
        for f in EXTRA:
            p = os.path.join(REPO, f)
            if os.path.exists(p):
                z.write(p, top + ('outils/' + f if f != 'LICENSE' else 'LICENSE.txt'))
    print('written', out, os.path.getsize(out), 'bytes')


if __name__ == '__main__':
    main()
