// Fable II near ground, pixel shader 2F8A0341E8C09698: the lightmapped
// grass and forest floor around the player (the far terrain is
// 7DDAD5C29B3F56EE, ground.ps.hlsl, the same shading). Replaces the SDK's
// translation through the shader_replace_dir cvar (see shaders/README.md).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers). What the original does:
//   - tf13 colour at v0.xy (squared to linear); tf3 baked light at v0.zw,
//     raised to c21.w (log / exp) and tinted by c21.xyz;
//   - sun diffuse (c80, c11.x), sky term (c23), ambient c22 / c20,
//     specular colour c87; normal v2, world position v1;
//   - distance fog beyond c67.x (the lit shaders' block);
//   - the colour times saturate(dist^2 * c31.x + c31.y): a fade with
//     distance; opaque.
// Xenos reading notes are in xe_common.hlsli.

#ifndef DEBUG_VIEW
#define DEBUG_VIEW 0
#endif
// Improvements (0 / 1 = original look):
// SMOOTH_COLOR / SMOOTH_LIGHT: the colour map (where magnified) and the
//   baked light map read with a cubic B-spline at texel centres instead of
//   the guest's point filter. Both are a few texels per metre, so read as
//   the game reads them every texel is a hard square on the ground.
// ALBEDO_BUMP / FOG: as in lit.ps.hlsl (tangent directions from
//   screen-space derivatives, as in ground.ps.hlsl).
#ifndef SMOOTH_COLOR
#define SMOOTH_COLOR 1
#endif
#ifndef SMOOTH_LIGHT
#define SMOOTH_LIGHT 1
#endif
// GROUND_DETAIL: where the colour map is magnified (its texels are blobs),
//   procedural world-space detail: tone variation and grain on the colour
//   and a matching height field that tilts the normal (0 = off).
#ifndef GROUND_DETAIL
#define GROUND_DETAIL 1.0
#endif
#ifndef ALBEDO_BUMP
#define ALBEDO_BUMP 5.0
#endif
#ifndef FOG
#define FOG 0.6
#endif

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#define XE_FLOAT_CONSTANTS 14
#define XE_DESCRIPTOR_INDICES 4
#include "xe_common.hlsli"
#include "modern_common.hlsli"
#if SPARROW
#include "sparrow_common.hlsli"
#endif

#define C11 K[0]
#define C19 K[1]
#define C20 K[2]
#define C21 K[3]
#define C22 K[4]
#define C23 K[5]
#define C28 K[6]
#define C31 K[7]
#define C66 K[8]
#define C67 K[9]
#define C68 K[10]
#define C80 K[11]
#define C87 K[12]
#define C255 K[13]

struct PSInput3 {
  centroid float4 v0 : TEXCOORD0;
  float4 v1 : TEXCOORD1;
  float4 v2 : TEXCOORD2;
  float4 position : SV_Position;
  bool front_face : SV_IsFrontFace;
};

// Texture bindings of this shader, in the translator's order.
#define TF13(uv) Fetch(13, 0, uv, false)
#define TF13_OFF(uv, ox, oy) FetchOffset(13, 0, uv, int2(ox, oy))
#define TF3(uv) Fetch(3, 1, uv, false)
#define TF4(x) Fetch(4, 2, float2(x, 0.0), true)
#define TF5(x) Fetch(5, 3, float2(x, 0.0), true)

// Smooth bilinear: the 2x2 texel-centre reads around the point, blended with
// smoothstep weights. Continuous, no squares, and it reaches only one texel
// (a wider cubic crossed the light map's tile borders as dark seams).




// Forest-floor height in metres from the world position: clods and dips,
// twigs-and-leaf-litter grain, fine soil speckle.
float GroundHeight(float3 p) {
  return 0.010 * Noise3(p * 3.0) + 0.004 * Noise3(p * 14.0) + 0.0015 * Noise3(p * 45.0);
}
float4 main(PSInput3 input) : SV_Target0 {
  float4 r0 = input.v0, r1 = input.v1, r2 = input.v2;
  float4 r3 = 0.0, r4 = 0.0, r5 = 0.0, r6 = 0.0, r7 = 0.0;
  float ps;
  float2 uv = r0.xy;

  float magnify = 0.0;
  if (ALBEDO_BUMP != 0.0 || SMOOTH_COLOR) {
    magnify = Magnification(0, uv);
  }
  if (ALBEDO_BUMP != 0.0) {
    float3 dpx = ddx(r1.xyz), dpy = ddy(r1.xyz);
    float2 dux = ddx(uv), duy = ddy(uv);
    float3 n = normalize(r2.xyz);
    float3 t = dpx * duy.y - dpy * dux.y;
    float3 b = dpy * dux.x - dpx * duy.x;
    t = normalize(t - n * dot(n, t) + 1e-6);
    b = normalize(b - n * dot(n, b) + 1e-6);
    float3 lw = float3(0.299, 0.587, 0.114);
    float he = dot(TF13_OFF(uv, 1, 0).xyz, lw), hw = dot(TF13_OFF(uv, -1, 0).xyz, lw);
    float hn = dot(TF13_OFF(uv, 0, 1).xyz, lw), hs = dot(TF13_OFF(uv, 0, -1).xyz, lw);
    // Weaker where the map is magnified: there its texels are blobs, not grain.
    float2 slope = float2(he - hw, hn - hs) * (0.5 * ALBEDO_BUMP * (1.0 - 0.7 * magnify));
    float3 nn = n - t * slope.x - b * slope.y;
    if (GROUND_DETAIL != 0.0 && magnify > 0.0) {
      // Height-field slope along the surface (finite difference, 4 mm).
      const float e = 0.004;
      float3 pw = r1.xyz;
      float h0 = GroundHeight(pw);
      float gt = (GroundHeight(pw + t * e) - h0) / e, gb = (GroundHeight(pw + b * e) - h0) / e;
      nn -= (t * gt + b * gb) * (GROUND_DETAIL * magnify);
    }
    r2.xyz = normalize(nn) * length(r2.xyz);
  }
  r5.xyz = TF13(r0.xy).xyz;                                              // 5
  if (SMOOTH_COLOR && magnify > 0.0) r5.xyz = lerp(r5.xyz, SmoothFetch(13, 0, uv).xyz, magnify);
  if (GROUND_DETAIL != 0.0 && magnify > 0.0) {
    float3 pw = r1.xyz;
    float tone = Noise3(pw * 0.8 + 7.0) - 0.5;                    // patches over metres
    float grain = (Noise3(pw * 14.0) - 0.5) * 0.6 + (Noise3(pw * 45.0) - 0.5) * 0.4;
    float dip = 1.0 - smoothstep(0.35, 0.6, Noise3(pw * 3.0));   // low spots hold shade
    float w = 1.0 + (0.18 * tone + 0.30 * grain - 0.10 * dip) * GROUND_DETAIL * magnify;
    r5.xyz *= w;
  }
  { float4 t = SMOOTH_LIGHT ? SmoothFetch(3, 1, r0.zw) : TF3(r0.zw);     // 6
    r0.x = t.x; r0.y = t.y; r0.w = t.z; }
  r4.xyz = -C22.xyz + C255.x; ps = C87.x;                                // 7
  { float s = ps * C11.x; r3.xyz = -r1.zyx + C19.zyx; r6.x = s; }        // 8
  { float s = log2(abs(r0.x)); r1.y = dot(r2.zxy, r2.zxy); r0.x = s; }   // 9
  { float s = log2(abs(r0.y)); float3 v = r5.xyz * r5.xyz; r1.x = v.x; r1.z = v.y; r1.w = v.z; r0.z = s; }  // 10
  { float s = rsqrt(abs(r1.y)); r2.w = dot(r3.xzy, r3.xzy); r0.y = s; }  // 11
  r1.y = saturate(r2.w * C31.x + C31.y);                                 // 12
  { float s = log2(abs(r0.w)); r7.xyz = r0.y * C23.zyx; r0.w = s; }      // 13
  { float s = sqrt(abs(r2.w)); r5.xyz = r0.y * C80.xyz; r0.y = s; }      // 14
  { float s = rsqrt(abs(r2.w)); r0.xzw = r0.xzw * C21.w; r2.w = s; }     // 15
  { float s = r0.y - C67.x; r3.xyz = r3.xyz * r2.w; r0.y = s; }          // 16
  { float s = exp2(r0.x); r6.z = saturate(dot(r5.zxy, r2.zxy)); r5.x = s; }  // 17
#if SPARROW
  // Sparrow: the sun shadow map (sparrow_common.hlsli).
  r6.z *= saturate(SparrowSunOr(1.0, input.v1.xyz, normalize(input.v2.xyz)));
#endif
  { float s = exp2(r0.z); r0.x = r6.z * C11.x; r5.y = s; }               // 18
  { float s = C87.y * r0.x; r6.y = saturate(dot(r7.xzy, r2.zxy)); r2.y = s; }  // 19
  { float s = exp2(r0.w); float2 v = float2(r6.x * r6.z, r6.y * r6.y); r2.x = v.x; r2.w = v.y; r5.z = s; }  // 20
  r4.xyz = r2.w * r4.xyz + C22.xyz;                                      // 21
  { float s = C87.z * r0.x; r5.xyz = r5.xyz * C21.xyz; r2.z = s; }       // 22
  float3 light = r5.xyz;
  { float3 v = r5.xyz * r4.xyz + C20.xyz; r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 23
  bool fog = r0.y > 0.0;
  { float3 v = float3(r1.x, r1.z, r1.w) * float3(r0.x, r0.z, r0.w); r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 24
  { float3 v = float3(r1.x, r1.z, r1.w) * r2.xyz + float3(r0.x, r0.z, r0.w); r1.x = v.x; r1.z = v.y; r1.w = v.z; }  // 25
  if (fog) {
    { float s = C67.w * r0.y; r0.x = saturate(dot(-r3.xzy, C66.zxy)); r2.x = s; }  // 26
    { float3 t = TF4(r0.x).xyz; r0.x = t.x; r0.z = t.y; r0.w = t.z; }   // 27
    r2.xyz = TF5(r2.x).xyz;                                              // 28
    r3.xyz = C255.x - r2.xyz;                                            // 29
    { float s = saturate(C67.z * r0.y); r0.x -= C68.x; r0.z -= C68.y; r0.w -= C68.z; r0.y = s; }  // 30
    r0.xyz = r0.y * float3(r0.w, r0.z, r0.x) + C68.zyx;                  // 31
    r3.xyz = r3.zyx * C28.y;                                             // 32
    r0.xyz = r3.xyz * r0.xyz - float3(r1.w, r1.z, r1.x);                 // 33
    r0.xyz = float3(r1.w, r1.z, r1.x) * r2.zyx + r0.xyz;                 // 34
    { float f = C28.x * FOG; r1.x += r0.z * f; r1.z += r0.y * f; r1.w += r0.x * f; }  // 35
  }
  r0.xy = r1.xy * C20.w;                                                 // 36
  float4 o = float4(r0.x * r1.y, r0.y * r1.z, r0.y * r1.w, 1.0);         // 37
#if DEBUG_VIEW == 1
  o.xyz = sqrt(float3(r1.x, r1.z, r1.w)) * 0.0 + light * 0.5;   // baked light alone
#elif DEBUG_VIEW == 2
  o.xyz = float3(magnify, 0.0, 0.0);
#endif
  return o * xe_color_exp_bias.x;
}
