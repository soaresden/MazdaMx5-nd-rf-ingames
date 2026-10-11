"""The MX-5 RF of Assetto Corsa as seen by the Gran Turismo (PS1) converter: the outer shell
(for the low-poly model) and a coloured scene (for the texture pictures), in Gran Turismo's axes
(x right, y up, z forward, metres; Assetto Corsa's x points left).
"""
import io

import numpy as np
from PIL import Image

import acmodel
import views as V

# Materials of the shell (the outer surface: what the low-poly model wraps)
SHELL = {'EXT_Carpaint', 'EXT_Plastic_Black', 'EXT_Lights_Chrome', 'EXT_Carpaint_Roof', 'EXT_Details',
         'EXT_Skirt_PLASTIC', 'EXT_Chrome', 'EXT_Lights_Plastic', 'EXT_Rubber', 'EXT_Glass',
         'EXT_Glass_rear_Light', 'EXT_Plastic_Black_Roof', 'EXT_Glass_flat', 'EXT_PLATE_plastic'}
OPEN_SHELL = {'INT_LR', 'INT_LR_carpaint'}
DROP = {'EXT_RearLight_Beam', 'EXT_FrontLight_Beam', 'DAMAGE_GLASS', 'INT_Glass_REFLEX'}
WHEEL_MATS = {'EXT_Tyre', 'EXT_Rim', 'EXT_Loghi_CUP', 'EXT_Disc', 'EXT_Calipers', 'EXT_Details_CUP'}
MIRROR_HOUSINGS = ('GEO_Door_L_SUB1', 'GEO_Door_R_SUB1')
DROP_NAMES = {'gum_07'}  # the antenna mast


def to_gt(p):
    return np.asarray(p, np.float64) * [-1, 1, 1]


class Textures:
    def __init__(self, textures):
        self.t = textures
        self.cache = {}

    def __call__(self, name):
        if name not in self.cache:
            # RGB first: the alpha of AC's maps is gloss, not coverage
            im = Image.open(io.BytesIO(self.t[name])).convert('RGB')
            self.cache[name] = np.asarray(im, np.float32) / 255.0
        return self.cache[name]

    def ao(self, name, uv):
        return V.sample(self(name), uv).mean(1)


def load(kn5_path, top='closed'):
    """(shell_pos, shell_tri, scene, wheels): wheels = {'LF': centre, ...} in Gran Turismo's axes."""
    textures, materials, meshes, nodes = acmodel.load(kn5_path)
    T = Textures(textures)
    scene = V.Scene()
    sp, st = [], []
    n = 0
    wheels = {k[6:]: to_gt(nodes[k][3, :3]) for k in ('WHEEL_LF', 'WHEEL_RF', 'WHEEL_LR', 'WHEEL_RR')}
    for m in meshes:
        mat, path, name = m['mat']['name'], m['path'], m['name']
        if 'COCKPIT_HR' in path or mat in DROP or name in DROP_NAMES or name.startswith('GEO_Shift'):
            continue
        if mat in WHEEL_MATS or 'WHEEL_' in path or 'DISC_' in path or 'SUSP_' in path:
            continue  # the game draws the wheels itself
        pos, nrm, uv, tri = to_gt(m['pos']), m['nrm'] * [-1, 1, 1], m['uv'].copy(), m['tri']
        uv -= np.floor(uv.min(0))
        tx = m['mat']['tex'].get('txDiffuse', '')
        hard = name.startswith('HardTop_')
        if top == 'open' and hard:
            continue
        # open: the shell wraps the cockpit (seats, dashboard) where the roof was
        in_shell = mat in SHELL or (top == 'open' and mat in OPEN_SHELL)
        if in_shell and name not in MIRROR_HOUSINGS:
            sp.append(pos)
            st.append(tri + n)
            n += len(pos)
        cent = pos[tri].mean(1)
        ao = lambda tex=tx: T.ao(tex, uv)
        if mat == 'EXT_Carpaint':
            scene.add(pos, nrm, tri, 1.0, V.PAINT, shade=np.clip(0.3 + 0.7 * ao(), 0, 1))
        elif mat == 'EXT_Carpaint_Roof':
            a = np.clip(0.35 + 0.65 * T.ao('AO_Roof.dds', uv), 0, 1)
            # the RF's roof panels above the cabin are gloss black, the buttresses behind body colour
            black = (cent[:, 2] > -0.80) & (cent[:, 1] > 1.08)
            if (~black).any():
                scene.add(pos, nrm, tri[~black], 1.0, V.PAINT, shade=a)
            if black.any():
                scene.add(pos, nrm, tri[black], (0.05 * a)[:, None] * [1, 1, 1] + 0.02, V.BLACK)
        elif mat in ('EXT_Plastic_Black', 'EXT_Plastic_Black_Roof', 'EXT_Rubber'):
            src = 'AO_Roof.dds' if 'Roof' in mat else 'Skin_00.dds'
            k = 0.08 if mat == 'EXT_Rubber' else 0.12
            scene.add(pos, nrm, tri, (k * np.clip(0.4 + 0.6 * T.ao(src, uv), 0, 1))[:, None] * [1, 1, 1], V.BLACK)
        elif mat == 'EXT_Skirt_PLASTIC':
            scene.add(pos, nrm, tri, 0.18, V.BLACK, tex=T(tx), uv=uv)
        elif mat == 'EXT_Chrome':
            scene.add(pos, nrm, tri, 0.7, V.OTHER)
        elif mat in ('EXT_Lights_Chrome', 'EXT_Lights_Plastic'):
            front = cent[:, 2] > 0
            for sel, cls in ((front, V.LAMP_F), (~front, V.LAMP_R)):
                if sel.any():
                    scene.add(pos, nrm, tri[sel], 1.0, cls, tex=T(tx), uv=uv)
        elif mat == 'EXT_Glass_rear_Light':
            continue  # the lamp texture has the red lenses already
        elif mat in ('EXT_Glass', 'EXT_Glass_flat'):
            scene.add(pos, nrm, tri, V.GLASS_RGB, V.GLASS, glass=True)
        elif mat in ('EXT_Details', 'EXT_PLATE_plastic'):
            scene.add(pos, nrm, tri, 1.0, V.OTHER, tex=T(tx), uv=uv)
        elif mat == 'Mirror':
            scene.add(pos, nrm, tri, 0.35, V.OTHER)
        elif mat == 'INT_LR':
            scene.add(pos, nrm, tri, 0.7, V.OTHER, tex=T(tx), uv=uv)
        elif mat == 'INT_LR_carpaint':
            scene.add(pos, nrm, tri, 1.0, V.PAINT, shade=np.clip(0.3 + 0.5 * ao(), 0, 1))
        elif mat == 'INT_Decals_Chrome_Aluminium':
            scene.add(pos, nrm, tri, 0.5, V.OTHER)
        elif mat.startswith('INT_OCC') or mat in ('INT_SeatBelts', 'INT_Grid_Rear'):
            k = 0.45 if 'Fabric' in mat else (0.3 if 'Skin' in mat else 0.08)
            scene.add(pos, nrm, tri, k, V.OTHER)
        else:
            scene.add(pos, nrm, tri, 0.3, V.OTHER)
    return np.concatenate(sp), np.concatenate(st), scene, wheels
