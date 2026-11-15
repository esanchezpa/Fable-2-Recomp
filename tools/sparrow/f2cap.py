"""Reader for Project Sparrow scene captures (the sparrow_capture cvar).

A capture is a folder <sparrow_capture_dir>/<frame>/ holding capture.json and
blob.bin, written by thirdparty/rexglue-sdk/src/graphics/d3d12/sparrow_capture.cpp.
Each draw records its shaders, the context registers (0x2000..0x23FF) and shader
constants (0x4000..0x4927) as they were at the draw, the vertex layout of its
vertex shader, the texture hash bound to each fetch constant it reads, and copies
of its vertex and index buffers from guest memory (big-endian, as the game
wrote them).

Vertex shaders are decoded one by one (see DECODERS): each knows where its
shader takes position, normal, UV and colour from, and which constants hold
its world and world-view-projection matrices.
"""

import json
import os

import numpy as np

# Registers (thirdparty/rexglue-sdk/include/rex/graphics/register_table.inc).
VGT_INDX_OFFSET = 0x2102
VGT_MULTI_PRIM_IB_RESET_INDX = 0x2103
PA_CL_VPORT_XSCALE = 0x210F
PA_CL_VPORT_YSCALE = 0x2111
RB_DEPTHCONTROL = 0x2200
RB_BLENDCONTROL0 = 0x2201
RB_COLORCONTROL = 0x2202
PA_SU_SC_MODE_CNTL = 0x2205
RB_COLOR_MASK = 0x2104
FETCH_BASE = 0x4800

# xenos::PrimitiveType
PRIM_TRIANGLE_LIST = 0x04
PRIM_TRIANGLE_FAN = 0x05
PRIM_TRIANGLE_STRIP = 0x06
PRIM_RECTANGLE_LIST = 0x08
PRIM_QUAD_LIST = 0x0D

# xenos::VertexFormat
VF_8_8_8_8 = 6
VF_2_10_10_10 = 7
VF_10_11_11 = 16
VF_11_11_10 = 17
VF_16_16 = 25
VF_16_16_16_16 = 26
VF_16_16_FLOAT = 31
VF_16_16_16_16_FLOAT = 32
VF_32 = 33
VF_32_32 = 34
VF_32_32_32_32 = 35
VF_32_FLOAT = 36
VF_32_32_FLOAT = 37
VF_32_32_32_32_FLOAT = 38
VF_32_32_32_FLOAT = 57


def swap32(words, endian):
    """Applies a xenos::Endian swap to little-endian-read dwords."""
    w = words.astype(np.uint32)
    if endian == 1:  # 8in16
        return ((w & 0x00FF00FF) << 8) | ((w >> 8) & 0x00FF00FF)
    if endian == 2:  # 8in32
        return w.byteswap()
    if endian == 3:  # 16in32
        return (w << 16) | (w >> 16)
    return w


def _bits(w, shift, count, signed, normalized):
    v = ((w >> np.uint32(shift)) & np.uint32((1 << count) - 1)).astype(np.int64)
    if signed:
        v = np.where(v >= (1 << (count - 1)), v - (1 << count), v)
        if normalized:
            return np.maximum(v / float((1 << (count - 1)) - 1), -1.0)
        return v.astype(np.float64)
    if normalized:
        return v / float((1 << count) - 1)
    return v.astype(np.float64)


def decode_attribute(words, vertex, stride, attr):
    """Fetches one vertex attribute for each vertex index, as an (n, 4) array of
    the components in memory order (x, y, z, w; missing ones are 0, w is 1)."""
    fmt, off = attr['fmt'], attr['off']
    signed, normalized = bool(attr['signed']), not attr['int']
    base = vertex.astype(np.int64) * stride + off
    n = len(vertex)
    out = np.zeros((n, 4))
    out[:, 3] = 1.0

    def dword(k):
        idx = base + k
        ok = (idx >= 0) & (idx < len(words))
        return np.where(ok, words[np.clip(idx, 0, len(words) - 1)], 0).astype(np.uint32)

    if fmt == VF_8_8_8_8:
        w = dword(0)
        for c in range(4):
            out[:, c] = _bits(w, 8 * c, 8, signed, normalized)
    elif fmt == VF_2_10_10_10:
        w = dword(0)
        for c in range(3):
            out[:, c] = _bits(w, 10 * c, 10, signed, normalized)
        out[:, 3] = _bits(w, 30, 2, signed, normalized)
    elif fmt == VF_10_11_11:
        w = dword(0)
        out[:, 0] = _bits(w, 0, 11, signed, normalized)
        out[:, 1] = _bits(w, 11, 11, signed, normalized)
        out[:, 2] = _bits(w, 22, 10, signed, normalized)
    elif fmt == VF_11_11_10:
        w = dword(0)
        out[:, 0] = _bits(w, 0, 10, signed, normalized)
        out[:, 1] = _bits(w, 10, 11, signed, normalized)
        out[:, 2] = _bits(w, 21, 11, signed, normalized)
    elif fmt in (VF_16_16, VF_16_16_16_16):
        for k in range(1 if fmt == VF_16_16 else 2):
            w = dword(k)
            out[:, 2 * k] = _bits(w, 0, 16, signed, normalized)
            out[:, 2 * k + 1] = _bits(w, 16, 16, signed, normalized)
    elif fmt in (VF_16_16_FLOAT, VF_16_16_16_16_FLOAT):
        for k in range(1 if fmt == VF_16_16_FLOAT else 2):
            w = dword(k)
            out[:, 2 * k] = (w & 0xFFFF).astype(np.uint16).view(np.float16)
            out[:, 2 * k + 1] = (w >> 16).astype(np.uint16).view(np.float16)
    elif fmt in (VF_32_FLOAT, VF_32_32_FLOAT, VF_32_32_32_FLOAT, VF_32_32_32_32_FLOAT):
        count = {VF_32_FLOAT: 1, VF_32_32_FLOAT: 2, VF_32_32_32_FLOAT: 3, VF_32_32_32_32_FLOAT: 4}[fmt]
        for c in range(count):
            out[:, c] = dword(c).view(np.float32)
    elif fmt in (VF_32, VF_32_32, VF_32_32_32_32):
        count = {VF_32: 1, VF_32_32: 2, VF_32_32_32_32: 4}[fmt]
        for c in range(count):
            w = dword(c)
            out[:, c] = w.view(np.int32) if signed else w
    else:
        raise ValueError(f'vertex format {fmt} not handled')
    if attr.get('exp'):
        out[:, :3] *= 2.0 ** attr['exp']
    return out


class Draw:
    def __init__(self, cap, d):
        self.cap = cap
        self.d = d
        self.index = d['i']
        self.vs = d['vs']
        self.ps = d['ps']
        self.prim = d['prim']
        self.count = d['count']
        self.textures = {slot: h for slot, h in d['tex']}
        c = cap.header
        self._ctx = np.frombuffer(cap.blob, '<u4', c['ctx_count'], d['ctx'])
        self._consts = np.frombuffer(cap.blob, '<u4', c['const_count'], d['consts'])

    def reg(self, index):
        if 0x2000 <= index < 0x2000 + len(self._ctx):
            return int(self._ctx[index - 0x2000])
        if 0x4000 <= index < 0x4000 + len(self._consts):
            return int(self._consts[index - 0x4000])
        raise KeyError(hex(index))

    def regf(self, index):
        return float(np.uint32(self.reg(index)).view(np.float32))

    def vs_const(self, i):
        """Vertex shader float constant c<i> as 4 floats."""
        return self._consts[4 * i:4 * i + 4].view(np.float32).astype(np.float64)

    def ps_const(self, i):
        return self._consts[4 * (256 + i):4 * (256 + i) + 4].view(np.float32).astype(np.float64)

    def vs_matrix(self, first, rows=4):
        return np.stack([self.vs_const(first + r) for r in range(rows)])

    @property
    def viewport(self):
        return abs(self.regf(PA_CL_VPORT_XSCALE)) * 2.0, abs(self.regf(PA_CL_VPORT_YSCALE)) * 2.0

    @property
    def depth_test(self):
        return bool(self.reg(RB_DEPTHCONTROL) & 0x2)

    @property
    def depth_write(self):
        return bool(self.reg(RB_DEPTHCONTROL) & 0x4)

    @property
    def alpha_test(self):
        return bool(self.reg(RB_COLORCONTROL) & 0x8)

    @property
    def blend(self):
        return self.reg(RB_BLENDCONTROL0)

    @property
    def color_mask(self):
        return self.reg(RB_COLOR_MASK) & 0xFFFF

    def content_key(self):
        """Identifies a draw by everything it draws with, so the same draw
        repeated for another screen tile can be dropped."""
        vb = tuple((b['fc'], b['blob'], b['size']) for b in self.d['vb'])
        ib = self.d['index']
        # Vertex shader constants only: the tile copies differ in a pixel shader
        # constant (c0.y) and the scissor.
        return (self.vs, self.ps, self.prim, self.count, self._consts[:1024].tobytes(), vb,
                ib['blob'] if ib else None, tuple(map(tuple, self.d['tex'])))

    def buffer_words(self, binding):
        if binding['blob'] is None:
            return None
        raw = np.frombuffer(self.cap.blob, '<u4', binding['size'] // 4, binding['blob'])
        return swap32(raw, binding['endian'])

    def indices(self):
        """Guest vertex indices of the draw (before VGT_INDX_OFFSET), with
        primitive restart markers kept as -1."""
        ib = self.d['index']
        if ib is None:
            return np.arange(self.count, dtype=np.int64)
        if ib['fmt'] == 0:
            raw = np.frombuffer(self.cap.blob, '<u2', ib['len'] // 2, ib['blob']).astype(np.uint32)
            if ib['endian'] in (1, 2):
                raw = ((raw & 0xFF) << 8) | (raw >> 8)
            reset = 0xFFFF
        else:
            raw = swap32(np.frombuffer(self.cap.blob, '<u4', ib['len'] // 4, ib['blob']), ib['endian'])
            reset = 0xFFFFFFFF
        idx = raw[:self.count].astype(np.int64)
        if self.prim in (PRIM_TRIANGLE_STRIP, PRIM_TRIANGLE_FAN):
            idx[raw[:self.count] == reset] = -1
        return idx

    def triangles(self):
        """(vertex index array, (t, 3) triangle corners as positions in it)."""
        idx = self.indices()
        p = self.prim
        if p == PRIM_TRIANGLE_LIST:
            t = len(idx) // 3
            tris = np.arange(t * 3).reshape(t, 3)
        elif p == PRIM_QUAD_LIST:
            q = len(idx) // 4
            b = np.arange(q) * 4
            tris = np.concatenate([np.stack([b, b + 1, b + 2], 1), np.stack([b, b + 2, b + 3], 1)])
        elif p in (PRIM_TRIANGLE_STRIP, PRIM_TRIANGLE_FAN):
            tris = []
            start = 0
            for k in list(np.nonzero(idx < 0)[0]) + [len(idx)]:
                n = k - start
                for i in range(n - 2):
                    a = start + i
                    if p == PRIM_TRIANGLE_FAN:
                        tris.append((start, a + 1, a + 2))
                    elif i % 2 == 0:
                        tris.append((a, a + 1, a + 2))
                    else:
                        tris.append((a + 1, a, a + 2))
                start = k + 1
            tris = np.array(tris, dtype=np.int64).reshape(-1, 3)
        else:
            tris = np.zeros((0, 3), dtype=np.int64)
        return idx, tris


class Capture:
    def __init__(self, folder):
        self.folder = folder
        with open(os.path.join(folder, 'capture.json'), encoding='utf-8') as f:
            self.header = json.load(f)
        with open(os.path.join(folder, 'blob.bin'), 'rb') as f:
            self.blob = f.read()
        self.frame = self.header['frame']
        self.draws = [Draw(self, d) for d in self.header['draws']]

    def main_viewport(self):
        """The largest viewport drawn with depth testing: the game's main view."""
        sizes = {}
        for d in self.draws:
            if d.depth_test:
                sizes[d.viewport] = sizes.get(d.viewport, 0) + 1
        return max(sizes, key=lambda s: (s[0] * s[1], sizes[s]))


    def main_colour_viewport(self):
        """The viewport with the most colour-writing, depth-tested draws: the
        game's main view."""
        sizes = {}
        for d in self.draws:
            if d.depth_test and d.color_mask:
                sizes[d.viewport] = sizes.get(d.viewport, 0) + 1
        return max(sizes, key=sizes.get)


def latest_capture(root):
    frames = [n for n in os.listdir(root) if n.isdigit() and
              os.path.exists(os.path.join(root, n, 'capture.json'))]
    # Newest by time: frame numbers restart with every game session.
    return os.path.join(root, max(frames, key=lambda n: os.path.getmtime(
        os.path.join(root, n, 'capture.json'))))


# --- Vertex shader decoders -------------------------------------------------
#
# Each takes a Draw and returns a Mesh or None (draw not understood).

class Mesh:
    """World-space triangles of one draw."""

    def __init__(self, draw, position, tris, normal=None, uv=None, color=None, clip_matrix=None,
                 world_matrix=None, object_position=None):
        self.draw = draw
        self.position = position          # (n, 3) world space
        self.tris = tris                  # (t, 3) into the vertex arrays
        self.normal = normal              # (n, 3) world space, or None
        self.uv = uv                      # (n, 2) or None
        self.color = color                # (n, 4) or None
        self.clip_matrix = clip_matrix    # 4x4 world-view-projection of the draw (object -> clip)
        self.world_matrix = world_matrix  # 4x4 object -> world
        self.object_position = object_position


def _stream(draw, vf):
    """Vertex stream vf<N> of the shader's disassembly: fetch constant 95 - N."""
    for b in draw.d['vb']:
        if b['fc'] == 95 - vf:
            return b
    return None


def _world4(m34):
    m = np.eye(4)
    m[:3, :] = m34
    return m


def decode_static_world(draw):
    """VS ECD66A10092E6562, the shader of most of the world (buildings, props).

    vf0 (5 dwords): half4 position (x, y, z in components y, x, w), 10_11_11
    normal, half2 UV (u, v in components y, x), 2_10_10_10 tangent; vf3: 8888
    colour. oPos = c0..c3 . position, world = c4..c6 . position, and c20.x is
    added to the vertex index."""
    b0, b3 = _stream(draw, 0), _stream(draw, 3)
    if b0 is None or b0['blob'] is None:
        return None
    words0 = draw.buffer_words(b0)
    idx, tris = draw.triangles()
    if len(tris) == 0:
        return None
    vertex = np.where(idx < 0, 0, idx) + draw.reg(VGT_INDX_OFFSET) + int(draw.vs_const(20)[0])
    attrs = b0['attrs']
    p = decode_attribute(words0, vertex, b0['stride'], attrs[0])
    n = decode_attribute(words0, vertex, b0['stride'], attrs[1])
    t = decode_attribute(words0, vertex, b0['stride'], attrs[2])
    pos = np.stack([p[:, 1], p[:, 0], p[:, 3], np.ones(len(p))], 1)
    world = draw.vs_matrix(4, 3)
    clip = draw.vs_matrix(0, 4)
    wpos = pos @ world.T
    wn = n[:, :3] @ world[:, :3].T
    wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-9)
    uv = np.stack([t[:, 1], t[:, 0]], 1)
    color = None
    if b3 is not None and b3['blob'] is not None:
        color = decode_attribute(draw.buffer_words(b3), vertex, b3['stride'], b3['attrs'][0])
    return Mesh(draw, wpos, tris, wn, uv, color, clip_matrix=clip, world_matrix=_world4(world),
                object_position=pos[:, :3])


DECODERS = {
    'ECD66A10092E6562': decode_static_world,
}


def decode(draw):
    fn = DECODERS.get(draw.vs)
    return fn(draw) if fn else None
