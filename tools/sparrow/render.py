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
out vec3 v_normal;
out vec2 v_uv;
out vec4 v_color;
out vec3 v_world;
void main() {
    vec4 clip = view_proj * vec4(in_pos, 1.0);
    // The game's clip z runs 0..w; OpenGL's runs -w..w.
    clip.z = clip.z * 2.0 - clip.w;
    gl_Position = clip;
    v_normal = in_normal;
    v_uv = in_uv;
    v_color = in_color;
    v_world = in_pos;
}
'''

FRAGMENT = '''
#version 330
uniform sampler2D albedo;
uniform int has_albedo;
uniform int alpha_test;
uniform int mode;          // 0 lit albedo, 1 albedo only, 2 normals
uniform vec3 sun_dir;
in vec3 v_normal;
in vec2 v_uv;
in vec4 v_color;
in vec3 v_world;
out vec4 frag;
void main() {
    vec4 a = has_albedo != 0 ? texture(albedo, v_uv) : vec4(0.6, 0.6, 0.6, 1.0);
    if (alpha_test != 0 && a.a < 0.5) discard;
    vec3 n = normalize(v_normal);
    if (mode == 2) { frag = vec4(n * 0.5 + 0.5, 1.0); return; }
    vec3 c = a.rgb * v_color.rgb;
    if (mode == 0) {
        float l = max(dot(n, sun_dir), 0.0);
        c *= 0.45 + 0.75 * l;
    }
    frag = vec4(c, 1.0);
}
'''


class TextureStore:
    def __init__(self, ctx, folder):
        self.ctx = ctx
        self.folder = folder
        self.cache = {}
        self.missing = set()

    def get(self, tex_hash):
        if tex_hash in self.cache:
            return self.cache[tex_hash]
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
        # Albedo: the first bound, dumped texture the pixel shader samples.
        uv, albedo = None, None
        for slot in sorted(d.textures):
            h = d.textures[slot]
            if h == '0' * 16 or slot in (8, 13, 14):  # 8: screen-space shadow, 13/14: environment
                continue
            uv = xvs.texture_coords(d, out, shader_dir, slot)
            if uv is not None:
                albedo = h
                break
        mesh = f2cap.Mesh(d, pos, tris, smooth_normals(pos, tris), uv)
        mesh.cull = gl_cull_face(d)
        mesh.albedo = albedo
        meshes.append(mesh)
    for vs, why in reasons.items():
        print(f'vs {vs}: {why}')
    return meshes, skipped, vp, spread


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
        for m in meshes:
            n = len(m.position)
            normal = m.normal if m.normal is not None else np.tile([0.0, 0.0, 1.0], (n, 1))
            uv = m.uv if m.uv is not None else np.zeros((n, 2))
            color = m.color if m.color is not None else np.ones((n, 4))
            data = np.hstack([m.position, normal, uv, color]).astype('f4')
            tris = m.tris.astype('i4')
            vbo = ctx.buffer(data.tobytes())
            ibo = ctx.buffer(tris.tobytes())
            vao = ctx.vertex_array(self.prog, [(vbo, '3f 3f 2f 4f', 'in_pos', 'in_normal', 'in_uv',
                                                'in_color')], ibo)
            tex = textures.get(m.albedo) if getattr(m, 'albedo', None) else None
            self.items.append((vao, tex, m.draw.alpha_test, len(tris) * 3, getattr(m, 'cull', None)))
        self.triangles = sum(i[3] for i in self.items) // 3

    def draw(self, view_proj, mode=0, sun=(0.3, 0.4, 0.85)):
        self.prog['view_proj'].write(view_proj.T.astype('f4').tobytes())
        self.prog['mode'].value = mode
        s = np.array(sun) / np.linalg.norm(sun)
        self.prog['sun_dir'].value = tuple(s)
        for vao, tex, alpha_test, count, cull in self.items:
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
        fbo.clear(0.55, 0.62, 0.72, 1.0)
        scene.draw(vp, mode)
        im = Image.frombytes('RGB', (w, h), fbo.read(components=3)).transpose(Image.FLIP_TOP_BOTTOM)
        outputs.append(im)
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
        ctx.clear(0.55, 0.62, 0.72, 1.0)
        view, _, _ = look_at(eye, yaw, pitch)
        scene.draw(perspective(math.radians(60), w / max(h, 1), 0.1, 5000.0) @ view, mode)
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
