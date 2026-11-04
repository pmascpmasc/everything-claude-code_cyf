// Visual preflight for the USD course (stand-in for the article's ovrtx pass; no RTX GPU here).
// Renders colour + semantic views from the authored cameras, counts semantic pixels per class,
// writes SimReady thumbnails, and saves out/reports/preflight_report.json.
//
//   node render.mjs                      # three.js from cdn.jsdelivr.net
//   THREE_LOCAL=/path/to/node_modules/three node render.mjs   # offline: serve three.js from disk
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, '..', 'out');
const REP = path.join(OUT, 'reports');
const IMG = path.join(REP, 'preflight');
fs.mkdirSync(IMG, { recursive: true });

const CDN = 'https://cdn.jsdelivr.net/npm/three@0.160.0/';
// One fixed colour per class so semantic renders are comparable between runs.
const PALETTE = {
  floor: '#3b3b3b', hurdle: '#ffd400', mud: '#8b4513', curb: '#b0b0b0', stairs: '#1f77b4', platform: '#4a90d9',
  ramp: '#17becf', traffic_cone: '#ff7f0e', barrier: '#d62728', barrier_bar: '#e377c2', pitch_roll_ramp: '#2ca02c',
  gravel: '#9467bd', wall: '#7f7f7f', start_line: '#ffffff', robot_target: '#00ff7f', bypass_lane: '#bcbd22', null: '#ff00ff',
};
const STATION_TARGETS = {
  fpv_station_1: ['hurdle'], fpv_station_2: ['mud'], fpv_station_3: ['stairs'],
  fpv_station_5: ['barrier', 'barrier_bar', 'traffic_cone'], fpv_station_6: ['pitch_roll_ramp'], fpv_station_7: ['gravel'],
};

const PAGE = `<!doctype html><html><body style="margin:0;background:#000">
<script type="importmap">{"imports":{"three":"${CDN}build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
const PALETTE = ${JSON.stringify(PALETTE)};
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
document.body.appendChild(renderer.domElement);
let groups = { color: null, semantic: null };
window.loadScene = (data) => {
  for (const mode of ['color', 'semantic']) {
    const scene = new THREE.Scene();
    for (const m of data.meshes) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(m.positions, 3));
      g.setIndex(m.indices); g.computeVertexNormals();
      const mat = mode === 'semantic'
        ? new THREE.MeshBasicMaterial({ color: PALETTE[m.label] || PALETTE.null })
        : new THREE.MeshStandardMaterial({ color: new THREE.Color(...(m.color || [1, 0, 1])), roughness: 0.8, flatShading: true });
      scene.add(new THREE.Mesh(g, mat));
    }
    if (mode === 'color') {
      scene.background = new THREE.Color(0xbfd3dc);
      scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f84, 1.2));
      const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(30, -60, 90); scene.add(sun);
    } else scene.background = new THREE.Color(0x000000);
    groups[mode] = scene;
  }
  return data.meshes.length;
};
window.renderView = (cam, mode, w, h) => {
  renderer.setSize(w, h, false);
  const c = new THREE.PerspectiveCamera(cam.fov_deg, w / h, cam.near || 0.05, 2000);
  c.up.set(0, 0, 1); c.position.set(...cam.position); c.lookAt(...cam.target);
  renderer.render(groups[mode], c);
  const out = { png: renderer.domElement.toDataURL('image/png') };
  if (mode === 'semantic') {
    const gl = renderer.getContext(), px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    // output is sRGB-encoded, so compare against the palette's hex values with a small tolerance
    const pal = Object.entries(PALETTE).map(([k, v]) => [k, parseInt(v.slice(1, 3), 16), parseInt(v.slice(3, 5), 16), parseInt(v.slice(5, 7), 16)]);
    const counts = {}, memo = {};
    for (let i = 0; i < px.length; i += 4) {
      const key = px[i] + ',' + px[i + 1] + ',' + px[i + 2];
      let k = memo[key];
      if (k === undefined) {
        k = px[i] + px[i + 1] + px[i + 2] === 0 ? 'background' : 'other';
        let best = 13;
        for (const [name, r, g, b] of pal) { const d = Math.abs(px[i] - r) + Math.abs(px[i + 1] - g) + Math.abs(px[i + 2] - b); if (d < best) { best = d; k = name; } }
        memo[key] = k;
      }
      counts[k] = (counts[k] || 0) + 1;
    }
    out.counts = counts;
  } else {
    const gl = renderer.getContext(), px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    let s = 0; for (let i = 0; i < px.length; i += 4) s += 0.2126*px[i] + 0.7152*px[i+1] + 0.0722*px[i+2];
    out.luminance = s / (w * h * 255);
  }
  return out;
};
window.ready = true;
</script></body></html>`;

const save = (file, dataUrl) => fs.writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));
const fitCamera = (positions) => {
  const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
  for (let i = 0; i < positions.length; i += 3) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], positions[i + k]); hi[k] = Math.max(hi[k], positions[i + k]); }
  const c = lo.map((v, k) => (v + hi[k]) / 2), r = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2 || 1;
  return { position: [c[0] + r * 1.4, c[1] - r * 1.7, c[2] + r * 1.1], target: c, fov_deg: 35, near: r / 100 };
};

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage();
if (process.env.THREE_LOCAL) {
  await page.route(`${CDN}**`, (route) => route.fulfill({ path: path.join(process.env.THREE_LOCAL, route.request().url().slice(CDN.length)), contentType: 'text/javascript' }));
}
await page.setContent(PAGE);
await page.waitForFunction(() => window.ready === true, null, { timeout: 60000 });

const checks = [];
const check = (id, pass, detail) => checks.push({ id, status: pass ? 'pass' : 'fail', detail });

// course views
const course = JSON.parse(fs.readFileSync(path.join(OUT, 'preview', 'course.json'), 'utf8'));
await page.evaluate((d) => window.loadScene(d), course);
const W = 960, H = 540, views = {};
for (const cam of course.cameras) {
  const col = await page.evaluate(([c, w, h]) => window.renderView(c, 'color', w, h), [cam, W, H]);
  const sem = await page.evaluate(([c, w, h]) => window.renderView(c, 'semantic', w, h), [cam, W, H]);
  save(path.join(IMG, `${cam.name}_color.png`), col.png);
  save(path.join(IMG, `${cam.name}_semantic.png`), sem.png);
  views[cam.name] = { luminance: +col.luminance.toFixed(3), semantic_pixels: sem.counts };
}
// 1. every station target is visible from its robot-eye camera
for (const [cam, classes] of Object.entries(STATION_TARGETS)) {
  const px = classes.reduce((a, c) => a + (views[cam]?.semantic_pixels[c] || 0), 0), frac = px / (W * H);
  check(`target_visible.${cam}`, frac >= 0.01, `${classes.join('/')} covers ${(frac * 100).toFixed(1)}% of the robot-eye view`);
}
// 2. no unlabeled geometry rendered anywhere
const unl = Object.values(views).reduce((a, v) => a + (v.semantic_pixels.null || 0) + (v.semantic_pixels.other || 0), 0);
check('labels_attached', unl === 0, `${unl} pixels without a known class label across all views`);
// 3. every mesh renders with an authored material
const noMat = course.meshes.filter((m) => !m.color).length;
check('materials_render', noMat === 0, `${noMat} meshes without a bound UsdPreviewSurface colour`);
// 4. lighting plausible in the colour views
const lum = Object.entries(views).map(([k, v]) => [k, v.luminance]);
check('lighting_plausible', lum.every(([, l]) => l > 0.15 && l < 0.9), lum.map(([k, l]) => `${k} ${l}`).join(', '));
// 5. robot-eye cameras are not clipped by or buried in geometry (ground must not fill the frame)
const buried = Object.entries(views).filter(([k, v]) => k.startsWith('fpv') && (v.semantic_pixels.floor || 0) / (W * H) > 0.95);
check('camera_not_blocked', buried.length === 0, buried.length ? `blocked: ${buried.map(([k]) => k).join(', ')}` : 'all robot-eye views see past the ground');

// 6. object scale against the briefing, from the asset extents
const idx = JSON.parse(fs.readFileSync(path.join(OUT, 'assets_index.json'), 'utf8'));
const spec = JSON.parse(fs.readFileSync(path.join(HERE, '..', 'course_spec.json'), 'utf8'));
const scaleOk = Math.abs(idx.traffic_cone.extents[2] - spec.cone.height) < 0.01 &&
  spec.hurdles.height.every((h) => Math.abs(idx[`hurdle_h${String(Math.round(h * 100)).padStart(2, '0')}`].extents[2] - h) < 0.005);
check('object_scale', scaleOk, `cone ${idx.traffic_cone.extents[2]} m (spec ${spec.cone.height}); hurdles ${spec.hurdles.height.map((h) => idx[`hurdle_h${String(Math.round(h * 100)).padStart(2, '0')}`].extents[2]).join('/')} m`);

// SimReady thumbnails (SR.002): <asset>/simready_usd/.thumbs/256x256/<usd file>.png
for (const [name, meta] of Object.entries(idx)) {
  const d = JSON.parse(fs.readFileSync(path.join(OUT, 'preview', `asset_${name}.json`), 'utf8'));
  await page.evaluate((x) => window.loadScene(x), d);
  const cam = fitCamera(d.meshes.flatMap((m) => m.positions));
  const r = await page.evaluate(([c]) => window.renderView(c, 'color', 256, 256), [cam]);
  const usd = path.join(OUT, meta.path), dir = path.join(path.dirname(usd), '.thumbs', '256x256');
  fs.mkdirSync(dir, { recursive: true });
  save(path.join(dir, `${path.basename(usd)}.png`), r.png);
  save(path.join(IMG, `thumb_${name}.png`), r.png);
}
await browser.close();

const report = { renderer: 'three.js 0.160 (WebGL, SwiftShader) — stand-in for ovrtx', image_size: [W, H], checks, views };
fs.writeFileSync(path.join(REP, 'preflight_report.json'), JSON.stringify(report, null, 2));
for (const c of checks) console.log(`${c.status.toUpperCase().padEnd(4)} ${c.id.padEnd(30)} ${c.detail}`);
console.log(`preflight: ${checks.filter((c) => c.status === 'pass').length}/${checks.length} pass`);
process.exit(checks.every((c) => c.status === 'pass') ? 0 : 1);
