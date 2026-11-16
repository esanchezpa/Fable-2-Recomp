// Fable II characters with four lights, pixel shader F2F103F16764043B: the
// four-light build of 401A01FD (character.ps.hlsl), with lights c80-c83
// (colours c87-c90, ranges c96, cones c98-c101 / c105 / c107 / c94). Built
// only for Project Sparrow (tools/shaders/build_replace.py --sparrow).
//
// Stage 1: a literal port of the game's Xenos microcode (comments give the
// ucode instruction numbers); see character.ps.hlsl for what it does. The
// compiler laid the registers out differently, so this is its own port.
// Xenos reading notes are in xe_common.hlsli.

// --- SDK translator interface (shaders/xe_common.hlsli) -------------------
#define XE_FLOAT_CONSTANTS 53
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
#define C82 K[33]
#define C83 K[34]
#define C87 K[35]
#define C88 K[36]
#define C89 K[37]
#define C90 K[38]
#define C94 K[39]
#define C96 K[40]
#define C98 K[41]
#define C99 K[42]
#define C100 K[43]
#define C101 K[44]
#define C105 K[45]
#define C107 K[46]
#define C112 K[47]
#define C114 K[48]
#define C252 K[49]
#define C253 K[50]
#define C254 K[51]
#define C255 K[52]

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

  { float3 v = C254.x - C22.xyz; r2.w = C254.x; ps = r2.w; r12.xyz = v; }  // 24
  { float v = dot(C36.zxyw, r2.zxyw); r8.x = rcp(C13.x); ps = r8.x; r8.z = v; }  // 25
  { float v = dot(C39.zxyw, r2.zxyw); r8.y = rcp(C13.y); ps = r8.y; r6.w = v; }  // 26
  { float v = dot(C37.zxyw, r2.zxyw); r14.w = rcp(r6.w); ps = r14.w; r8.w = v; }  // 27
  r13 = r8.xzwy * r14.w;                                                 // 28
  r1.w = TF6(r13.yz, -2, 2).x;                                           // 29
  r9.zw = r0.yx * C9.yx + C9.wz;                                         // 30
  r7.xy = r0.yx * C8.yx + C8.wz;                                         // 31
  r7.zw = r0.yx * C10.yx + C10.wz;                                       // 32
  r24.x = dot(C40.zxyw, r2.zxyw);                                        // 33
  r24.y = dot(C41.zxyw, r2.zxyw);                                        // 34
  r24.z = dot(C42.zxyw, r2.zxyw);                                        // 35
  r4.w = dot(C43.zxyw, r2.zxyw);                                         // 36
  r14.z = dot(C38.zxyw, r2.zxyw);                                        // 37
  { float2 v = float2(r13.w * r8.w, r13.x * r8.z); r13.x = v.x; r13.w = v.y; }  // 38
  r0.zw = r13.xw + C255.x;                                               // 39
  r9.xy = floor(-r0.zw);                                                 // 40
  r8.xyz = C254.xyz - r9.x;                                              // 41
  r0.zw = -r13.wx - r9.yx;                                               // 42
  { float3 v = r8.xyz - r13.x; r10.x = v.x; r10.z = v.y; r10.w = v.z; }  // 43
  { float4 v = r0.wwzw * C253.zxzy; r14.x = C253.x * r0.z; ps = r14.x; r16 = v; }  // 44
  { float3 v = r10.xzw * C253.x; r6.w = r16.y * r16.w; ps = r6.w; r11.xyz = v; }  // 45
  { float v = r6.w * r16.w; r14.y = C253.y * r0.z; ps = r14.y; r8.w = v; }  // 46
  { float3 v = r10.xzw * C254.w; r0.z = r14.x * r14.y; ps = r0.z; r8.xyz = v; }  // 47
  { float3 v = r11.xyz * r8.xyz; r6.w = r14.z * r14.w; ps = r6.w; r11.xyz = v; }  // 48
  { float3 v = r11.xyz * r8.xyz; r3.w = C254.x - r6.w; ps = r3.w; r8.xyz = v; }  // 49
  { float4 v = C254.w - r8; r10.y = rcp(r4.w); ps = r10.y; r8 = v; }     // 50
  r8.xyz = saturate(r10.zwx * C253.z + r8.yzx);                          // 51
  { float v = Gt(r3.w, r1.w); r24.w = saturate(C254.x - r8.y); ps = r24.w; r10.x = v; }  // 52
  r10 = r24.zxyw * r10.yyyx;                                             // 53
  r26.xy = TF2(r7.wz).xy;                                                // 54
  // The character shadow map on a 5x5 footprint (24 taps, the centre is 76).
  r23.x = TF6(r13.yz, 1, 2).x;                                           // 55
  r23.y = TF6(r13.yz, -1, 2).x;                                          // 56
  r23.z = TF6(r13.yz, 0, 2).x;                                           // 57
  r23.w = TF6(r13.yz, 2, 2).x;                                           // 58
  r21.x = TF6(r13.yz, -2, 1).x;                                          // 59
  r21.y = TF6(r13.yz, -2, 0).x;                                          // 60
  r21.z = TF6(r13.yz, -2, -1).x;                                         // 61
  r21.w = TF6(r13.yz, -2, -2).x;                                         // 62
  r22.x = TF6(r13.yz, 0, 1).x;                                           // 63
  r22.y = TF6(r13.yz, 0, -1).x;                                          // 64
  r22.z = TF6(r13.yz, 1, 1).x;                                           // 65
  r22.w = TF6(r13.yz, 1, 0).x;                                           // 66
  r18.x = TF6(r13.yz, 1, -1).x;                                          // 67
  r18.y = TF6(r13.yz, -1, -1).x;                                         // 68
  r18.z = TF6(r13.yz, -1, 0).x;                                          // 69
  r18.w = TF6(r13.yz, -1, 1).x;                                          // 70
  r11.x = TF6(r13.yz, 1, -2).x;                                          // 71
  r11.y = TF6(r13.yz, 0, -2).x;                                          // 72
  r11.z = TF6(r13.yz, -1, -2).x;                                         // 73
  r11.w = TF6(r13.yz, 2, -2).x;                                          // 74
  r19.x = TF6(r13.yz, 2, 1).x;                                           // 75
  r19.y = TF6(r13.yz, 0, 0).x;                                           // 76
  r19.z = TF6(r13.yz, 2, -1).x;                                          // 77
  r19.w = TF6(r13.yz, 2, 0).x;                                           // 78
  { float4 t = TF0(r7.yx); r7 = t.wxyz; }                                // 79
  r13.xyz = TF1(r9.wz).xyz;                                              // 80
  r15.xy = frac(r10.yz * TextureSize(7) - 0.5);                          // 81 (getWeights2D)
  r17.x = TF7(r10.yz, 0, -1).x;                                          // 82
  r17.y = TF7(r10.yz, 0, 0).x;                                           // 83
  r17.z = TF7(r10.yz, -1, -1).x;                                         // 84
  r17.w = TF7(r10.yz, -1, 0).x;                                          // 85
  r4.w = dot(r5.xyz, r5.xyz);                                            // 86
  r5.w = dot(r1.xyz, r1.xyz);                                            // 87
  r20.xyz = C19.zyx - r2.zyx;                                            // 88
  r25.xyz = r2.xyz - C19.xyz;                                            // 89
  { float v = dot(r25.xyz, r25.xyz); r1.w = rcp(C12.z); ps = r1.w; r6.w = v; }  // 90
  { float v = dot(r20.xyz, r20.xyz); r6.w = sqrt(abs(r6.w)); ps = r6.w; r0.w = v; }  // 91
  r9.z = r0.z * r14.y;                                                   // 92
  r9 = C254 - r9.yyyz;                                                   // 93
  r27.xyz = r9.xyz - r13.w;                                              // 94
  r25.xyz = r27.xyz * C253.x;                                            // 95
  r14.yzw = r27.xyz * C254.w;                                            // 96
  { float3 v = r25.xyz * r14.yzw; r14.x = log2(abs(r6.x)); ps = r14.x; r25.xyz = v; }  // 97
  r25.xyz = -r25.xyz * r14.yzw + C254.w;                                 // 98
  { float v = C254.x - r10.x; r14.y = log2(abs(r6.y)); ps = r14.y; r0.z = v; }  // 99
  r9.xyz = saturate(r27.xzy * C253.z + r25.xzy);                         // 100
  { float4 v = Ge4(r0.z, r17); r14.z = log2(abs(r6.z)); ps = r14.z; r17 = v; }  // 101
  { float2 v = r17.xy - r17.zw; r6.y = rsqrt(abs(r5.w)); ps = r6.y; r6.x = v.x; r6.z = v.y; }  // 102
  r17.xy = r6.xz * r15.x + r17.zw;                                       // 103
  { float v = r17.y - r17.x; r6.z = rsqrt(abs(r4.w)); ps = r6.z; r6.x = v; }  // 104
  { float v = r6.x * r15.y; r6.x = rsqrt(abs(r0.w)); ps = r6.x; r16.y = v; }  // 105
  r7.yzw = r7.yzw * r7.yzw;                                              // 106
  r15.xyz = r14.xyz * C21.w;                                             // 107
  r5.xyz = r6.z * r5.zyx;                                                // 108
  r14.xyz = r6.y * r1.zyx;                                               // 109
  { float3 v = r20.zyx * r6.x; ps = r9.w; r10.xyz = v; }                 // 110
  { float4 v = Gt4(r3.w, r19); r9.w = saturate(r16.z + ps); ps = r9.w; r20 = v; }  // 111
  { float4 v = Gt4(r3.w, r11); ps = r8.w; r11 = v; }                     // 112
  { float4 v = Gt4(r3.w, r18); r19.w = saturate(r16.x + ps); ps = r19.w; r18 = v; }  // 113
  { float4 v = Gt4(r3.w, r22); ps = r8.z; r22 = v; }                     // 114
  { float4 v = Gt4(r3.w, r21); r19.z = saturate(-r19.w + ps); ps = r19.z; r21 = v; }  // 115
  { float4 v = Gt4(r3.w, r23); r19.x = saturate(r8.y - r8.x); ps = r19.x; r23 = v; }  // 116
  { float4 v = r24.w * r23; r19.y = saturate(r8.x - r8.z); ps = r19.y; r25 = v; }  // 117
  r8 = r9.w * r19.yxzw;                                                  // 118
  r26.w = dot(r8.yxwz, r21.xywz);                                        // 119
  r24.yzw = saturate(r9.yzx - r9.zxw);                                   // 120
  r8 = r24.wyww * r19.zzyx;                                              // 121
  { float4 v = r24.zyyz * r19.xxyz; r24.x = saturate(C254.x - r9.y); ps = r24.x; r23 = v; }  // 122
  r0.z = dot(r25.wxz, r24.xyz);                                          // 123
  r6.x = dot(r23.yzx, r22.zwx);                                          // 124
  r21 = r24.xxxz * r19.xzyy;                                             // 125
  r26.z = dot(r8.wzx, r18.wzy);                                          // 126
  r19 = r24.ywzx * r19.w;                                                // 127
  r2.w = dot(r19.xzy, r11.xyz);                                          // 128
  { float3 v = float3(r26.x + r26.x, r26.y + r26.y, r26.z + r26.w); r8.x = v.x; r8.z = v.y; r8.w = v.z; }  // 129
  { float2 v = r8.zx + C252.w; r6.y = -C12.x + r6.w; ps = r6.y; r16.x = v.x; r16.w = v.y; }  // 130
  r3.w = r10.w * r9.w + r8.w;                                            // 131
  { float v = dot(r21.xzy, r20.xwz); ps = r3.w; r6.z = v; }              // 132
  { float3 v = r16.x * r4.zxy; r2.w = r2.w + ps; ps = r2.w; r9.xyz = v; }  // 133
  r11.xyz = r16.w * r3.zxy + r9.xyz;                                     // 134
  r2.w = r25.y * r24.w + r2.w;                                           // 135
  r2.w = r23.w * r22.y + r2.w;                                           // 136
  r2.w = r21.w * r20.y + r2.w;                                           // 137
  { float v = r2.w + r6.x; r6.x = -C12.y + r6.w; ps = r6.x; r2.w = v; }  // 138
  { float v = r2.w + r0.z; ps = r19.w; r6.w = v; }                       // 139
  r6.w = r8.y * r18.x + r6.w;                                            // 140
  { float v = r6.w + r6.z; r16.z = ps * r11.w; ps = r16.z; r17.z = v; }  // 141
  { float2 v = r17.xz + r16.yz; ps = r6.y; r6.zw = v; }                  // 142
  { float v = r6.z - r6.w; r0.z = saturate(ps * r1.w); ps = r0.z; r6.y = v; }  // 143
  r8.y = r0.z * r6.y + r6.w;                                             // 144
  { float v = C12.w - r8.y; r16.y = saturate(C253.w * r6.x); ps = r16.y; r16.z = v; }  // 145
  { float3 v = r16.wxy * r16.wxz; r6.x = exp2(r15.x); ps = r6.x; r8.x = v.x; r8.z = v.y; r8.w = v.z; }  // 146
  { float2 v = r8.xy + r8.zw; r6.y = exp2(r15.y); ps = r6.y; r6.zw = v; }  // 147
  { float2 v = C254.x - r6.zw; r6.z = exp2(r15.z); ps = r6.z; r8.xy = v; }  // 148
  { float3 v = r6.xyz * C21.xyz; r6.x = sqrt(abs(r8.x)); ps = r6.x; r9.xyz = v; }  // 149
  r6.yzw = r14.xyz * r6.x + r11.xzy;                                     // 150
  r6.x = dot(r6.ywz, r6.ywz);                                            // 151
  { float4 v = r8.y * C112; r6.x = rsqrt(abs(r6.x)); ps = r6.x; r11 = v; }  // 152
  r8.xyz = r6.yzw * r6.x;                                                // 153
  r6.x = saturate(dot(r5.xzy, r8.xzy));                                  // 154
  { float3 v = r13.xyz * r13.xyz; r6.x = r6.x * r6.x; ps = r6.x; r5.xyz = v; }  // 155
  r6.xyz = r6.x * r12.xyz + C22.xyz;                                     // 156
  r6.xyz = r9.xyz * r6.xyz + C20.xyz;                                    // 157
  float sky_vis = -1.0;
#if SPARROW
  // Sparrow: sky openness and the sun's bounce on the ambient, as lit.ps.hlsl
  // (r8.zyx is the world normal; the sun is the light c112 picks for shadows).
  if (SparrowActive())
    r6.xyz = SparrowAmbient(r6.xyz, input.v2.xyz, r8.zyx, C87.xyz * C112.x + C88.xyz * C112.y + C89.xyz * C112.z + C90.xyz * C112.w, sky_vis);
#endif
  r6.xyz = r7.yzw * r6.xyz;                                              // 158
  { float3 v = r6.xyz * C27.w; r0.z = sqrt(abs(r0.w)); ps = r0.z; r9.xyz = v; }  // 159
  if (XeBool(135)) {
    r15 = float4(C252.x == 0.0 ? r2.z : C254.x, C252.x == 0.0 ? r2.x : C254.x,
                 C252.x == 0.0 ? r2.y : C254.x, C252.y == 0.0 ? r2.y : C254.x);  // 160
    { float v = dot(C32.zxyw, r15); r13.x = rcp(C48.x); r13.z = v; }     // 161
    { float v = dot(C35.zxyw, r15); r13.y = rcp(C48.y); r6.x = v; }      // 162
    { float v = dot(C33.zxyw, r15); r6.w = rcp(r6.x); ps = r6.w; r13.w = v; }  // 163
    r14 = r13 * r6.w;                                                    // 164
    r12.x = TF9(r14.zw, 0, 0).x;                                         // 165
    r12.y = TF9(r14.zw, 0, 1).x;                                         // 166
    r12.z = TF9(r14.zw, 1, 0).x;                                         // 167
    r12.w = TF9(r14.zw, 1, 1).x;                                         // 168
    r6.x = dot(C34.zxyw, r15);                                           // 169
    { float2 v = r14.xy * r13.zw; r6.y = v.x; r6.z = v.y; }              // 170
    { float2 v = frac(r6.zy); ps = r6.x; r6.y = v.x; r6.z = v.y; }       // 171
    { float v = C254.x - r6.y; r6.w = r6.w * ps; ps = r6.w; r6.x = v; }  // 172
    r13.xy = C254.x - r6.wz;                                             // 173
    r12 = Ge4(r13.x, r12);                                               // 174
    r12.xy = r13.y * r12.xy;                                             // 175
    r12.zw = r12.zw * r6.z;                                              // 176
    r6.y = dot(r12.wyxz, r6.yyxx);                                       // 177
    r6.x = C254.x - r6.y;                                                // 178
    r6 = r6.x * C114;                                                    // 179
    r11 = max(r11, r6);                                                  // 180
  }
  r15.xyz = -r2.xyz * C83.w + C83.xyz;                                   // 181
  r14.xyz = -r2.xyz * C82.w + C82.xyz;                                   // 182
  r12.xyz = -r2.xyz * C81.w + C81.xyz;                                   // 183
  r2.xyz = -r2.xyz * C80.w + C80.xyz;                                    // 184
  r0.w = dot(r2.xyz, r2.xyz);                                            // 185
  { float v = dot(r12.xyz, r12.xyz); r6.x = sqrt(abs(r0.w)); ps = r6.x; r1.w = v; }  // 186
  { float v = dot(r14.xyz, r14.xyz); r6.y = sqrt(abs(r1.w)); ps = r6.y; r2.w = v; }  // 187
  { float v = dot(r15.xyz, r15.xyz); r6.z = sqrt(abs(r2.w)); ps = r6.z; r6.w = v; }  // 188
  { float4 v = C254.x - r11.xzyw; r3.w = rsqrt(abs(r6.w)); ps = r3.w; r13 = v; }  // 189
  { float3 v = r15.xyz * r3.w; r2.w = rsqrt(abs(r2.w)); ps = r2.w; r17.xyz = v; }  // 190
  { float3 v = r14.xyz * r2.w; r1.w = rsqrt(abs(r1.w)); ps = r1.w; r14.xyz = v; }  // 191
  { float3 v = r12.xyz * r1.w; r0.w = rsqrt(abs(r0.w)); ps = r0.w; r15.xyz = v; }  // 192
  { float3 v = r2.xyz * r0.w; r6.w = sqrt(abs(r6.w)); ps = r6.w; r16.xyz = v; }  // 193
  r11 = saturate(-r6.wyxz * C96.wyxz + C254.x);                          // 194
  r12.x = dot(r16.zxy, C98.zxy);                                         // 195
  r12.y = dot(r15.zxy, C99.zxy);                                         // 196
  r12.z = dot(r14.zxy, C100.zxy);                                        // 197
  r12.w = dot(r17.zxy, C101.zxy);                                        // 198
  r2.w = saturate(dot(r8.xzy, r16.zxy));                                 // 199
  r2.x = saturate(dot(r8.xzy, r15.zxy));                                 // 200
  r2.y = saturate(dot(r8.xzy, r14.zxy));                                 // 201
  r2.z = saturate(dot(r8.xzy, r17.zxy));                                 // 202
  r6.x = dot(r8.xzy, r16.zxy);                                           // 203
  r6.y = dot(r8.xzy, r15.zxy);                                           // 204
  r6.z = dot(r8.xzy, r14.zxy);                                           // 205
  r6.w = dot(r8.xzy, r17.zxy);                                           // 206
  r6 = r6 + r6;                                                          // 207
  r12 = r12 - C105;                                                      // 208
  r12 = saturate(r12.xwzy * C107.xwzy);                                  // 209
  r14.xyz = -r8.xyz * r6.z + r14.zyx;                                    // 210
  r15.xyz = -r8.xyz * r6.y + r15.zyx;                                    // 211
  r6.yzw = -r8.xyz * r6.w + r17.zyx;                                     // 212
  r16.xyz = -r8.xyz * r6.x + r16.zyx;                                    // 213
  r6.x = saturate(dot(-r10.zxy, r16.xzy));                               // 214
  r6.y = saturate(dot(-r10.zxy, r6.ywz));                                // 215
  r6.z = saturate(dot(-r10.zxy, r15.xzy));                               // 216
  r6.w = saturate(dot(-r10.zxy, r14.xzy));                               // 217
  r11 = r12.yxzw * r11.xzwy + C252.w;                                    // 218
  r12 = r11.xzwy * C94.wzyx + C254.x;                                    // 219
  { float4 v = r6 * r6; r6.x = r2.w; ps = r6.x; r14 = v; }               // 220
  { float4 v = r12.wyzx * r13; r15.x = saturate(C23.w * r6.x); ps = r15.x; r11 = v; }  // 221
  { float4 v = r14 * r14; r15.y = saturate(C23.w * r2.x); ps = r15.y; r6 = v; }  // 222
  { float4 v = r11 * r2.wyxz; r15.z = saturate(C23.w * r2.y); ps = r15.z; r11 = v; }  // 223
  { float3 v = r11.w * C90.xyz; r15.w = saturate(C23.w * r2.z); ps = r15.w; r14.xyz = v; }  // 224
  r6 = r15.xwyz * r6;                                                    // 225
  r2.xyz = r11.y * C89.xzy + r14.xzy;                                    // 226
  r6 = r6.xwyz * r13.xywz;                                               // 227
  r6 = r6.zywx * r12;                                                    // 228
  r2.xyz = r11.z * C88.xyz + r2.xzy;                                     // 229
  r2.xyz = r11.x * C87.xzy + r2.xzy;                                     // 230
  r11.xyz = r6.x * C90.xyz;                                              // 231
  r11.xyz = r6.y * C89.xzy + r11.xzy;                                    // 232
  r6.xyz = r6.z * C88.xyz + r11.xzy;                                     // 233
  r6.xyz = r6.w * C87.xzy + r6.xzy;                                      // 234
  r6.xyz = r5.xyz * r6.xzy + r9.xyz;                                     // 235
  r2.xyz = r7.yzw * r2.xzy + r6.xyz;                                     // 236
  if (XeBool(133)) {
    r6.xyz = TF13(r0.xy).xyz;                                            // 237
    r6.xyz = r6.xyz * r6.xyz;                                            // 238
    r2.xyz = r6.xyz * C24.z + r2.xyz;                                    // 239
  }
  if (XeBool(134)) {
    r6.x = dot(-r10.zxy, r8.xzy);                                        // 240
    r6.x = r6.x + r6.x;                                                  // 241
    { float3 v = -r8.xzy * r6.x - r10.zxy; r6.x = v.x; r6.y = v.y; r6.w = v.z; }  // 242
    { float3 v = r6.y * r3.zxy; r0.x = v.x; r0.y = v.y; r0.w = v.z; }    // 243
    r6.xyz = r6.x * r1.zxy + float3(r0.x, r0.y, r0.w);                   // 244
    r6.z = -r6.w * r4.y - r6.z;                                          // 245
    r6.xy = r6.w * r4.xz + r6.yx;                                        // 246
    r6 = XeCube(r6.xyz);                                                 // 247
    { float v = r6.w; r0.x = rcp(abs(r6.z)); r0.w = v; }                 // 248
    r0.xy = r6.yx * r0.x + C252.z;                                       // 249
    r6.xyz = TF14(float3(r0.x, r0.y, r0.w)).xyz;                         // 250
    r6.xyz = r6.xyz * r6.xyz;                                            // 251
    r2.xyz = r5.xyz * r6.xyz + r2.xyz;                                   // 252
  }
  r6.x = r0.z - C67.x;                                                   // 253
  r6.yzw = r2.xyz * C49.xyz;                                             // 254
  if (r6.x > 0.0) {                                                      // p0
    { float v = saturate(dot(-r10.zxy, C66.zxy)); r0.y = C67.w * r6.x; r0.x = v; }  // 255
    r1.xyz = TF5(r0.y).xyz;                                              // 256
    r0.xyz = TF4(r0.x).xyz;                                              // 257
    r0.xyz = r0.xyz - C68.xyz;                                           // 258
    { float3 v = C254.x - r1.xyz; r0.w = C28.y * r7.x; r2.xyz = v; }     // 259
    { float3 v = r0.w * r2.zyx; r6.x = saturate(C67.z * r6.x); r2.xyz = v; }  // 260
    r0.xyz = r6.x * r0.zyx + C68.zyx;                                    // 261
    r0.xyz = r2.zyx * r0.zyx - r6.yzw;                                   // 262
    r0.xyz = r6.yzw * r1.xyz + r0.xyz;                                   // 263
    r6.yzw = r0.xyz * C28.x + r6.yzw;                                    // 264
  }
  r0.xyz = C20.w * C26.xyz;                                              // 265
  float4 o = float4(r0.xyz * r6.yzw, C26.w * r7.x);                      // 266
#if SPARROW
  if (SparrowDebug() == 3) o.xyz = SparrowVisDebug(sky_vis);  // red open, green closed
#endif
  AlphaTest(o.w);
  coverage = AlphaToMask(o.w, input.position.xy);
  return o * xe_color_exp_bias.x;
}
