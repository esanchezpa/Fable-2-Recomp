// Fable II translucent character parts, two lights + shadow map, pixel shader
// F96A4494958BFA12: drawn with the skinned character vertex shaders (xe_flags
// bit 31), alongside 648B965C200A5113 (lit_shadow.ps.hlsl); beetle wings and
// other blended parts of creatures and people. Replaces the SDK's translation
// through the shader_replace_dir cvar (see shaders/README.md).
//
// A literal port of the game's Xenos microcode (comments give the ucode
// instruction numbers). It is lit_shadow.ps.hlsl's material with two
// differences, as char_alpha.ps.hlsl is to lit.ps.hlsl:
//   - tf1's alpha (r12.w) sets the specular power per pixel, between c24.x
//     and c24.y;
//   - the output keeps the albedo's alpha (c26.w * tf0.w), so the draw blends.
// Layout as lit_shadow.ps.hlsl: tf0 albedo through c8, tf1 specular + gloss
// through c9, tf2 normal offset through c10, tangent frame v3 / v4 / v1, world
// position v2, view c19 - v2, screen-space shadow tf8, the b135 shadow-map
// projection (c32..c35, c48) with 2x2 PCF on tf9 biased by c114, two lights
// c80 / c81 (c87 / c88, falloffs c96, cones c98 / c99 / c105 / c107, gains
// c94), lightmap tf13 (b133), environment cube tf14 (b134), and the fog.
//
// Sparrow: the sun shadow map, sky openness and bounce on the ambient, and
// the shared character lobe for both lights plus the sheen, as
// lit_shadow.ps.hlsl's character branch.
// Xenos reading notes are in xe_common.hlsli.

#ifndef FOG
#define FOG 0.6  // distance fog strength, as lit_shadow.ps.hlsl
#endif

#define XE_FLOAT_CONSTANTS 36
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
#define C32 K[13]
#define C33 K[14]
#define C34 K[15]
#define C35 K[16]
#define C48 K[17]
#define C49 K[18]
#define C66 K[19]
#define C67 K[20]
#define C68 K[21]
#define C80 K[22]
#define C81 K[23]
#define C87 K[24]
#define C88 K[25]
#define C94 K[26]
#define C96 K[27]
#define C98 K[28]
#define C99 K[29]
#define C105 K[30]
#define C107 K[31]
#define C112 K[32]
#define C114 K[33]
#define C254 K[34]
#define C255 K[35]

// Texture bindings of this shader, in the translator's order.
#define TF2(uv) Fetch(2, 0, uv, false)
#define TF0(uv) Fetch(0, 1, uv, false)
#define TF1(uv) Fetch(1, 2, uv, false)
#define TF8(uv) Fetch(8, 3, uv, false)
#define TF9(uv, o) FetchOffset(9, 4, uv, o)
#define TF13(uv) Fetch(13, 5, uv, false)
#define TF14(stf) FetchCube(14, 6, stf)
#define TF4(x) Fetch(4, 7, float2(x, 0.0), true)
#define TF5(x) Fetch(5, 8, float2(x, 0.0), true)

float4 main(PSInput7 input, out uint coverage : SV_Coverage) : SV_Target0 {
  float4 r0 = input.v0, r1 = input.v1, r2 = input.v2, r3 = input.v3;
  float4 r4 = input.v4, r5 = input.v5, r6 = input.v6;
  float4 r7 = 0.0, r8 = 0.0, r9 = 0.0, r10 = 0.0, r11 = 0.0, r12 = 0.0, r13 = 0.0, r14 = 0.0;
  float ps = 0.0;
  r7.xy = GuestPixelPosition(input.position, input.front_face);

  r0.zw = r0.yx * C9.yx + C9.wz;                                         // 14
  r8.xy = r0.yx * C8.yx + C8.wz;                                         // 15
  r8.zw = r0.yx * C10.yx + C10.wz;                                       // 16
  r10.zw = TF2(r8.wz).xy;                                                // 17
  { float4 t = TF0(r8.yx); r8 = t.wxyz; }                                // 18
  float3 sp_albedo = r8.yzw * r8.yzw;  // Sparrow: colour map, linear (character material)
  r12 = TF1(r0.wz);                                                      // 19
  r2.w = dot(r1.xyz, r1.xyz);                                            // 20
  { float3 v = C19.zyx - r2.zyx; r0.z = C24.y - C24.x; r9.xyz = v; }     // 21
  r0.w = r0.z * r12.w + C24.x;                                           // 22
  { float3 v = r8.yzw * r8.yzw; r10.x = r12.x * r12.x; r11.xyz = v; }    // 23
  { float v = dot(r9.xyz, r9.xyz); r10.y = r12.y * r12.y; r0.z = v; }    // 24
  { float2 v = r10.wz * C255.x + C254.z; r10.z = v.x; r10.w = v.y; }     // 25
  r1.w = r10.w * r10.w + r10.z * r10.z + C254.x;                         // 26
  { float3 v = r10.z * r4.zxy; r10.z = r12.z * r12.z; r8.yzw = v; }      // 27
  r8.yzw = r10.w * r3.zxy + r8.yzw;                                      // 28
  { float v = C254.y - r1.w; r2.w = rsqrt(abs(r2.w)); r1.w = v; }        // 29
  { float3 v = r2.w * r1.zyx; r1.w = sqrt(abs(r1.w)); r12.xyz = v; }     // 30
  r8.yzw = r12.xyz * r1.w + r8.ywz;                                      // 31
  { float v = dot(r8.ywz, r8.ywz); r2.w = rsqrt(abs(r0.z)); r1.w = v; }  // 32
  { float3 v = r9.zyx * r2.w; r1.w = rsqrt(abs(r1.w)); r9.xyz = v; }     // 33
  { float3 v = r8.yzw * r1.w; r0.z = sqrt(abs(r0.z)); r8.yzw = v; }      // 34
  if (XeBool(128)) {
    r1.w = r8.x * r8.x;                                                  // 35
    r1.w = rcp(r1.w);                                                    // 36
    r11.xyz = r11.xyz * r1.w;                                            // 37
  }
  r7.xy = abs(r7.xy) * C0.zw + C0.xy;                                    // 38
  r6.w = TF8(r7.xy).x;                                                   // 39
#if SPARROW
  // Sparrow: the sun shadow map (sparrow_common.hlsli).
  r6.w = SparrowSunOr(r6.w, input.v2.xyz, normalize(input.v1.xyz));
#endif
  r12.x = log2(abs(r6.x));                                               // 40
  { float3 v = C254.y - C22.xyz; r6.w = C254.y - r6.w; r13.xyz = v; }    // 41
  { float3 v = r11.xyz * C27.w; r12.y = log2(abs(r6.y)); r7.xyz = v; }   // 42
  { float v = dot(r5.xyz, r5.xyz); r12.z = log2(abs(r6.z)); r6.x = v; }  // 43
  { float3 v = r12.xyz * C21.w; r6.x = rsqrt(abs(r6.x)); r12.xyz = v; }  // 44
  { float2 v = r6.w * C112.xy; r12.x = exp2(r12.x); r6.yz = v; }         // 45
  { float3 v = r6.x * r5.zyx; r12.y = exp2(r12.y); r5.xyz = v; }         // 46
  { float v = saturate(dot(r5.xzy, r8.ywz)); r12.z = exp2(r12.z); r6.x = v; }  // 47
  { float3 v = r12.xyz * C21.xyz; r6.x = r6.x * r6.x; r12.xyz = v; }     // 48
  r5.xyz = r6.x * r13.xyz + C22.xyz;                                     // 49
  r5.xyz = r12.xyz * r5.xyz + C20.xyz;                                   // 50
  float sky_vis = -1.0;
#if SPARROW
  // Sparrow: sky openness and the sun's bounce on the ambient (r8 holds the
  // normal as wzy; c112 picks which of the two lights casts shadows).
  if (SparrowActive())
    r5.xyz = SparrowAmbient(r5.xyz, input.v2.xyz, r8.wzy, C87.xyz * C112.x + C88.xyz * C112.y,
                            sky_vis);
#endif
  float3 ambient = r5.xyz;
  r5.xyz = r7.xyz * r5.xyz;                                              // 51
  if (XeBool(135)) {
    r14 = float4(C254.x == 0.0 ? r2.z : C254.y, C254.x == 0.0 ? r2.x : C254.y,
                 C254.x == 0.0 ? r2.y : C254.y, C254.y == 0.0 ? r2.y : C254.y);  // 52
    { float v = dot(C32.zxyw, r14); r7.x = rcp(C48.x); r7.z = v; }       // 53
    { float v = dot(C35.zxyw, r14); r7.y = rcp(C48.y); r6.x = v; }       // 54
    { float v = dot(C33.zxyw, r14); r6.x = rcp(r6.x); r7.w = v; }        // 55
    r13 = r7 * r6.x;                                                     // 56
    r12.x = TF9(r13.zw, int2(0, 0)).x;                                   // 57
    r12.y = TF9(r13.zw, int2(0, 1)).x;                                   // 58
    r12.z = TF9(r13.zw, int2(1, 0)).x;                                   // 59
    r12.w = TF9(r13.zw, int2(1, 1)).x;                                   // 60
    r6.w = dot(C34.zxyw, r14);                                           // 61
    r7.xy = r13.xy * r7.zw;                                              // 62
    { float2 v = frac(r7.yx); ps = r6.w; r7.yz = v; }                    // 63
    { float v = C254.y - r7.y; r7.w = r6.x * ps; r7.x = v; }             // 64
    { float2 v = C254.y - r7.wz; r6.x = v.x; r6.w = v.y; }               // 65
    r12 = float4(r6.x >= r12.x ? 1.0 : 0.0, r6.x >= r12.y ? 1.0 : 0.0,
                 r6.x >= r12.z ? 1.0 : 0.0, r6.x >= r12.w ? 1.0 : 0.0);  // 66
    r12.xy = r6.w * r12.xy;                                              // 67
    r12.zw = r12.zw * r7.z;                                              // 68
    r6.x = dot(r12.wyxz, r7.yyxx);                                       // 69
    r6.x = C254.y - r6.x;                                                // 70
    { float2 v = r6.x * C114.xy; r6.x = v.x; r6.w = v.y; }               // 71
    r6.yz = max(r6.yz, r6.xw);                                           // 72
  }
  r7.xyz = -r2.xyz * C81.w + C81.xyz;                                    // 73
  r12.xyz = -r2.xyz * C80.w + C80.xyz;                                   // 74
  r1.w = dot(r12.xyz, r12.xyz);                                          // 75
  { float v = dot(r7.xyz, r7.xyz); r6.x = sqrt(abs(r1.w)); r6.w = v; }   // 76
  { float2 v = C254.y - r6.yz; r6.y = rsqrt(abs(r6.w)); r2.xy = v; }     // 77
  { float3 v = r7.xyz * r6.y; r6.y = rsqrt(abs(r1.w)); r7.yzw = v; }     // 78
  { float3 v = r12.xyz * r6.y; r6.w = sqrt(abs(r6.w)); r12.xyz = v; }    // 79
  float3 l0 = r12.xyz, l1 = r7.yzw;  // Sparrow: toward the lights (world)
  { float2 v = saturate(-r6.wx * C96.yx + C254.y); r6.z = v.x; r6.w = v.y; }  // 80
  r13.x = dot(r8.ywz, r12.zxy);                                          // 81
  r6.y = dot(r12.zxy, C98.zxy);                                          // 82
  r6.x = dot(r7.wyz, C99.zxy);                                           // 83
  { float v = dot(r8.ywz, r7.wyz); r2.z = r6.y - C105.x; r13.y = v; }    // 84
  { float2 v = r13.yx + r13.yx; r2.w = r6.x - C105.y; r13.x = v.x; r13.w = v.y; }  // 85
  r13.xyz = -r8.yzw * r13.x + r7.wzy;                                    // 86
  r2.zw = saturate(r2.zw * C107.xy);                                     // 87
  r14.xyz = -r8.yzw * r13.w + r12.zyx;                                   // 88
  r6.x = saturate(dot(-r9.zxy, r14.xzy));                                // 89
  { float2 v = r2.wz * r6.zw + C254.z; r6.y = v.x; r6.z = v.y; }         // 90
  { float2 v = r6.yz * C94.yx + C254.y; r6.y = v.x; r6.z = v.y; }        // 91
  { float v = saturate(dot(-r9.zxy, r13.xzy)); r6.x = log2(r6.x); r6.w = v; }  // 92
  { float v = saturate(dot(r8.ywz, r12.zxy)); r6.w = log2(r6.w); r7.x = v; }  // 93
  { float2 v = r0.w * r6.xw; r6.x = v.x; r6.w = v.y; }                   // 94
  { float v = saturate(dot(r8.ywz, r7.wyz)); r6.x = exp2(r6.x); r7.y = v; }  // 95
  { float2 v = saturate(r7.xy * C23.w); r6.w = exp2(r6.w); r2.zw = v; }  // 96
  { float2 v = r2.zw * r6.xw; r6.x = v.x; r6.w = v.y; }                  // 97
  r2 = r6.zxwy * r2.xxyy;                                                // 98
  // Sparrow: each light's diffuse factor (shadow, range, cone, gain) without N.L.
  float light0 = r2.x, light1 = r2.w;
  { float2 v = r2.wx * r7.yx; r2.x = v.x; r2.w = v.y; }                  // 99
  { float2 v = r2.zy * r6.yz; r6.x = v.x; r6.w = v.y; }                  // 100
  r6.xyz = r6.x * C88.xyz;                                               // 101
  r2.xyz = r2.x * C88.xyz;                                               // 102
  r2.xyz = r2.w * C87.xyz + r2.xyz;                                      // 103
  r6.xyz = r6.w * C87.xyz + r6.xyz;                                      // 104
  r6.xyz = r10.xyz * r6.xyz + r5.xyz;                                    // 105
  r2.xyz = r2.xyz * r11.xyz + r6.xyz;                                    // 106
#if SPARROW
  if (SparrowActive() && (xe_flags & 0x80000000u)) {
    // The shared character lobe for both lights and the fabric sheen.
    float3 n = r8.wzy, v = r9.xyz;
    SparrowCharMat cm = SparrowCharMaterial(sp_albedo);
    float3 sparrow_add = SparrowCharacterSpecular(n, v, l0, C87.xyz * light0, cm) +
                         SparrowCharacterSpecular(n, v, l1, C88.xyz * light1, cm) +
                         SparrowCharacterSheen(ambient * C27.w, n, v, cm);
    r2.xyz = SparrowDebug() == 2 ? sparrow_add : r2.xyz + sparrow_add;
  }
#endif
  if (XeBool(133)) {
    r6.xyz = TF13(r0.xy).xyz;                                            // 107
    r6.xyz = r6.xyz * r6.xyz;                                            // 108
    r2.xyz = r6.xyz * C24.z + r2.xyz;                                    // 109
  }
  if (XeBool(134)) {
    r6.x = dot(-r9.zxy, r8.ywz);                                         // 110
    r6.x = r6.x + r6.x;                                                  // 111
    { float3 v = -r8.ywz * r6.x - r9.zxy; r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 112
    { float3 v = r6.y * r3.zxy; r0.x = v.x; r0.y = v.y; r0.w = v.z; }    // 113
    r6.xyz = r6.x * r1.zxy + float3(r0.x, r0.y, r0.w);                   // 114
    r6.z = -r6.w * r4.y - r6.z;                                          // 115
    r6.xy = r6.w * r4.xz + r6.yx;                                        // 116
    r6 = XeCube(r6.xyz);                                                 // 117
    { float v = r6.w; r0.x = rcp(abs(r6.z)); r0.w = v; }                 // 118
    r0.xy = r6.yx * r0.x + C254.w;                                       // 119
    r6.xyz = TF14(float3(r0.x, r0.y, r0.w)).xyz;                         // 120
    r6.xyz = r6.xyz * r6.xyz;                                            // 121
    r2.xyz = r10.xyz * r6.xyz + r2.xyz;                                  // 122
  }
  r6.x = r0.z - C67.x;                                                   // 123
  r6.yzw = r2.xyz * C49.xyz;                                             // 124
  if (r6.x > 0.0) {                                                      // p0
    { float v = saturate(dot(-r9.zxy, C66.zxy)); r0.w = C67.w * r6.x; r0.x = v; }  // 125
    r0.xyz = TF4(r0.x).xyz;                                              // 126
    r1.xyz = TF5(r0.w).xyz;                                              // 127
    r2.xyz = C254.y - r1.xyz;                                            // 128
    { float3 v = r0.xyz - C68.xyz; r6.x = saturate(C67.z * r6.x); r0.xyz = v; }  // 129
    r0.xyz = r6.x * r0.zyx + C68.zyx;                                    // 130
    r2.xyz = r2.xyz * C28.y;                                             // 131
    r0.xyz = r2.xyz * r0.zyx - r6.yzw;                                   // 132
    r0.xyz = r6.yzw * r1.xyz + r0.xyz;                                   // 133
    r6.yzw = r0.xyz * (C28.x * FOG) + r6.yzw;                            // 134
  }
  r0.xyz = C20.w * C26.xyz;                                              // 135
  float4 o = float4(r0.xyz * r6.yzw, C26.w * r8.x);                      // 136
#if SPARROW
  if (SparrowDebug() == 3) o.xyz = SparrowVisDebug(sky_vis);  // red open, green closed
#endif
  AlphaTest(o.w);
  coverage = AlphaToMask(o.w, input.position.xy);
  return o * xe_color_exp_bias.x;
}
