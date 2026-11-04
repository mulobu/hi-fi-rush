/* Prototype for obs-shaderfilter's User-defined shader TRANSITION.
   Samples real scene A/B textures on a perspective-projected curved surface.
   No prerecorded video and no HTML grid covering an unchanged video.
   Requires plugin + distinct scene compositions. NOT yet compiled in OBS.
   Use ~1500 ms transition duration. */
uniform texture2d image_a;
uniform texture2d image_b;
uniform float transition_time = 0.0;
uniform bool convert_linear = true;
uniform float Grid_Columns <
  string label = "Grid columns";
  float minimum = 40.0;
  float maximum = 140.0;
  float step = 1.0;
> = 96.0;
uniform float Bend <
  string label = "Surface bend";
  float minimum = 0.0;
  float maximum = 1.0;
  float step = 0.01;
> = 0.65;

float surfaceDepth(float2 p, float t, float strength) {
  return strength * sin(p.x * 2.6 + t * 5.0) * cos(p.y * 1.8 - t * 2.0);
}

float raySurface(float3 origin, float3 direction, float distance, float t, float strength) {
  float3 p = origin + direction * distance;
  return p.z - surfaceDepth(p.xy, t, strength);
}

float4 mainImage(VertData v_in) : TARGET {
  float t = saturate(transition_time);
  if(t <= 0.001) return image_a.Sample(textureSampler, v_in.uv);
  if(t >= 0.999) return image_b.Sample(textureSampler, v_in.uv);
  float energy = sin(t * 3.14159265);
  float aspect = uv_size.x / uv_size.y;
  float2 ndc = (v_in.uv * 2.0 - 1.0) * float2(aspect, 1.0);
  float3 origin = float3(0.0, 0.0, 2.5);
  float3 direction = float3(ndc, -2.5);
  float lo = 0.6;
  float hi = 1.4;
  float strength = energy * Bend;
  /* Solve ray/heightfield intersection. At most .65 depth, so these
     bounds bracket the surface. A real perspective deformation. */
  for(int i = 0; i < 12; i++) {
    float mid = (lo + hi) * 0.5;
    if(raySurface(origin, direction, mid, t, strength) > 0.0) lo = mid;
    else hi = mid;
  }
  float3 hit = origin + direction * ((lo + hi) * 0.5);
  float height = lerp(1.0, 0.16, energy * energy);
  float width = lerp(1.0, 0.91, energy);
  float2 uv = hit.xy / float2(aspect * width, height) * 0.5 + 0.5;
  float3 background = float3(0.055, 0.028, 0.065);
  float3 col = background;
  if(uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0) {
    float blend = smoothstep(0.44, 0.56, t);
    float3 tex = lerp(image_a.Sample(textureSampler,uv).rgb,image_b.Sample(textureSampler,uv).rgb,blend);
    float2 cells = float2(Grid_Columns, Grid_Columns / aspect);
    float2 grid = abs(frac(uv * cells + 0.5) - 0.5);
    float2 derivative = max(abs(ddx(uv)) + abs(ddy(uv)), float2(0.0001,0.0001)) * cells;
    float wireMask = 1.0 - saturate(min(grid.x / derivative.x, grid.y / derivative.y));
    float3 tint = lerp(float3(1.0,0.36,0.66),float3(0.50,0.91,0.87),saturate(uv.x * 0.7 + t * 0.3));
    float3 wires = lerp(tint * 0.45, tex * 1.35 + tint * 0.25, 0.75);
    float wireAmount = smoothstep(0.0, 0.40, energy);
    col = lerp(tex, background + wires * wireMask, wireAmount);
  }
  if(convert_linear) col = srgb_nonlinear_to_linear(col);
  return float4(col,1.0);
}
