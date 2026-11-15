"""Draws a Project Sparrow scene capture (see f2cap.py) with OpenGL.

    python tools/sparrow/render.py [capture folder] [--shot game.png] [--out out.png]
    python tools/sparrow/render.py [capture folder] --fly

Without --fly it renders the decoded scene from the game's own camera and
writes out.png (plus a side-by-side with --shot, the game's screenshot of the
same moment). With --fly it opens a window with a free camera: WASD + mouse
(hold the right button), Q/E down/up, Shift faster, B backface culling, C
prints the camera, Esc
quits.

The capture folder defaults to the newest one in the Release build's
sparrow_capture folder. Textures come from the texture dump
(textures/dump/<hash>_*.dds, written with --texture_dump=true).
"""

import argparse
import glob
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2cap  # noqa: E402
import xtex  # noqa: E402
import xvs  # noqa: E402

BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out', 'build',
                     'win-amd64-release')

VERTEX = '''
#version 330
uniform mat4 view_proj;
in vec3 in_pos;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_color;
in vec2 in_uv2;
in vec2 in_uv3;
in vec2 in_uv4;
in vec3 in_tnormal;
out vec3 v_normal;
out vec2 v_uv;
out vec4 v_color;
out vec3 v_world;
out vec2 v_uv2;
out vec2 v_uv3;
out vec2 v_uv4;
out vec3 v_tnormal;
void main() {
    vec4 clip = view_proj * vec4(in_pos, 1.0);
    // The game's clip z runs 0..w; OpenGL's runs -w..w.
    clip.z = clip.z * 2.0 - clip.w;
    gl_Position = clip;
    v_normal = in_normal;
    v_uv = in_uv;
    v_color = in_color;
    v_world = in_pos;
    v_uv2 = in_uv2;
    v_uv3 = in_uv3;
    v_uv4 = in_uv4;
    v_tnormal = in_tnormal;
}
'''

FRAGMENT = '''
#version 330
uniform sampler2D albedo;
uniform sampler2D cliff;
uniform sampler2D shadow;
uniform int has_albedo;
uniform int has_cliff;
uniform int has_shadow;
uniform int material;  // 0 plain, 1 terrain layer (pixel shader 9C2144E4), 2 water, 3 sky, 4 impostor
uniform vec3 eye;
uniform vec2 cliff_ab; // the layer shader's c45.xy: grass weight = sat(|n.z| * b + a)
uniform int alpha_test;
uniform int mode;          // 0 lit albedo, 1 albedo only, 2 normals, 3 draw ids (--pick)
uniform vec3 id_color;
uniform vec3 sun_dir;
in vec3 v_normal;
in vec2 v_uv;
in vec4 v_color;
in vec3 v_world;
in vec2 v_uv2;
in vec2 v_uv3;
in vec2 v_uv4;
in vec3 v_tnormal;
out vec4 frag;
vec4 terrain() {
    // As the game's layer shader: the layer texture and a cliff texture
    // projected along x and y, blended by slope, in linear (squared) colour.
    vec3 c = has_albedo != 0 ? texture(albedo, v_uv).rgb : vec3(0.6);
    c *= c;
    float g = clamp(abs(v_tnormal.z) * cliff_ab.y + cliff_ab.x, 0.0, 1.0);
    if (g < 1.0 && has_cliff != 0) {
        vec3 ca = texture(cliff, v_uv2).rgb;
        vec3 cb = texture(cliff, v_uv3).rgb;
        vec2 w = abs(v_tnormal.xy) + 1e-4;
        w /= w.x + w.y;
        c = c * g + (ca * ca * w.x + cb * cb * w.y) * (1.0 - g);
    }
    return vec4(sqrt(c), v_color.a);
}
vec3 sky_colour(vec3 d) {
    float t = clamp(d.z, 0.0, 1.0);
    return mix(vec3(0.78, 0.80, 0.84), vec3(0.36, 0.52, 0.74), sqrt(t));
}
vec4 fog(vec4 c) {
    // Distance haze toward the horizon colour, roughly the game's look.
    if (mode != 0) return c;
    float d = length(v_world - eye);
    float k = 1.0 - exp(-max(d - 20.0, 0.0) / 260.0);
    return vec4(mix(c.rgb, sky_colour(normalize(v_world - eye)) * 0.95, k * 0.8), c.a);
}
vec4 water() {
    // Two scrolling layers of the game's water normal map (tf2, DXN: x, y).
    vec2 d = vec2(0.0);
    if (has_albedo != 0) {
        d = texture(albedo, v_uv).rg * 2.0 - 1.0 + texture(albedo, v_uv2).rg * 2.0 - 1.0;
    }
    vec3 n = normalize(vec3(d * 0.35, 1.0));
    vec3 v = normalize(eye - v_world);
    float f = 0.02 + 0.98 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
    vec3 r = reflect(-v, n);
    f = 0.25 + 0.75 * f;
    vec3 c = mix(vec3(0.10, 0.17, 0.18), sky_colour(r), f);
    c += vec3(1.0, 0.95, 0.85) * pow(max(dot(r, normalize(sun_dir)), 0.0), 300.0) * 4.0;
    return vec4(c, 1.0);
}
void main() {
    if (material == 2 && mode != 2) { frag = fog(water()); return; }
    if (material == 3 && mode != 2) {
        vec3 d = normalize(v_world - eye);
        vec3 c = sky_colour(d) + vec3(1.0, 0.9, 0.7) * pow(max(dot(d, normalize(sun_dir)), 0.0), 64.0) * 0.6;
        frag = vec4(c, 1.0);
        return;
    }
    // Tree impostors: the baked colour is linear; shown like other albedo.
    vec4 a = material == 4 ? (has_albedo != 0 ? sqrt(texture(albedo, v_uv)) : vec4(0.3))
           : material == 1 ? terrain()
           : has_albedo != 0 ? texture(albedo, v_uv) : vec4(0.6, 0.6, 0.6, 1.0);
    if (alpha_test != 0 && a.a < 0.5) discard;
    vec3 n = normalize(v_normal);
    if (mode == 2) { frag = vec4(n * 0.5 + 0.5, 1.0); return; }
    if (mode == 3) { frag = vec4(id_color, 1.0); return; }
    vec3 c = material >= 1 ? a.rgb : a.rgb * v_color.rgb;
    if (mode == 0) {
        float l = max(dot(n, sun_dir), 0.0);
        // Baked terrain lightmap (shadows of buildings and trees) when there is one.
        float s = has_shadow != 0 ? texture(shadow, v_uv4).r : 1.0;
        // Sky ambient (cool, dimmer in the lightmap's shadows) + warm sun.
        c *= vec3(0.40, 0.43, 0.50) * mix(0.6, 1.0, s) + vec3(1.0, 0.90, 0.72) * 1.15 * l * s;
    }
    frag = fog(vec4(c, material == 1 ? a.a : 1.0));
}
'''


class TextureStore:
    def __init__(self, ctx, folder):
        self.ctx = ctx
        self.folder = folder
        self.cache = {}
        self.missing = set()

    def get(self, tex_hash, source=None):
        """A dumped texture by hash, or with source = (draw, slot) a texture
        the capture saved as raw memory (ptex: render-to-texture results)."""
        if tex_hash in self.cache:
            return self.cache[tex_hash]
        if source is not None:
            tex = None
            try:
                t = xtex.Texture(source[0], source[1], source[2])
                rgba = (np.clip(t.data, 0.0, 1.0) * 255).astype(np.uint8)
                tex = self.ctx.texture((rgba.shape[1], rgba.shape[0]), 4, np.ascontiguousarray(rgba).tobytes())
                tex.build_mipmaps()
                tex.filter = (self.ctx.LINEAR_MIPMAP_LINEAR, self.ctx.LINEAR)
            except ValueError as e:
                print(f'texture {tex_hash}: {e}')
                self.missing.add(tex_hash)
            self.cache[tex_hash] = tex
            return tex
        tex = None
        files = glob.glob(os.path.join(self.folder, f'{tex_hash}_*.dds'))
        if files:
            try:
                im = Image.open(files[0]).convert('RGBA')
                tex = self.ctx.texture(im.size, 4, im.tobytes())
                tex.build_mipmaps()
                tex.filter = (self.ctx.LINEAR_MIPMAP_LINEAR, self.ctx.LINEAR)
                tex.anisotropy = 8.0
            except Exception as e:  # noqa: BLE001 - an unreadable texture is drawn grey
                print(f'texture {tex_hash}: {e}')
        if tex is None:
            self.missing.add(tex_hash)
        self.cache[tex_hash] = tex
        return tex


def smooth_normals(pos, tris):
    n = np.zeros_like(pos)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def colour_pass_meshes(cap, shader_dir, only=None):
    """Meshes of the main view's colour pass, each draw once (the game draws
    the colour pass once per screen tile). Every draw's own vertex shader is run
    (xvs.py) and its clip-space output taken back to world space through the
    game camera."""
    main = cap.main_colour_viewport()
    main_draws = [d for d in cap.draws if d.viewport == main and d.color_mask]
    camera_draws = main_draws
    if only:
        main_draws = [d for d in main_draws if d.vs.startswith(tuple(only)) or d.vs == 'ECD66A10092E6562']
    vp, spread = game_view_proj(camera_draws)
    inv_vp = np.linalg.inv(vp)
    seen = set()
    meshes, skipped, reasons = [], {}, {}
    palette = terrain_palette(main_draws)
    for d in main_draws:
        if only and not d.vs.startswith(tuple(only)):
            continue
        key = d.content_key()
        if key in seen:
            continue
        seen.add(key)
        try:
            r = xvs.run_draw(d, shader_dir)
        except (ValueError, NotImplementedError, IndexError, KeyError) as e:
            reasons.setdefault(d.vs, repr(e))
            r = None
        if r is None:
            skipped[d.vs] = skipped.get(d.vs, 0) + 1
            continue
        _, tris, out, _ = r
        w = out['oPos'] @ inv_vp.T
        with np.errstate(all='ignore'):
            pos = w[:, :3] / w[:, 3:4]
        finite = np.isfinite(pos).all(1)
        if not finite.any():
            continue  # wholly hidden (terrain layers whose mask is empty)
        if not finite.all():
            # Shaders hide vertices by writing NaN; drop those triangles.
            tris = tris[finite[tris].all(1)]
            pos = np.where(finite[:, None], pos, 0.0)
            out = {k: np.where(finite[:, None], v, 0.0) for k, v in out.items()}
        if is_terrain_layer(d):
            mesh = terrain_layer_mesh(d, pos, tris, out)
            if mesh is not None:
                meshes.append(mesh)
                continue
        if d.ps.startswith(WATER_PS) and 'o1' in out:
            mesh = f2cap.Mesh(d, pos, tris, np.tile([0.0, 0.0, 1.0], (len(pos), 1)), out['o1'][:, :2])
            mesh.uv2 = out['o1'][:, 2:4]
            mesh.material, mesh.albedo, mesh.cull = 2, d.textures.get(2), gl_cull_face(d)
            meshes.append(mesh)
            continue
        if (d.blend & 0x1F) in (8, 9) and (d.blend >> 8) & 0x1F == 0:
            # Multiply decals (src = dst colour): blob shadows under characters.
            # Not drawn yet: they darken what is below, which needs its colour.
            continue
        if d.ps.startswith(IMPOSTOR_PS):
            uv, albedo = draw_albedo(d, out, shader_dir)
            mesh = f2cap.Mesh(d, pos, tris, np.tile([0.0, 0.0, 1.0], (len(pos), 1)), uv)
            mesh.material, mesh.albedo, mesh.cull = 4, albedo, gl_cull_face(d)
            meshes.append(mesh)
            continue
        if d.ps.startswith(SKY_PS):
            mesh = f2cap.Mesh(d, pos, tris, np.tile([0.0, 0.0, 1.0], (len(pos), 1)))
            mesh.material, mesh.cull = 3, None
            meshes.append(mesh)
            continue
        if d.ps.startswith(COARSE_TERRAIN_PS) and palette:
            meshes.append(coarse_terrain_mesh(d, pos, tris, out, shader_dir, palette))
            continue
        uv, albedo = draw_albedo(d, out, shader_dir)
        mesh = f2cap.Mesh(d, pos, tris, smooth_normals(pos, tris), uv)
        mesh.cull = gl_cull_face(d)
        mesh.albedo = albedo
        meshes.append(mesh)
    normalize_terrain_weights(meshes)
    for vs, why in reasons.items():
        print(f'vs {vs}: {why}')
    return meshes, skipped, vp, spread


def normalize_terrain_weights(meshes):
    """Scale the near terrain layers' mask weights to sum to 1 at each point.
    In the game the coarse terrain below supplies what the layers leave out
    (through its runtime palette, which the capture doesn't have); here the
    coarse terrain is hidden under the layers instead, so they must cover
    fully. Points no layer claims get an even mix."""
    layers = [m for m in meshes if getattr(m, 'material', 0) == 1 and is_terrain_layer(m.draw)]
    if not layers:
        return
    keys = [np.round(m.position[:, :2] * 8).astype(np.int64) for m in layers]
    total, count = {}, {}
    for m, k in zip(layers, keys):
        used = np.zeros(len(m.position), bool)
        used[m.tris.ravel()] = True
        for kk, a in zip(map(tuple, k[used]), m.color[used, 3]):
            total[kk] = total.get(kk, 0.0) + float(a)
            count[kk] = count.get(kk, 0) + 1
    for m, k in zip(layers, keys):
        t = np.array([total.get(kk, 1.0) for kk in map(tuple, k)])
        n = np.array([count.get(kk, 1) for kk in map(tuple, k)])
        m.color[:, 3] = np.where(t > 0.05, m.color[:, 3] / np.maximum(t, 1e-6), 1.0 / n)


# Pixel shaders whose albedo isn't the first dumped texture: {ps hash prefix: slot}.
ALBEDO_SLOT = {
    '4B1D3E6E': 0,   # tree impostors: billboards the game bakes at runtime (from ptex)
}
# Terrain layer vertex shaders and where their pixel shaders read their inputs
# (vertex shader outputs): layer texture uv, cliff texture uvs (projected along
# x and y), slope normal, lightmap uv, and the register whose w is the mask
# weight. Each comes with several pixel shader variants (with or without the
# sun shadow map, lights...) that read the same inputs.
TERRAIN_LAYERS = {
    'C30A97D9': {'uv': 'o2', 'cliff': ('o0', 'o1'), 'normal': 'o3', 'lightmap': 'o5', 'alpha': 'o9'},
    'FB68A7F2': {'uv': 'o0', 'cliff': None, 'normal': None, 'lightmap': 'o3', 'alpha': 'o7'},
}


def is_terrain_layer(d):
    return d.vs.startswith(tuple(TERRAIN_LAYERS)) and d.textures.get(0, '0' * 16) != '0' * 16
WATER_PS = ('2B091BD0',)
SKY_PS = ('F7601FBE',)
IMPOSTOR_PS = ('4B1D3E6E',)
# Coarse terrain: its own colour texture (tf13) is a tiny runtime bake that the
# capture doesn't get back, so it gets the layer material (dominant layer
# texture + cliff by slope) in world space instead.
COARSE_TERRAIN_PS = ('7DDAD5C2', '2F8A0341')


def terrain_palette(draws):
    """The layer texture most terrain layers use (grass), the cliff texture,
    and the slope weights, from the frame's terrain layer draws."""
    from collections import Counter
    layers = [d for d in draws if is_terrain_layer(d) and d.vs.startswith('C30A97D9')]
    if not layers:
        return None
    grass = Counter(d.textures.get(0) for d in layers).most_common(1)[0][0]
    cliff = Counter(d.textures.get(13) for d in layers).most_common(1)[0][0]
    return {'albedo': grass, 'cliff': cliff,
            'cliff_ab': tuple(float(x) for x in layers[0].ps_const(45)[:2])}


def coarse_terrain_mesh(d, pos, tris, out, shader_dir, palette):
    normal = smooth_normals(pos, tris)
    mesh = f2cap.Mesh(d, pos, tris, normal, np.stack([pos[:, 0], -pos[:, 1]], 1) / 8.0)
    mesh.cull = gl_cull_face(d)
    mesh.material = 1
    mesh.albedo, mesh.cliff, mesh.cliff_ab = palette['albedo'], palette['cliff'], palette['cliff_ab']
    mesh.uv2 = np.stack([pos[:, 1], -pos[:, 2]], 1) / 8.0
    mesh.uv3 = np.stack([pos[:, 0], -pos[:, 2]], 1) / 8.0
    mesh.tnormal = normal
    mesh.shadow = d.textures.get(3)
    # Pushed back in depth so the near layers, which coincide with it, win the
    # pre-pass: the game hides it there through its palette (black under the
    # near detail, so the additive layers sum on black).
    mesh.depth_bias = True
    mesh.uv4 = xvs.texture_coords(d, out, shader_dir, 3) if mesh.shadow else None
    if mesh.uv4 is None:
        mesh.shadow = None
    return mesh


def draw_albedo(d, out, shader_dir):
    """(uv, texture key) of a draw's albedo: the first bound, dumped texture
    its pixel shader samples, or the slot ALBEDO_SLOT names (which may be a
    render-to-texture result saved as raw memory)."""
    forced = next((s for ps, s in ALBEDO_SLOT.items() if d.ps.startswith(ps)), None)
    if forced is not None:
        h = d.textures.get(forced)
        if h is None:
            return None, None
        uv = xvs.texture_coords(d, out, shader_dir, forced)
        if uv is None:
            return None, None
        if h == '0' * 16:
            return (uv, ptex_key(d, forced)) if forced in d.ptex else (None, None)
        return uv, h
    for slot in sorted(d.textures):
        h = d.textures[slot]
        if h == '0' * 16 or slot in (8, 13, 14):  # 8: screen-space shadow, 13/14: environment
            continue
        uv = xvs.texture_coords(d, out, shader_dir, slot)
        if uv is not None:
            return uv, h
    return None, None


def ptex_key(draw, slot):
    """Texture store key + source for a texture saved as raw memory."""
    e = draw.ptex[slot]
    return ('ptex:%x' % e['addr'], (draw, slot, e))


def terrain_layer_mesh(d, pos, tris, out):
    """A terrain layer draw with what its pixel shader reads (TERRAIN_LAYERS):
    layer texture tf0, cliff texture tf13, lightmap tf3, and the mask weight
    that the draw's blend state uses as alpha. None if an input is missing."""
    io = next(v for k, v in TERRAIN_LAYERS.items() if d.vs.startswith(k))
    regs = [io['uv'], io['lightmap'], io['alpha']] + list(io['cliff'] or []) + [io['normal']] * bool(io['normal'])
    if any(rg not in out for rg in regs):
        return None
    n = len(pos)
    color = np.ones((n, 4))
    color[:, 3] = np.clip(out[io['alpha']][:, 3], 0.0, 1.0)
    normal = smooth_normals(pos, tris)
    mesh = f2cap.Mesh(d, pos, tris, normal, out[io['uv']][:, :2], color)
    mesh.cull = gl_cull_face(d)
    mesh.material = 1
    mesh.albedo = d.textures.get(0)
    mesh.shadow = d.textures.get(3)
    mesh.uv4 = out[io['lightmap']][:, :2]
    mesh.tnormal = out[io['normal']][:, :3] if io['normal'] else normal
    if io['cliff']:
        mesh.cliff = d.textures.get(13)
        mesh.uv2, mesh.uv3 = out[io['cliff'][0]][:, :2], out[io['cliff'][1]][:, :2]
        mesh.cliff_ab = tuple(float(x) for x in d.ps_const(45)[:2])
    return mesh

# xenos::BlendFactor -> moderngl factor name; ops: add, subtract, min, max, reverse subtract.
BLEND_FACTORS = {0: 'ZERO', 1: 'ONE', 4: 'SRC_COLOR', 5: 'ONE_MINUS_SRC_COLOR', 6: 'SRC_ALPHA',
                 7: 'ONE_MINUS_SRC_ALPHA', 8: 'DST_COLOR', 9: 'ONE_MINUS_DST_COLOR',
                 10: 'DST_ALPHA', 11: 'ONE_MINUS_DST_ALPHA'}


def game_sun(draws):
    """The sun direction the terrain shaders light with (PS c80, world space),
    or a default."""
    for d in draws:
        if d.vs.startswith('C30A97D9'):
            v = d.ps_const(80)[:3]
            if np.isfinite(v).all() and np.linalg.norm(v) > 0.5:
                return tuple(float(x) for x in v)
    return (0.3, 0.4, 0.85)


def gl_blend(draw):
    """(src, dst) moderngl factor names for the draw's colour blend, or None
    when it writes opaquely (one, zero, add) or uses something unmapped."""
    b = draw.blend
    src, op, dst = b & 0x1F, (b >> 5) & 7, (b >> 8) & 0x1F
    if (src, dst, op) == (1, 0, 0) or op != 0:
        return None
    if src not in BLEND_FACTORS or dst not in BLEND_FACTORS:
        return None
    return BLEND_FACTORS[src], BLEND_FACTORS[dst]


def gl_cull_face(draw):
    """Which GL face to cull ('front', 'back' or None) to match the draw's
    PA_SU_SC_MODE_CNTL, with GL's front = counter-clockwise in NDC. Xenos
    decides facing in window space (y down), so the viewport scales' signs
    say how NDC winding maps to it."""
    mode = draw.reg(f2cap.PA_SU_SC_MODE_CNTL)
    cull_front, cull_back, face_cw = mode & 1, (mode >> 1) & 1, (mode >> 2) & 1
    if cull_front == cull_back:
        return None  # neither, or both (then the draw shows nothing: rare)
    flip = np.sign(draw.regf(f2cap.PA_CL_VPORT_XSCALE) or 1.0) * np.sign(draw.regf(f2cap.PA_CL_VPORT_YSCALE) or 1.0)
    # Counter-clockwise on screen with y down = negative NDC area when flip > 0.
    front_ndc_ccw = (flip < 0) != bool(face_cw)
    keep_ccw = front_ndc_ccw if cull_back else not front_ndc_ccw
    return 'back' if keep_ccw else 'front'


def game_view_proj(draws):
    """The game camera's world -> clip matrix, from the static-world draws
    (c0..c3 world-view-projection, c4..c6 world); also how much they disagree."""
    vps = []
    for d in draws:
        if d.vs == 'ECD66A10092E6562':
            world = np.eye(4)
            world[:3, :] = d.vs_matrix(4, 3)
            vps.append(d.vs_matrix(0, 4) @ np.linalg.inv(world))
    if not vps:
        raise SystemExit('no draw gives the camera')
    vps = np.array(vps)
    vp = np.median(vps, axis=0)
    spread = np.max(np.abs(vps - vp)) / max(np.max(np.abs(vp)), 1e-9)
    return vp, spread


class Scene:
    def __init__(self, ctx, meshes, textures):
        self.ctx = ctx
        self.prog = ctx.program(vertex_shader=VERTEX, fragment_shader=FRAGMENT)
        self.items = []
        self.cull = True  # match the game's backface culling (B toggles it in --fly)
        self.sun = game_sun([m.draw for m in meshes])
        for m in meshes:
            n = len(m.position)
            normal = m.normal if m.normal is not None else np.tile([0.0, 0.0, 1.0], (n, 1))
            uv = m.uv if m.uv is not None else np.zeros((n, 2))
            color = m.color if m.color is not None else np.ones((n, 4))
            z2 = np.zeros((n, 2))
            extra = [getattr(m, 'uv2', None), getattr(m, 'uv3', None), getattr(m, 'uv4', None)]
            extra = [e if e is not None else z2 for e in extra]
            tn = getattr(m, 'tnormal', None)
            tn = tn if tn is not None else np.tile([0.0, 0.0, 1.0], (n, 1))
            data = np.hstack([m.position, normal, uv, color] + extra + [tn]).astype('f4')
            tris = m.tris.astype('i4')
            vbo = ctx.buffer(data.tobytes())
            ibo = ctx.buffer(tris.tobytes())
            names = ['in_pos', 'in_normal', 'in_uv', 'in_color', 'in_uv2', 'in_uv3', 'in_uv4', 'in_tnormal']
            fmt = ['3f', '3f', '2f', '4f', '2f', '2f', '2f', '3f']
            # Attributes the shader compiled away must be skipped with 'x' padding.
            fmt = [f if nm in self.prog else f.replace('f', 'x4') for f, nm in zip(fmt, names)]
            used = [nm for nm in names if nm in self.prog]
            vao = ctx.vertex_array(self.prog, [(vbo, ' '.join(fmt), *used)], ibo)
            tex = self._texture(textures, getattr(m, 'albedo', None))
            extras = {
                'material': getattr(m, 'material', 0),
                'cliff': self._texture(textures, getattr(m, 'cliff', None)),
                'shadow': self._texture(textures, getattr(m, 'shadow', None)),
                'cliff_ab': getattr(m, 'cliff_ab', (1.0, 0.0)),
                'blend': gl_blend(m.draw),
                'bias': getattr(m, 'depth_bias', False),
            }
            self.items.append((vao, tex, m.draw.alpha_test, len(tris) * 3, getattr(m, 'cull', None), extras))
        self.triangles = sum(i[3] for i in self.items) // 3

    @staticmethod
    def _texture(textures, key):
        if not key:
            return None
        if isinstance(key, tuple):
            return textures.get(key[0], key[1])
        if key == '0' * 16:
            return None
        return textures.get(key)

    def _set(self, name, value):
        if name in self.prog:
            self.prog[name].value = value

    def draw(self, view_proj, mode=0, sun=None, target=None):
        """target: the framebuffer being drawn into (its colour mask is
        switched off for the depth pre-pass)."""
        self.prog['view_proj'].write(view_proj.T.astype('f4').tobytes())
        # Camera position: the point view_proj maps to clip x = y = w = 0.
        m = view_proj[[0, 1, 3]]
        self._set('eye', tuple(float(x) for x in np.linalg.solve(m[:, :3], -m[:, 3])))
        self.prog['mode'].value = mode
        sun = sun if sun is not None else self.sun
        s = np.array(sun) / np.linalg.norm(sun)
        self.prog['sun_dir'].value = tuple(s)
        ctx = self.ctx
        self._set('albedo', 0)
        self._set('cliff', 1)
        self._set('shadow', 2)
        # Like the game: a depth-only pass of everything that isn't see-through,
        # then colour only where a surface matches that depth. That keeps the
        # coarse terrain from under the near terrain layers (which add onto
        # whatever colour is below them).
        # Which way depth grows with distance (the game camera's z is reversed).
        e = np.linalg.solve(m[:, :3], -m[:, 3])
        fwd = np.linalg.inv(view_proj) @ [0.0, 0.0, 0.5, 1.0]
        fwd = fwd[:3] / fwd[3] - e
        fwd /= np.linalg.norm(fwd)
        z1, z2 = (view_proj @ np.append(e + fwd * 1.0, 1.0)), (view_proj @ np.append(e + fwd * 100.0, 1.0))
        self.bias_sign = 1.0 if (z2[2] * 2 - z2[3]) / z2[3] > (z1[2] * 2 - z1[3]) / z1[3] else -1.0
        fbo = target if target is not None else ctx.fbo
        fbo.color_mask = (False, False, False, False)
        fbo.use()
        ctx.depth_mask = True
        ctx.depth_func = '<'
        self._draw_items(mode, depth_only=True)
        fbo.color_mask = (True, True, True, True)
        fbo.use()
        ctx.depth_mask = False
        ctx.depth_func = '=='  # same vertices, same depth: only the pre-pass winner draws
        self._draw_items(mode, depth_only=False)
        ctx.depth_mask = True
        ctx.polygon_offset = (0.0, 0.0)

    def _draw_items(self, mode, depth_only):
        ctx = self.ctx
        for item, (vao, tex, alpha_test, count, cull, ex) in enumerate(self.items):
            see_through = ex['blend'] is not None and ex['blend'][1] == 'ONE_MINUS_SRC_ALPHA'
            ctx.polygon_offset = (2.0 * self.bias_sign, 8.0 * self.bias_sign) if ex['bias'] else (0.0, 0.0)
            if depth_only and see_through:
                continue
            if see_through and not depth_only:
                ctx.depth_mask = False
            if mode == 3:
                k = item + 1
                self._set('id_color', ((k & 255) / 255.0, ((k >> 8) & 255) / 255.0, ((k >> 16) & 255) / 255.0))
            self._set('material', ex['material'])
            self._set('cliff_ab', ex['cliff_ab'])
            for unit, name in ((1, 'cliff'), (2, 'shadow')):
                if ex[name] is not None:
                    ex[name].use(unit)
                self._set('has_' + name, int(ex[name] is not None))
            if ex['blend'] and mode < 2 and not depth_only:
                ctx.enable(ctx.BLEND)
                ctx.blend_func = (getattr(ctx, ex['blend'][0]), getattr(ctx, ex['blend'][1]))
            else:
                ctx.disable(ctx.BLEND)
            if cull and self.cull:
                self.ctx.enable(self.ctx.CULL_FACE)
                self.ctx.cull_face = cull
            else:
                self.ctx.disable(self.ctx.CULL_FACE)
            if tex is not None:
                tex.use(0)
                self.prog['has_albedo'].value = 1
            else:
                self.prog['has_albedo'].value = 0
            self.prog['alpha_test'].value = int(alpha_test)
            vao.render(vertices=count)


def render_still(cap, meshes, args):
    import moderngl
    ctx = moderngl.create_standalone_context()
    main = cap.main_colour_viewport()
    scale = args.scale
    w, h = int(main[0] * scale), int(main[1] * scale)
    scene = Scene(ctx, meshes, TextureStore(ctx, args.textures))
    vp, spread = args.vp, args.spread
    print(f'{len(meshes)} draws, {scene.triangles} triangles; camera from draws agrees to {spread:.2e}')
    fbo = ctx.simple_framebuffer((w, h))
    fbo.use()
    ctx.enable(moderngl.DEPTH_TEST)
    outputs = []
    if args.camera:
        x, y, z, yaw, pitch = args.camera
        view, _, _ = look_at(np.array([x, y, z]), math.radians(yaw), math.radians(pitch))
        vp = perspective(math.radians(args.fov), w / h, 0.1, 5000.0) @ view
    for mode in args.modes:
        fbo.clear(0.0, 0.0, 0.0, 1.0)  # black like the game: terrain layers add onto it
        scene.draw(vp, mode, target=fbo)
        im = Image.frombytes('RGB', (w, h), fbo.read(components=3)).transpose(Image.FLIP_TOP_BOTTOM)
        outputs.append(im)
    if args.pick:
        fbo.clear(0.0, 0.0, 0.0, 1.0)
        scene.draw(vp, 3, target=fbo)
        ids = np.frombuffer(fbo.read(components=3), np.uint8).reshape(h, w, 3)[::-1].astype(np.int64)
        for px, py in zip(args.pick[::2], args.pick[1::2]):
            x, y = int(px * scale), int(py * scale)
            k = ids[y, x, 0] | (ids[y, x, 1] << 8) | (ids[y, x, 2] << 16)
            if not k:
                print(f'pick ({px:g}, {py:g}): nothing')
                continue
            m = meshes[k - 1]
            d = m.draw
            print(f'pick ({px:g}, {py:g}): draw {d.index} vs {d.vs} ps {d.ps} albedo {getattr(m, "albedo", None)} '
                  f'blend {d.blend:#x} textures {d.textures}')
    out = outputs[0]
    out.save(args.out)
    print(f'wrote {args.out}')
    if args.shot:
        shot = Image.open(args.shot).convert('RGB').resize((w, h), Image.LANCZOS)
        row = [shot] + outputs
        sbs = Image.new('RGB', (w * len(row), h))
        for i, im in enumerate(row):
            sbs.paste(im, (i * w, 0))
        side = os.path.splitext(args.out)[0] + '_vs_game.png'
        sbs.save(side)
        print(f'wrote {side}')


def look_at(eye, yaw, pitch):
    """World z is up. Returns the 4x4 view matrix (camera looks down -z)."""
    f = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
    r = np.cross(f, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    v = np.eye(4)
    v[0, :3], v[1, :3], v[2, :3] = r, u, -f
    v[:3, 3] = -v[:3, :3] @ eye
    return v, f, r


def perspective(fov_y, aspect, near, far):
    """Clip z 0..w (the game's convention, converted in the vertex shader)."""
    t = 1.0 / math.tan(fov_y / 2)
    p = np.zeros((4, 4))
    p[0, 0], p[1, 1] = t / aspect, t
    p[2, 2] = far / (near - far)
    p[2, 3] = near * far / (near - far)
    p[3, 2] = -1.0
    return p


def camera_from_view_proj(vp):
    """Position and yaw/pitch of the game camera, for the fly mode's start."""
    inv = np.linalg.inv(vp)

    def unproject(x, y, z):
        h = inv @ np.array([x, y, z, 1.0])
        return h[:3] / h[3]
    near, far = unproject(0, 0, 0.0), unproject(0, 0, 0.5)
    f = far - near
    f /= np.linalg.norm(f)
    return near, math.atan2(f[1], f[0]), math.asin(max(-1.0, min(1.0, f[2])))


def fly(cap, meshes, args):
    import glfw
    import moderngl
    if not glfw.init():
        raise SystemExit('glfw init failed')
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    win = glfw.create_window(1600, 900, f'Sparrow capture {cap.frame}', None, None)
    glfw.make_context_current(win)
    glfw.swap_interval(1)
    ctx = moderngl.create_context()
    scene = Scene(ctx, meshes, TextureStore(ctx, args.textures))
    vp = args.vp
    eye, yaw, pitch = camera_from_view_proj(vp)
    print(f'{len(meshes)} draws, {scene.triangles} triangles; start at {eye.round(2)}')
    mode = 0
    last = glfw.get_time()
    mouse = None
    while not glfw.window_should_close(win):
        glfw.poll_events()
        now = glfw.get_time()
        dt, last = now - last, now
        if glfw.get_key(win, glfw.KEY_ESCAPE) == glfw.PRESS:
            break
        if glfw.get_mouse_button(win, glfw.MOUSE_BUTTON_RIGHT) == glfw.PRESS:
            x, y = glfw.get_cursor_pos(win)
            if mouse is not None:
                yaw -= (x - mouse[0]) * 0.003
                pitch = max(-1.5, min(1.5, pitch - (y - mouse[1]) * 0.003))
            mouse = (x, y)
        else:
            mouse = None
        _, f, r = look_at(eye, yaw, pitch)
        speed = 30.0 if glfw.get_key(win, glfw.KEY_LEFT_SHIFT) == glfw.PRESS else 6.0
        move = np.zeros(3)
        for key, vec in ((glfw.KEY_W, f), (glfw.KEY_S, -f), (glfw.KEY_D, r), (glfw.KEY_A, -r),
                         (glfw.KEY_E, np.array([0, 0, 1.0])), (glfw.KEY_Q, np.array([0, 0, -1.0]))):
            if glfw.get_key(win, key) == glfw.PRESS:
                move += vec
        eye = eye + move * speed * dt
        for i, key in enumerate((glfw.KEY_1, glfw.KEY_2, glfw.KEY_3)):
            if glfw.get_key(win, key) == glfw.PRESS:
                mode = i
        b_down = glfw.get_key(win, glfw.KEY_B) == glfw.PRESS
        if b_down and not getattr(scene, '_b_was_down', False):
            scene.cull = not scene.cull
            print('backface culling', 'on' if scene.cull else 'off')
        scene._b_was_down = b_down
        if glfw.get_key(win, glfw.KEY_C) == glfw.PRESS:
            print(f'camera {eye.round(2)} yaw {math.degrees(yaw):.1f} pitch {math.degrees(pitch):.1f}')
        w, h = glfw.get_framebuffer_size(win)
        ctx.viewport = (0, 0, w, h)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.clear(0.0, 0.0, 0.0, 1.0)  # black like the game: terrain layers add onto it
        view, _, _ = look_at(eye, yaw, pitch)
        scene.draw(perspective(math.radians(60), w / max(h, 1), 0.1, 5000.0) @ view, mode, target=ctx.screen)
        glfw.swap_buffers(win)
    glfw.terminate()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('capture', nargs='?')
    ap.add_argument('--shot', help="the game's screenshot of the same frame, for a side-by-side")
    ap.add_argument('--out', default='sparrow_render.png')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--modes', type=int, nargs='+', default=[0, 2],
                    help='0 lit albedo, 1 albedo only, 2 normals')
    ap.add_argument('--textures', default=os.path.join(BUILD, 'textures', 'dump'))
    ap.add_argument('--shaders', default=os.path.join(BUILD, 'shdump'),
                    help='shader disassembly folder (the dump_shaders cvar)')
    ap.add_argument('--camera', type=float, nargs=5, metavar=('X', 'Y', 'Z', 'YAW', 'PITCH'),
                    help='render from this free camera instead of the game one (degrees)')
    ap.add_argument('--fov', type=float, default=60.0, help='vertical field of view for --camera')
    ap.add_argument('--only', nargs='+', help='only draws whose vertex shader hash starts with these')
    ap.add_argument('--fly', action='store_true')
    ap.add_argument('--pick', type=float, nargs='+', metavar='XY',
                    help='print the draw under these pixels (x y pairs, game resolution)')
    args = ap.parse_args()
    folder = args.capture or f2cap.latest_capture(os.path.join(BUILD, 'sparrow_capture'))
    cap = f2cap.Capture(folder)
    meshes, skipped, args.vp, args.spread = colour_pass_meshes(cap, args.shaders, args.only)
    if skipped:
        print('not decoded yet (vertex shader: draws): ' +
              ', '.join(f'{k[:8]}:{v}' for k, v in sorted(skipped.items(), key=lambda kv: -kv[1])))
    if args.fly:
        fly(cap, meshes, args)
    else:
        render_still(cap, meshes, args)


if __name__ == '__main__':
    main()
