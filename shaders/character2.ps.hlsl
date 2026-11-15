// Fable II characters with two lights, pixel shader 44B567635EB10620: the
// two-light build of 401A01FD (character.ps.hlsl), with a second light c81
// (colour c88, range c96.y, cone c99 / c105.y / c107.y / c94.y). Built only
// for Project Sparrow (tools/shaders/build_replace.py --sparrow).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers); see character.ps.hlsl for what it does. The
// compiler laid the registers out differently, so this is its own port.
// Xenos reading notes are in xe_common.hlsli.

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#define XE_FLOAT_CONSTANTS 47
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
#define C81 K[32]
#define C87 K[33]
#define C88 K[34]
#define C94 K[35]
#define C96 K[36]
#define C98 K[37]
#define C99 K[38]
#define C105 K[39]
#define C107 K[40]
#define C112 K[41]
#define C114 K[42]
#define C252 K[43]
#define C253 K[44]
#define C254 K[45]
#define C255 K[46]

// Texture bindings of this shader, in the translator's order (first use).
#define TF6(uv, ox, oy) FetchOffset(6, 0, uv, int2(ox, oy))
#define TF2(uv) Fetch(2, 1, uv, false)
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

  { float3 v = C254.x - C22.xyz; r2.w = C254.x; ps = r2.w; r12.xyz = v; }  // 22
  { float v = dot(C36.zxyw, r2.zxyw); r8.x = rcp(C13.x); ps = r8.x; r8.z = v; }  // 23
  { float v = dot(C39.zxyw, r2.zxyw); r8.y = rcp(C13.y); ps = r8.y; r6.w = v; }  // 24
  { float v = dot(C37.zxyw, r2.zxyw); r14.w = rcp(r6.w); ps = r14.w; r8.w = v; }  // 25
  r11 = r8.xzyw * r14.w;                                                 // 26
  r1.w = TF6(r11.yw, -2, 2).x;                                           // 27
  r9.zw = r0.yx * C9.yx + C9.wz;                                         // 28
  r7.xy = r0.yx * C8.yx + C8.wz;                                         // 29
  r7.zw = r0.yx * C10.yx + C10.wz;                                       // 30
  r25.x = dot(C40.zxyw, r2.zxyw);                                        // 31
  r25.y = dot(C41.zxyw, r2.zxyw);                                        // 32
  r25.z = dot(C42.zxyw, r2.zxyw);                                        // 33
  r4.w = dot(C43.zxyw, r2.zxyw);                                         // 34
  r14.z = dot(C38.zxyw, r2.zxyw);                                        // 35
  { float2 v = float2(r11.z * r8.w, r11.x * r8.z); r11.x = v.x; r11.z = v.y; }  // 36
  r0.zw = r11.xz + C255.x;                                               // 37
  r9.xy = floor(-r0.zw);                                                 // 38
  r8.xyz = C254.xyz - r9.x;                                              // 39
  r0.zw = -r11.zx - r9.yx;                                               // 40
  { float3 v = r8.xyz - r11.x; r10.x = v.x; r10.z = v.y; r10.w = v.z; }  // 41
  { float4 v = r0.wwzw * C253.xzzy; r14.x = C253.x * r0.z; ps = r14.x; r16 = v; }  // 42
  { float3 v = r10.xzw * C253.x; r6.w = r16.x * r16.w; ps = r6.w; r13.xyz = v; }  // 43
  { float v = r6.w * r16.w; r14.y = C253.y * r0.z; ps = r14.y; r8.w = v; }  // 44
  { float3 v = r10.xzw * C254.w; r0.z = r14.x * r14.y; ps = r0.z; r8.xyz = v; }  // 45
  { float3 v = r13.xyz * r8.xyz; r6.w = r14.z * r14.w; ps = r6.w; r13.xyz = v; }  // 46
  { float3 v = r13.xyz * r8.xyz; r3.w = C254.x - r6.w; ps = r3.w; r8.xyz = v; }  // 47
  { float4 v = C254.w - r8; r10.y = rcp(r4.w); ps = r10.y; r8 = v; }     // 48
  r8.xyz = saturate(r10.zwx * C253.z + r8.yzx);                          // 49
  { float v = Gt(r3.w, r1.w); r25.w = saturate(C254.x - r8.y); ps = r25.w; r10.x = v; }  // 50
  r10 = r25.zxyw * r10.yyyx;                                             // 51
  r27.xy = TF2(r7.wz).xy;                                                // 52
  // The character shadow map on a 5x5 footprint (24 taps, the centre is 74).
  r24.x = TF6(r11.yw, 1, 2).x;                                           // 53
  r24.y = TF6(r11.yw, -1, 2).x;                                          // 54
  r24.z = TF6(r11.yw, 0, 2).x;                                           // 55
  r24.w = TF6(r11.yw, 2, 2).x;                                           // 56
  r22.x = TF6(r11.yw, -2, 1).x;                                          // 57
  r22.y = TF6(r11.yw, -2, 0).x;                                          // 58
  r22.z = TF6(r11.yw, -2, -1).x;                                         // 59
  r22.w = TF6(r11.yw, -2, -2).x;                                         // 60
  r23.x = TF6(r11.yw, 0, 1).x;                                           // 61
  r23.y = TF6(r11.yw, 0, -1).x;                                          // 62
  r23.z = TF6(r11.yw, 1, 1).x;                                           // 63
  r23.w = TF6(r11.yw, 1, 0).x;                                           // 64
  r19.x = TF6(r11.yw, 1, -1).x;                                          // 65
  r19.y = TF6(r11.yw, -1, -1).x;                                         // 66
  r19.z = TF6(r11.yw, -1, 0).x;                                          // 67
  r19.w = TF6(r11.yw, -1, 1).x;                                          // 68
  r18.x = TF6(r11.yw, 1, -2).x;                                          // 69
  r18.y = TF6(r11.yw, 0, -2).x;                                          // 70
  r18.z = TF6(r11.yw, -1, -2).x;                                         // 71
  r18.w = TF6(r11.yw, 2, -2).x;                                          // 72
  r20.x = TF6(r11.yw, 2, 1).x;                                           // 73
  r20.y = TF6(r11.yw, 0, 0).x;                                           // 74
  r20.z = TF6(r11.yw, 2, -1).x;                                          // 75
  r20.w = TF6(r11.yw, 2, 0).x;                                           // 76
  { float4 t = TF0(r7.yx); r7 = t.wxyz; }                                // 77
  r13.xyz = TF1(r9.wz).xyz;                                              // 78
  r11.xy = frac(r10.yz * TextureSize(7) - 0.5);                          // 79 (getWeights2D)
  r15.x = TF7(r10.yz, 0, -1).x;                                          // 80
  r15.y = TF7(r10.yz, 0, 0).x;                                           // 81
  r15.z = TF7(r10.yz, -1, -1).x;                                         // 82
  r15.w = TF7(r10.yz, -1, 0).x;                                          // 83
  r4.w = dot(r5.xyz, r5.xyz);                                            // 84
  r5.w = dot(r1.xyz, r1.xyz);                                            // 85
  r21.xyz = C19.zyx - r2.zyx;                                            // 86
  r17.xyz = r2.xyz - C19.xyz;                                            // 87
  { float v = dot(r17.xyz, r17.xyz); r1.w = rcp(C12.z); ps = r1.w; r6.w = v; }  // 88
  { float v = dot(r21.xyz, r21.xyz); r6.w = sqrt(abs(r6.w)); ps = r6.w; r0.w = v; }  // 89
  r9.z = r0.z * r14.y;                                                   // 90
  r9 = C254 - r9.yyyz;                                                   // 91
  r26.xyz = r9.xyz - r11.z;                                              // 92
  r17.xyz = r26.xyz * C253.x;                                            // 93
  r14.yzw = r26.xyz * C254.w;                                            // 94
  { float3 v = r17.xyz * r14.yzw; r14.x = log2(abs(r6.x)); ps = r14.x; r17.xyz = v; }  // 95
  r17.xyz = -r17.xyz * r14.yzw + C254.w;                                 // 96
  { float v = C254.x - r10.x; r14.y = log2(abs(r6.y)); ps = r14.y; r0.z = v; }  // 97
  r9.xyz = saturate(r26.xzy * C253.z + r17.xzy);                         // 98
  { float4 v = Ge4(r0.z, r15); r14.z = log2(abs(r6.z)); ps = r14.z; r15 = v; }  // 99
  { float2 v = r15.xy - r15.zw; r6.y = rsqrt(abs(r5.w)); ps = r6.y; r6.x = v.x; r6.z = v.y; }  // 100
  r17.xy = r6.xz * r11.x + r15.zw;                                       // 101
  { float v = r17.y - r17.x; r6.z = rsqrt(abs(r4.w)); ps = r6.z; r6.x = v; }  // 102
  { float v = r6.x * r11.y; r6.x = rsqrt(abs(r0.w)); ps = r6.x; r16.x = v; }  // 103
  r11.xyz = r7.yzw * r7.yzw;                                             // 104
  r15.xyz = r14.xyz * C21.w;                                             // 105
  r5.xyz = r6.z * r5.zyx;                                                // 106
  r14.xyz = r6.y * r1.zyx;                                               // 107
  { float3 v = r21.zyx * r6.x; ps = r9.w; r10.xyz = v; }                 // 108
  { float4 v = Gt4(r3.w, r20); r9.w = saturate(r16.z + ps); ps = r9.w; r21 = v; }  // 109
  { float4 v = Gt4(r3.w, r18); ps = r8.w; r18 = v; }                     // 110
  { float4 v = Gt4(r3.w, r19); r20.w = saturate(r16.y + ps); ps = r20.w; r19 = v; }  // 111
  { float4 v = Gt4(r3.w, r23); ps = r8.z; r23 = v; }                     // 112
  { float4 v = Gt4(r3.w, r22); r20.z = saturate(-r20.w + ps); ps = r20.z; r22 = v; }  // 113
  { float4 v = Gt4(r3.w, r24); r20.x = saturate(r8.y - r8.x); ps = r20.x; r24 = v; }  // 114
  { float4 v = r25.w * r24; r20.y = saturate(r8.x - r8.z); ps = r20.y; r26 = v; }  // 115
  r8 = r9.w * r20.yxzw;                                                  // 116
  r27.w = dot(r8.yxwz, r22.xywz);                                        // 117
  r25.yzw = saturate(r9.yzx - r9.zxw);                                   // 118
  r8 = r25.wyww * r20.zzxy;                                              // 119
  { float4 v = r25.zyyz * r20.xxyz; r25.x = saturate(C254.x - r9.y); ps = r25.x; r24 = v; }  // 120
  r0.z = dot(r26.wxz, r25.xyz);                                          // 121
  r6.x = dot(r24.yzx, r23.zwx);                                          // 122
  r22 = r25.xxxz * r20.xzyy;                                             // 123
  r27.z = dot(r8.zwx, r19.wzy);                                          // 124
  r20 = r25.ywzx * r20.w;                                                // 125
  r2.w = dot(r20.xzy, r18.xyz);                                          // 126
  r7.yzw = r27.xyz + r27.xyw;                                            // 127
  { float2 v = r7.zy + C252.w; r6.y = -C12.x + r6.w; ps = r6.y; r8.x = v.x; r8.w = v.y; }  // 128
  r3.w = r10.w * r9.w + r7.w;                                            // 129
  { float v = dot(r22.xzy, r21.xwz); ps = r3.w; r6.z = v; }              // 130
  { float3 v = r8.x * r4.zxy; r2.w = r2.w + ps; ps = r2.w; r7.yzw = v; } // 131
  r7.yzw = r8.w * r3.zxy + r7.yzw;                                       // 132
  r2.w = r26.y * r25.w + r2.w;                                           // 133
  r2.w = r24.w * r23.y + r2.w;                                           // 134
  r2.w = r22.w * r21.y + r2.w;                                           // 135
  { float v = r2.w + r6.x; r6.x = -C12.y + r6.w; ps = r6.x; r2.w = v; }  // 136
  { float v = r2.w + r0.z; ps = r20.w; r6.w = v; }                       // 137
  r6.w = r8.y * r19.x + r6.w;                                            // 138
  { float v = r6.w + r6.z; r16.y = ps * r18.w; ps = r16.y; r17.z = v; }  // 139
  { float2 v = r17.xz + r16.xy; ps = r6.y; r6.zw = v; }                  // 140
  { float v = r6.z - r6.w; r0.z = saturate(ps * r1.w); ps = r0.z; r6.y = v; }  // 141
  r9.y = r0.z * r6.y + r6.w;                                             // 142
  { float v = C12.w - r9.y; r8.y = saturate(C253.w * r6.x); ps = r8.y; r8.z = v; }  // 143
  { float3 v = r8.wxy * r8.wxz; r8.x = exp2(r15.x); ps = r8.x; r9.x = v.x; r9.z = v.y; r9.w = v.z; }  // 144
  { float2 v = r9.xy + r9.zw; r8.y = exp2(r15.y); ps = r8.y; r6.xy = v; }  // 145
  { float2 v = C254.x - r6.yx; r8.z = exp2(r15.z); ps = r8.z; r6.xy = v; }  // 146
  { float3 v = r8.xyz * C21.xyz; r6.z = sqrt(abs(r6.y)); ps = r6.z; r9.xyz = v; }  // 147
  r7.yzw = r14.xyz * r6.z + r7.ywz;                                      // 148
  r6.y = dot(r7.ywz, r7.ywz);                                            // 149
  { float2 v = r6.x * C112.yx; r6.y = rsqrt(abs(r6.y)); ps = r6.y; r6.x = v.x; r6.z = v.y; }  // 150
  r7.yzw = r7.yzw * r6.y;                                                // 151
  r6.y = saturate(dot(r5.xzy, r7.ywz));                                  // 152
  { float3 v = r13.xyz * r13.xyz; r6.y = r6.y * r6.y; ps = r6.y; r8.xyz = v; }  // 153
  r5.xyz = r6.y * r12.xyz + C22.xyz;                                     // 154
  r5.xyz = r9.xyz * r5.xyz + C20.xyz;                                    // 155
  r5.xyz = r11.xyz * r5.xyz;                                             // 156
  { float3 v = r5.xyz * C27.w; r0.z = sqrt(abs(r0.w)); ps = r0.z; r5.xyz = v; }  // 157
  if (XeBool(135)) {
    r14 = float4(C252.x == 0.0 ? r2.z : C254.x, C252.x == 0.0 ? r2.x : C254.x,
                 C252.x == 0.0 ? r2.y : C254.x, C252.y == 0.0 ? r2.y : C254.x);  // 158
    { float v = dot(C32.zxyw, r14); r9.x = rcp(C48.x); r9.z = v; }       // 159
    { float v = dot(C35.zxyw, r14); r9.y = rcp(C48.y); r6.y = v; }       // 160
    { float v = dot(C33.zxyw, r14); r6.y = rcp(r6.y); ps = r6.y; r9.w = v; }  // 161
    r13 = r9 * r6.y;                                                     // 162
    r12.x = TF9(r13.zw, 0, 0).x;                                         // 163
    r12.y = TF9(r13.zw, 0, 1).x;                                         // 164
    r12.z = TF9(r13.zw, 1, 0).x;                                         // 165
    r12.w = TF9(r13.zw, 1, 1).x;                                         // 166
    r6.w = dot(C34.zxyw, r14);                                           // 167
    r9.xy = r13.xy * r9.zw;                                              // 168
    { float2 v = frac(r9.yx); ps = r6.w; r9.yz = v; }                    // 169
    { float v = C254.x - r9.y; r9.w = ps * r6.y; ps = r9.w; r9.x = v; }  // 170
    { float2 v = C254.x - r9.wz; r6.y = v.x; r6.w = v.y; }               // 171
    r12 = Ge4(r6.y, r12);                                                // 172
    r12.xy = r6.w * r12.xy;                                              // 173
    r12.zw = r12.zw * r9.z;                                              // 174
    r6.y = dot(r12.wyxz, r9.yyxx);                                       // 175
    r6.y = C254.x - r6.y;                                                // 176
    { float2 v = r6.y * C114.xy; r6.y = v.x; r6.w = v.y; }               // 177
    { float2 v = max(r6.xz, r6.wy); r6.x = v.x; r6.z = v.y; }            // 178
  }
  r9.xyz = -r2.xyz * C81.w + C81.xyz;                                    // 179
  { float3 v = -r2.xyz * C80.w + C80.xyz; r2.x = v.x; r2.y = v.y; r2.w = v.z; }  // 180
  r0.w = dot(r2.wxy, r2.wxy);                                            // 181
  { float v = dot(r9.xyz, r9.xyz); r6.y = sqrt(abs(r0.w)); ps = r6.y; r6.w = v; }  // 182
  { float v = C254.x - r6.x; r6.x = rsqrt(abs(r6.w)); ps = r6.x; r2.z = v; }  // 183
  { float3 v = r9.xyz * r6.x; r6.x = rsqrt(abs(r0.w)); ps = r6.x; r13.xyz = v; }  // 184
  { float3 v = r2.xyw * r6.x; r6.w = sqrt(abs(r6.w)); ps = r6.w; r9.yzw = v; }  // 185
  r12.xy = saturate(-r6.yw * C96.xy + C254.x);                           // 186
  r6.x = dot(r9.wyz, C98.zxy);                                           // 187
  r12.z = dot(r7.ywz, r9.wyz);                                           // 188
  r2.x = saturate(dot(r7.ywz, r9.wyz));                                  // 189
  r2.y = saturate(dot(r7.ywz, r13.zxy));                                 // 190
  { float v = dot(r7.ywz, r13.zxy); r9.x = saturate(C23.w * r2.x); ps = r9.x; r12.w = v; }  // 191
  { float v = dot(r13.zxy, C99.zxy); r6.w = r12.z + r12.z; ps = r6.w; r6.y = v; }  // 192
  { float2 v = r6.yx - C105.yx; r0.w = r12.w + r12.w; ps = r0.w; r6.xy = v; }  // 193
  r13.xyz = -r7.yzw * r0.w + r13.zyx;                                    // 194
  r9.yzw = -r7.yzw * r6.w + r9.wzy;                                      // 195
  { float v = saturate(dot(-r10.zxy, r9.ywz)); r12.z = saturate(C107.x * r6.y); ps = r12.z; r9.y = v; }  // 196
  { float v = saturate(dot(-r10.zxy, r13.xzy)); r12.w = saturate(C107.y * r6.x); ps = r12.w; r9.z = v; }  // 197
  r6.xy = r12.zw * r12.xy + C252.w;                                      // 198
  r12.xy = r6.yx * C94.yx + C254.x;                                      // 199
  { float2 v = r9.yz * r9.yz; ps = r12.x; r6.xy = v; }                   // 200
  { float2 v = r6.xy * r6.xy; r6.w = ps * r2.z; ps = r6.w; r6.xy = v; }  // 201
  { float v = r6.w * r2.y; r9.y = saturate(C23.w * r2.y); ps = r9.y; r6.w = v; }  // 202
  { float2 v = r9.xy * r6.xy; r12.w = C254.x - r6.z; ps = r12.w; r9.xy = v; }  // 203
  { float v = r9.x * r12.w; r13.x = C88.x * r6.w; ps = r13.x; r12.z = v; }  // 204
  { float2 v = r12.yz * r12.wy; r13.y = C88.y * r6.w; ps = r13.y; r9.zw = v; }  // 205
  { float2 v = r9.yz * r2.zx; r13.z = C88.z * r6.w; ps = r13.z; r6.xy = v; }  // 206
  r2.xyz = r6.y * C87.xyz + r13.xyz;                                     // 207
  r6.x = r6.x * r12.x;                                                   // 208
  r6.xyz = r6.x * C88.xyz;                                               // 209
  r6.xyz = r9.w * C87.xyz + r6.xyz;                                      // 210
  r6.xyz = r8.xyz * r6.xyz + r5.xyz;                                     // 211
  r2.xyz = r11.xyz * r2.xyz + r6.xyz;                                    // 212
  if (XeBool(133)) {
    r6.xyz = TF13(r0.xy).xyz;                                            // 213
    r6.xyz = r6.xyz * r6.xyz;                                            // 214
    r2.xyz = r6.xyz * C24.z + r2.xyz;                                    // 215
  }
  if (XeBool(134)) {
    r6.x = dot(-r10.zxy, r7.ywz);                                        // 216
    r6.x = r6.x + r6.x;                                                  // 217
    { float3 v = -r7.ywz * r6.x - r10.zxy; r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 218
    { float3 v = r6.y * r3.zxy; r0.x = v.x; r0.y = v.y; r0.w = v.z; }    // 219
    r6.xyz = r6.x * r1.zxy + float3(r0.x, r0.y, r0.w);                   // 220
    r6.z = -r6.w * r4.y - r6.z;                                          // 221
    r6.xy = r6.w * r4.xz + r6.yx;                                        // 222
    r6 = XeCube(r6.xyz);                                                 // 223
    { float v = r6.w; r0.x = rcp(abs(r6.z)); r0.w = v; }                 // 224
    r0.xy = r6.yx * r0.x + C252.z;                                       // 225
    r6.xyz = TF14(float3(r0.x, r0.y, r0.w)).xyz;                         // 226
    r6.xyz = r6.xyz * r6.xyz;                                            // 227
    r2.xyz = r8.xyz * r6.xyz + r2.xyz;                                   // 228
  }
  r6.x = r0.z - C67.x;                                                   // 229
  r6.yzw = r2.xyz * C49.xyz;                                             // 230
  if (r6.x > 0.0) {                                                      // p0
    { float v = saturate(dot(-r10.zxy, C66.zxy)); r0.y = C67.w * r6.x; r0.x = v; }  // 231
    r1.xyz = TF5(r0.y).xyz;                                              // 232
    r0.xyz = TF4(r0.x).xyz;                                              // 233
    r0.xyz = r0.xyz - C68.xyz;                                           // 234
    { float3 v = C254.x - r1.xyz; r0.w = C28.y * r7.x; r2.xyz = v; }     // 235
    { float3 v = r0.w * r2.zyx; r6.x = saturate(C67.z * r6.x); r2.xyz = v; }  // 236
    r0.xyz = r6.x * r0.zyx + C68.zyx;                                    // 237
    r0.xyz = r2.zyx * r0.zyx - r6.yzw;                                   // 238
    r0.xyz = r6.yzw * r1.xyz + r0.xyz;                                   // 239
    r6.yzw = r0.xyz * C28.x + r6.yzw;                                    // 240
  }
  r0.xyz = C20.w * C26.xyz;                                              // 241
  float4 o = float4(r0.xyz * r6.yzw, C26.w * r7.x);                      // 242
  AlphaTest(o.w);
  coverage = AlphaToMask(o.w, input.position.xy);
  return o * xe_color_exp_bias.x;
}
