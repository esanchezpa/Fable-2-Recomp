"""The game's final tonemap, so the redraw can light in the game's own HDR
units (albedo squared, exposure c20.w) and finish the same way.

The game's last full-screen pass (pixel shader 37B186F4) does per pixel:
    Y = luminance(hdr)
    gain = curve[Y * c46.x] * c77.y          (tf1: a 512-entry 1D table)
    c = saturate(mix(Y, hdr, saturate(c47.x * Y)) * gain)
    c = c + bloom * (1 - c)                  (left out here)
    c = c + (c - luminance(c)) * c77.x       (saturation)
    out = c ^ c78.x                          (gamma)
"""

import numpy as np

import xtex
import xvs

TONEMAP_PS = '37B186F4'
LUMA = (0.2125, 0.7154, 0.0721)

GLSL = '''
#version 330
uniform sampler2D hdr;
uniform sampler2D curve;     // 512 x 1, gain in .r
uniform vec4 tone;           // c46.x (curve scale), c47.x (grey below), c77.x (saturation), c77.y (gain)
uniform float gamma;         // c78.x
uniform int passthrough;     // debug modes write display colour directly
in vec2 v_pos;
out vec4 frag;
const vec3 LUMA = vec3(0.2125, 0.7154, 0.0721);
void main() {
    vec3 h = texture(hdr, v_pos).rgb;
    if (passthrough != 0) { frag = vec4(h, 1.0); return; }
    h = max(h, vec3(0.0));
    float y = dot(h, LUMA);
    int i = clamp(int(floor(y * tone.x * 512.0 + 0.5)), 0, 511);
    float g = texelFetch(curve, ivec2(i, 0), 0).r * tone.w;
    vec3 c = clamp(mix(vec3(y), h, clamp(tone.y * y, 0.0, 1.0)) * g, 0.0, 1.0);
    c += (c - dot(c, LUMA)) * tone.z;
    frag = vec4(pow(max(c, vec3(0.0)), vec3(gamma)), 1.0);
}
'''

QUAD_VS = '''
#version 330
in vec2 in_vert;
out vec2 v_pos;
void main() { v_pos = in_vert * 0.5 + 0.5; gl_Position = vec4(in_vert, 0.0, 1.0); }
'''

# GLSL for materials authored as display colour (sky, water, haze): back to
# HDR through the inverse of the tone curve (inv_curve: display luminance ->
# HDR luminance, 1024 x 1).
TO_HDR = '''
uniform sampler2D inv_curve;
vec3 to_hdr(vec3 d) {
    vec3 c = pow(max(d, vec3(0.0)), vec3(1.0 / tone_gamma));
    float yc = dot(c, vec3(0.2125, 0.7154, 0.0721));
    float yh = texture(inv_curve, vec2(clamp(yc, 0.0, 1.0) * (1023.0 / 1024.0) + 0.5 / 1024.0, 0.5)).r;
    return c * (yh / max(yc, 1e-5));
}
'''


class Tonemap:
    def __init__(self, cap):
        """Constants and curve from the capture's tonemap draw; a plain
        filmic-ish stand-in when the capture doesn't have one."""
        self.scale, self.grey, self.saturation, self.gain, self.gamma = 0.25, 50.0, -0.13, 1.046, 0.4545
        self.curve = None
        for d in reversed(cap.draws if cap is not None else []):
            if d.ps.startswith(TONEMAP_PS):
                c = xvs.Machine(d, 1, pixel=True).consts
                self.scale, self.grey = float(c[46][0]), float(c[47][0])
                self.saturation, self.gain, self.gamma = float(c[77][0]), float(c[77][1]), float(c[78][0])
                if 1 in d.ptex:
                    try:
                        t = xtex.Texture(d, 1, d.ptex[1])
                        self.curve = t.data.reshape(-1, t.data.shape[-1])[:, 0].astype(np.float32)
                    except ValueError as e:
                        print(f'tonemap curve: {e}')
                break
        if self.curve is None or len(self.curve) < 2:
            y = (np.arange(512) + 0.5) / 512.0 / self.scale
            self.curve = (1.0 / (1.0 + y)).astype(np.float32)  # Reinhard-like gain
        self.inverse = self._inverse()

    def display_luma(self, yh):
        n = len(self.curve)
        i = np.clip(np.floor(yh * self.scale * n + 0.5).astype(int), 0, n - 1)
        return np.minimum(yh * self.curve[i] * self.gain, 1.0)

    def _inverse(self):
        yh = np.concatenate([[0.0], np.geomspace(1e-4, 64.0, 4096)])
        yc = np.maximum.accumulate(self.display_luma(yh))
        keep = np.concatenate([[True], np.diff(yc) > 0])
        target = np.linspace(0.0, 1.0, 1024)
        return np.interp(target, yc[keep], yh[keep]).astype(np.float32)

    def textures(self, ctx):
        curve = ctx.texture((len(self.curve), 1), 1, self.curve.tobytes(), dtype='f4')
        curve.filter = (ctx.NEAREST, ctx.NEAREST)
        inv = ctx.texture((len(self.inverse), 1), 1, self.inverse.tobytes(), dtype='f4')
        inv.filter = (ctx.LINEAR, ctx.LINEAR)
        inv.repeat_x = inv.repeat_y = False
        return curve, inv
