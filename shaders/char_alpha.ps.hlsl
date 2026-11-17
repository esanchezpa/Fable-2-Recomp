// Fable II translucent character parts, sun only, pixel shader
// 2FD24989AB04A475: drawn with the skinned character vertex shaders (xe_flags
// bit 31), alongside 8D900846800943C8 (lit.ps.hlsl). Replaces the SDK's
// translation through the shader_replace_dir cvar (see shaders/README.md).
//
// A literal port of the game's Xenos microcode (comments give the ucode
// instruction numbers). It is lit.ps.hlsl's material with two differences:
//   - tf1's alpha (fetched into r10.z) sets the specular power per pixel,
//     between c24.x and c24.y;
//   - the output keeps the albedo's alpha (c26.w * tf0.w), so the draw blends.
// Layout: tf0 albedo (alpha in .x) through c8, tf1 specular + gloss through
// c9, tf2 a two-channel normal offset through c10, tangent frame v3 / v4 / v1,
// world position v2, view vector c19 - v2, screen-space shadow tf8, the
// optional lightmap tf13 (b133), the environment cube tf14 (b134) and the
// distance fog beyond c67.x with the tf4 / tf5 ramps. The sun is c80 / c87.
//
// Sparrow: the sun shadow map, sky openness and bounce on the ambient, and
// the shared character lobe and sheen, as lit.ps.hlsl's character branch.
// Xenos reading notes are in xe_common.hlsli.

#ifndef FOG
#define FOG 0.6  // distance fog strength, as lit.ps.hlsl
#endif

#define XE_FLOAT_CONSTANTS 21
#define XE_DESCRIPTOR_INDICES 7
#include "xe_common.hlsli"
#if SPARROW
#include "sparrow_common.hlsli"
#endif

#define C0 K[0]
#define C8 K[1]
#define C9 K[2]
#define C10 K[3]
#define C19 K[4]
#define C20 K[5]
#define C21 K[6]
#define C22 K[7]
#define C23 K[8]
#define C24 K[9]
#define C26 K[10]
#define C27 K[11]
#define C28 K[12]
#define C49 K[13]
#define C66 K[14]
#define C67 K[15]
#define C68 K[16]
#define C80 K[17]
#define C87 K[18]
#define C254 K[19]
#define C255 K[20]

// Texture bindings of this shader, in the translator's order.
#define TF2(uv) Fetch(2, 0, uv, false)
#define TF0(uv) Fetch(0, 1, uv, false)
#define TF1(uv) Fetch(1, 2, uv, false)
#define TF8(uv) Fetch(8, 3, uv, false)
#define TF13(uv) Fetch(13, 4, uv, false)
#define TF14(stf) FetchCube(14, 5, stf)
#define TF4(x) Fetch(4, 6, float2(x, 0.0), true)
#define TF5(x) Fetch(5, 7, float2(x, 0.0), true)

float4 main(PSInput7 input, out uint coverage : SV_Coverage) : SV_Target0 {
  float4 r0 = input.v0, r1 = input.v1, r2 = input.v2, r3 = input.v3;
  float4 r4 = input.v4, r5 = input.v5, r6 = input.v6;
  float4 r7 = 0.0, r8 = 0.0, r9 = 0.0, r10 = 0.0, r11 = 0.0, r12 = 0.0, r13 = 0.0, r14 = 0.0;
  r7.xy = GuestPixelPosition(input.position, input.front_face);

  r0.zw = r0.yx * C9.yx + C9.wz;                                         // 10
  r8.xy = r0.yx * C8.yx + C8.wz;                                         // 11
  r8.zw = r0.yx * C10.yx + C10.wz;                                       // 12
  r9.zw = TF2(r8.wz).xy;                                                 // 13
  { float4 t = TF0(r8.yx); r8 = t.wxyz; }                                // 14
  float3 sp_albedo = r8.yzw * r8.yzw;  // Sparrow: colour map, linear (character material)
  { float4 t = TF1(r0.wz); r10 = t.xywz; }                               // 15
  r3.w = dot(r1.xyz, r1.xyz);                                            // 16
  { float3 v = C19.zyx - r2.zyx; r0.z = C24.y - C24.x; r2.yzw = v; }     // 17
  r0.w = r0.z * r10.z + C24.x;                                           // 18
  { float3 v = r8.wzy * r8.wzy; r9.x = r10.x * r10.x; r8.yzw = v; }      // 19
  { float v = dot(r2.ywz, r2.ywz); r9.y = r10.y * r10.y; r0.z = v; }     // 20
  { float2 v = r9.wz * C254.x + C254.z; r9.z = v.x; r9.w = v.y; }        // 21
  r1.w = r9.w * r9.w + r9.z * r9.z + C254.y;                             // 22
  { float3 v = r9.z * r4.zxy; r9.z = r10.w * r10.w; r10.xyz = v; }       // 23
  r10.xyz = r9.w * r3.zxy + r10.xyz;                                     // 24
  { float v = C254.w - r1.w; r2.x = rsqrt(abs(r3.w)); r1.w = v; }        // 25
  { float3 v = r2.x * r1.zyx; r1.w = sqrt(abs(r1.w)); r11.xyz = v; }     // 26
  r10.xyz = r11.xyz * r1.w + r10.xzy;                                    // 27
  { float v = dot(r10.xzy, r10.xzy); r2.x = rsqrt(abs(r0.z)); r1.w = v; }  // 28
  { float3 v = r2.wzy * r2.x; r1.w = rsqrt(abs(r1.w)); r2.xyz = v; }     // 29
  { float3 v = r10.xyz * r1.w; r0.z = sqrt(abs(r0.z)); r10.xyz = v; }    // 30
  if (XeBool(128)) {
    r1.w = r8.x * r8.x;                                                  // 31
    r1.w = rcp(r1.w);                                                    // 32
    r8.yzw = r8.yzw * r1.w;                                              // 33
  }
  r7.xy = abs(r7.xy) * C0.zw + C0.xy;                                    // 34
  r6.w = TF8(r7.xy).x;                                                   // 35
#if SPARROW
  // Sparrow: the real sun shadow map (v2 is the world position, v1 the normal).
  r6.w = SparrowSunOr(r6.w, input.v2.xyz, normalize(input.v1.xyz));
#endif
  float shadow = r6.w;
  r14.xyz = C254.w - C22.xyz;                                            // 36
  { float3 v = r8.wzy * C27.w; r11.x = log2(abs(r6.x)); r7.xyz = v; }    // 37
  { float v = dot(r5.xyz, r5.xyz); r11.y = log2(abs(r6.y)); r2.w = v; }  // 38
  { float v = saturate(dot(r10.xzy, C80.zxy)); r11.z = log2(abs(r6.z)); r6.x = v; }  // 39
  { float v = dot(r10.xzy, C80.zxy); r1.w = saturate(C23.w * r6.x); r6.y = v; }  // 40
  { float3 v = r11.xyz * C21.w; r6.y = r6.y + r6.y; r11.xyz = v; }       // 41
  r12.xyz = -r10.xyz * r6.y + C80.zyx;                                   // 42
  { float v = saturate(dot(-r2.zxy, r12.xzy)); r6.z = rsqrt(abs(r2.w)); r6.y = v; }  // 43
  { float3 v = r6.z * r5.zyx; r6.y = log2(r6.y); r5.yzw = v; }           // 44
  { float v = r0.w * r6.y; r5.x = exp2(r11.x); r6.y = v; }               // 45
  { float v = saturate(dot(r5.ywz, r10.xzy)); r6.y = exp2(r6.y); r6.z = v; }  // 46
  { float v = r1.w * r6.y; r5.y = exp2(r11.y); r6.y = v; }               // 47
  { float3 v = r6.zyx * r6.zww; r5.z = exp2(r11.z); r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 48
  { float3 v = r5.xyz * C21.xyz; r12.x = C87.x * r6.w; r13.xyz = v; }    // 49
  { float3 v = r6.y * C87.xyz; r12.y = C87.y * r6.w; r11.xyz = v; }      // 50
  r5.xyz = r6.x * r14.xyz + C22.xyz;                                     // 51
  r5.xyz = r13.xyz * r5.xyz + C20.xyz;                                   // 52
  float sky_vis = -1.0;
#if SPARROW
  // Sparrow: sky openness and the sun's bounce on the ambient (r10 holds the
  // normal as zyx).
  if (SparrowActive()) r5.xyz = SparrowAmbient(r5.xyz, input.v2.xyz, r10.zyx, C87.xyz, sky_vis);
#endif
  float3 ambient = r5.xyz;
  { float3 v = r9.xzy * r11.xzy; r12.z = C87.z * r6.w; r11.xyz = v; }    // 53
  r6.xyz = r12.xyz * r8.wzy + r11.xzy;                                   // 54
  float3 sparrow_add = 0.0;
#if SPARROW
  if (SparrowActive() && (xe_flags & 0x80000000u)) {
    // The shared character lobe and fabric sheen (lit.ps.hlsl).
    float3 n = r10.zyx, v = r2.xyz;
    SparrowCharMat cm = SparrowCharMaterial(sp_albedo);
    sparrow_add = SparrowCharacterSpecular(n, v, C80.xyz, C87.xyz * shadow, cm) +
                  SparrowCharacterSheen(ambient * C27.w, n, v, cm);
  }
#endif
  r5.xyz = r7.xyz * r5.xyz + r6.xyz;                                     // 55
#if SPARROW
  r5.xyz = (SparrowDebug() == 2 && SparrowActive()) ? sparrow_add : r5.xyz + sparrow_add;
#endif
  if (XeBool(133)) {
    r6.xyz = TF13(r0.xy).xyz;                                            // 56
    r6.xyz = r6.xyz * r6.xyz;                                            // 57
    r5.xyz = r6.xyz * C24.z + r5.xyz;                                    // 58
  }
  if (XeBool(134)) {
    r6.x = dot(-r2.zxy, r10.xzy);                                        // 59
    r6.x = r6.x + r6.x;                                                  // 60
    { float3 v = -r10.xzy * r6.x - r2.zxy; r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 61
    { float3 v = r6.y * r3.zxy; r0.x = v.x; r0.y = v.y; r0.w = v.z; }    // 62
    r6.xyz = r6.x * r1.zxy + float3(r0.x, r0.y, r0.w);                   // 63
    r6.z = -r6.w * r4.y - r6.z;                                          // 64
    r6.xy = r6.w * r4.xz + r6.yx;                                        // 65
    r6 = XeCube(r6.xyz);                                                 // 66
    { float v = r6.w; r0.x = rcp(abs(r6.z)); r0.w = v; }                 // 67
    r0.xy = r6.yx * r0.x + C255.x;                                       // 68
    r6.xyz = TF14(float3(r0.x, r0.y, r0.w)).xyz;                         // 69
    r6.xyz = r6.xyz * r6.xyz;                                            // 70
    r5.xyz = r9.xyz * r6.xyz + r5.xyz;                                   // 71
  }
  r6.x = r0.z - C67.x;                                                   // 72
  r6.yzw = r5.xyz * C49.xyz;                                             // 73
  if (r6.x > 0.0) {                                                      // p0
    { float v = saturate(dot(-r2.zxy, C66.zxy)); r0.w = C67.w * r6.x; r0.x = v; }  // 74
    r0.xyz = TF4(r0.x).xyz;                                              // 75
    r1.xyz = TF5(r0.w).xyz;                                              // 76
    r2.xyz = C254.w - r1.xyz;                                            // 77
    { float3 v = r0.xyz - C68.xyz; r6.x = saturate(C67.z * r6.x); r0.xyz = v; }  // 78
    r0.xyz = r6.x * r0.zyx + C68.zyx;                                    // 79
    r2.xyz = r2.xyz * C28.y;                                             // 80
    r0.xyz = r2.xyz * r0.zyx - r6.yzw;                                   // 81
    r0.xyz = r6.yzw * r1.xyz + r0.xyz;                                   // 82
    r6.yzw = r0.xyz * (C28.x * FOG) + r6.yzw;                            // 83
  }
  r0.xyz = C20.w * C26.xyz;                                              // 84
  float4 o = float4(r0.xyz * r6.yzw, C26.w * r8.x);                      // 85
#if SPARROW
  if (SparrowDebug() == 3) o.xyz = SparrowVisDebug(sky_vis);  // red open, green closed
#endif
  AlphaTest(o.w);
  coverage = AlphaToMask(o.w, input.position.xy);
  return o * xe_color_exp_bias.x;
}
