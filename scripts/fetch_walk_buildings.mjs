import { spawn } from 'node:child_process';
import fs from 'node:fs';

// Real OpenStreetMap urban/town districts along Danny's walk.
// Queries multiple adjacent neighborhood tiles at zoom 14.7 so towns form
// cohesive, recognizable street fabrics rather than sparse isolated blocks!
const CLUSTERS = [
  { id: 'amarillo_tascosa', realm: 1, label: 'Tascosa High School & Wolflin/Amarillo Neighborhoods', lon: -101.8825, lat: 35.2038, radiusM: 1250, maxKeep: 900, minSpan: 5.0, defH: 5.5 },
  { id: 'amarillo_bivins',  realm: 1, label: 'Dick Bivins Stadium & East Amarillo Blocks',           lon: -101.7907, lat: 35.1955, radiusM: 1150, maxKeep: 750, minSpan: 5.0, defH: 6.5 },
  { id: 'tucumcari_rt66',   realm: 2, label: 'Historic Route 66 Boulevard, Tucumcari NM',            lon: -103.7250, lat: 35.1717, radiusM: 950,  maxKeep: 500, minSpan: 5.5, defH: 6.0 },
  { id: 'monument_homes',   realm: 3, label: 'Colorado Springs & Foothills Neighborhoods',           lon: -104.7815, lat: 38.8952, radiusM: 1100, maxKeep: 700, minSpan: 5.5, defH: 6.8 },
  { id: 'paris_notredame',  realm: 4, label: 'Notre-Dame & Île de la Cité, Paris',                   lon: 2.3499,    lat: 48.8530, radiusM: 720,  maxKeep: 650, minSpan: 6.0, defH: 19.0 },
  { id: 'rome_colosseum',   realm: 4, label: 'Colosseum & Historic Center, Rome',                    lon: 12.4922,   lat: 41.8902, radiusM: 720,  maxKeep: 600, minSpan: 6.0, defH: 18.0 },
  { id: 'denver_milehigh',  realm: 7, label: 'Empower Field at Mile High & West Denver',             lon: -105.0201, lat: 39.7439, radiusM: 850,  maxKeep: 500, minSpan: 6.0, defH: 12.0 },
];

const PORT = 9251;
const chrome = spawn(
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--window-size=1600,1200',
    '--use-gl=angle',
    '--use-angle=metal',
    `--user-data-dir=/tmp/ofm_bldg_dense_${Date.now()}`,
    'http://localhost:8770/#tour',
  ],
  { stdio: 'ignore' }
);

let wsUrl;
for (let i = 0; i < 30; i++) {
  try {
    const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
    const p = tabs.find((x) => x.type === 'page' && x.url.includes('8770') && x.webSocketDebuggerUrl);
    if (p) { wsUrl = p.webSocketDebuggerUrl; break; }
  } catch {}
  await new Promise((r) => setTimeout(r, 250));
}
await new Promise((r) => setTimeout(r, 1500));

const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener('open', r));

const call = (expression) => {
  ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, awaitPromise: true, returnByValue: true } }));
  return new Promise((r) => ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.id === 1) r(m.result?.result?.value ?? m);
  }, { once: true }));
};

const result = await call(`(async () => {
  const { loadMapLibre } = await import('http://localhost:8770/js/globe3d.js');
  const maplibregl = await loadMapLibre();
  const div = document.createElement('div');
  div.style.cssText = 'position:fixed;inset:0;width:1600px;height:1200px;';
  document.body.appendChild(div);
  const map = new maplibregl.Map({
    container: div,
    style: {
      version: 8,
      sources: { ofm: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' } },
      layers: [{ id: 'b', type: 'fill', source: 'ofm', 'source-layer': 'building', paint: { 'fill-color': '#fff' } }]
    },
    center: [-101.8825, 35.2038],
    zoom: 14.6
  });
  await new Promise(r => map.once('load', r));

  const clusters = ${JSON.stringify(CLUSTERS)};
  const out = [];
  for (const c of clusters) {
    const mPerLat = 111132.0;
    const mPerLon = 111320.0 * Math.cos(c.lat * Math.PI / 180);
    const seen = new Set();
    const footprints = [];

    // Pan across a 2x2 neighborhood grid around the center at zoom 15.0 so all nearby blocks load!
    const offsets = [[0, 0], [-0.005, -0.004], [0.005, -0.004], [-0.005, 0.004], [0.005, 0.004]];
    for (const [dlon, dlat] of offsets) {
      map.jumpTo({ center: [c.lon + dlon, c.lat + dlat], zoom: 15.0 });
      await new Promise(r => map.once('idle', r));
      const feats = map.querySourceFeatures('ofm', { sourceLayer: 'building' });
      for (const f of feats) {
        const rings = f.geometry.type === 'Polygon' ? [f.geometry.coordinates[0]]
                    : f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates.map(p => p[0]) : [];
        for (const ring of rings) {
          if (!ring || ring.length < 4) continue;
          let cx = 0, cy = 0;
          const pts = [];
          for (let i = 0; i < ring.length - 1; i++) {
            const dx = +((ring[i][0] - c.lon) * mPerLon).toFixed(1);
            const dy = +((ring[i][1] - c.lat) * mPerLat).toFixed(1);
            cx += dx; cy += dy;
            pts.push([dx, dy]);
          }
          cx /= pts.length; cy /= pts.length;
          const dist = Math.hypot(cx, cy);
          if (dist > c.radiusM) continue;
          const key = Math.round(cx * 0.5) + ':' + Math.round(cy * 0.5);
          if (seen.has(key)) continue;
          seen.add(key);
          const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
          const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
          if (span < c.minSpan) continue;
          const slim = pts.length > 22 ? pts.filter((_, i) => i % Math.ceil(pts.length / 20) === 0) : pts;
          const rawH = Number(f.properties?.render_height);
          // Give residential homes natural slight height variation (4.8..7.2m) instead of identical flat boxes
          const jitter = 0.86 + ((Math.abs(Math.round(cx * 7 + cy * 13)) % 29) / 100.0);
          const h = Math.max(4.2, Math.min(64, rawH > 0 ? rawH : c.defH * jitter));
          footprints.push({ pts_m: slim, h_m: +h.toFixed(1), span_m: +span.toFixed(1), dist_m: Math.round(dist) });
        }
      }
    }
    // Sort primarily by proximity to center so we get a complete contiguous town neighborhood (houses + landmarks together!)
    footprints.sort((a, b) => (a.dist_m - b.dist_m) - (b.span_m > 35 ? 260 : 0) + (a.span_m > 35 ? 260 : 0));
    out.push({ id: c.id, realm: c.realm, label: c.label, footprints: footprints.slice(0, c.maxKeep) });
  }
  return out;
})()`);

for (const c of result) {
  console.log(`${c.id.padEnd(20)} | ${String(c.footprints.length).padStart(4)} real 3D OSM buildings`);
}
fs.writeFileSync('data/walk_buildings.json', JSON.stringify({ clusters: result }));
console.log('Saved data/walk_buildings.json');
ws.close();
chrome.kill();
