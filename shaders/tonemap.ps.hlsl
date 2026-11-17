// Fable II final composite / tone map, pixel shader 37B186F4BD3288F7 (the
// full-screen 1280x720 pass after the quarter-res bloom chain). Replaces the
// SDK's translation through the shader_replace_dir cvar (see
// shaders/README.md).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers). What the original does:
//   - samples the HDR scene (tf0) and takes its luminance (c255 weights);
//   - looks the luminance (times c46.x) up in a 1-D tone curve (tf1, point
//     sampled) and scales the colour by curve * c77.y, with c47.x blending
//     between the colour and its grey;
//   - screen-blends the quarter-res bloom (tf2 * c31.x): out = s + b - s*b;
//   - saturation around the grey (c77.x) and a final power (c78.x).
// The screen-blended bloom is the soft glow over the whole picture; the
// scene texture is the 1120-wide frame stretched to 1280, so it is also a
// little soft.
// Xenos reading notes are in xe_common.hlsli.

#ifndef DEBUG_VIEW
#define DEBUG_VIEW 0
#endif
// Improvements (1/0 = original look):
// GLOW: scale on the game's bloom (1 = original, 0 = none). The bloom is a
//   blurred copy of the whole bright picture, so at 1 it veils detail in
//   every lit area, not only around highlights.
// SHARPEN: contrast-adaptive sharpening of the scene before the tone curve
//   (0 = off), on the host pixel grid, to undo the 1120 -> 1280 stretch and
//   bring out texture detail. SHARPEN_LIMIT caps the change per pixel
//   (relative to the local brightness) so edges do not ring.
// CLARITY: local contrast against a wider (4-pixel) neighbourhood, which
//   firms up surface detail that the haze flattens (0 = off).
#ifndef GLOW
#define GLOW 0.3
#endif
#ifndef SHARPEN
#define SHARPEN 0.6
#endif
#ifndef SHARPEN_LIMIT
#define SHARPEN_LIMIT 0.25
#endif
#ifndef CLARITY
#define CLARITY 0.25
#endif
// HIGHLIGHTS: soft roll-off instead of the original hard clip at 1 (0 =
//   original). Values below this knee are untouched; above it the brightest
//   channel eases toward 1 keeping the hue, so the sky keeps its gradient and
//   clouds and sunlit leaves keep detail. HIGHLIGHT_WHITE: blend from that
//   hue-kept curve (0) to a per-channel curve (1), which lets the brightest
//   colours drift toward white as film does.
#ifndef HIGHLIGHTS
#define HIGHLIGHTS 0.75
#endif
// VIBRANCE: extra saturation that favours muted colours (0 = off), so
//   hazy greens and earth tones get richer while already strong colours
//   (and skin) barely move.
#ifndef VIBRANCE
#define VIBRANCE 0.4
#endif
#ifndef HIGHLIGHT_WHITE
#define HIGHLIGHT_WHITE 1.0
#endif

float RollOff1(float x) {
  float k = HIGHLIGHTS, r = 1.0 - HIGHLIGHTS;
  return x <= k ? x : k + r * (1.0 - exp(-(x - k) / r));
}

float3 RollOff(float3 c) {
  float m = max(c.x, max(c.y, c.z));
  if (HIGHLIGHTS <= 0.0 || m <= HIGHLIGHTS) return saturate(c);
  // Hue-kept: scale the colour so its brightest channel follows the curve.
  float3 h = c * (RollOff1(m) / m);
  // Per channel: each channel follows the curve on its own, so the very
  // brightest colours drift toward white as film does (a blown sky stays a
  // bright haze rather than turning a strong pink or blue).
  float3 f = float3(RollOff1(c.x), RollOff1(c.y), RollOff1(c.z));
  return saturate(lerp(h, f, HIGHLIGHT_WHITE));
}

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#define XE_FLOAT_CONSTANTS 6
#define XE_DESCRIPTOR_INDICES 3
#include "xe_common.hlsli"

#define C31 K[0]
#define C46 K[1]
#define C47 K[2]
#define C77 K[3]
#define C78 K[4]
#define C255 K[5]

struct PSInput1 {
  float4 v0 : TEXCOORD0;
  float4 position : SV_Position;
  bool front_face : SV_IsFrontFace;
};

// The ucode's OffsetX/Y = 0.5 fetches: half a guest texel on top of the
// translator's own small offset (scaled by 1/3 when the texture is
// resolution-scaled, as FetchCore does).
float2 HalfTexel(uint tf, float2 uv) {
  float2 half_texel = 0.5 / TextureSize(tf);
  bool scaled = ((xe_textures_resolution_scaled >> tf) & 1) != 0;
  return uv + (scaled ? half_texel * (1.0 / 3.0) : half_texel);
}
// Texture bindings of this shader, in the translator's order.
#define TF0(uv) Fetch(0, 0, HalfTexel(0, uv), false)
#define TF2(uv) Fetch(2, 1, HalfTexel(2, uv), false)
#define TF1(u) Fetch(1, 2, float2(u, 0.0) + float2(0.5 / TextureSize(1).x, 0.0), true)

float Luma(float3 c) { return dot(c, float3(0.299, 0.587, 0.114)); }

float4 main(PSInput1 input) : SV_Target0 {
  float4 r0 = input.v0;
  float4 r1 = 0.0, r2 = 0.0;
  float2 uv = r0.xy;

  r2.xyz = TF0(uv).xyz;                                                  // 3
  if (SHARPEN != 0.0 || CLARITY != 0.0) {
    // One host pixel in this texture's UV space.
    float2 px = float2(abs(ddx_fine(uv.x)), abs(ddy_fine(uv.y)));
    float3 c = r2.xyz;
    float l = Luma(c);
    float ln = Luma(TF0(uv + float2(0, -px.y)).xyz), ls = Luma(TF0(uv + float2(0, px.y)).xyz);
    float lw = Luma(TF0(uv + float2(-px.x, 0)).xyz), le = Luma(TF0(uv + float2(px.x, 0)).xyz);
    float mn = min(l, min(min(ln, ls), min(lw, le)));
    float mx = max(l, max(max(ln, ls), max(lw, le)));
    float delta = 0.0;
    if (SHARPEN != 0.0) {
    // AMD CAS-style weight: less sharpening where the neighbourhood already
    // spans a wide range (strong edges), more on flat, detailed surfaces.
    // (The scene is HDR: judge the range on a compressed l / (1 + l) scale.)
    float mnc = mn / (1.0 + mn), mxc = mx / (1.0 + mx);
    float amp = saturate(min(mnc, max(1e-4, 1.0 - mxc)) / max(mxc, 1e-4));
    amp = sqrt(amp);
    float sharp = (4.0 * l - ln - ls - lw - le) * 0.25 * amp * SHARPEN * 2.0;
    delta += sharp;
    }
    if (CLARITY != 0.0) {
    float2 w = px * 4.0;
    float lwide = 0.25 * (Luma(TF0(uv + float2(w.x, w.y)).xyz) + Luma(TF0(uv + float2(-w.x, w.y)).xyz) +
                          Luma(TF0(uv + float2(w.x, -w.y)).xyz) + Luma(TF0(uv + float2(-w.x, -w.y)).xyz));
    delta += (l - lwide) * CLARITY;
    }
    delta = clamp(delta, -SHARPEN_LIMIT * max(l, 0.02), SHARPEN_LIMIT * max(l, 0.02));
    // Scale the colour (keeps hue) by the luminance change.
    r2.xyz = c * (max(l + delta, 0.0) / max(l, 1e-4));
  }
  r0.z = dot(r2.zxy, C255.xyz);                                          // 4
  r1.w = C46.x * r0.z;                                                   // 5
  r1.xyz = TF2(uv).xyz;                                                  // 6
  r0.x = TF1(r1.w).x;                                                    // 7
  { float s = C77.y * r0.x; r1.xyz = saturate(r1.xzy * C31.x); r0.w = s; }  // 8
  r1.xyz *= GLOW;
  { float s = saturate(C47.x * r0.z); r2.xyz = -r0.z + r2.xyz; r0.x = s; }  // 9
  r0.xyz = r0.x * r2.xyz + r0.z;                                         // 10
  float3 pre_clip = r0.w * r0.xzy;
  r0.xyz = RollOff(pre_clip);                                            // 11 (saturate)
  r1.xyz = -r1.xyz * r0.xyz + r1.xyz;                                    // 12
  r0.xyz = r1.xzy + r0.xzy;                                              // 13
  r0.w = dot(r0.zxy, C255.xyz);                                          // 14
  r1.xyz = r0.xzy - r0.w;                                                // 15
  r0.xyz = r1.xzy * C77.x + r0.xyz;                                      // 16
  if (VIBRANCE != 0.0) {
    float sat = max(r0.x, max(r0.y, r0.z)) - min(r0.x, min(r0.y, r0.z));
    r0.xyz = max(r0.w + (r0.xyz - r0.w) * (1.0 + VIBRANCE * (1.0 - saturate(sat))), 0.0);
  }
  r0.xyz = log2(abs(r0.xyz));                                            // 17-19
  r0.xyz = r0.xyz * C78.x;                                               // 20
  float4 o = float4(exp2(r0.x), exp2(r0.y), exp2(r0.z), exp2(r0.z));     // 21-23
#if DEBUG_VIEW == 2
  // Clipping: red = how far the brightest channel goes over 1 (x4), green =
  // the luminance before the clip (dimmed).
  { float m = max(pre_clip.x, max(pre_clip.y, pre_clip.z));
    o = float4(saturate((m - 1.0) * 4.0), saturate(Luma(pre_clip)) * 0.5, 0.0, 1.0); }
#endif
#if DEBUG_VIEW == 1
  o = float4(r1.xzy, 1.0);   // the (scaled) bloom alone
#endif
  return o * xe_color_exp_bias.x;
}
