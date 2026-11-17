// Fable II lightmapped ground, pixel shader 7DDAD5C29B3F56EE: the dirt and
// path patches laid over the near terrain (Bower Lake's paths and bare
// earth). Replaces the SDK's translation through the shader_replace_dir cvar
// (see shaders/README.md).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers). What the original does:
//   - tf13 colour at v0.xy (squared to linear);
//   - tf3 baked light at v0.zw, raised to c21.w through log / exp and tinted
//     by c21.xyz: the ambient light of the patch;
//   - sun diffuse (c80, c11.x) and a sky term (c23), specular colour c87;
//     ambient c22 / c20;
//   - distance fog beyond c67.x, the same block as the lit shaders;
//   - output opaque (alpha 1).
// Xenos reading notes are in xe_common.hlsli.

#ifndef DEBUG_VIEW
#define DEBUG_VIEW 0
#endif
// Improvements (0 / 1 = original look):
// SMOOTH_LIGHT: samples the baked light map with a 16-tap cubic B-spline on
//   its texel grid instead of the guest's filter. The map is a few texels
//   per metre; read as it was, each texel shows as a square of light on the
//   ground at the higher render resolution.
// ALBEDO_BUMP / FOG: as in lit.ps.hlsl (the ground normal is v2; the relief
//   tilts it along the colour map's u / v directions in world space, taken
//   from screen-space derivatives).
#ifndef SMOOTH_LIGHT
#define SMOOTH_LIGHT 1
#endif
#ifndef ALBEDO_BUMP
#define ALBEDO_BUMP 5.0
#endif
#ifndef FOG
#define FOG 1.0  // far terrain keeps its haze: it hides the low-detail backdrop patches
#endif

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#define XE_FLOAT_CONSTANTS 13
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
#define C66 K[7]
#define C67 K[8]
#define C68 K[9]
#define C80 K[10]
#define C87 K[11]
#define C255 K[12]

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
#define TF3_TEXEL(uv) FetchLevel(3, 1, uv, false, 0.0)
#define TF4(x) Fetch(4, 2, float2(x, 0.0), true)
#define TF5(x) Fetch(5, 3, float2(x, 0.0), true)

// Cubic B-spline weights for fraction f (sum to 1).

// The light map read at texel centres (exact whatever the guest filter) and
// blended with B-spline weights: smooth, no squares, no ringing.


float4 main(PSInput3 input) : SV_Target0 {
  float4 r0 = input.v0, r1 = input.v1, r2 = input.v2;
  float4 r3 = 0.0, r4 = 0.0, r5 = 0.0, r6 = 0.0, r7 = 0.0;
  float ps;

  if (ALBEDO_BUMP != 0.0) {
    // World-space directions of the colour map's u and v at this pixel,
    // from screen-space derivatives (the shader has no tangent frame).
    float2 uv = r0.xy;
    float3 dpx = ddx(r1.xyz), dpy = ddy(r1.xyz);
    float2 dux = ddx(uv), duy = ddy(uv);
    float3 n = normalize(r2.xyz);
    float3 t = dpx * duy.y - dpy * dux.y;   // d position / d u (unnormalised)
    float3 b = dpy * dux.x - dpx * duy.x;   // d position / d v
    t = normalize(t - n * dot(n, t) + 1e-6);
    b = normalize(b - n * dot(n, b) + 1e-6);
    float3 lw = float3(0.299, 0.587, 0.114);
    float he = dot(TF13_OFF(uv, 1, 0).xyz, lw), hw = dot(TF13_OFF(uv, -1, 0).xyz, lw);
    float hn = dot(TF13_OFF(uv, 0, 1).xyz, lw), hs = dot(TF13_OFF(uv, 0, -1).xyz, lw);
    float2 slope = float2(he - hw, hn - hs) * (0.5 * ALBEDO_BUMP);
    // Keep the original length: the shader uses |v2| (rsq at 11).
    r2.xyz = normalize(n - t * slope.x - b * slope.y) * length(r2.xyz);
  }
  r3.xyz = TF13(r0.xy).xyz;                                              // 5
  { float4 t = SMOOTH_LIGHT ? SmoothFetch(3, 1, r0.zw) : TF3(r0.zw);           // 6
    r0.x = t.x; r0.y = t.y; r0.w = t.z; }
  r4.xyz = -C22.xyz + C255.x; ps = C87.x;                                // 7
  { float s = ps * C11.x; r1.yzw = -r1.xyz + C19.xyz; r6.x = s; }        // 8
  { float s = log2(abs(r0.x)); r2.w = dot(r2.zxy, r2.zxy); r0.x = s; }   // 9
  { float s = log2(abs(r0.y)); r3.xyz = r3.xyz * r3.xyz; r0.z = s; }     // 10
  { float s = rsqrt(abs(r2.w)); r1.x = dot(r1.wyz, r1.wyz); r0.y = s; }  // 11
  { float s = log2(abs(r0.w)); r7.xyz = r0.y * C23.zyx; r0.w = s; }      // 12
  { float s = sqrt(abs(r1.x)); r5.xyz = r0.y * C80.xyz; r0.y = s; }      // 13
  { float s = rsqrt(abs(r1.x)); r0.xzw = r0.xzw * C21.w; r1.x = s; }     // 14
  { float s = r0.y - C67.x; r1.xyz = r1.wzy * r1.x; r0.y = s; }          // 15
  { float s = exp2(r0.x); r6.z = saturate(dot(r5.zxy, r2.zxy)); r5.x = s; }  // 16
#if SPARROW
  // Sparrow: the sun shadow map (sparrow_common.hlsli).
  r6.z *= saturate(SparrowSunOr(1.0, input.v1.xyz, normalize(input.v2.xyz)));
#endif
  { float s = exp2(r0.z); r0.x = r6.z * C11.x; r5.y = s; }               // 17
  { float s = C87.y * r0.x; r6.y = saturate(dot(r7.xzy, r2.zxy)); r2.y = s; }  // 18
  { float s = exp2(r0.w); float2 v = float2(r6.x * r6.z, r6.y * r6.y); r2.x = v.x; r2.w = v.y; r5.z = s; }  // 19
  r4.xyz = r2.w * r4.xyz + C22.xyz;                                      // 20
  { float s = C87.z * r0.x; r5.xyz = r5.xyz * C21.xyz; r2.z = s; }       // 21
  float3 light = r5.xyz;
  { float3 v = r5.xyz * r4.xyz + C20.xyz; r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 22
  float sky_vis = -1.0;
#if SPARROW
  // Sparrow: sky light and bounce from the ground ambient grid.
  if (SparrowActive()) {
    float3 a = SparrowGroundAmbientLight(float3(r0.x, r0.z, r0.w), input.v1.xyz, normalize(input.v2.xyz), C87.xyz * C11.x, sky_vis);
    r0.x = a.x; r0.z = a.y; r0.w = a.z;
  }
#endif
  bool fog = r0.y > 0.0;
  { float3 v = r3.xyz * float3(r0.x, r0.z, r0.w); r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 23
  { float3 v = r3.xyz * r2.xyz + float3(r0.x, r0.z, r0.w); r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 24
  if (fog) {
    { float s = C67.w * r0.y; r1.x = saturate(dot(-r1.xzy, C66.zxy)); r1.w = s; }  // 25
    r1.xyz = TF4(r1.x).xyz;                                              // 26
    r2.xyz = TF5(r1.w).xyz;                                              // 27
    r3.xyz = C255.x - r2.xyz;                                            // 28
    { float s = saturate(C67.z * r0.y); r1.xyz = r1.xyz - C68.xyz; r0.y = s; }  // 29
    r1.xyz = r0.y * r1.zyx + C68.zyx;                                    // 30
    r3.xyz = r3.zyx * C28.y;                                             // 31
    r1.xyz = r3.xyz * r1.xyz - float3(r0.w, r0.z, r0.x);                 // 32
    r1.xyz = float3(r0.w, r0.z, r0.x) * r2.zyx + r1.xyz;                 // 33
    { float3 v = r1.zyx * (C28.x * FOG) + float3(r0.x, r0.z, r0.w); r0.x = v.x; r0.z = v.y; r0.w = v.z; }  // 34
  }
  float4 o = float4(float3(r0.x, r0.z, r0.w) * C20.w, 1.0);              // 35
#if DEBUG_VIEW == 1
  o.xyz = light * 0.5;   // the baked light alone
#elif DEBUG_VIEW == 2
  o.xyz = sqrt(r3.xyz);  // the colour map alone
#endif
#if SPARROW
  // red open sky, green closed in (sparrow_debug 3)
  if (SparrowDebug() == 3) o.xyz = SparrowVisDebug(sky_vis);
#endif
  return o * xe_color_exp_bias.x;
}
