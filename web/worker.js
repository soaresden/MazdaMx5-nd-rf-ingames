// Web worker: runs games/nfs-most-wanted-x360/make_car.py in Pyodide, in the visitor's browser.
// The disc image is never loaded whole: Python's open() of it reads slices of the chosen File
// with FileReaderSync (only available in workers). Nothing is sent anywhere.

importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

const SOURCES = [
  'common/kn5.py', 'common/acmodel.py', 'common/qem.py',
  ...['attrib360', 'build_mx5', 'dxt', 'fe_badges', 'geo360', 'huff', 'jdlz', 'make_car', 'sol360',
      'solids', 'tpk', 'tpk360', 'xdvdfs', 'xenos', 'zzdata']
    .map((m) => `games/nfs-most-wanted-x360/${m}.py`),
  'games/nfs-most-wanted-x360/assets/badge_mx5_miata_1024.png',
];

const say = (type, data) => postMessage({ type, ...data });
// language of the page (worker.js?lang=en); the steps logged by make_car.py are in French
const EN = new URL(self.location).searchParams.get('lang') === 'en';
const T = (fr, en) => (EN ? en : fr);
const STEPS_EN = [
  [/^1\/3 la voiture.*/, '1/3 the car (geometry, textures, wheels, performance, sound)'],
  [/^2\/3 les menus.*/, '2/3 the menus (logo and name)'],
  [/^3\/3 le zip/, '3/3 the zip'],
  [/^VF : (\d+) entrées anglaises masquées.*/, 'French dub: $1 English entries hidden in GLOBALMEMORYFILE.BIN'],
];
const tr = (text) => { if (EN) for (const [re, en] of STEPS_EN) if (re.test(text)) return text.replace(re, en); return text; };
let pyodide = null;

async function init() {
  say('log', { text: T('Chargement de Python (Pyodide)…', 'Loading Python (Pyodide)…') });
  pyodide = await loadPyodide();
  await pyodide.loadPackage(['numpy', 'pillow']);
  say('log', { text: T('Chargement des outils…', 'Loading the tools…') });
  for (const path of SOURCES) {
    const res = await fetch(new URL(`../${path}`, self.location));
    if (!res.ok) throw new Error(`${path} : ${res.status}`);
    const dir = '/app/' + path.split('/').slice(0, -1).join('/');
    pyodide.FS.mkdirTree(dir);
    pyodide.FS.writeFile('/app/' + path, new Uint8Array(await res.arrayBuffer()));
  }
  pyodide.FS.mkdirTree('/in');
  await pyodide.runPythonAsync(`
import builtins, io, sys
sys.path[:0] = ['/app/games/nfs-most-wanted-x360', '/app/common']
from js import FileReaderSync

class BlobFile(io.RawIOBase):
    """Read-only, seekable view of a browser File, read in slices."""
    def __init__(self, f):
        self.f, self.pos, self.size, self.r = f, 0, int(f.size), FileReaderSync.new()
    def readable(self):
        return True
    def seekable(self):
        return True
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def tell(self):
        return self.pos
    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        b[:n] = self.r.readAsArrayBuffer(self.f.slice(self.pos, self.pos + n)).to_py()
        self.pos += n
        return n

class UrlFile(BlobFile):
    """Same, over HTTP Range requests (test mode, served by a local server)."""
    def __init__(self, url):
        from js import XMLHttpRequest
        self.url, self.pos, self.X = url, 0, XMLHttpRequest
        x = XMLHttpRequest.new(); x.open('HEAD', url, False); x.send()
        self.size = int(x.getResponseHeader('Content-Length'))
    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        x = self.X.new(); x.open('GET', self.url, False); x.responseType = 'arraybuffer'
        x.setRequestHeader('Range', 'bytes=%d-%d' % (self.pos, self.pos + n - 1)); x.send()
        b[:n] = x.response.to_py()
        self.pos += n
        return n

ISO_PATH = '/in/disc.iso'
ISO_FILE = None
_open = builtins.open
def _patched_open(path, mode='r', *a, **k):
    if path == ISO_PATH and 'w' not in mode and ISO_FILE is not None:
        raw = UrlFile(ISO_FILE) if isinstance(ISO_FILE, str) else BlobFile(ISO_FILE)
        return io.BufferedReader(raw, 1 << 16)
    return _open(path, mode, *a, **k)
builtins.open = _patched_open
`);
  say('ready', {});
}

const ready = init().catch((e) => say('error', { text: String(e) }));

onmessage = async (ev) => {
  await ready;
  const { iso, kn5, options, badges } = ev.data;
  try {
    const t0 = Date.now();
    // test mode: URLs of a local server instead of chosen files
    const kn5Data = typeof kn5 === 'string' ? await (await fetch(kn5)).arrayBuffer() : await kn5.arrayBuffer();
    const mb = (kn5Data.byteLength / 1048576).toFixed(0);
    say('log', { text: T(`Modèle lu (${mb} Mo).`, `Model read (${mb} MB).`) });
    pyodide.FS.writeFile('/in/model.kn5', new Uint8Array(kn5Data));
    const names = [];
    for (let i = 0; i < (badges || []).length; i++) {
      const p = `/in/badge${i}.png`;
      pyodide.FS.writeFile(p, new Uint8Array(await badges[i].arrayBuffer()));
      names.push(p);
    }
    pyodide.globals.set('ISO_FILE', iso);
    pyodide.globals.set('OPTIONS', pyodide.toPy({ ...options, names: names.length ? names : null }));
    pyodide.globals.set('jslog', (text) => say('log', { text: tr(text) }));
    const zip = await pyodide.runPythonAsync(`
import make_car
o = OPTIONS
entries = make_car.generate(ISO_PATH, '/in/model.kn5', o['car'], o['top'], o['sound'] or None,
                            o['perf'] or None, o['logo'], o['names'], o['vf'], log=jslog)
make_car.write_zip(entries)
`);
    const bytes = zip.toJs();
    zip.destroy();
    say('done', { zip: bytes, seconds: Math.round((Date.now() - t0) / 1000) });
  } catch (e) {
    say('error', { text: String(e) });
  }
};
