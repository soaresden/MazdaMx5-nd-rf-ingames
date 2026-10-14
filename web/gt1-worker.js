// Web worker: runs games/gran-turismo-ps1/make_car.py in Pyodide, in the visitor's browser.
// The CHD is never loaded whole: Python reads slices of the chosen File with FileReaderSync
// (only available in workers). The disc image (~690 MB) is never held whole either: it is made
// a few MB at a time (Disc.bin_chunks) and each piece goes straight to its destination:
//   - the file chosen with showSaveFilePicker (Chrome, Edge), written from here;
//   - otherwise a file of the site's private storage (OPFS), which the page then offers as a
//     download read from the disk;
//   - otherwise (old browsers) a Blob made of the pieces.
// Nothing is sent anywhere.

importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

const GT = 'games/gran-turismo-ps1';
const SOURCES = [
  'common/chd.py', 'common/binimage.py', 'common/kn5.py', 'common/acmodel.py',
  ...['build_car', 'carinf', 'dealer', 'decimate', 'disc', 'gt1car', 'gt1data', 'gtarc', 'infopage',
      'make_car', 'menus', 'mx5scene', 'preview', 'shell', 'slt', 'tim', 'titles', 'views']
    .map((m) => `${GT}/${m}.py`),
  `${GT}/fonts/LiberationSans-Bold.ttf`,
  'games/nfs-most-wanted-x360/assets/badge_mx5_miata_1024.png',   // the MX-5 emblem of the names
];
const OPFS_NAME = 'gt1_mx5_rf.bin';

const say = (type, data) => postMessage({ type, ...data });
// language of the page (gt1-worker.js?lang=en); the steps logged by make_car.py are in French
const EN = new URL(self.location).searchParams.get('lang') === 'en';
const T = (fr, en) => (EN ? en : fr);
const STEPS_EN = [
  [/^1\/4 la MX-5.*/, '1/4 the MX-5 (model and texture)'],
  [/^2\/4 CAR\.DAT/, '2/4 CAR.DAT'],
  [/^3\/4 noms.*/, '3/4 names, paints, specifications and price (CARINF.DAT)'],
  [/^4\/4 les menus.*/, '4/4 the menus (name, dealer pictures, price)'],
  [/\(neuve, /, '(new, '], [/\(occasion, course\)/, '(used, race)'], [/\(occasion\)/, '(used)'],
  [/\(spéciale, course\)/, '(special, race)'], [/\(spéciale\)/, '(special)'], [/\(course\)/, '(race)'],
  [/^ {2}MENU_IMG\.ARC : noms \((.*)\) et vignettes du concessionnaire, 6 langues/,
    '  MENU_IMG.ARC: names ($1) and dealer pictures, 6 languages'],
  [/^ {2}MENU_IMG\.ARC : page INFO.*/, '  MENU_IMG.ARC: INFO page (history of the MX-5 RF), 6 languages'],
  [/^ {2}CARINF\.DAT : /, '  CARINF.DAT: '],
];
const tr = (text) => { if (EN) for (const [re, en] of STEPS_EN) text = text.replace(re, en); return text; };
let pyodide = null;

async function init() {
  say('log', { text: T('Chargement de Python (Pyodide)…', 'Loading Python (Pyodide)…') });
  pyodide = await loadPyodide();
  // lzma: the codec of the CHD sectors (a separate package of Pyodide's standard library)
  await pyodide.loadPackage(['numpy', 'pillow', 'lzma']);
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
import io, sys
sys.path[:0] = ['/app/${GT}', '/app/common']
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

def open_chd(f):
    return io.BufferedReader(UrlFile(f) if isinstance(f, str) else BlobFile(f), 1 << 16)
`);
  say('ready', {});
}

const ready = init().catch((e) => say('error', { text: String(e) }));

// where the pieces of the .bin go
async function openSink(target, size) {
  if (target) {
    const w = await target.createWritable();
    return { kind: 'file', write: (b) => w.write(b), close: async () => { await w.close(); return { saved: target.name }; },
             abort: () => w.abort().catch(() => {}) };
  }
  try {
    const root = await navigator.storage.getDirectory();
    const est = navigator.storage.estimate ? await navigator.storage.estimate() : null;
    try { await root.removeEntry(OPFS_NAME); } catch (_) { /* none yet */ }
    if (est && est.quota - est.usage < size + (64 << 20)) throw new Error('quota');
    const fh = await root.getFileHandle(OPFS_NAME, { create: true });
    const h = await fh.createSyncAccessHandle();
    h.truncate(0);
    let at = 0;
    return {
      kind: 'opfs',
      write: (b) => {
        const n = h.write(b, { at });
        if (n !== b.byteLength) throw new Error(T('disque plein ?', 'disk full?'));
        at += n;
      },
      close: () => { h.flush(); h.close(); return { opfs: OPFS_NAME }; },
      abort: () => { try { h.close(); } catch (_) {} root.removeEntry(OPFS_NAME).catch(() => {}); },
    };
  } catch (_) {
    const parts = [];
    return { kind: 'blob', write: (b) => { parts.push(new Blob([b])); },
             close: () => ({ blob: new Blob(parts, { type: 'application/octet-stream' }) }), abort: () => { parts.length = 0; } };
  }
}

onmessage = async (ev) => {
  await ready;
  const { chd, kn5, options, target } = ev.data;
  let sink = null;
  try {
    const t0 = Date.now();
    // test mode: URLs of a local server instead of chosen files
    const kn5Data = typeof kn5 === 'string' ? await (await fetch(kn5)).arrayBuffer() : await kn5.arrayBuffer();
    const mb = (kn5Data.byteLength / 1048576).toFixed(0);
    say('log', { text: T(`Modèle lu (${mb} Mo).`, `Model read (${mb} MB).`) });
    pyodide.FS.writeFile('/in/model.kn5', new Uint8Array(kn5Data));
    pyodide.globals.set('CHD_FILE', chd);
    pyodide.globals.set('OPTIONS', pyodide.toPy(options));
    pyodide.globals.set('jslog', (text) => say('log', { text: tr(text) }));
    await pyodide.runPythonAsync(`
import make_car
o = OPTIONS
FILES, DISC = make_car.generate(open_chd(CHD_FILE), '/in/model.kn5', dict(o['cars']), o['top'],
                                int(o['price']), log=jslog)
TOTAL = DISC.c.frames * 2352
GEN = DISC.bin_chunks(FILES)
def next_chunk():
    return next(GEN, None)
`);
    const total = pyodide.globals.get('TOTAL');
    say('log', { text: T('L\'image disque (.bin), écrite au fur et à mesure', 'The disc image (.bin), written as it is made') });
    sink = await openSink(target, total);
    const next = pyodide.globals.get('next_chunk');
    let done = 0;
    for (;;) {
      const c = next();
      if (c === undefined || c === null) break;
      const bytes = c.toJs();
      c.destroy();
      await sink.write(bytes);
      done += bytes.byteLength;
      say('progress', { done, total });
    }
    next.destroy();
    pyodide.runPython('del FILES, DISC, GEN');
    const result = await sink.close();
    say('done', { ...result, kind: sink.kind, size: done, seconds: Math.round((Date.now() - t0) / 1000) });
  } catch (e) {
    if (sink) sink.abort();
    try { pyodide.runPython("for _k in ('FILES', 'DISC', 'GEN'): globals().pop(_k, None)"); } catch (_) {}
    say('error', { text: String(e) });
  }
};
