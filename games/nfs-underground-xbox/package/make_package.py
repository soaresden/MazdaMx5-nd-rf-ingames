"""Builds the Windows package MX5-RF_NFSUnderground.zip: FABRIQUER.bat, LISEZMOI.txt / README.txt
and outils/ (the Python tools of this repository, in the same tree). No game data.

python make_package.py [output.zip]   (default: ../../../dist/MX5-RF_NFSUnderground.zip)
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
TOOLS = ['games/nfs-underground-xbox', 'games/nfs-most-wanted-x360', 'common']


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'dist', 'MX5-RF_NFSUnderground.zip')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    top = 'MX5-RF_NFSUnderground/'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('FABRIQUER.bat', 'LISEZMOI.txt', 'README.txt'):
            data = open(os.path.join(HERE, name), 'rb').read().replace(b'\r\n', b'\n')
            z.writestr(top + name, data.replace(b'\n', b'\r\n'))   # Windows line ends (cmd needs them)
        n = 0
        for d in TOOLS:
            for f in sorted(os.listdir(os.path.join(REPO, d))):
                if f.endswith('.py'):
                    z.write(os.path.join(REPO, d, f), top + 'outils/' + d + '/' + f)
                    n += 1
        z.write(os.path.join(REPO, 'LICENSE'), top + 'LICENSE.txt')
    print('written', out, os.path.getsize(out), 'bytes,', n, 'tools')


if __name__ == '__main__':
    main()
