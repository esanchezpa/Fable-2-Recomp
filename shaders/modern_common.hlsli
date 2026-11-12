// Helpers shared by the Modern-graphics ground rewrites (terrain, ground,
// grass, splat). Include after xe_common.hlsli.
#ifndef MODERN_COMMON_HLSLI
#define MODERN_COMMON_HLSLI

// Size of the texture actually bound for this shader's texture binding:
// the texture pack's replacement (2x-4x the game's) when there is one, else
// the game's own. TextureSize() gives the game's (guest) size.
float2 HostTextureSize(uint binding) {
  uint w, h, layers, levels;
  xe_textures_2d[NonUniformResourceIndex(DescriptorIndex(2 + 3 * binding))]
      .GetDimensions(0, w, h, layers, levels);
  return float2(w, h);
}

// Smooth bilinear: the 2x2 texel-centre reads (level 0) around the point,
// blended with smoothstep weights, on the bound texture's own texel grid.
// The game point-samples its small ground colour and light maps, which
// shows every texel as a hard square at the higher render resolution; this
// is continuous and, reaching only one texel, does not cross into the next
// tile of a light-map atlas (a 4x4 cubic did, as dark seams).
float4 SmoothFetch(uint tf, uint binding, float2 uv) {
  float2 size = HostTextureSize(binding);
  float2 p = uv * size - 0.5;
  float2 i = floor(p), f = p - i;
  f = f * f * (3.0 - 2.0 * f);
  float4 a = FetchLevel(tf, binding, (i + float2(0.5, 0.5)) / size, false, 0.0);
  float4 b = FetchLevel(tf, binding, (i + float2(1.5, 0.5)) / size, false, 0.0);
  float4 c = FetchLevel(tf, binding, (i + float2(0.5, 1.5)) / size, false, 0.0);
  float4 d = FetchLevel(tf, binding, (i + float2(1.5, 1.5)) / size, false, 0.0);
  return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
}

// 0..1 when the bound texture is magnified (one of its texels covers more
// than half a pixel ... fully from 1 texel = 1 pixel on).
float Magnification(uint binding, float2 uv) {
  float2 tex = HostTextureSize(binding);
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
