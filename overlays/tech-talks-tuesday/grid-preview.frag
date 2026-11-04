#version 300 es
precision highp float;
in vec2 screenUV;out vec4 outputColor;
uniform sampler2D sceneA;uniform sampler2D sceneB;uniform float progress;
float saturate(float x){return clamp(x,0.,1.);}
vec4 sampleScene(vec2 uv,float raw){return raw<0.47?textureLod(sceneA,uv,0.):textureLod(sceneB,uv,0.);}
/* Shared rendering body: HLSL for OBS, translated to GLSL by
   tools/build-tuesday-grid.py. Each host supplies sampleScene(uv, raw),
   a single-level sample (it is called inside the march, where a sample
   with gradients is not allowed), and CUT, the progress at which the
   scene underneath changes.

   The reference is a "3D grid transitions" pack (the user's recording of
   2026-11-03): the picture turns into a wire mesh lifted by its own
   brightness, tilts back into a floor until it is a glowing line edge-on,
   and the next picture rises out of that line and settles flat. The cut
   happens inside the line, where the whole frame is a few pixels tall.

   Units: the frame is the rectangle [-aspect, aspect] x [-1, 1] at z = 0,
   seen from (0, 0, CAM) so that, flat, it fills the screen exactly. */

#define CAM 5.0
#define STEPS 36
#define REFINE 6
/* Phosphor (ADR 0023): the line's glow, its hot core, and the ground. */
#define GLOW vec3(0.29, 0.87, 0.50)
#define GLOW_CORE vec3(0.85, 1.0, 0.90)
#define GROUND vec3(0.043, 0.067, 0.051)

float ease(float a, float b, float x) { return smoothstep(a, b, x); }

/* Tilt, in radians: fast to about 35 degrees, a slow drift, then fast to
   edge-on; held through the cut; back to about 33 degrees, a slow drift,
   and flat. Never reaches 90 degrees, so the camera stays above the floor. */
float tiltAt(float raw) {
  if(raw < 0.42) {
    float a = raw / 0.42;
    return 0.60 * ease(0.0, 0.32, a) + 0.12 * a + 0.83 * ease(0.58, 1.0, a);
  }
  if(raw < 0.54) return 1.55;
  float b = (raw - 0.54) / 0.46;
  return (1.55 - 0.93 * ease(0.0, 0.30, b) - 0.07 * b) * (1.0 - ease(0.66, 1.0, b));
}

float lumaOf(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

/* The mesh: one vertex per grid intersection, raised by the brightness
   under it, bilinear in between, like a displaced plane in 3D software.
   Vertices are clamped a pixel inside the picture: OBS samples past its
   edge as transparent black, and a filtered sample on the edge itself is
   half that black, either of which drops the rim toward the floor and
   stands it up as a wall. */
/* The waves: two travelling ripples across the sheet, so a page with no
   light and dark to raise still moves like cloth as it flips. */
float waveAt(vec2 local, float raw) {
  float phase = raw * 10.0;
  return 0.62 * sin(local.x * 2.3 + local.y * 0.7 - phase) + 0.38 * sin(local.y * 3.4 - local.x * 1.1 + phase * 0.8);
}

float heightAt(vec2 local, float aspect, vec2 cells, float relief, float wave, float raw) {
  vec2 uv = vec2(local.x / aspect * 0.5 + 0.5, 0.5 - local.y * 0.5);
  vec2 c = uv * cells;
  vec2 i = floor(c);
  vec2 f = c - i;
  vec2 lo = vec2(0.001, 0.001);
  vec2 hi = vec2(0.999, 0.999);
  float h00 = lumaOf(sampleScene(clamp(i / cells, lo, hi), raw).rgb);
  float h10 = lumaOf(sampleScene(clamp((i + vec2(1.0, 0.0)) / cells, lo, hi), raw).rgb);
  float h01 = lumaOf(sampleScene(clamp((i + vec2(0.0, 1.0)) / cells, lo, hi), raw).rgb);
  float h11 = lumaOf(sampleScene(clamp((i + vec2(1.0, 1.0)) / cells, lo, hi), raw).rgb);
  float h = mix(mix(h00, h10, f.x), mix(h01, h11, f.x), f.y);
  return relief * pow(h, 1.4) + wave * waveAt(local, raw);
}

vec4 renderGrid(vec2 screenUV, float raw, float aspect, float columns, float reliefMax, float waveMax) {
  if(raw <= 0.001 || raw >= 0.999) return sampleScene(screenUV, raw);

  float theta = tiltAt(raw);
  float sn = sin(theta);
  float cs = cos(theta);
  /* How far into the move: wires fade in at the start and out at the end;
     the glow belongs to the line. */
  float gridAmount = ease(0.0, 0.08, raw) * (1.0 - ease(0.92, 1.0, raw));
  float relief = reliefMax * ease(0.0, 0.16, raw) * (1.0 - ease(0.88, 1.0, raw));
  float wave = waveMax * ease(0.0, 0.14, raw) * (1.0 - ease(0.86, 1.0, raw));
  float edgeOn = ease(0.30, 0.42, raw) * (1.0 - ease(0.54, 0.66, raw));
  float swing = sin(raw * 3.14159265);

  /* Screen ray, up positive, with a slight roll toward the cut. */
  vec2 ndc = vec2((screenUV.x * 2.0 - 1.0) * aspect, 1.0 - screenUV.y * 2.0);
  float roll = -0.035 * swing;
  ndc = vec2(ndc.x * cos(roll) - ndc.y * sin(roll), ndc.x * sin(roll) + ndc.y * cos(roll));

  /* The floor is pushed back as it tilts so its near edge stays about
     full width, and dropped a little so the line sits just under centre. */
  vec3 centre = vec3(0.0, -0.06 * sn, -0.85 * sn);
  vec3 q = vec3(0.0, 0.0, CAM) - centre;
  vec3 d = vec3(ndc.x, ndc.y, -CAM);
  /* Into the floor's own frame: u across, v up the picture, h off it. */
  vec3 ro = vec3(q.x, q.y * cs - q.z * sn, q.y * sn + q.z * cs);
  vec3 rd = vec3(d.x, d.y * cs - d.z * sn, d.y * sn + d.z * cs);

  vec3 ground = GROUND;
  float lineY = (centre.y + 0.05 * relief / max(reliefMax, 0.001)) * CAM / (CAM - centre.z);
  float halfWidth = aspect * CAM / (CAM - centre.z);
  float across = 1.0 - ease(halfWidth - 0.05, halfWidth + 0.35, abs(ndc.x));
  float dy = abs(ndc.y - lineY);
  vec3 glow = (GLOW * exp(-dy / 0.07) * 0.55 + GLOW_CORE * exp(-dy / 0.014) * 0.6) * edgeOn * across;

  /* The slab the mesh lives in, h from relief plus the wave crest down to
     the wave trough, clipped to the picture's rectangle. */
  float enter = (relief + wave + 0.0005 - ro.z) / rd.z;
  float leave = (-wave - 0.0005 - ro.z) / rd.z;
  float sx = rd.x >= 0.0 ? 1.0 : -1.0;
  float sy = rd.y >= 0.0 ? 1.0 : -1.0;
  float ix = 1.0 / (rd.x + sx * 0.000001);
  float iy = 1.0 / (rd.y + sy * 0.000001);
  float ax = (-aspect - ro.x) * ix;
  float bx = (aspect - ro.x) * ix;
  float ay = (-1.0 - ro.y) * iy;
  float by = (1.0 - ro.y) * iy;
  enter = max(enter, max(min(ax, bx), min(ay, by)));
  leave = min(leave, min(max(ax, bx), max(ay, by)));
  if(enter >= leave) return vec4(ground + glow, 1.0);

  /* The mesh is a sheet with no thickness: a ray hits it only by crossing
     it from above. One that comes in under the sheet, past the picture's
     edge, sees nothing, so a raised edge floats rather than standing on a
     wall. */
  vec2 cells = vec2(columns, floor(columns / aspect + 0.5));
  float found = 0.0;
  float above = 0.0;
  float before = enter;
  float after = leave;
  for(int i = 0; i <= STEPS; i++) {
    float s = mix(enter, leave, float(i) / float(STEPS));
    vec3 p = ro + rd * s;
    if(p.z <= heightAt(p.xy, aspect, cells, relief, wave, raw)) {
      if(above > 0.5) {
        found = 1.0;
        after = s;
        break;
      }
      above = 0.0;
    } else {
      above = 1.0;
    }
    before = s;
  }
  if(found < 0.5) return vec4(ground + glow, 1.0);
  for(int k = 0; k < REFINE; k++) {
    float s = (before + after) * 0.5;
    vec3 p = ro + rd * s;
    if(p.z <= heightAt(p.xy, aspect, cells, relief, wave, raw)) after = s;
    else before = s;
  }
  vec3 hit = ro + rd * after;
  vec2 uv = vec2(hit.x / aspect * 0.5 + 0.5, 0.5 - hit.y * 0.5);
  vec3 tex = sampleScene(uv, raw).rgb;
  float luma = lumaOf(tex);

  /* Wires on the grid lines, about a third of a cell wide. Where cells
     shrink under a pixel, they blend to the coverage they would average to. */
  vec2 c = uv * cells;
  vec2 g = abs(fract(c + 0.5) - 0.5);
  vec2 px = clamp((abs(dFdx(c)) + abs(dFdy(c))) * 0.7, vec2(0.02, 0.02), vec2(0.6, 0.6));
  float w = 0.17;
  vec2 line2 = 1.0 - smoothstep(vec2(w, w) - px, vec2(w, w) + px, g);
  float wire = max(line2.x, line2.y);
  float fine = saturate(max(px.x, px.y) * 2.2 - 0.6);
  wire = mix(wire, 0.55, fine);

  /* Wires keep the picture's colour, a little brighter; the line glows. */
  vec3 wireColour = tex * 1.06 + (vec3(1.0, 1.0, 1.0) - tex) * (0.04 + 0.16 * luma * luma);
  wireColour = mix(wireColour, GLOW_CORE, 0.45 * edgeOn);
  wireColour *= 1.0 + 0.6 * edgeOn;
  vec3 gap = tex * 0.12;
  vec3 mesh = mix(gap, wireColour, wire) + glow;
  vec3 col = mix(tex, mesh, gridAmount);
  return vec4(col, 1.0);
}

void main(){outputColor=renderGrid(screenUV,clamp(progress,0.,1.),1920./1080.,96.,.18,.16);}
