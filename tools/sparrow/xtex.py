"""Xenos textures from a scene capture: untiling and sampling, for vertex
shaders that fetch textures (terrain heights, lookup tables).

The capture stores the base level of each texture a vertex shader reads
(draw.d['vtex']) as guest memory; the fetch constant (in the captured shader
constants) gives its format, size, tiling and endianness.
"""

import numpy as np

import f2cap

# xenos::TextureFormat -> (bytes per texel, components, decoder name). Only the
# uncompressed formats vertex shaders have been seen to read so far.
FORMATS = {
    2: (1, 1, 'u8'),         # k_8
    6: (4, 4, 'u8x4'),       # k_8_8_8_8
    24: (2, 1, 'u16'),       # k_16
    25: (4, 2, 'u16x2'),     # k_16_16
    26: (8, 4, 'u16x4'),     # k_16_16_16_16
    30: (2, 1, 'f16'),       # k_16_FLOAT (k_16_16_FLOAT is 31)
    31: (4, 2, 'f16x2'),     # k_16_16_FLOAT
    32: (8, 4, 'f16x4'),     # k_16_16_16_16_FLOAT
    36: (4, 1, 'f32'),       # k_32_FLOAT
    37: (8, 2, 'f32x2'),     # k_32_32_FLOAT
    38: (16, 4, 'f32x4'),    # k_32_32_32_32_FLOAT
    29: (8, 4, 'u16x4'),     # k_16_16_16_16_EXPAND (read as unsigned normalized)
}
# Block-compressed formats: (bytes per 4x4 block, components, decoder name).
BLOCK_FORMATS = {
    49: (16, 2, 'dxn'),      # k_DXN: two BC4 blocks (x, y)
    58: (8, 1, 'dxt3a'),     # k_DXT3A: 4-bit alpha per texel
    59: (8, 1, 'bc4'),       # k_DXT5A: one BC4 block
}


def _bc4(blocks):
    """(n, 8) uint8 BC4 blocks -> (n, 16) values 0..1, texels in row order."""
    r0 = blocks[:, 0].astype(np.float64)
    r1 = blocks[:, 1].astype(np.float64)
    bits = np.zeros(len(blocks), np.uint64)
    for k in range(6):
        bits |= blocks[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
    idx = np.stack([(bits >> np.uint64(3 * t)) & np.uint64(7) for t in range(16)], 1).astype(np.int64)
    pal = np.zeros((len(blocks), 8))
    pal[:, 0], pal[:, 1] = r0, r1
    big = r0 > r1
    for k in range(1, 7):
        pal[:, k + 1] = np.where(big, ((7 - k) * r0 + k * r1) / 7.0, 0.0)
    for k in range(1, 5):
        pal[:, k + 1] = np.where(big, pal[:, k + 1], ((5 - k) * r0 + k * r1) / 5.0)
    pal[:, 6] = np.where(big, pal[:, 6], 0.0)
    pal[:, 7] = np.where(big, pal[:, 7], 255.0)
    return np.take_along_axis(pal, idx, 1) / 255.0


class FetchConstant:
    def __init__(self, draw, index):
        w = [draw.reg(f2cap.FETCH_BASE + index * 6 + k) for k in range(6)]
        self.words = w
        self.signs = [(w[0] >> (2 + 2 * c)) & 3 for c in range(4)]
        self.clamp = [(w[0] >> (10 + 3 * c)) & 7 for c in range(3)]
        self.pitch = ((w[0] >> 22) & 0x1FF) * 32
        self.tiled = bool(w[0] >> 31)
        self.format = w[1] & 0x3F
        self.endian = (w[1] >> 6) & 3
        self.base = (w[1] >> 12) << 12
        self.dimension = (w[5] >> 9) & 3  # 0 1D, 1 2D, 2 3D/stacked, 3 cube
        if self.dimension == 0:
            self.width, self.height = (w[2] & 0xFFFFFF) + 1, 1
        else:
            self.width, self.height = (w[2] & 0x1FFF) + 1, ((w[2] >> 13) & 0x1FFF) + 1
        self.num_format = w[3] & 1
        self.swizzle = [(w[3] >> (1 + 3 * c)) & 7 for c in range(4)]
        self.exp_adjust = ((w[3] >> 13) & 0x3F) - (64 if (w[3] >> 13) & 0x20 else 0)
        self.mag_filter = (w[3] >> 19) & 3
        self.min_filter = (w[3] >> 21) & 3


def tiled_offsets(x, y, pitch, bpp):
    """XGAddress2DTiledOffset: texel index of (x, y) in a tiled 2D surface."""
    aligned = (pitch + 31) & ~31
    log_bpp = (bpp >> 2) + ((bpp >> 1) >> (bpp >> 2))
    x = x.astype(np.int64)
    y = y.astype(np.int64)
    macro = ((x >> 5) + (y >> 5) * (aligned >> 5)) << (log_bpp + 7)
    micro = ((x & 7) + ((y & 6) << 2)) << log_bpp
    offset = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 8) << (3 + log_bpp)) + ((y & 1) << 4)
    return (((offset & ~511) << 3) + ((offset & 448) << 2) + (offset & 63) + ((y & 16) << 7) +
            (((((y & 8) >> 2) + (x >> 3)) & 3) << 6)) >> log_bpp


class Texture:
    """A captured texture's base level as an (h, w, 4) float array, with the
    fetch constant's swizzle applied."""

    def __init__(self, draw, fc_index, vtex):
        f = FetchConstant(draw, fc_index)
        self.fetch = f
        if f.format in BLOCK_FORMATS:
            self._init_blocks(draw, f, vtex)
            return
        if f.format not in FORMATS:
            raise ValueError(f'texture format {f.format} not handled')
        bpp, comps, kind = FORMATS[f.format]
        raw = np.frombuffer(draw.cap.blob, np.uint8, vtex['size'], vtex['blob'])
        h, w = f.height, f.width
        ys, xs = np.mgrid[0:h, 0:w]
        if f.tiled:
            idx = tiled_offsets(xs.ravel(), ys.ravel(), f.pitch, bpp)
        else:
            idx = (ys * f.pitch + xs).ravel()
        idx = np.clip(idx, 0, len(raw) // bpp - 1)
        texels = raw[:len(raw) // bpp * bpp].reshape(-1, bpp)[idx]
        # Endian swap within each texel's units.
        if f.endian == 1:  # 8in16
            texels = texels.reshape(-1, bpp // 2, 2)[:, :, ::-1].reshape(-1, bpp)
        elif f.endian == 2:  # 8in32
            texels = texels.reshape(-1, max(bpp // 4, 1), min(bpp, 4))[:, :, ::-1].reshape(-1, bpp)
        elif f.endian == 3:  # 16in32
            texels = texels.reshape(-1, max(bpp // 4, 1), 2, 2)[:, :, ::-1, :].reshape(-1, bpp)
        texels = np.ascontiguousarray(texels)
        if kind in ('u8', 'u8x4'):
            v = texels.astype(np.float64)
            v = (v - 256 * (v >= 128)) / 127.0 if f.signs[0] == 1 else v / 255.0
        elif kind in ('u16', 'u16x2', 'u16x4'):
            v = texels.view('<u2').astype(np.float64)
            v = (v - 65536 * (v >= 32768)) / 32767.0 if f.signs[0] == 1 else v / 65535.0
        elif kind.startswith('f16'):
            v = texels.view('<f2').astype(np.float64)
        else:
            v = texels.view('<f4').astype(np.float64)
        self._finish(v.reshape(h, w, comps), comps)

    def _init_blocks(self, draw, f, vtex):
        bpb, comps, kind = BLOCK_FORMATS[f.format]
        raw = np.frombuffer(draw.cap.blob, np.uint8, vtex['size'], vtex['blob'])
        bw, bh = (f.width + 3) // 4, (f.height + 3) // 4
        ys, xs = np.mgrid[0:bh, 0:bw]
        pitch_blocks = f.pitch // 4
        if f.tiled:
            idx = tiled_offsets(xs.ravel(), ys.ravel(), pitch_blocks, bpb)
        else:
            idx = (ys * pitch_blocks + xs).ravel()
        idx = np.clip(idx, 0, len(raw) // bpb - 1)
        blocks = raw[:len(raw) // bpb * bpb].reshape(-1, bpb)[idx]
        if f.endian == 1:
            blocks = blocks.reshape(-1, bpb // 2, 2)[:, :, ::-1].reshape(-1, bpb)
        elif f.endian == 2:
            blocks = blocks.reshape(-1, bpb // 4, 4)[:, :, ::-1].reshape(-1, bpb)
        blocks = np.ascontiguousarray(blocks)
        if kind == 'dxt3a':
            vals = np.stack([(blocks[:, t // 2] >> (4 * (t % 2))) & 15 for t in range(16)], 1) / 15.0
            chans = [vals]
        elif kind == 'bc4':
            chans = [_bc4(blocks)]
        else:  # dxn
            chans = [_bc4(blocks[:, :8]), _bc4(blocks[:, 8:])]
        out = np.zeros((bh * 4, bw * 4, len(chans)))
        for c, vals in enumerate(chans):
            t = vals.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)
            out[..., c] = t
        out = out[:f.height, :f.width]
        if kind == 'dxt3a':
            # A single value: every component reads it.
            out = np.repeat(out, 4, 2)
            comps = 4
        self._finish(out, comps)

    def _finish(self, v, comps):
        f = self.fetch
        h, w = v.shape[:2]
        full = np.zeros((h, w, 4))
        full[..., :comps] = v
        full[..., 3] = 1.0 if comps < 4 else full[..., 3]
        sel = []
        for s in f.swizzle:
            if s < 4:
                sel.append(full[..., s])
            else:
                sel.append(np.full((h, w), 0.0 if s == 4 else 1.0))
        self.data = np.stack(sel, -1)
        if f.exp_adjust:
            self.data = self.data * 2.0 ** f.exp_adjust

    def sample(self, u, v, linear, offset=(0.0, 0.0), unnormalized=False):
        h, w = self.data.shape[:2]
        x = u if unnormalized else u * w
        y = v if unnormalized else v * h
        x = x - 0.5 + offset[0]
        y = y - 0.5 + offset[1]
        if not linear:
            xi = np.clip(np.floor(x + 0.5).astype(np.int64), 0, w - 1)
            yi = np.clip(np.floor(y + 0.5).astype(np.int64), 0, h - 1)
            return self.data[yi, xi]
        x0 = np.floor(x)
        y0 = np.floor(y)
        fx = (x - x0)[:, None]
        fy = (y - y0)[:, None]
        x0 = x0.astype(np.int64)
        y0 = y0.astype(np.int64)

        def at(xx, yy):
            return self.data[np.clip(yy, 0, h - 1), np.clip(xx, 0, w - 1)]
        return ((at(x0, y0) * (1 - fx) + at(x0 + 1, y0) * fx) * (1 - fy) +
                (at(x0, y0 + 1) * (1 - fx) + at(x0 + 1, y0 + 1) * fx) * fy)


def draw_textures(draw):
    """{fetch constant: Texture} for the textures the draw's vertex shader reads."""
    out = {}
    for vt in draw.d.get('vtex', []):
        try:
            out[vt['fc']] = Texture(draw, vt['fc'], vt)
        except ValueError as e:
            print(f'draw {draw.index} tf{vt["fc"]}: {e}')
    return out
