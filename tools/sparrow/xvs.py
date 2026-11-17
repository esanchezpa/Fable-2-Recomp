"""Runs Xbox 360 (Xenos) vertex shaders on the CPU, from their disassembly.

The SDK writes each shader's disassembly to <dump_shaders>/shader_<hash>.ucode.vert
(the dump_shaders cvar; the Release build keeps them in out/.../shdump). This runs
one over all of a captured draw's vertices at once with numpy, so the captured
scene gets exactly the positions and interpolators the game's own shader made,
whatever it does (skinning by bone constants, wind, terrain) - the "capture the
shader's output instead of rebuilding it" route of the Sparrow plan.

Supported: the ALU ops the game's shaders use, co-issued scalar ops, per-vertex
predication, relative constants (c[N+a0]), vfetch, tfetch1D/2D of the textures
the capture saved for vertex shaders (xtex.py), forward jumps and jumps on bool
constants, and tessellated quad patches (a regular grid per patch). Not yet:
loops.
"""

import re

import numpy as np

import f2cap
import xtex

VECTOR_OPS = {'add', 'mul', 'max', 'min', 'seq', 'sgt', 'sge', 'sne', 'frc', 'trunc', 'floor', 'mad',
              'cndeq', 'cndge', 'cndgt', 'dp4', 'dp3', 'dp2add', 'maxa', 'max4'}
SCALAR_OPS = {'adds', 'adds_prev', 'muls', 'muls_prev', 'muls_prev2', 'maxs', 'mins', 'seqs', 'sgts',
              'sges', 'snes', 'frcs', 'truncs', 'floors', 'exp', 'log', 'logc', 'rcp', 'rcpc', 'rcpf',
              'rsq', 'rsqc', 'rsqf', 'maxas', 'maxasf', 'subs', 'subs_prev', 'setp_eq', 'setp_ne',
              'setp_gt', 'setp_ge', 'setp_inv', 'setp_pop', 'setp_clr', 'setp_rstr', 'sqrt', 'sin',
              'cos', 'mulsc', 'addsc', 'subsc', 'retain_prev'}

FORMATS = {
    'FMT_8_8_8_8': f2cap.VF_8_8_8_8, 'FMT_2_10_10_10': f2cap.VF_2_10_10_10,
    'FMT_10_11_11': f2cap.VF_10_11_11, 'FMT_11_11_10': f2cap.VF_11_11_10,
    'FMT_16_16': f2cap.VF_16_16, 'FMT_16_16_16_16': f2cap.VF_16_16_16_16,
    'FMT_16_16_FLOAT': f2cap.VF_16_16_FLOAT, 'FMT_16_16_16_16_FLOAT': f2cap.VF_16_16_16_16_FLOAT,
    'FMT_32': f2cap.VF_32, 'FMT_32_32': f2cap.VF_32_32, 'FMT_32_32_32_32': f2cap.VF_32_32_32_32,
    'FMT_32_FLOAT': f2cap.VF_32_FLOAT, 'FMT_32_32_FLOAT': f2cap.VF_32_32_FLOAT,
    'FMT_32_32_32_FLOAT': f2cap.VF_32_32_32_FLOAT, 'FMT_32_32_32_32_FLOAT': f2cap.VF_32_32_32_32_FLOAT,
}

COMP = {'x': 0, 'y': 1, 'z': 2, 'w': 3}
SRC_RE = re.compile(r'^(-?)(?:r_abs\[(\d+)\]|([rc])(\d+)|c\[(\d+)\+a0\])(?:\.([xyzw01_]+))?$')


class Source:
    def __init__(self, text):
        m = SRC_RE.match(text)
        if not m:
            raise ValueError(f'source {text!r}')
        neg, absreg, kind, num, rel, sw = m.groups()
        self.neg = neg == '-'
        self.abs = absreg is not None
        if absreg is not None:
            self.kind, self.num = 'r', int(absreg)
        elif rel is not None:
            self.kind, self.num = 'crel', int(rel)
        else:
            self.kind, self.num = kind, int(num)
        sw = sw or 'xyzw'
        sw = (sw + sw[-1] * 4)[:4]
        self.swizzle = [COMP[c] for c in sw]


class Dest:
    def __init__(self, text):
        name, _, mask = text.partition('.')
        self.name = name
        mask = mask or 'xyzw'
        # ALU masks are positional (r0.x_zw); a lone '_' writes nothing.
        self.mask = [i for i, c in enumerate(mask[:4]) if c != '_']
        self.fetch_select = mask  # vfetch: which fetched component goes to each position


class Op:
    def __init__(self, pred, name, args):
        self.pred = pred
        self.name = name
        self.args = args


class Program:
    def __init__(self, text):
        self.instructions = []   # each: ('alu', [ops]) | ('vfetch', ...) | ('jmp'/'label'/...)
        self.uses_tfetch = False
        self.has_loop = False
        current = None
        cond_open = False
        for raw in text.splitlines():
            line = re.sub(r'^\s*/\*.*?\*/', '', raw).strip()
            if not line:
                continue
            coissue = line.startswith('+')
            if coissue:
                line = line[1:].strip()
            pred = None
            m = re.match(r'^\((!?)p0\)\s*(.*)$', line)
            if m:
                pred = m.group(1) != '!'
                line = m.group(2)
            word, _, rest = line.partition(' ')
            if word in ('exec', 'exece', 'alloc', 'cnop', 'nop', 'cexec'):
                # A control-flow line ends the previous exec block; cexec
                # [!]b<N> starts one that only runs when that bool is set.
                if cond_open:
                    self.instructions.append(('endcond',))
                    cond_open = False
                if word == 'cexec':
                    cond = rest.strip().split()[0] if rest.strip() else ''
                    if cond.lstrip('!').startswith('b'):
                        self.instructions.append(('cond', cond.startswith('!'),
                                                  int(cond.lstrip('!b'))))
                        cond_open = True
                current = None
                continue
            if word == 'serialize':
                current = None
                continue
            if cond_open and word in ('label', 'jmp', 'cjmp', 'loop', 'endloop', 'call', 'ret'):
                self.instructions.append(('endcond',))
                cond_open = False
            if word == 'label':
                self.instructions.append(('label', rest.strip()))
                current = None
                continue
            if word == 'jmp':
                self.instructions.append(('jmp', pred, rest.strip()))
                current = None
                continue
            if word == 'cjmp':
                # cjmp [!]b<N>, L<label>: jump on a bool constant.
                cond, _, label = rest.partition(',')
                cond = cond.strip()
                self.instructions.append(('cjmp', cond.startswith('!'), int(cond.lstrip('!b')),
                                          label.strip()))
                current = None
                continue
            if word in ('loop', 'endloop', 'call', 'ret'):
                self.has_loop = True
                self.instructions.append(('unsupported', word))
                current = None
                continue
            args = [a.strip() for a in rest.split(',')] if rest else []
            if word in ('vfetch_full', 'vfetch_mini'):
                self.instructions.append(('vfetch', pred, word, args))
                current = None
                continue
            if word.startswith(('tfetch', 'getGradients', 'getWeights', 'setTex', 'getBCF', 'getComp')):
                self.uses_tfetch = True
                self.instructions.append(('tfetch', pred, args, word))
                current = None
                continue
            if word.startswith('kill'):
                # Alpha test: discards pixels and writes nothing we read.
                current = None
                continue
            base = word[:-4] if word.endswith('_sat') else word
            if base not in VECTOR_OPS and base not in SCALAR_OPS:
                # Only an error if it is reached (see Machine.run).
                self.instructions.append(('unsupported', word))
                current = None
                continue
            op = Op(pred, word, args)
            if coissue and current is not None:
                current.append(op)
            else:
                current = [op]
                self.instructions.append(('alu', current))


class Machine:
    """Runs a Program for n vertices of a captured draw."""

    def __init__(self, draw, n, pixel=False):
        self.draw = draw
        self.n = n
        self.r = np.zeros((64, n, 4))
        self.out = {}
        # Vertex shaders read float constants 0..255, pixel shaders 256..511.
        bank = draw._consts[1024:2048] if pixel else draw._consts[:1024]
        self.consts = bank.view(np.float32).astype(np.float64).reshape(256, 4)
        self.p0 = np.zeros(n, bool)
        self.a0 = np.zeros(n, np.int64)
        self.ps = np.zeros(n)
        self.fetch = None  # (words, base vertex index, stride) of the last vfetch_full
        self.textures = None  # {fetch constant: xtex.Texture}, loaded on first tfetch

    def read(self, s):
        if s.kind == 'r':
            v = self.r[s.num]
        elif s.kind == 'c':
            v = np.broadcast_to(self.consts[s.num], (self.n, 4))
        else:
            v = self.consts[np.clip(s.num + self.a0, 0, 255)]
        v = v[:, s.swizzle]
        if s.abs:
            v = np.abs(v)
        if s.neg:
            v = -v
        return v

    def write(self, dest, value, mask_rows):
        if not dest.mask:
            return
        if dest.name.startswith('r'):
            target = self.r[int(dest.name[1:])]
        else:
            target = self.out.setdefault(dest.name, np.zeros((self.n, 4)))
        for c in dest.mask:
            target[mask_rows, c] = value[mask_rows, c]

    def vector(self, op, srcs):
        name = op.name[:-4] if op.name.endswith('_sat') else op.name
        a = srcs[0]
        b = srcs[1] if len(srcs) > 1 else None
        c = srcs[2] if len(srcs) > 2 else None
        if name == 'add':
            v = a + b
        elif name == 'mul':
            v = a * b
        elif name in ('max', 'maxa'):
            v = np.maximum(a, b)
            if name == 'maxa':
                self.a0 = np.clip(np.floor(a[:, 3] + 0.5), -256, 255).astype(np.int64)
        elif name == 'min':
            v = np.minimum(a, b)
        elif name == 'seq':
            v = (a == b).astype(float)
        elif name == 'sgt':
            v = (a > b).astype(float)
        elif name == 'sge':
            v = (a >= b).astype(float)
        elif name == 'sne':
            v = (a != b).astype(float)
        elif name == 'frc':
            v = a - np.floor(a)
        elif name == 'trunc':
            v = np.trunc(a)
        elif name == 'floor':
            v = np.floor(a)
        elif name == 'mad':
            v = a * b + c
        elif name == 'cndeq':
            v = np.where(a == 0, b, c)
        elif name == 'cndge':
            v = np.where(a >= 0, b, c)
        elif name == 'cndgt':
            v = np.where(a > 0, b, c)
        elif name == 'dp4':
            v = np.repeat((a * b).sum(1, keepdims=True), 4, 1)
        elif name == 'dp3':
            v = np.repeat((a[:, :3] * b[:, :3]).sum(1, keepdims=True), 4, 1)
        elif name == 'dp2add':
            v = np.repeat((a[:, :2] * b[:, :2]).sum(1, keepdims=True) + c[:, :1], 4, 1)
        elif name == 'max4':
            v = np.repeat(a.max(1, keepdims=True), 4, 1)
        else:
            raise ValueError(name)
        if op.name.endswith('_sat'):
            v = np.clip(v, 0.0, 1.0)
        return v

    def scalar(self, op, srcs, rows):
        name = op.name[:-4] if op.name.endswith('_sat') else op.name
        if not srcs:
            a = b = np.zeros(self.n)
        elif name in ('mulsc', 'addsc', 'subsc'):
            a, b = srcs[0][:, 0], srcs[1][:, 0]
        else:
            a, b = srcs[0][:, 0], srcs[0][:, 1]
        ps = self.ps
        with np.errstate(all='ignore'):
            if name in ('adds', 'addsc'):
                v = a + b
            elif name == 'adds_prev':
                v = a + ps
            elif name in ('muls', 'mulsc'):
                v = a * b
            elif name in ('muls_prev', 'muls_prev2'):
                v = a * ps
            elif name in ('subs', 'subsc'):
                v = a - b
            elif name == 'subs_prev':
                v = a - ps
            elif name in ('maxs', 'maxas', 'maxasf'):
                v = np.maximum(a, b)
                if name != 'maxs':
                    new_a0 = np.clip(np.floor(a + 0.5) if name == 'maxas' else np.floor(a), -256, 255)
                    self.a0 = np.where(rows, new_a0.astype(np.int64), self.a0)
            elif name == 'mins':
                v = np.minimum(a, b)
            elif name == 'seqs':
                v = (a == 0).astype(float)
            elif name == 'sgts':
                v = (a > 0).astype(float)
            elif name == 'sges':
                v = (a >= 0).astype(float)
            elif name == 'snes':
                v = (a != 0).astype(float)
            elif name == 'frcs':
                v = a - np.floor(a)
            elif name == 'truncs':
                v = np.trunc(a)
            elif name == 'floors':
                v = np.floor(a)
            elif name == 'exp':
                v = np.exp2(a)
            elif name in ('log', 'logc'):
                v = np.log2(a)
                if name == 'logc':
                    v = np.where(np.isneginf(v), -np.finfo(np.float32).max, v)
            elif name in ('rcp', 'rcpc', 'rcpf'):
                v = 1.0 / a
            elif name in ('rsq', 'rsqc', 'rsqf'):
                v = 1.0 / np.sqrt(a)
            elif name == 'sqrt':
                v = np.sqrt(a)
            elif name == 'sin':
                v = np.sin(a)
            elif name == 'cos':
                v = np.cos(a)
            elif name == 'retain_prev':
                v = ps.copy()
            elif name.startswith('setp_'):
                cond = {'setp_eq': a == 0, 'setp_ne': a != 0, 'setp_gt': a > 0, 'setp_ge': a >= 0,
                        'setp_inv': a == 0, 'setp_clr': np.zeros_like(a, bool),
                        'setp_pop': a - 1.0 <= 0, 'setp_rstr': a == 0}[name]
                self.p0 = np.where(rows, cond, self.p0)
                if name == 'setp_inv':
                    v = np.where(a == 0, 1.0, np.where(a == 1.0, 0.0, a))
                elif name == 'setp_pop':
                    v = np.where(cond, 0.0, a - 1.0)
                elif name == 'setp_clr':
                    v = np.full_like(a, np.finfo(np.float32).max)
                elif name == 'setp_rstr':
                    v = a.copy()
                else:
                    v = np.where(cond, 0.0, 1.0)
            else:
                raise ValueError(name)
        if op.name.endswith('_sat'):
            v = np.clip(v, 0.0, 1.0)
        return np.repeat(v[:, None], 4, 1)

    def vfetch(self, word, args, rows):
        dest = Dest(args[0])
        opts = dict(a.split('=', 1) for a in args if '=' in a)
        if word == 'vfetch_full':
            index = self.read(Source(args[1]))[:, 0]
            vf = int(args[2][2:])
            binding = next((b for b in self.draw.d['vb'] if b['fc'] == 95 - vf), None)
            words = self.draw.buffer_words(binding) if binding else None
            # The hardware truncates a float index unless the instruction asks
            # for rounding (impostors fetch at i * 0.25 + 0.125).
            if opts.get('RoundIndex', 'false') == 'true':
                index = np.floor(index + 0.5)
            self.fetch = (words, np.floor(index).astype(np.int64), int(opts.get('Stride', 0)))
        words, vertex, stride = self.fetch
        if words is None:
            return
        attr = {'fmt': FORMATS[opts['DataFormat']], 'off': int(opts.get('Offset', 0)),
                'signed': opts.get('Signed', 'false') == 'true',
                'int': opts.get('NumFormat', 'fraction') == 'integer',
                'exp': int(opts.get('ExpAdjust', 0))}
        fetched = f2cap.decode_attribute(words, vertex, stride, attr)
        reg = self.r[int(dest.name[1:])]
        for i, c in enumerate(dest.fetch_select[:4]):
            if c in COMP:
                reg[rows, i] = fetched[rows, COMP[c]]
            elif c in '01':
                reg[rows, i] = float(c)

    def tfetch(self, word, args, rows):
        if self.textures is None:
            self.textures = xtex.draw_textures(self.draw)
        dest = Dest(args[0])
        slot = int(args[2][2:])
        tex = self.textures.get(slot)
        if tex is None or word not in ('tfetch1D', 'tfetch2D'):
            return
        opts = dict(a.split('=', 1) for a in args[3:] if '=' in a)
        coord = self.read(Source(args[1]))
        linear_mode = opts.get('MagFilter', 'keep')
        linear = (linear_mode == 'linear') if linear_mode != 'keep' else tex.fetch.mag_filter == 1
        offset = (float(opts.get('OffsetX', 0.0)), float(opts.get('OffsetY', 0.0)))
        unnormalized = opts.get('UnnormalizedTextureCoords', 'false') == 'true'
        v = coord[:, 1] if word == 'tfetch2D' else np.full(self.n, 0.5)
        value = tex.sample(coord[:, 0], v, linear, offset, unnormalized)
        reg = self.r[int(dest.name[1:])]
        for i, c in enumerate(dest.fetch_select[:4]):
            if c in COMP:
                reg[rows, i] = value[rows, COMP[c]]
            elif c in '01':
                reg[rows, i] = float(c)

    def rows(self, active, pred):
        if pred is None:
            return active
        return active & (self.p0 if pred else ~self.p0)

    def run(self, program, vertex_index=None, stop_at_texture=None, registers=None):
        """vertex_index: what a vertex shader gets in r0.x (index +
        VGT_INDX_OFFSET); registers: other starting values, {register: (n, 4)}.
        With stop_at_texture, returns the coordinates of the first fetch from
        that texture fetch constant instead."""
        if vertex_index is not None:
            self.r[0, :, 0] = vertex_index
        for reg, value in (registers or {}).items():
            self.r[reg] = value
        active = np.ones(self.n, bool)
        held = active
        waiting = {}  # label -> vertices that jumped to it
        for ins in program.instructions:
            kind = ins[0]
            if kind == 'label':
                if ins[1] in waiting:
                    active = active | waiting.pop(ins[1])
                continue
            if kind == 'jmp':
                jumping = self.rows(active, ins[1])
                waiting[ins[2]] = waiting.get(ins[2], np.zeros(self.n, bool)) | jumping
                active = active & ~jumping
                continue
            if kind == 'cond':
                bools = self.draw.reg(0x4900 + ins[2] // 32)
                value = bool((bools >> (ins[2] % 32)) & 1)
                held = active
                if value == ins[1]:  # cexec b skips when b is false (!b: when true)
                    active = np.zeros(self.n, bool)
                continue
            if kind == 'endcond':
                active = held
                continue
            if kind == 'cjmp':
                bools = self.draw.reg(0x4900 + ins[2] // 32)
                value = bool((bools >> (ins[2] % 32)) & 1)
                if value != ins[1]:  # jump when b is true (or false for !b)
                    waiting[ins[3]] = waiting.get(ins[3], np.zeros(self.n, bool)) | active
                    active = np.zeros(self.n, bool)
                continue
            if kind == 'unsupported':
                if not active.any():
                    continue
                raise NotImplementedError(ins[1])
            if not active.any():
                continue
            if kind == 'vfetch':
                self.vfetch(ins[2], ins[3], self.rows(active, ins[1]))
                continue
            if kind == 'tfetch':
                args = ins[2]
                if stop_at_texture is not None:
                    if len(args) > 2 and args[2] == f'tf{stop_at_texture}':
                        return self.read(Source(args[1]))
                    continue
                if len(args) > 2 and args[2].startswith('tf'):
                    self.tfetch(ins[3], args, self.rows(active, ins[1]))
                continue
            ops = ins[1]
            # Co-issued ops read their sources before either writes.
            results = []
            for op in ops:
                srcs = [self.read(Source(a)) for a in op.args[1:]]
                rows = self.rows(active, op.pred)
                base = op.name[:-4] if op.name.endswith('_sat') else op.name
                if base in SCALAR_OPS:
                    results.append((op, self.scalar(op, srcs, rows), rows, True))
                else:
                    results.append((op, self.vector(op, srcs), rows, False))
            for op, value, rows, is_scalar in results:
                self.write(Dest(op.args[0]), value, rows)
                if is_scalar:
                    self.ps = np.where(rows, value[:, 0], self.ps)
        return None if stop_at_texture is not None else self.out


_programs = {}


def load_program(shader_dir, shader_hash, kind='vert'):
    key = (shader_hash, kind)
    if key not in _programs:
        import glob
        import os
        files = glob.glob(os.path.join(shader_dir, f'shader_{shader_hash}.ucode.{kind}'))
        if not files:
            _programs[key] = None
        else:
            with open(files[0], encoding='utf-8', errors='replace') as f:
                try:
                    _programs[key] = Program(f.read())
                except ValueError as e:
                    print(f'shader {shader_hash}.{kind}: {e}')
                    _programs[key] = None
    return _programs[key]


def texture_coords(draw, outputs, shader_dir, slot=0):
    """Per-vertex coordinates the pixel shader samples texture fetch constant
    `slot` with (its code up to that fetch, run on the vertex shader's
    interpolators), or None."""
    program = load_program(shader_dir, draw.ps, 'frag')
    if program is None:
        return None
    n = len(outputs['oPos'])
    m = Machine(draw, n, pixel=True)
    for name, value in outputs.items():
        if name.startswith('o') and name[1:].isdigit():
            m.r[int(name[1:])] = value
    try:
        coords = m.run(program, stop_at_texture=slot)
    except (ValueError, NotImplementedError, IndexError, KeyError) as e:
        print(f'pixel shader {draw.ps}: {e!r}')
        return None
    return None if coords is None else coords[:, :2]


PRIM_QUAD_PATCH = 0x12


def quad_patch_grid(level):
    """Domain locations (u, v) of a quad patch split into level x level quads,
    and its triangles (counter-clockwise in (u, v); the game's terrain then
    faces up, which its culling state expects)."""
    k = level + 1
    v, u = np.mgrid[0:k, 0:k]
    uv = np.stack([u.ravel(), v.ravel()], 1) / level
    i = (np.arange(level)[:, None] * k + np.arange(level)[None, :]).ravel()
    tris = np.concatenate([np.stack([i, i + 1, i + k], 1), np.stack([i + 1, i + k + 1, i + k], 1)])
    return uv, tris


def run_quad_patches(draw, program):
    """Tessellated quad patches: each patch is split into a regular grid at its
    largest edge factor (adaptive mode: 4 factors per patch in the "index"
    buffer) or at VGT_HOS_MAX_TESS_LEVEL, and the shader runs as the domain
    shader: r0.x = patch index, r0.yz = domain location (u, v), r1.x = 0 (the
    edge swizzle, identity here)."""
    mode = draw.reg(0x2285) & 3  # VGT_HOS_CNTL tess_mode: 0 discrete, 1 continuous, 2 adaptive
    # The hardware's factors are the stored values + 1 (as are the limits).
    max_level = max(1, int(round(draw.regf(0x2286) + 1.0)))
    ib = draw.d['index']
    if mode == 2 and ib is not None:
        factors = f2cap.swap32(np.frombuffer(draw.cap.blob, '<u4', ib['len'] // 4, ib['blob']),
                               ib['endian']).view(np.float32)[:draw.count] + 1.0
        patches = len(factors) // 4
        levels = [max(1, min(max_level, int(np.ceil(factors[4 * p:4 * p + 4].max()))))
                  for p in range(patches)]
    else:
        patches = draw.count
        levels = [max_level] * patches
    uv_all, tris_all, patch_all = [], [], []
    grids = {}
    base = 0
    for p, level in enumerate(levels):
        if level not in grids:
            grids[level] = quad_patch_grid(level)
        uv, tris = grids[level]
        uv_all.append(uv)
        tris_all.append(tris + base)
        patch_all.append(np.full(len(uv), p, dtype=np.float64))
        base += len(uv)
    uv = np.concatenate(uv_all)
    n = len(uv)
    r0 = np.zeros((n, 4))
    r0[:, 0] = np.concatenate(patch_all) + draw.reg(f2cap.VGT_INDX_OFFSET)
    r0[:, 1], r0[:, 2] = uv[:, 0], uv[:, 1]
    m = Machine(draw, n)
    out = m.run(program, registers={0: r0, 1: np.zeros((n, 4))})
    if 'oPos' not in out:
        raise ValueError('no oPos written')
    return np.arange(n), np.concatenate(tris_all), out, program


def run_draw(draw, shader_dir):
    """Runs a draw's vertex shader over its vertices. Returns (vertex index
    array, triangles, outputs {'oPos': (n,4), 'o0': ...}, program) or None."""
    program = load_program(shader_dir, draw.vs)
    if program is None:
        raise ValueError('no disassembly')
    if draw.prim == PRIM_QUAD_PATCH:
        return run_quad_patches(draw, program)
    idx, tris = draw.triangles()
    if len(tris) == 0:
        return None
    # Run each distinct vertex once.
    used = np.where(idx < 0, 0, idx)
    unique, inverse = np.unique(used, return_inverse=True)
    m = Machine(draw, len(unique))
    out = m.run(program, (unique + draw.reg(f2cap.VGT_INDX_OFFSET)).astype(np.float64))
    if 'oPos' not in out:
        raise ValueError('no oPos written')
    tris = inverse[tris]
    return unique, tris, out, program
