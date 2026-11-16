// Web worker of gt2.html: runs games/gran-turismo-2/make_gt2.py in Pyodide, in the visitor's browser.
// Two results from the same disc and model:
//   - ps1: the new disc image (~690 MB), made a few MB at a time (Gt2Disc.bin_chunks) and written
//     as it is made: to the file chosen with showSaveFilePicker (Chrome, Edge), else to the site's
//     private storage (OPFS), else to a Blob; with the cheat menu of GranTurismo2-OverlayCheat if
//     asked (its Python is read from that project's site);
//   - pc: a zip for the PC port gt-2-pc (make_gt2_mods.package): mods/mx5 + JOUER_MX5.bat.
// The disc image is never loaded whole: Python reads slices of the chosen File with FileReaderSync
// (only available in workers). Nothing is sent anywhere.

importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

const GT1 = 'games/gran-turismo-ps1';
const GT2 = 'games/gran-turismo-2';
const SOURCES = [
  ...['chd', 'binimage', 'kn5', 'acmodel', 'chdmake'].map((m) => `common/${m}.py`),
  ...['build_car', 'decimate', 'disc', 'gt1car', 'mx5scene', 'shell', 'views'].map((m) => `${GT1}/${m}.py`),
  `${GT1}/fonts/LiberationSans-Bold.ttf`,
  ...['build_gt2car', 'gt2data', 'gt2disc', 'gt2menu', 'gt2model', 'gt2texture', 'gt2vol', 'make_gt2', 'make_gt2_mods']
    .map((m) => `${GT2}/${m}.py`),
];
// the cheat: the Python of github.com/soaresden/GranTurismo2-OverlayCheat, from its own site
const CHEAT_URL = 'https://soaresden.github.io/GranTurismo2-OverlayCheat/gt2cheat/';
const CHEAT_SOURCES = ['chd', 'disc', 'game', 'patcher', 'payload', 'ppf'];   // a package without __init__.py
const OPFS_NAME = 'gt2_mx5_rf.bin';

const say = (type, data) => postMessage({ type, ...data });
// language of the page (gt2-worker.js?lang=en); the steps logged by make_gt2.py are in French
const EN = new URL(self.location).searchParams.get('lang') === 'en';
const T = (fr, en) => (EN ? en : fr);
const STEPS_EN = [
  [/^1\/4 les modèles/, '1/4 the models'], [/décapotée/g, 'open'], [/capotée/g, 'closed'],
  [/ sommets, /, ' vertices, '], [/ octets$/, ' bytes'],
  [/^2\/4 caractéristiques et noms/, '2/4 figures and names'], [/^ {2}peintures : /, '  paints: '],
  [/^3\/4 menus : titres, description, occasions/, '3/4 menus: titles, description, used cars'],
  [/^ {2}titres « Mazda MX-5 RF » : (\d+) images/, '  « Mazda MX-5 RF » titles: $1 pictures'],
  [/^ {2}description (\w+) : pages/, '  description $1: pages'],
  [/annonce\(s\) à (\d+) Cr -> la RF décapotée/, 'ad(s) at $1 Cr -> the open RF'],
  [/sur (\d+) écrans de démarrage \(langues, titres\)/, 'on $1 start screens (languages, titles)'],
];
const tr = (text) => { if (EN) for (const [re, en] of STEPS_EN) text = text.replace(re, en); return text; };
let pyodide = null;

async function fetchTo(url, path) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} : ${res.status}`);
  pyodide.FS.mkdirTree(path.split('/').slice(0, -1).join('/'));
  pyodide.FS.writeFile(path, new Uint8Array(await res.arrayBuffer()));
}

async function init() {
  say('log', { text: T('Chargement de Python (Pyodide)…', 'Loading Python (Pyodide)…') });
  pyodide = await loadPyodide();
  // lzma: the codec of the CHD sectors (a separate package of Pyodide's standard library)
  await pyodide.loadPackage(['numpy', 'pillow', 'lzma']);
  say('log', { text: T('Chargement des outils…', 'Loading the tools…') });
  for (const path of SOURCES) await fetchTo(new URL(`../${path}`, self.location), '/app/' + path);
  pyodide.FS.mkdirTree('/in');
  pyodide.globals.set('LANG_EN', EN);
  await pyodide.runPythonAsync(`
import io, sys
sys.path[:0] = ['/app/${GT2}', '/app/${GT1}', '/app/common']
from js import FileReaderSync

class BlobFile(io.RawIOBase):
    """Read-only, seekable view of a browser File, read in slices."""
    def __init__(self, f):
        self.f, self.pos, self.size, self.r = f, 0, int(f.size), FileReaderSync.new()
        self.name = str(f.name)
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
        self.url, self.pos, self.X, self.name = url, 0, XMLHttpRequest, url.split('/')[-1]
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

def open_disc(f):
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
    let parts = null;          // the site's storage is full: the rest goes to memory (a Blob)
    const sink = {
      kind: 'opfs',
      write: (b) => {
        if (parts) { parts.push(new Blob([b])); return; }
        let n = 0;
        try { n = h.write(b, { at }); } catch (_) { n = -1; }
        if (n === b.byteLength) { at += n; return; }
        const head = new Uint8Array(at);
        h.read(head, { at: 0 });
        h.close();
        root.removeEntry(OPFS_NAME).catch(() => {});
        parts = [new Blob([head]), new Blob([b])];
        sink.kind = 'blob';
      },
      close: () => {
        if (parts) return { blob: new Blob(parts, { type: 'application/octet-stream' }) };
        h.flush(); h.close(); return { opfs: OPFS_NAME };
      },
      abort: () => { parts = null; try { h.close(); } catch (_) {} root.removeEntry(OPFS_NAME).catch(() => {}); },
    };
    return sink;
  } catch (_) {
    const parts = [];
    return { kind: 'blob', write: (b) => { parts.push(new Blob([b])); },
             close: () => ({ blob: new Blob(parts, { type: 'application/octet-stream' }) }), abort: () => { parts.length = 0; } };
  }
}

onmessage = async (ev) => {
  await ready;
  const { disc, kn5, options, target } = ev.data;
  let sink = null;
  try {
    const t0 = Date.now();
    // test mode: URLs of a local server instead of chosen files
    const kn5Data = typeof kn5 === 'string' ? await (await fetch(kn5)).arrayBuffer() : await kn5.arrayBuffer();
    const mb = (kn5Data.byteLength / 1048576).toFixed(0);
    say('log', { text: T(`Modèle lu (${mb} Mo).`, `Model read (${mb} MB).`) });
    pyodide.FS.writeFile('/in/model.kn5', new Uint8Array(kn5Data));
    if (options.output === 'ps1' && options.cheat) {
      say('log', { text: T('Le menu de triche (GranTurismo2-OverlayCheat)…', 'The cheat menu (GranTurismo2-OverlayCheat)…') });
      for (const m of CHEAT_SOURCES) await fetchTo(CHEAT_URL + m + '.py', `/app/cheat/gt2cheat/${m}.py`);
    }
    pyodide.globals.set('DISC_FILE', disc);
    pyodide.globals.set('OPTIONS', pyodide.toPy(options));
    pyodide.globals.set('jslog', (text) => say('log', { text: tr(text) }));
    await pyodide.runPythonAsync(`
import os
import make_gt2, make_gt2_mods
o = OPTIONS
DISC, FILES = make_gt2.generate(open_disc(DISC_FILE), '/in/model.kn5', dict(o['cars']), log=jslog,
                                menus_too=o['output'] == 'ps1')
if o['output'] == 'pc':
    ZIP, _kept = make_gt2_mods.package(FILES, dict(o['cars']))
    jslog(('mods/mx5 : %d fichiers' if not LANG_EN else 'mods/mx5: %d files') % len(_kept))
else:
    EXES = None
    if o.get('cheat'):
        if 'SCES_123.80' not in DISC.files:
            raise ValueError("le menu de triche ne va que sur le disque européen (SCES-12380)" if not LANG_EN
                             else 'the cheat menu only goes on the European disc (SCES-12380)')
        os.environ['GT2CHEAT_DIR'] = '/app/cheat'
        EXES = make_gt2.cheat_files(DISC, log=jslog)
    TOTAL = (DISC.c.frames + DISC.plan(FILES)[1]) * 2352
    GEN = DISC.bin_chunks(FILES, files=EXES)
    def next_chunk():
        return next(GEN, None)
`);
    if (options.output === 'pc') {
      const z = pyodide.globals.get('ZIP');
      const bytes = z.toJs();
      z.destroy();
      pyodide.runPython("for _k in ('FILES', 'DISC', 'ZIP'): globals().pop(_k, None)");
      say('done', { kind: 'zip', blob: new Blob([bytes], { type: 'application/zip' }), size: bytes.byteLength,
                    seconds: Math.round((Date.now() - t0) / 1000) });
      return;
    }
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
    pyodide.runPython("for _k in ('FILES', 'DISC', 'GEN', 'EXES'): globals().pop(_k, None)");
    const result = await sink.close();
    say('done', { ...result, kind: sink.kind, size: done, seconds: Math.round((Date.now() - t0) / 1000) });
  } catch (e) {
    if (sink) sink.abort();
    try { pyodide.runPython("for _k in ('FILES', 'DISC', 'GEN', 'EXES', 'ZIP'): globals().pop(_k, None)"); } catch (_) {}
    let text = String(e);
    const m = text.match(/(ValueError|KeyError|SystemExit|PatchError): (.*)/);
    if (m) {
      // the end of the Python traceback in the log, for a bug report
      say('log', { text: String(e).trim().split('\n').slice(-8).join('\n') });
      text = m[2];
    }
    say('error', { text });
  }
};
