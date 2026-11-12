// Helpers shared by the Modern-graphics ground rewrites (terrain, ground,
// grass, splat). Include after xe_common.hlsli.
#ifndef MODERN_COMMON_HLSLI
#define MODERN_COMMON_HLSLI

// Smooth bilinear: the 2x2 texel-centre reads (level 0) around the point,
// blended with smoothstep weights. The game point-samples its small ground
// colour and light maps, which shows every texel as a hard square at the
// higher render resolution; this is continuous and, reaching only one
// texel, does not cross into the next tile of a light-map atlas (a 4x4
// cubic did, as dark seams).
float4 SmoothFetch(uint tf, uint binding, float2 uv) {
  float2 size = TextureSize(tf);
  float2 p = uv * size - 0.5;
  float2 i = floor(p), f = p - i;
  f = f * f * (3.0 - 2.0 * f);
  float4 a = FetchLevel(tf, binding, (i + float2(0.5, 0.5)) / size, false, 0.0);
  float4 b = FetchLevel(tf, binding, (i + float2(1.5, 0.5)) / size, false, 0.0);
  float4 c = FetchLevel(tf, binding, (i + float2(0.5, 1.5)) / size, false, 0.0);
  float4 d = FetchLevel(tf, binding, (i + float2(1.5, 1.5)) / size, false, 0.0);
  return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
}

// 0..1 when the map of fetch constant tf is magnified (a texel covers more
// than half a pixel ... fully at 1 texel = 1 pixel and beyond).
float Magnification(uint tf, float2 uv) {
  float2 tex = TextureSize(tf);
  float2 fx = ddx(uv) * tex, fy = ddy(uv) * tex;
  return saturate((1.0 - sqrt(max(dot(fx, fx), dot(fy, fy)))) * 2.0);
}

float Hash3(float3 p) {
  p = frac(p * 0.1031);
  p += dot(p, p.yzx + 33.33);
  return frac((p.x + p.y) * p.z);
}
// Smooth value noise in 0..1.
float Noise3(float3 p) {
  float3 i = floor(p), f = frac(p);
  f = f * f * (3.0 - 2.0 * f);
  float4 a = float4(Hash3(i), Hash3(i + float3(1, 0, 0)), Hash3(i + float3(0, 1, 0)), Hash3(i + float3(1, 1, 0)));
  float4 b = float4(Hash3(i + float3(0, 0, 1)), Hash3(i + float3(1, 0, 1)), Hash3(i + float3(0, 1, 1)), Hash3(i + float3(1, 1, 1)));
  float4 c = lerp(a, b, f.z);
  float2 d = lerp(c.xy, c.zw, f.y);
  return lerp(d.x, d.y, f.x);
}

#endif
