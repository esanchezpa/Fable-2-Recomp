// Fable II characters, pixel shader 401A01FD4E5F8757: the hero's hair,
// trousers and boots, villagers' robes and other skinned meshes (vertex
// shaders D4D558DA / A1F7E988 / 79EAC495). Built only for Project Sparrow
// (tools/shaders/build_replace.py --sparrow).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers). What the original does:
//   - tf0 albedo (alpha in .x) through c8, tf1 a specular colour map through
//     c9, tf2 a two-channel normal offset through c10; tangent frame v3 / v4 /
//     v1, world position v2 (w forced to c255.x), camera c19;
//   - a character shadow map tf6 read 24 times on a 5x5 footprint around the
//     point projected through c36..c39, compared against the depth, and
//     filtered with smooth (B-spline-like) weights from the texel fraction;
//     blended by distance (c12.x..c12.z) with a 2x2 bilinear PCF of a second
//     shadow map tf7 (projection c40..c43, getWeights), then c12.w, c13;
//   - under b135 the projected shadow map tf9 (c32..c35, c48), as
//     lit_shadow.ps.hlsl, biased by c114;
//   - tf3-less ambient: v6 raised to c21.w and tinted by c21.xyz, a sky term
//     from c22 / c20 by N.L of v5, scaled by c27.w;
//   - one light c80 (position, w = 1 point / 0 directional), falloff c96,
//     cone c98 / c105 / c107 / c94, colour c87, the sun slot c112 dimmed by
//     the shadow, wrap c23.w;
//   - lightmap tf13 (b133, c24.z), reflection cube tf14 (b134), distance fog
//     beyond c67.x (tf4 / tf5 ramps, c66 / c68 / c28, scaled by the alpha).
// Xenos reading notes are in xe_common.hlsli.

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#ifndef DEBUG_VIEW
#define DEBUG_VIEW 0  // 7: the specular map (x4), for tuning highlights
#endif
#define XE_FLOAT_CONSTANTS 44
#define XE_DESCRIPTOR_INDICES 8
#include "xe_common.hlsli"
#if SPARROW
#include "sparrow_common.hlsli"
#endif

#define C8 K[0]
#define C9 K[1]
#define C10 K[2]
#define C12 K[3]
#define C13 K[4]
#define C19 K[5]
#define C20 K[6]
#define C21 K[7]
#define C22 K[8]
#define C23 K[9]
#define C24 K[10]
#define C26 K[11]
#define C27 K[12]
#define C28 K[13]
#define C32 K[14]
#define C33 K[15]
#define C34 K[16]
#define C35 K[17]
#define C36 K[18]
#define C37 K[19]
#define C38 K[20]
#define C39 K[21]
#define C40 K[22]
#define C41 K[23]
#define C42 K[24]
#define C43 K[25]
#define C48 K[26]
#define C49 K[27]
#define C66 K[28]
#define C67 K[29]
#define C68 K[30]
#define C80 K[31]
#define C87 K[32]
#define C94 K[33]
#define C96 K[34]
#define C98 K[35]
#define C105 K[36]
#define C107 K[37]
#define C112 K[38]
#define C114 K[39]
#define C252 K[40]
#define C253 K[41]
#define C254 K[42]
#define C255 K[43]

// Texture bindings of this shader, in the translator's order (first use).
#define TF2(uv) Fetch(2, 0, uv, false)
#define TF6(uv, ox, oy) FetchOffset(6, 1, uv, int2(ox, oy))
#define TF0(uv) Fetch(0, 2, uv, false)
#define TF1(uv) Fetch(1, 3, uv, false)
#define TF7(uv, ox, oy) FetchOffset(7, 4, uv, int2(ox, oy))
#define TF9(uv, ox, oy) FetchOffset(9, 5, uv, int2(ox, oy))
#define TF13(uv) Fetch(13, 6, uv, false)
#define TF14(stf) FetchCube(14, 7, stf)
#define TF5(x) Fetch(5, 8, float2(x, 0.0), true)
#define TF4(x) Fetch(4, 9, float2(x, 0.0), true)

float Gt(float a, float b) { return a > b ? 1.0 : 0.0; }
float4 Gt4(float a, float4 b) { return float4(a > b.x, a > b.y, a > b.z, a > b.w); }
float4 Ge4(float a, float4 b) { return float4(a >= b.x, a >= b.y, a >= b.z, a >= b.w); }

float4 main(PSInput7 input, out uint coverage : SV_Coverage) : SV_Target0 {
  float4 r0 = input.v0, r1 = input.v1, r2 = input.v2, r3 = input.v3;
  float4 r4 = input.v4, r5 = input.v5, r6 = input.v6;
  float4 r7 = 0.0, r8 = 0.0, r9 = 0.0, r10 = 0.0, r11 = 0.0, r12 = 0.0, r13 = 0.0;
  float4 r14 = 0.0, r15 = 0.0, r16 = 0.0, r17 = 0.0, r18 = 0.0, r19 = 0.0, r20 = 0.0;
  float4 r21 = 0.0, r22 = 0.0, r23 = 0.0, r24 = 0.0, r25 = 0.0, r26 = 0.0, r27 = 0.0;
  float ps = 0.0;

  r0.zw = r0.yx * C9.yx + C9.wz;                                         // 21
  r7.xy = r0.yx * C8.yx + C8.wz;                                         // 22
  r9.xy = r0.yx * C10.yx + C10.wz;                                       // 23
  { float v = dot(r5.xyz, r5.xyz); r2.w = C255.x; r3.w = v; }            // 24
  r15.x = dot(C36.zxyw, r2.zxyw);                                        // 25
  r15.z = dot(C37.zxyw, r2.zxyw);                                        // 26
  r1.w = dot(C39.zxyw, r2.zxyw);                                         // 27
  r8.x = dot(C40.zxyw, r2.zxyw);                                         // 28
  r8.y = dot(C41.zxyw, r2.zxyw);                                         // 29
  r4.w = dot(C43.zxyw, r2.zxyw);                                         // 30
  { float v = dot(C42.zxyw, r2.zxyw); r4.w = rcp(r4.w); r8.z = v; }      // 31
  { float3 v = r8.xzy * r4.w; r15.w = rcp(r1.w); r8.xyz = v; }           // 32
  r7.zw = r15.xz * r15.w;                                                // 33
  { float2 t = TF2(r9.yx).xy; r26.y = t.x; r26.z = t.y; }                // 34
  // The character shadow map on a 5x5 footprint (24 taps, the centre is 57).
  r21.x = TF6(r7.zw, 1, 2).x;                                            // 35
  r21.y = TF6(r7.zw, -1, 2).x;                                           // 36
  r21.z = TF6(r7.zw, 0, 2).x;                                            // 37
  r21.w = TF6(r7.zw, 2, 2).x;                                            // 38
  r1.w = TF6(r7.zw, -2, 2).x;                                            // 39
  r18.x = TF6(r7.zw, -2, 1).x;                                           // 40
  r18.y = TF6(r7.zw, -2, 0).x;                                           // 41
  r18.z = TF6(r7.zw, -2, -1).x;                                          // 42
  r18.w = TF6(r7.zw, -2, -2).x;                                          // 43
  r19.x = TF6(r7.zw, 0, 1).x;                                            // 44
  r19.y = TF6(r7.zw, 0, -1).x;                                           // 45
  r19.z = TF6(r7.zw, 1, 1).x;                                            // 46
  r19.w = TF6(r7.zw, 1, 0).x;                                            // 47
  r17.x = TF6(r7.zw, 1, -1).x;                                           // 48
  r17.y = TF6(r7.zw, -1, -1).x;                                          // 49
  r17.z = TF6(r7.zw, -1, 0).x;                                           // 50
  r17.w = TF6(r7.zw, -1, 1).x;                                           // 51
  r13.x = TF6(r7.zw, 1, -2).x;                                           // 52
  r13.y = TF6(r7.zw, 0, -2).x;                                           // 53
  r13.z = TF6(r7.zw, -1, -2).x;                                          // 54
  r13.w = TF6(r7.zw, 2, -2).x;                                           // 55
  r20.x = TF6(r7.zw, 2, 1).x;                                            // 56
  r20.y = TF6(r7.zw, 0, 0).x;                                            // 57
  r20.z = TF6(r7.zw, 2, -1).x;                                           // 58
  r20.w = TF6(r7.zw, 2, 0).x;                                            // 59
  { float4 t = TF0(r7.yx); r7 = t.wxyz; }                                // 60
  r12.xyz = TF1(r0.wz).xyz;                                              // 61
  r11.xy = frac(r8.xz * TextureSize(7) - 0.5);                           // 62 (getWeights2D)
  r16.x = TF7(r8.xz, 0, -1).x;                                           // 63
  r16.y = TF7(r8.xz, 0, 0).x;                                            // 64
  r16.z = TF7(r8.xz, -1, -1).x;                                          // 65
  r16.w = TF7(r8.xz, -1, 0).x;                                           // 66
  { float v = dot(r1.xyz, r1.xyz); r10.x = log2(abs(r6.x)); r4.w = v; }  // 67
  { float3 v = r2.xyz - C19.xyz; r10.y = log2(abs(r6.y)); r14.xyz = v; } // 68
  { float3 v = C19.zyx - r2.zyx; r10.z = rcp(C13.x); r9.xyz = v; }       // 69
  { float v = dot(r9.xyz, r9.xyz); r10.w = rcp(C13.y); r0.z = v; }       // 70
  { float v = dot(r14.xyz, r14.xyz); r0.w = rcp(C12.z); r6.w = v; }      // 71
  { float v = dot(C38.zxyw, r2.zxyw); r6.w = sqrt(abs(r6.w)); r14.z = v; }  // 72
  { float2 v = r10.zw * r15.w; r2.w = C255.x - r8.y; r14.xy = v; }       // 73
  { float4 v = Ge4(r2.w, r16); r10.z = log2(abs(r6.z)); r8 = v; }        // 74
  { float2 v = r8.xy - r8.zw; r6.z = rsqrt(abs(r4.w)); r6.xy = v; }      // 75
  r16.xy = r6.xy * r11.x + r8.zw;                                        // 76
  { float v = r16.y - r16.x; r3.w = rsqrt(abs(r3.w)); r6.x = v; }        // 77
  { float v = r6.x * r11.y; r2.w = rsqrt(abs(r0.z)); r15.y = v; }        // 78
  { float3 v = C255.x - C22.xyz; ps = r14.x; r11.xyz = v; }              // 79
  { float3 v = r12.xyz * r12.xyz; r6.x = ps * r15.x; ps = r6.x; r8.xyz = v; }  // 80
  { float3 v = r7.yzw * r7.yzw; ps = r14.y; r7.yzw = v; }                // 81
  { float3 v = r10.xyz * C21.w; r6.y = ps * r15.z; ps = r6.y; r10.xyz = v; }  // 82
  { float3 v = r3.w * r5.zyx; ps = r14.z; r12.xyz = v; }                 // 83
  { float3 v = r6.z * r1.zyx; r6.z = ps * r15.w; ps = r6.z; r14.xyz = v; }  // 84
  { float3 v = r9.zyx * r2.w; r6.z = C255.x - r6.z; ps = r6.z; r9.xyz = v; }  // 85
  r20 = Gt4(r6.z, r20);                                                  // 86
  { float4 v = Gt4(r6.z, r13); r3.w = C252.z + r6.y; ps = r3.w; r13 = v; }  // 87
  { float4 v = Gt4(r6.z, r17); r2.w = C252.z + r6.x; ps = r2.w; r17 = v; }  // 88
  { float4 v = Gt4(r6.z, r19); r15.x = floor(-r3.w); ps = r15.x; r22 = v; } // 89
  { float4 v = Gt4(r6.z, r18); r15.z = floor(-r2.w); ps = r15.z; r23 = v; } // 90
  r5.xyz = C255.xyz - r15.x;                                             // 91
  { float3 v = r5.xyz - r6.y; ps = -r6.y; r5.yzw = v; }                  // 92
  { float4 v = r5.wyzw * C254.xyyy; r5.x = -r15.x + ps; ps = r5.x; r24 = v; }  // 93
  { float4 v = r5.xxyz * C253.zxxx; ps = -r6.x; r19 = v; }               // 94
  { float4 v = r5.wxyz * C253.xyyy; r5.z = -r15.z + ps; ps = r5.z; r18 = v; }  // 95
  { float v = r18.x * r24.x; r18.x = C253.x * r5.z; ps = r18.x; r6.y = v; }  // 96
  { float3 v = r19.yzw * r18.yzw; ps = r6.y; r5.x = v.x; r5.y = v.y; r5.w = v.z; }  // 97
  { float3 v = r5.ywx * r18.zwy; r25.z = ps * r24.x; ps = r25.z; r25.x = v.x; r25.y = v.y; r25.w = v.z; }  // 98
  { float4 v = C255.w - r25.wxyz; r18.y = C253.y * r5.z; ps = r18.y; r25 = v; }  // 99
  { float v = Gt(r6.z, r1.w); ps = r25.x; r18.w = v; }                   // 100
  { float3 v = saturate(r25.zwy + r24.zwy); r19.w = saturate(r19.x + ps); ps = r19.w;
    r5.x = v.x; r5.y = v.y; r5.w = v.z; }                                // 101
  { float v = saturate(r5.w - r19.w); r18.z = saturate(C255.x - r5.y); ps = r18.z; r19.z = v; }  // 102
  { float4 v = Gt4(r6.z, r21); r19.x = saturate(r5.y - r5.x); ps = r19.x; r21 = v; }  // 103
  { float2 v = r18.xz * r18.yw; r19.y = saturate(r5.x - r5.w); ps = r19.y; r6.yz = v; }  // 104
  { float v = r6.y * r18.y; ps = r18.z; r15.w = v; }                     // 105
  { float4 v = C255 - r15.zzzw; r25.x = ps * r21.x; ps = r25.x; r27 = v; }  // 106
  { float3 v = r27.xyz - r6.x; ps = r18.z; r5.x = v.x; r5.y = v.y; r5.w = v.z; }  // 107
  { float4 v = r5.xywz * C254.xxxy; r25.y = ps * r21.y; ps = r25.y; r24 = v; }  // 108
  { float3 v = r5.xyw * C253.x; ps = r27.w; r15.x = v.x; r15.z = v.y; r15.w = v.z; }  // 109
  { float3 v = r15.xzw * r24.xyz; r5.z = saturate(r24.w + ps); ps = r5.z;
    r15.x = v.x; r15.z = v.y; r15.w = v.z; }                             // 110
  { float3 v = -r15.xzw * r24.xyz + C255.w; r15.x = v.x; r15.z = v.y; r15.w = v.z; }  // 111
  { float4 v = r5.z * r19.yxzw; ps = r18.z; r24 = v; }                   // 112
  { float v = dot(r24.yxwz, r23.xywz); r25.z = ps * r21.z; ps = r25.z; r26.w = v; }  // 113
  { float3 v = saturate(r5.xwy * C254.y + r15.xwz); r5.x = v.x; r5.y = v.y; r5.w = v.z; }  // 114
  { float3 v = saturate(r5.ywx - r5.wxz); ps = r18.z; r24.yzw = v; }     // 115
  { float4 v = r24.wyww * r19.zzyx; r25.w = ps * r21.w; ps = r25.w; r18 = v; }  // 116
  { float4 v = r24.zyyz * r19.xxyz; r24.x = saturate(C255.x - r5.y); ps = r24.x; r23 = v; }  // 117
  r1.w = dot(r25.wxz, r24.xyz);                                          // 118
  r6.x = dot(r23.yzx, r22.zwx);                                          // 119
  r21 = r24.xxxz * r19.xzyy;                                             // 120
  r26.x = dot(r18.wzx, r17.wzy);                                         // 121
  r19 = r24.ywzx * r19.w;                                                // 122
  r2.w = dot(r19.xzy, r13.xyz);                                          // 123
  r13.xyz = r26.xyz + r26.wyz;                                           // 124
  { float2 v = r13.zy + C252.x; r6.y = -C12.x + r6.w; ps = r6.y; r15.x = v.x; r15.w = v.y; }  // 125
  r3.w = r6.z * r5.z + r13.x;                                            // 126
  { float v = dot(r21.xzy, r20.xwz); ps = r3.w; r6.z = v; }              // 127
  { float3 v = r15.x * r4.zxy; r2.w = r2.w + ps; ps = r2.w; r5.xyz = v; }  // 128
  r13.xyz = r15.w * r3.zxy + r5.xyz;                                     // 129
  r2.w = r25.y * r24.w + r2.w;                                           // 130
  r2.w = r23.w * r22.y + r2.w;                                           // 131
  r2.w = r21.w * r20.y + r2.w;                                           // 132
  { float v = r2.w + r6.x; r6.x = -C12.y + r6.w; ps = r6.x; r2.w = v; }  // 133
  { float v = r2.w + r1.w; ps = r19.w; r6.w = v; }                       // 134
  r6.w = r18.y * r17.x + r6.w;                                           // 135
  { float v = r6.w + r6.z; r15.z = ps * r13.w; ps = r15.z; r16.z = v; }  // 136
  { float2 v = r16.xz + r15.yz; ps = r6.y; r6.zw = v; }                  // 137
  { float v = r6.z - r6.w; r0.w = saturate(ps * r0.w); ps = r0.w; r6.y = v; }  // 138
  r5.y = r0.w * r6.y + r6.w;                                             // 139
  { float v = C12.w - r5.y; r15.y = saturate(C253.w * r6.x); ps = r15.y; r15.z = v; }  // 140
  { float3 v = r15.wxy * r15.wxz; r6.x = exp2(r10.x); ps = r6.x; r5.x = v.x; r5.z = v.y; r5.w = v.z; }  // 141
  { float2 v = r5.xy + r5.zw; r6.y = exp2(r10.y); ps = r6.y; r6.zw = v; }  // 142
  { float2 v = C255.x - r6.zw; r6.z = exp2(r10.z); ps = r6.z; r10.xy = v; }  // 143
  { float3 v = r6.xyz * C21.xyz; r6.x = sqrt(abs(r10.x)); ps = r6.x; r5.xyz = v; }  // 144
  { float3 v = r14.xyz * r6.x + r13.xzy; r6.yzw = v; }                   // 145
  r6.x = dot(r6.ywz, r6.ywz);                                            // 146
  { float v = r10.y * C112.x; r6.x = rsqrt(abs(r6.x)); ps = r6.x; r0.w = v; }  // 147
  r10.xyz = r6.yzw * r6.x;                                               // 148
  r6.x = saturate(dot(r12.xzy, r10.xzy));                                // 149
  r6.x = r6.x * r6.x; ps = r6.x;                                         // 150
  r6.xyz = r6.x * r11.xyz + C22.xyz;                                     // 151
  r6.xyz = r5.xyz * r6.xyz + C20.xyz;                                    // 152
  float sky_vis = -1.0;
#if SPARROW
  // Sparrow: sky openness and the sun's bounce on the ambient, as lit.ps.hlsl
  // (r10.zyx is the world normal; the sun is the light c112 picks for shadows).
  if (SparrowActive())
    r6.xyz = SparrowAmbient(r6.xyz, input.v2.xyz, r10.zyx, C87.xyz, sky_vis);
#endif
  float3 char_ambient = r6.xyz;  // Sparrow: the ambient light, before the albedo
  r6.xyz = r7.yzw * r6.xyz;                                              // 153
  { float3 v = r6.xyz * C27.w; r0.z = sqrt(abs(r0.z)); ps = r0.z; r5.xyz = v; }  // 154
  if (XeBool(135)) {
    r13 = float4(C254.z == 0.0 ? r2.z : C255.x, C254.z == 0.0 ? r2.x : C255.x,
                 C254.z == 0.0 ? r2.y : C255.x, C254.w == 0.0 ? r2.y : C255.x);  // 155
    r6.x = dot(C35.zxyw, r13);                                           // 156
    { float v = dot(C33.zxyw, r13); r6.x = rcp(r6.x); r12.y = v; }       // 157
    { float v = dot(C32.zxyw, r13); r6.y = rcp(C48.x); r12.x = v; }      // 158
    r6.zw = r12.xy * r6.x;                                               // 159
    r11.x = TF9(r6.zw, 0, 0).x;                                          // 160
    r11.y = TF9(r6.zw, 0, 1).x;                                          // 161
    r11.z = TF9(r6.zw, 1, 0).x;                                          // 162
    r11.w = TF9(r6.zw, 1, 1).x;                                          // 163
    { float v = dot(C34.zxyw, r13); r6.z = rcp(C48.y); r6.w = v; }       // 164
    { float3 v = r6.yzw * r6.x; r6.x = v.x; r6.y = v.y; r6.w = v.z; }    // 165
    r6.yz = r6.xy * r12.xy;                                              // 166
    { float2 v = frac(r6.zy); r6.x = C255.x - r6.w; r6.yz = v; }         // 167
    { float4 v = Ge4(r6.x, r11); r6.x = C255.x - r6.y; r11 = v; }        // 168
    { float2 v = r11.zw * r6.z; r6.w = C255.x - r6.z; r11.zw = v; }      // 169
    r11.xy = r6.w * r11.xy;                                              // 170
    r6.y = dot(r11.wyxz, r6.yyxx);                                       // 171
    r6.y = C255.x - r6.y;                                                // 172
    r6.x = C114.x * r6.y;                                                // 173
    r0.w = max(r0.w, r6.x);                                              // 174
  }
  r12 = float4(C254.z == 0.0 ? r10.x : C255.x, C254.z == 0.0 ? r10.z : C255.x,
               C254.z == 0.0 ? r10.y : C255.x, C254.w == 0.0 ? r10.y : C255.x);  // 175
  { float3 v = -r2.xyz * C80.w + C80.xyz; r2.x = v.x; r2.y = v.y; r2.w = v.z; }  // 176
  r6.y = dot(r2.wxy, r2.wxy);                                            // 177
  r6.x = rsqrt(abs(r6.y));                                               // 178
  { float v = C255.x - r0.w; r6.y = sqrt(abs(r6.y)); r6.w = v; }         // 179
  r2.z = saturate(-r6.y * C96.x + C255.x);                               // 180
  r11.xyz = r2.xyw * r6.x;                                               // 181
  r11.w = dot(r10.xzy, r11.zxy);                                         // 182
  r6.y = dot(r11.zxy, C98.zxy);                                          // 183
  r6.z = saturate(dot(r10.xzy, r11.zxy));                                // 184
  r6.x = dot(r11.zxyw, r12);                                             // 185
  { float3 v = -r10.xyz * r6.x + r11.zyx; r2.x = v.x; r2.y = v.y; r2.w = v.z; }  // 186
  { float v = saturate(dot(-r9.zxy, r2.xwy)); r6.y = -C105.x + r6.y; r6.x = v; }  // 187
  { float v = r6.x * r6.x; r2.y = saturate(C107.x * r6.y); r2.x = v; }   // 188
  { float2 v = r2.xy * r2.xz; r0.w = saturate(C23.w * r6.z); r6.xy = v; }  // 189
  { float v = r0.w * r6.x; r6.y = -C255.x + r6.y; r6.x = v; }            // 190
  r6.y = r6.y * C94.x + C255.x;                                          // 191
  r2.xy = r6.xy * r6.w;                                                  // 192
  float char_light = r2.y;  // Sparrow: range * cone * shadow, without N.L
  r6.xy = r2.yx * r6.zy;                                                 // 193
  r2.xyz = r6.x * C87.xyz;                                               // 194
  r6.xyz = r6.y * C87.xyz;                                               // 195
  r6.xyz = r8.xyz * r6.xyz + r5.xyz;                                     // 196
  r2.xyz = r7.yzw * r2.xyz + r6.xyz;                                     // 197
#if SPARROW
  if (SparrowActive() && (xe_flags & 0x80000000u)) {
    // Characters: the soft universal lobe per light and the fabric sheen
    // (sparrow_common.hlsli; their specular maps are near zero).
    float3 n = r10.zyx, v = r9.xyz;
    float3 char_add = SparrowCharacterSpecular(n, v, r11.xyz, C87.xyz * char_light) +
              SparrowCharacterSheen(char_ambient * C27.w, n, v);
    r2.xyz = SparrowDebug() == 2 ? char_add : r2.xyz + char_add;  // 2: only what Sparrow adds
  }
#endif
  if (XeBool(133)) {
    r6.xyz = TF13(r0.xy).xyz;                                            // 198
    r6.xyz = r6.xyz * r6.xyz;                                            // 199
    r2.xyz = r6.xyz * C24.z + r2.xyz;                                    // 200
  }
  if (XeBool(134)) {
    r6.x = dot(-r9.zxy, r10.xzy);                                        // 201
    r6.x = r6.x + r6.x;                                                  // 202
    { float3 v = -r10.xzy * r6.x - r9.zxy; r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 203
    { float3 v = r6.y * r3.zxy; r0.x = v.x; r0.y = v.y; r0.w = v.z; }    // 204
    r6.xyz = r6.x * r1.zxy + float3(r0.x, r0.y, r0.w);                   // 205
    r6.z = -r6.w * r4.y - r6.z;                                          // 206
    r6.xy = r6.w * r4.xz + r6.yx;                                        // 207
    r6 = XeCube(r6.xyz);                                                 // 208
    { float v = r6.w; r0.x = rcp(abs(r6.z)); r0.w = v; }                 // 209
    r0.xy = r6.yx * r0.x + C252.y;                                       // 210
    r6.xyz = TF14(float3(r0.x, r0.y, r0.w)).xyz;                         // 211
    r6.xyz = r6.xyz * r6.xyz;                                            // 212
    r2.xyz = r8.xyz * r6.xyz + r2.xyz;                                   // 213
  }
  r6.x = r0.z - C67.x;                                                   // 214
  r6.yzw = r2.xyz * C49.xyz;                                             // 215
  if (r6.x > 0.0) {                                                      // p0
    { float v = saturate(dot(-r9.zxy, C66.zxy)); r0.y = C67.w * r6.x; r0.x = v; }  // 216
    r1.xyz = TF5(r0.y).xyz;                                              // 217
    r0.xyz = TF4(r0.x).xyz;                                              // 218
    r0.xyz = r0.xyz - C68.xyz;                                           // 219
    { float3 v = C255.x - r1.xyz; r0.w = C28.y * r7.x; r2.xyz = v; }     // 220
    { float3 v = r0.w * r2.zyx; r6.x = saturate(C67.z * r6.x); r2.xyz = v; }  // 221
    r0.xyz = r6.x * r0.zyx + C68.zyx;                                    // 222
    r0.xyz = r2.zyx * r0.zyx - r6.yzw;                                   // 223
    r0.xyz = r6.yzw * r1.xyz + r0.xyz;                                   // 224
    r6.yzw = r0.xyz * C28.x + r6.yzw;                                    // 225
  }
  r0.xyz = C20.w * C26.xyz;                                              // 226
  float4 o = float4(r0.xyz * r6.yzw, C26.w * r7.x);                      // 227
#if DEBUG_VIEW == 7
  o.xyz = r8.xyz * 4.0;
#endif
#if SPARROW
  if (SparrowDebug() == 3) o.xyz = SparrowVisDebug(sky_vis);  // red open, green closed
#endif
  AlphaTest(o.w);
  coverage = AlphaToMask(o.w, input.position.xy);
  return o * xe_color_exp_bias.x;
}
