// Project Sparrow: frame data and the real sun shadow map for the material
// shaders, built with /D SPARROW=1 (tools/shaders/build_replace.py writes
// them to shaders/sparrow_replace; only the Sparrow edition loads that).
//
// The SDK (cvar sparrow_renderer) copies its sun shadow map (post_sun_map)
// into an R32_FLOAT texture at a fixed index of the bindless 2D table after
// the game's depth pre-pass, before the colour pass (sparrow_sun.cs.hlsl in
// the SDK):
//   rows 0 .. size-1  depth along the sun, reversed (larger = nearer the
//                     sun, 0 = nothing drawn there);
//   row size          frame data: 0-2 map centre, 3 signed half width
//                     (negative: up axis flipped), 4 half depth, 5 size,
//                     6 valid, 7 bias texels, 8-10 direction toward the
//                     sun, 11 frame counter, 12 debug mode (SDK cvar
//                     sparrow_debug: 1 = no sun wherever the map covers).
// Include after xe_common.hlsli.

#ifndef SPARROW_COMMON_HLSLI
#define SPARROW_COMMON_HLSLI

#define SPARROW_SUN_INDEX 3

// Map height in texels plus the frame row; 0 when the slot is still null.
uint SparrowSunRows() {
  uint w, h, n;
  xe_textures_2d[SPARROW_SUN_INDEX].GetDimensions(w, h, n);
  return h;
}

float SparrowMap(int2 p) {
  return xe_textures_2d[SPARROW_SUN_INDEX].Load(int4(p, 0, 0)).x;
}

// Sun visibility at a world position (1 lit, 0 shadowed, 3x3 PCF), or -1
// when the map is off or the point lies outside it: the caller then keeps
// the game's own shadow. n is the surface normal (for the normal offset);
// pass 0 for leaves, bark and ferns (no usable normal): the point then steps
// toward the sun instead.
float SparrowSunShadow(float3 pos, float3 n) {
  uint rows = SparrowSunRows();
  if (rows < 2u) return -1.0;
  int frame_row = int(rows) - 1;
  if (SparrowMap(int2(6, frame_row)) < 0.5) return -1.0;
  float3 centre = float3(SparrowMap(int2(0, frame_row)), SparrowMap(int2(1, frame_row)),
                         SparrowMap(int2(2, frame_row)));
  float signed_radius = SparrowMap(int2(3, frame_row));
  float depth_half = SparrowMap(int2(4, frame_row));
  float size = SparrowMap(int2(5, frame_row));
  float bias_texels = SparrowMap(int2(7, frame_row));
  float3 l = float3(SparrowMap(int2(8, frame_row)), SparrowMap(int2(9, frame_row)),
                    SparrowMap(int2(10, frame_row)));
  float radius = abs(signed_radius);
  if (radius <= 0.0 || depth_half <= 0.0 || size < 1.0) return -1.0;
  // The basis the SDK drew the map with (SetupSunMapFrame / post_ao.cs.hlsl).
  float3 ref = abs(l.x) < 0.9 ? float3(1.0, 0.0, 0.0) : float3(0.0, 1.0, 0.0);
  float3 right = normalize(cross(ref, l));
  float3 up = cross(l, right);
  if (signed_radius < 0.0) up = -up;
  float texel = 2.0 * radius / size;
  if (dot(n, n) < 0.25) n = l;
  float ndl = dot(n, l);
  // Facing away: no direct sun on the game's own terms either (skin wraps
  // past the terminator), so leave it to the game.
  if (ndl <= 0.0) return -1.0;
  // Normal offset, more of it at grazing angles where acne starts.
  float3 v = pos + n * (texel * bias_texels * (1.0 + 2.0 * (1.0 - ndl))) - centre;
  float x = dot(right, v) / radius, y = dot(up, v) / radius;
  float z = dot(l, v) / (2.0 * depth_half) + 0.5;
  float edge = max(abs(x), abs(y));
  if (edge >= 1.0 || z >= 1.0 || z <= 0.0) return -1.0;
  float2 uv = float2(x * 0.5 + 0.5, 0.5 - y * 0.5) * size - 0.5;
  float z_bias = texel * bias_texels / (2.0 * depth_half);
  int2 base = int2(floor(uv));
  float2 f = uv - float2(base);
  int max_texel = int(size) - 1;
  float lit[4][4];
  [unroll] for (int j = 0; j < 4; ++j) {
    [unroll] for (int i = 0; i < 4; ++i) {
      int2 q = clamp(base + int2(i - 1, j - 1), int2(0, 0), int2(max_texel, max_texel));
      lit[j][i] = SparrowMap(q) > z + z_bias ? 0.0 : 1.0;
    }
  }
  float sum = 0.0;
  [unroll] for (int j2 = 0; j2 < 3; ++j2) {
    [unroll] for (int i2 = 0; i2 < 3; ++i2) {
      float top = lerp(lit[j2][i2], lit[j2][i2 + 1], f.x);
      float bottom = lerp(lit[j2 + 1][i2], lit[j2 + 1][i2 + 1], f.x);
      sum += lerp(top, bottom, f.y);
    }
  }
  if (SparrowMap(int2(12, frame_row)) > 0.5) return 0.0;
  return sum / 9.0;
}

// The game's shadow value combined with the map's where the map covers the
// point: shadowed if either says so (the game's cascade holds casters off
// screen; ours reaches much further).
float SparrowSunOr(float game_shadow, float3 pos, float3 n) {
  float s = SparrowSunShadow(pos, n);
  return s < 0.0 ? game_shadow : min(game_shadow, s);
}

// No surface normal: leaves, bark, ferns.
float SparrowSunOrVolume(float game_shadow, float3 pos) {
  return SparrowSunOr(game_shadow, pos, float3(0.0, 0.0, 0.0));
}

#endif
