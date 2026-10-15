"""The visual front end of make_sd.py: a page served on this PC only (127.0.0.1), opened in the
browser. It finds the files put next to the package, opens the Windows file dialogs, runs
make_sd.py and shows its progress.

python ui_server.py --dossier <package folder> [--port 0] [--no-browser]

  GET  /                      the page (package ui/index.html)
  GET  /ui/<file>             its pictures
  GET  /api/detect?game=ug1   files found in the package folder, and which exist
  POST /api/pick              {"kind": "iso"|"zip"|"kn5"|"nro"|"env"|"folder"} -> {"path"} (Windows dialog)
  POST /api/run               the options -> starts make_sd.py
  GET  /api/status?from=n     its output lines from n, running, exit code
  POST /api/open              {"path"} opens the folder in the Explorer
  POST /api/quit              stops the server
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fabriquer_sd  # noqa: E402

TYPES = {'.html': 'text/html; charset=utf-8', '.jpg': 'image/jpeg', '.png': 'image/png',
         '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml'}
# the page's pictures: in the package's ui/, else the repository's docs/
PICTURES = {'nfsu1.jpg': 'nfsu1_en_jeu.jpg', 'nfsu2.jpg': 'nfsu2_en_jeu.jpg'}
FILTERS = {
    'iso': 'Image disque Xbox (*.iso)|*.iso|Tous les fichiers (*.*)|*.*',
    'zip': 'Release du portage (*.zip)|*.zip|Tous les fichiers (*.*)|*.*',
    'kn5': 'Modèle Assetto Corsa (*.kn5)|*.kn5|Tous les fichiers (*.*)|*.*',
    'nro': 'NRO Switch (*.nro)|*.nro|Tous les fichiers (*.*)|*.*',
    'env': 'Réglages (*.txt)|*.txt|Tous les fichiers (*.*)|*.*',
}


class Job:
    def __init__(self):
        self.lines, self.proc, self.code, self.out = [], None, None, None
        self.lock = threading.Lock()

    def running(self):
        return self.proc is not None and self.code is None

    def start(self, args, out):
        self.lines, self.code, self.out = [], None, out
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b''
        while True:
            b = self.proc.stdout.read1(4096) if hasattr(self.proc.stdout, 'read1') else self.proc.stdout.read(1)
            if not b:
                break
            buf += b
            *done, buf = buf.replace(b'\r', b'\n').split(b'\n')
            with self.lock:
                self.lines += [d.decode('utf-8', 'replace') for d in done if d.strip()]
        if buf.strip():
            with self.lock:
                self.lines.append(buf.decode('utf-8', 'replace'))
        self.code = self.proc.wait()


def pick(kind, start=''):
    """A Windows file (or folder) dialog in front of the browser; the chosen path, or ''."""
    if kind == 'folder':
        body = ("$d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.ShowNewFolderButton = $true;"
                "if ($d.ShowDialog($o) -eq 'OK') { $d.SelectedPath }")
    else:
        flt = FILTERS[kind].replace("'", "''")
        ini = os.path.dirname(start).replace("'", "''") if start else ''
        body = ("$d = New-Object System.Windows.Forms.OpenFileDialog; $d.Filter = '%s';"
                "if ('%s') { $d.InitialDirectory = '%s' };"
                "if ($d.ShowDialog($o) -eq 'OK') { $d.FileName }" % (flt, ini, ini))
    script = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms;"
              "$o = New-Object System.Windows.Forms.Form; $o.TopMost = $true; $o.ShowInTaskbar = $false;"
              "$o.StartPosition = 'CenterScreen'; $o.Width = 1; $o.Height = 1; $o.Show(); $o.Activate();" + body +
              "; $o.Close()")
    r = subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', script], capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return r.stdout.decode('utf-8', 'replace').strip().splitlines()[-1] if r.stdout.strip() else ''


def build_args(o):
    """make_sd.py's arguments from the page's options (each one checked)."""
    game = o.get('game')
    if game not in ('ug1', 'ug2'):
        raise ValueError('jeu inconnu')
    a = [sys.executable, os.path.join(HERE, 'make_sd.py'), '--game', game]
    for key, opt in (('usa', '--usa'), ('release', '--release'), ('out', '--out')):
        if not o.get(key):
            raise ValueError('il manque : ' + key)
        a += [opt, o[key]]
    for key in ('usa', 'release'):
        if not os.path.isfile(o[key]):
            raise ValueError('introuvable : ' + o[key])
    lang = o.get('lang', 'en')
    if lang != 'en':
        if not o.get('europe') or not os.path.isfile(o['europe']):
            raise ValueError('il faut le disque Europe pour cette langue')
        a += ['--europe', o['europe'], '--langue', lang]
    for key, opt in (('nro', '--nro'), ('env', '--env')):
        if o.get(key):
            if not os.path.isfile(o[key]):
                raise ValueError('introuvable : ' + o[key])
            a += [opt, o[key]]
    if o.get('top') in ('closed', 'open'):
        if not o.get('kn5') or not os.path.isfile(o['kn5']):
            raise ValueError('il faut le modèle mazda_mx5_rf.kn5 pour la MX-5')
        a += ['--kn5', o['kn5'], '--top', o['top']]
        if o.get('perf'):
            a.append('--perf')
        if o.get('names'):
            a.append('--names')
    if game == 'ug1' and not o.get('autoload', True):
        a.append('--no-autoload')
    return a


def make_handler(folder, ui_dir, job, server_box):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_host(self):
            host = (self.headers.get('Host') or '').split(':')[0]
            return host in ('127.0.0.1', 'localhost')

        def _send(self, code, body, ctype='application/json; charset=utf-8'):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self):
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')

        def do_GET(self):
            if not self._ok_host():
                return self._send(403, {'error': 'host'})
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path in ('/', '/index.html') or u.path.startswith('/ui/'):
                name = 'index.html' if u.path in ('/', '/index.html') else os.path.basename(u.path)
                p = os.path.join(ui_dir, name)
                if not os.path.isfile(p) and name in PICTURES:      # run from the repository
                    p = os.path.join(HERE, '..', '..', 'docs', PICTURES[name])
                if not os.path.isfile(p):
                    return self._send(404, {'error': 'not found'})
                return self._send(200, open(p, 'rb').read(), TYPES.get(os.path.splitext(p)[1], 'application/octet-stream'))
            if u.path == '/api/detect':
                game = q.get('game', 'ug1')
                g = fabriquer_sd.guess(folder, game)
                return self._send(200, {'folder': folder, 'files': {k.lstrip('-'): v for k, v in g.items()}})
            if u.path == '/api/exists':
                p = q.get('path', '')
                return self._send(200, {'file': os.path.isfile(p), 'dir': os.path.isdir(p),
                                        'empty': os.path.isdir(p) and not os.listdir(p)})
            if u.path == '/api/status':
                start = int(q.get('from', 0))
                with job.lock:
                    lines = job.lines[start:]
                    total = len(job.lines)
                return self._send(200, {'lines': lines, 'next': total, 'running': job.running(), 'code': job.code,
                                        'out': job.out})
            return self._send(404, {'error': 'not found'})

        def do_POST(self):
            if not self._ok_host():
                return self._send(403, {'error': 'host'})
            u = urlparse(self.path)
            try:
                o = self._json()
            except ValueError:
                return self._send(400, {'error': 'json'})
            if u.path == '/api/pick':
                kind = o.get('kind')
                if kind not in FILTERS and kind != 'folder':
                    return self._send(400, {'error': 'kind'})
                return self._send(200, {'path': pick(kind, o.get('start', ''))})
            if u.path == '/api/run':
                if job.running():
                    return self._send(409, {'error': 'déjà en cours'})
                try:
                    args = build_args(o)
                except ValueError as e:
                    return self._send(400, {'error': str(e)})
                job.start(args, os.path.join(o['out'], 'switch'))
                return self._send(200, {'started': True})
            if u.path == '/api/open':
                p = o.get('path', '')
                if os.path.isdir(p):
                    os.startfile(p)
                    return self._send(200, {'opened': p})
                return self._send(404, {'error': 'introuvable'})
            if u.path == '/api/quit':
                self._send(200, {'bye': True})
                threading.Thread(target=server_box[0].shutdown, daemon=True).start()
                return
            return self._send(404, {'error': 'not found'})
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dossier', default=os.getcwd(), help='dossier du paquet (où sont posés les fichiers)')
    ap.add_argument('--ui', default=None, help='dossier de la page (défaut : <dossier>/outils/ui)')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    folder = os.path.abspath(a.dossier)
    ui_dir = a.ui or os.path.join(folder, 'outils', 'ui')
    if not os.path.isfile(os.path.join(ui_dir, 'index.html')):
        ui_dir = os.path.join(HERE, 'package', 'ui')
    job, box = Job(), [None]
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(folder, ui_dir, job, box))
    box[0] = srv
    url = 'http://127.0.0.1:%d/' % srv.server_address[1]
    print('MX-5 RF · NFS Underground : %s' % url)
    print('(laisse cette fenêtre ouverte / keep this window open ; Ctrl+C pour arrêter)', flush=True)
    if not a.no_browser:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    if job.running():
        job.proc.terminate()


if __name__ == '__main__':
    main()
