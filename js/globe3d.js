// 3D Landscape, Footpath & Horizon Choreography Engine
// MapLibre GL 5.24 on a 3D terrain globe with sunlit golden-hour relief,
// real backcountry hiking trails & mountain peaks draped over 3D topography,
// terracotta-and-parchment footpath arcs, tactile trailhead posts, and a
// gentle ridge-walk horizon camera.

const VERSION = '5.24.0';
const CDN = `https://cdn.jsdelivr.net/npm/maplibre-gl@${VERSION}/dist`;

let libPromise;
export function loadMapLibre() {
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  return (libPromise ||= new Promise((resolve, reject) => {
    const css = Object.assign(document.createElement('link'), {
      rel: 'stylesheet',
      href: `${CDN}/maplibre-gl.css`,
    });
    const js = Object.assign(document.createElement('script'), {
      src: `${CDN}/maplibre-gl.js`,
      async: true,
    });
    js.onload = () => resolve(window.maplibregl);
    js.onerror = () => reject(new Error('Could not load MapLibre GL'));
    document.head.append(css, js);
  }));
}

const escHtml = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const STYLE = {
  version: 8,
  projection: { type: 'globe' },
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {
    sat: {
      type: 'raster',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 18,
      attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
    },
    dem: {
      type: 'raster-dem',
      tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 13,
      encoding: 'terrarium',
      attribution: 'Terrain: AWS · Map data © OpenStreetMap',
    },
    hs: {
      type: 'raster-dem',
      tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 11,
      encoding: 'terrarium',
    },
    ofm: {
      type: 'vector',
      url: 'https://tiles.openfreemap.org/planet',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#2b382f' } },
    {
      id: 'sat',
      type: 'raster',
      source: 'sat',
      paint: {
        'raster-brightness-min': 0.04,
        'raster-brightness-max': 0.97,
        'raster-saturation': -0.05,
        'raster-contrast': 0.05,
        'raster-fade-duration': 0,
      },
    },
    {
      id: 'hillshade',
      type: 'hillshade',
      source: 'hs',
      paint: {
        'hillshade-exaggeration': 0.56,
        'hillshade-shadow-color': '#142636',
        'hillshade-highlight-color': 'rgba(255, 236, 198, 0.44)',
        'hillshade-accent-color': '#233a30',
        'hillshade-illumination-direction': 292,
      },
    },
    // Subtle sunlit streams & rivers draped on valleys
    {
      id: 'ofm-waterway',
      type: 'line',
      source: 'ofm',
      'source-layer': 'waterway',
      minzoom: 10.5,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': 'rgba(182, 220, 244, 0.52)',
        'line-width': ['interpolate', ['linear'], ['zoom'], 10.5, 0.7, 15, 2.3],
      },
    },
    // Quiet country lanes & neighborhood traces
    {
      id: 'ofm-lanes',
      type: 'line',
      source: 'ofm',
      'source-layer': 'transportation',
      minzoom: 12,
      filter: ['in', ['get', 'class'], ['literal', ['secondary', 'tertiary', 'minor', 'service']]],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': 'rgba(248, 236, 214, 0.22)',
        'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.6, 16, 2.0],
      },
    },
    // Real backcountry hiking footpaths & 4WD tracks draped over 3D ridges
    {
      id: 'ofm-trails-casing',
      type: 'line',
      source: 'ofm',
      'source-layer': 'transportation',
      minzoom: 11,
      filter: ['in', ['get', 'class'], ['literal', ['path', 'track']]],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': 'rgba(20, 33, 27, 0.48)',
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.8, 16, 3.6],
      },
    },
    {
      id: 'ofm-trails',
      type: 'line',
      source: 'ofm',
      'source-layer': 'transportation',
      minzoom: 11,
      filter: ['in', ['get', 'class'], ['literal', ['path', 'track']]],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#f9ebd0',
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.0, 16, 2.1],
        'line-dasharray': [2.2, 2.3],
        'line-opacity': 0.85,
      },
    },
    // Topographic summit names & elevations on nearby mountain peaks
    {
      id: 'ofm-peaks',
      type: 'symbol',
      source: 'ofm',
      'source-layer': 'mountain_peak',
      minzoom: 10.2,
      filter: ['all', ['==', ['geometry-type'], 'Point'], ['has', 'name']],
      layout: {
        'text-field': [
          'case',
          ['has', 'ele_ft'],
          ['concat', '▲ ', ['get', 'name'], '\n', ['to-string', ['round', ['to-number', ['get', 'ele_ft']]]], ' ft'],
          ['concat', '▲ ', ['get', 'name']],
        ],
        'text-font': ['Noto Sans Italic'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 10.2, 10.5, 14.5, 12.5],
        'text-line-height': 1.18,
        'text-max-width': 9,
        'text-padding': 12,
      },
      paint: {
        'text-color': '#fff8ec',
        'text-halo-color': 'rgba(20, 32, 27, 0.82)',
        'text-halo-width': 1.35,
        'text-opacity': 0.88,
      },
    },
  ],
  sky: {
    'sky-color': '#355c85',
    'horizon-color': '#f2d7b4',
    'sky-horizon-blend': 0.68,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 0.88, 5, 0.72, 8.5, 0],
  },
};

// ---------- Spherical geometry & easing helpers ----------
const R = 6371008.8;
const toRad = (d) => (d * Math.PI) / 180;
const toDeg = (r) => (r * 180) / Math.PI;
const mod = (n, m) => ((n % m) + m) % m;
const shortestDelta = (from, to) => mod(to - from + 180, 360) - 180;

const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeInOutSine = (t) => -(Math.cos(Math.PI * t) - 1) / 2;

function circlePolygon([lon, lat], meters, steps = 20) {
  const ring = [];
  const cosLat = Math.max(0.15, Math.cos(toRad(lat)));
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    const dx = (meters * Math.cos(a)) / (R * cosLat);
    const dy = (meters * Math.sin(a)) / R;
    ring.push([lon + toDeg(dx), lat + toDeg(dy)]);
  }
  return [ring];
}

export function distanceKm(a, b) {
  const dLat = toRad(b[1] - a[1]);
  const dLon = toRad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
  return (2 * R * Math.asin(Math.sqrt(h))) / 1000;
}

// Great-circle slerp arc between two [lon, lat] points (handles antimeridian cleanly)
function greatCircleArc(a, b, segments = 64) {
  const [lon1, lat1] = [toRad(a[0]), toRad(a[1])];
  const [lon2, lat2] = [toRad(b[0]), toRad(b[1])];
  const v1 = [Math.cos(lat1) * Math.cos(lon1), Math.cos(lat1) * Math.sin(lon1), Math.sin(lat1)];
  const v2 = [Math.cos(lat2) * Math.cos(lon2), Math.cos(lat2) * Math.sin(lon2), Math.sin(lat2)];
  const dot = Math.max(-1, Math.min(1, v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]));
  const omega = Math.acos(dot);
  if (omega < 1e-5) return [[a, b]];

  const sinO = Math.sin(omega);
  const pts = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const s1 = Math.sin((1 - t) * omega) / sinO;
    const s2 = Math.sin(t * omega) / sinO;
    const x = s1 * v1[0] + s2 * v2[0];
    const y = s1 * v1[1] + s2 * v2[1];
    const z = s1 * v1[2] + s2 * v2[2];
    pts.push([toDeg(Math.atan2(y, x)), toDeg(Math.atan2(z, Math.hypot(x, y)))]);
  }

  // Split across antimeridian jumps so MapLibre never draws a horizontal world-wrap line
  const lines = [[]];
  for (let i = 0; i < pts.length; i++) {
    if (i > 0 && Math.abs(pts[i][0] - pts[i - 1][0]) > 180) {
      lines.push([]);
    }
    lines[lines.length - 1].push(pts[i]);
  }
  return lines.filter((l) => l.length > 1);
}

// ---------- Globe3D Controller ----------
export class Globe3D {
  constructor(container, fxCanvas, { onSelectMemory, onUserInterrupt } = {}) {
    this.container = container;
    this.fxCanvas = fxCanvas;
    this.fxCtx = fxCanvas.getContext('2d');
    this.onSelectMemory = onSelectMemory || (() => {});
    this.onUserInterrupt = onUserInterrupt || (() => {});

    this.memories = [];
    this.chapterColors = new Map();
    this.markers = new Map();
    this.activeId = null;
    this.flightToken = 0;
    this.stageCleanup = null;
    this.fxRaf = 0;
    this.blooms = [];
    this.programmatic = false;
  }

  async init() {
    const maplibregl = await loadMapLibre();
    this.lib = maplibregl;

    this.map = new maplibregl.Map({
      container: this.container,
      style: STYLE,
      center: [-98, 34],
      zoom: this.idealGlobeZoom(),
      pitch: 10,
      bearing: 0,
      maxPitch: 72,
      attributionControl: { compact: true },
      pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      fadeDuration: 0,
    });

    this.map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true, showZoom: false }),
      'bottom-right'
    );

    await new Promise((r) => (this.map.isStyleLoaded() ? r() : this.map.once('style.load', r)));
    this.map.setTerrain({ source: 'dem', exaggeration: 1.48 });

    const empty = { type: 'FeatureCollection', features: [] };
    this.map.addSource('journey', { type: 'geojson', data: empty });
    this.map.addSource('active-hop', { type: 'geojson', data: empty });
    this.map.addSource('beacons', { type: 'geojson', data: empty });
    this.map.addSource('beacon-pillars', { type: 'geojson', data: empty });

    // Warm terracotta & sun-bleached parchment footpath arcs
    this.map.addLayer({
      id: 'journey-glow',
      type: 'line',
      source: 'journey',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#c96a3b',
        'line-width': ['interpolate', ['linear'], ['zoom'], 1, 2.8, 10, 5.5],
        'line-blur': 2.5,
        'line-opacity': 0.34,
      },
    });
    this.map.addLayer({
      id: 'journey-line',
      type: 'line',
      source: 'journey',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#fff7e8',
        'line-width': ['interpolate', ['linear'], ['zoom'], 1, 1.2, 12, 2.0],
        'line-dasharray': [2, 2.4],
        'line-opacity': 0.72,
      },
    });

    // Active walk segment between stops
    this.map.addLayer({
      id: 'hop-glow',
      type: 'line',
      source: 'active-hop',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#d97843',
        'line-width': 6,
        'line-blur': 3.5,
        'line-opacity': 0.62,
      },
    });
    this.map.addLayer({
      id: 'hop-core',
      type: 'line',
      source: 'active-hop',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#fffaf0',
        'line-width': 2.1,
        'line-dasharray': [2.2, 2.2],
        'line-opacity': 0.95,
      },
    });

    // Warm sunlit cairn markers when viewing the full Earth atlas
    this.map.addLayer({
      id: 'beacons-glow',
      type: 'circle',
      source: 'beacons',
      maxzoom: 8.5,
      paint: {
        'circle-color': ['get', 'color'],
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          1, ['case', ['get', 'active'], 13, 7.5],
          7, ['case', ['get', 'active'], 26, 15],
        ],
        'circle-blur': 0.9,
        'circle-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0.85, 8.5, 0],
        'circle-pitch-alignment': 'map',
      },
    });
    this.map.addLayer({
      id: 'beacons-core',
      type: 'circle',
      source: 'beacons',
      maxzoom: 8.5,
      paint: {
        'circle-color': '#fff8ea',
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 2.5, 7, 4.4],
        'circle-stroke-width': 1.2,
        'circle-stroke-color': 'rgba(28, 42, 34, 0.65)',
        'circle-opacity': ['interpolate', ['linear'], ['zoom'], 6.5, 0.96, 8.5, 0],
        'circle-pitch-alignment': 'map',
      },
    });
    this.map.addLayer({
      id: 'beacon-pillars',
      type: 'fill-extrusion',
      source: 'beacon-pillars',
      maxzoom: 5.5,
      paint: {
        'fill-extrusion-color': ['get', 'color'],
        'fill-extrusion-height': ['get', 'height'],
        'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 3.0, 0.72, 5.3, 0],
        'fill-extrusion-vertical-gradient': true,
      },
    });

    // Ground survey ring + trailhead cairn dot on 3D hillsides up close
    this.map.addLayer({
      id: 'local-glow',
      type: 'circle',
      source: 'beacons',
      minzoom: 7.5,
      paint: {
        'circle-color': ['case', ['get', 'active'], '#d97843', '#e8d7bd'],
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          8, ['case', ['get', 'active'], 12, 6],
          15, ['case', ['get', 'active'], 24, 11],
        ],
        'circle-blur': 0.75,
        'circle-opacity': ['case', ['get', 'active'], 0.72, 0.34],
        'circle-pitch-alignment': 'map',
      },
    });
    this.map.addLayer({
      id: 'local-dot',
      type: 'circle',
      source: 'beacons',
      minzoom: 7.5,
      paint: {
        'circle-color': ['case', ['get', 'active'], '#c96a3b', '#f7f1e5'],
        'circle-radius': ['case', ['get', 'active'], 5.8, 3.8],
        'circle-stroke-width': ['case', ['get', 'active'], 2.4, 1.5],
        'circle-stroke-color': '#fffaf0',
        'circle-pitch-alignment': 'map',
      },
    });

    // Hover & click on atlas markers
    const pop = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'fx-pop',
      offset: 14,
    });

    for (const layerId of ['beacons-glow', 'beacon-pillars', 'beacons-core', 'local-dot']) {
      this.map.on('click', layerId, (e) => {
        const f = e.features?.[0];
        if (f) {
          pop.remove();
          this.onSelectMemory(f.properties.id);
        }
      });
      this.map.on('mousemove', layerId, (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties;
        this.map.getCanvas().style.cursor = 'pointer';
        pop
          .setLngLat(JSON.parse(p.coords))
          .setHTML(`<b>${escHtml(p.title)}</b><span>${escHtml(p.place)}</span>`)
          .addTo(this.map);
      });
      this.map.on('mouseleave', layerId, () => {
        this.map.getCanvas().style.cursor = '';
        pop.remove();
      });
    }

    // Detect manual user drag/zoom to pause automatic walk smoothly
    const onUserMove = (e) => {
      if (!e.originalEvent || this.programmatic) return;
      this.stopOrbit();
      this.onUserInterrupt();
    };
    for (const ev of ['dragstart', 'rotatestart', 'pitchstart', 'wheel', 'touchstart']) {
      this.map.on(ev, onUserMove);
    }

    this.resizeFxCanvas();
    window.addEventListener('resize', () => {
      this.map?.resize();
      this.resizeFxCanvas();
    });

    this.map.on('moveend', () => this.syncPinVisibility());
  }

  resizeFxCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = this.container.clientWidth || window.innerWidth;
    const h = this.container.clientHeight || window.innerHeight;
    this.fxCanvas.width = Math.round(w * dpr);
    this.fxCanvas.height = Math.round(h * dpr);
    this.fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  idealGlobeZoom() {
    const w = this.container.clientWidth || window.innerWidth;
    const h = this.container.clientHeight || window.innerHeight;
    const minDim = Math.min(w * 0.72, h);
    return Math.max(1.05, Math.min(1.78, Math.log2(minDim / 380) + 0.92));
  }

  cameraPadding(withCard = true) {
    if (!withCard) return { top: 0, right: 0, bottom: 0, left: 0 };
    const mobile = window.matchMedia('(max-width: 900px)').matches;
    if (mobile) {
      return { top: 60, right: 0, bottom: Math.round(window.innerHeight * 0.46), left: 0 };
    }
    const cardW = Math.min(468, window.innerWidth * 0.4) + 52;
    return { top: 96, right: Math.round(cardW), bottom: 24, left: 0 };
  }

  setData(memories, chapters) {
    this.memories = memories;
    this.chapterColors = new Map(chapters.map((c) => [c.id, c.color]));
    this.markers.forEach((entry) => entry.marker.remove());
    this.markers.clear();

    for (let i = 0; i < memories.length; i++) {
      const m = memories[i];
      const num = String(i + 1).padStart(2, '0');
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'pin-label';
      el.innerHTML = `<span class="pin-flag"><em>${num}</em><b>${escHtml(m.title)}</b></span>`;
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        this.onSelectMemory(m.id);
      });
      // Do NOT mount all 37 DOM markers at once—only mount local valley markers on demand!
      const marker = new this.lib.Marker({ element: el, anchor: 'bottom', offset: [0, -6] }).setLngLat(m.coords);
      this.markers.set(m.id, { marker, coords: m.coords, mounted: false });
    }

    this.refreshSources();
    this.syncPinVisibility();
  }

  syncPinVisibility({ flyingToCoords = null } = {}) {
    if (!this.map) return;
    const z = flyingToCoords ? 14 : this.map.getZoom();
    const ref = flyingToCoords || [this.map.getCenter().lng, this.map.getCenter().lat];

    for (const [id, entry] of this.markers) {
      const isActive = id === this.activeId;
      const km = distanceKm(ref, entry.coords);
      const shouldMount = flyingToCoords
        ? isActive
        : isActive
          ? z >= 7.0 && km < 120
          : z >= 12.2 && km < 12;

      const el = entry.marker.getElement();
      el.classList.toggle('active', isActive);

      if (shouldMount && !entry.mounted) {
        entry.marker.addTo(this.map);
        entry.mounted = true;
      } else if (!shouldMount && entry.mounted) {
        entry.marker.remove();
        entry.mounted = false;
      }
    }
  }

  refreshSources(visitedIndex = -1) {
    if (!this.map?.getSource('beacons')) return;
    const pts = [];
    const globePillars = [];

    for (let i = 0; i < this.memories.length; i++) {
      const m = this.memories[i];
      const active = m.id === this.activeId;
      const color = active ? '#e07a45' : this.chapterColors.get(m.chapter) || '#c96a3b';
      const mediaBoost = Math.min(4, m.media?.length || 0);

      pts.push({
        type: 'Feature',
        properties: {
          id: m.id,
          title: m.title,
          place: m.place,
          coords: JSON.stringify(m.coords),
          color,
          active,
        },
        geometry: { type: 'Point', coordinates: m.coords },
      });

      globePillars.push({
        type: 'Feature',
        properties: {
          id: m.id,
          title: m.title,
          place: m.place,
          coords: JSON.stringify(m.coords),
          color,
          height: active ? 360000 : 120000 + mediaBoost * 45000,
        },
        geometry: { type: 'Polygon', coordinates: circlePolygon(m.coords, 12500, 16) },
      });
    }

    this.map.getSource('beacons').setData({ type: 'FeatureCollection', features: pts });
    this.map.getSource('beacon-pillars').setData({ type: 'FeatureCollection', features: globePillars });

    // Build geodesic journey footpath arcs up to visitedIndex
    const arcLines = [];
    for (let i = 1; i <= visitedIndex && i < this.memories.length; i++) {
      const a = this.memories[i - 1].coords;
      const b = this.memories[i].coords;
      if (distanceKm(a, b) > 5) {
        for (const seg of greatCircleArc(a, b, 48)) arcLines.push(seg);
      }
    }
    this.map.getSource('journey').setData({
      type: 'FeatureCollection',
      features: arcLines.map((coordinates) => ({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates },
      })),
    });
  }

  setActiveHop(fromCoords, toCoords) {
    if (!this.map?.getSource('active-hop')) return;
    if (!fromCoords || !toCoords || distanceKm(fromCoords, toCoords) < 6) {
      this.map.getSource('active-hop').setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const segs = greatCircleArc(fromCoords, toCoords, 64);
    this.map.getSource('active-hop').setData({
      type: 'FeatureCollection',
      features: segs.map((coordinates) => ({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates },
      })),
    });
  }

  // Execute a single MapLibre native camera stage and resolve cleanly when complete or superseded
  runCameraStage(token, options) {
    return new Promise((resolve) => {
      if (this.flightToken !== token || !this.map) {
        resolve(false);
        return;
      }
      let settled = false;
      let fallbackTimer = 0;
      const finish = () => {
        if (settled) return;
        settled = true;
        clearTimeout(fallbackTimer);
        this.map.off('moveend', finish);
        if (this.stageCleanup === finish) this.stageCleanup = null;
        resolve(this.flightToken === token);
      };
      this.stageCleanup = finish;
      this.map.on('moveend', finish);
      fallbackTimer = setTimeout(finish, (options.duration || 0) + 240);

      this.programmatic = true;
      this.map.easeTo({ ...options, essential: true });
      this.programmatic = false;
    });
  }

  // Spin the whole Earth slowly in Field Atlas overview mode
  async globeOverview({ center = [-98, 28], immediate = false } = {}) {
    this.stopOrbit();
    const token = ++this.flightToken;
    this.activeId = null;
    this.setActiveHop(null, null);
    this.refreshSources(this.memories.length - 1);
    this.syncPinVisibility();

    const mobile = window.matchMedia('(max-width: 900px)').matches;
    const overviewPad = mobile
      ? { top: 20, right: 0, bottom: 220, left: 0 }
      : { top: 24, right: 0, bottom: 24, left: 340 };

    const startSpin = () => {
      const spinStep = async () => {
        if (this.flightToken !== token || this.activeId) return;
        const c = this.map.getCenter();
        const ok = await this.runCameraStage(token, {
          center: [c.lng + 90, c.lat],
          duration: 34000,
          easing: (t) => t,
        });
        if (ok && !this.activeId) spinStep();
      };
      spinStep();
    };

    const zTarget = this.idealGlobeZoom();
    if (immediate) {
      this.programmatic = true;
      this.map.jumpTo({
        center,
        zoom: zTarget,
        pitch: 10,
        bearing: 0,
        padding: overviewPad,
      });
      this.programmatic = false;
      startSpin();
      return;
    }

    // 1. Zoom straight out over current location first
    const cur = this.map.getCenter();
    const ok1 = await this.runCameraStage(token, {
      center: [cur.lng, cur.lat],
      zoom: zTarget,
      pitch: 10,
      bearing: 0,
      padding: overviewPad,
      duration: 4200,
      easing: easeInOutCubic,
    });
    if (!ok1 || this.activeId) return;

    // 2. Gently rotate the globe to the overview framing
    const ok2 = await this.runCameraStage(token, {
      center,
      zoom: zTarget,
      pitch: 10,
      bearing: 0,
      padding: overviewPad,
      duration: 3200,
      easing: easeInOutSine,
    });
    if (!ok2 || this.activeId) return;

    this.syncPinVisibility();
    startSpin();
  }

  // Uncoupled 3-Act Globe & Landscape Choreographer:
  // Act 1: Zoom smoothly straight out over the current place (lifting gaze to overhead).
  // Act 2: Rotate the globe / glide high above at constant altitude & pitch (zero tile-pyramid thrashing).
  // Act 3: Descend smoothly straight down onto the destination and gently lift gaze to the horizon.
  async flyToMemory(mem, prevMem, { visitedIndex = 0, speedMult = 1, onArrive } = {}) {
    this.stopOrbit();
    const token = ++this.flightToken;
    this.activeId = mem.id;
    this.refreshSources(visitedIndex);
    this.syncPinVisibility({ flyingToCoords: mem.coords });

    const startCenter = [this.map.getCenter().lng, this.map.getCenter().lat];
    const z0 = this.map.getZoom();
    const b0 = this.map.getBearing();

    const km = distanceKm(startCenter, mem.coords);
    this.setActiveHop(prevMem ? prevMem.coords : km > 40 ? startCenter : null, mem.coords);

    const pad1 = this.cameraPadding(true);
    const z1 = mem.zoom ?? 14.0;
    const p1 = mem.pitch ?? 64;
    const b1 = mem.bearing ?? 0;

    let revealed = false;
    const revealArrival = () => {
      if (revealed || this.flightToken !== token || this.activeId !== mem.id) return;
      revealed = true;
      this.setActiveHop(null, null);
      this.triggerArrivalBloom(mem.coords, this.chapterColors.get(mem.chapter) || '#c96a3b');
      onArrive?.();
    };

    if (speedMult === 0) {
      this.programmatic = true;
      this.map.jumpTo({ center: mem.coords, zoom: z1, pitch: p1, bearing: b1, padding: pad1 });
      this.programmatic = false;
      revealArrival();
      this.syncPinVisibility();
      this.startLocalOrbit(mem, token);
      return;
    }

    const fromGlobe = !prevMem && z0 < 4.5;
    const minGlobeZ = this.idealGlobeZoom();

    if (fromGlobe) {
      // Already zoomed out in space: rotate the globe first, then descend cleanly onto Stop 1
      const okRotate = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: z0,
        pitch: 8,
        bearing: 0,
        padding: pad1,
        duration: Math.round(4200 * speedMult),
        easing: easeInOutSine,
      });
      if (!okRotate) return;

      const zoomInMs = Math.round(5800 * speedMult);
      this.earlyTimer = setTimeout(revealArrival, Math.max(0, zoomInMs - 550));
      const okIn = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: z1,
        pitch: p1,
        bearing: b1,
        padding: pad1,
        duration: zoomInMs,
        easing: easeInOutCubic,
      });
      if (!okIn) return;
    } else if (km < 3.5) {
      // Immediate walking-distance neighbor in the same town/meadow:
      // Gently step up to a neighborhood overlook, glide across, and settle back down
      const cruiseZoom = Math.min(z0, z1, 13.4) - (km < 0.5 ? 0.85 : 1.35);
      const midBearing = b0 + shortestDelta(b0, b1) * 0.5;

      const okOut = await this.runCameraStage(token, {
        center: startCenter,
        zoom: cruiseZoom,
        pitch: 30,
        bearing: midBearing,
        padding: pad1,
        duration: Math.round(1650 * speedMult),
        easing: easeInOutCubic,
      });
      if (!okOut) return;

      const okGlide = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: cruiseZoom,
        pitch: 30,
        bearing: midBearing,
        padding: pad1,
        duration: Math.round(1850 * speedMult),
        easing: easeInOutSine,
      });
      if (!okGlide) return;

      const zoomInMs = Math.round(1850 * speedMult);
      this.earlyTimer = setTimeout(revealArrival, Math.max(0, zoomInMs - 450));
      const okIn = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: z1,
        pitch: p1,
        bearing: b1,
        padding: pad1,
        duration: zoomInMs,
        easing: easeInOutCubic,
      });
      if (!okIn) return;
    } else if (km < 300) {
      // Regional valley-to-valley walk:
      // 1) Zoom straight out above the mountain range, 2) glide overhead at constant altitude, 3) zoom down in
      const cruiseZoom = Math.max(5.3, Math.min(11.3, 12.65 - Math.log2(1 + km) * 0.92));
      const cruisePitch = km > 60 ? 12 : 16;
      const cruiseBearing = km > 45 ? 0 : b0 + shortestDelta(b0, b1) * 0.5;

      const zoomOutMs = Math.round((2500 + Math.min(1400, Math.log2(1 + km) * 180)) * speedMult);
      const glideMs = Math.round((2600 + Math.min(2200, (km / 300) * 2200)) * speedMult);
      const zoomInMs = Math.round((2800 + Math.min(1500, Math.log2(1 + km) * 190)) * speedMult);

      const okOut = await this.runCameraStage(token, {
        center: startCenter,
        zoom: cruiseZoom,
        pitch: cruisePitch,
        bearing: cruiseBearing,
        padding: pad1,
        duration: zoomOutMs,
        easing: easeInOutCubic,
      });
      if (!okOut) return;

      const okGlide = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: cruiseZoom,
        pitch: cruisePitch,
        bearing: cruiseBearing,
        padding: pad1,
        duration: glideMs,
        easing: easeInOutSine,
      });
      if (!okGlide) return;

      this.earlyTimer = setTimeout(revealArrival, Math.max(0, zoomInMs - 550));
      const okIn = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: z1,
        pitch: p1,
        bearing: b1,
        padding: pad1,
        duration: zoomInMs,
        easing: easeInOutCubic,
      });
      if (!okIn) return;
    } else {
      // Continental & Global transitions:
      // Act 1: Pull straight out into space to reveal the sunlit 3D Earth (North-up).
      // Act 2: Rotate the globe smoothly at constant orbital altitude & overhead gaze.
      // Act 3: Descend straight down into the new landscape and lift gaze onto the horizon.
      const globeCruiseZoom =
        km >= 3500
          ? minGlobeZ + 0.04
          : km >= 1200
            ? minGlobeZ + 0.52
            : Math.max(minGlobeZ + 1.1, 3.25 - ((km - 300) / 900) * 0.6);
      const cruisePitch = km >= 1200 ? 6 : 10;

      const zoomOutMs = Math.round((5000 + Math.min(1600, (km / 6000) * 1600)) * speedMult);
      const rotateMs = Math.round((4600 + Math.min(6800, (km / 18800) * 6800)) * speedMult);
      const zoomInMs = Math.round((5400 + Math.min(1400, (km / 6000) * 1400)) * speedMult);

      const okOut = await this.runCameraStage(token, {
        center: startCenter,
        zoom: globeCruiseZoom,
        pitch: cruisePitch,
        bearing: 0,
        padding: pad1,
        duration: zoomOutMs,
        easing: easeInOutCubic,
      });
      if (!okOut) return;

      const targetLng = startCenter[0] + shortestDelta(startCenter[0], mem.coords[0]);
      const okRotate = await this.runCameraStage(token, {
        center: [targetLng, mem.coords[1]],
        zoom: globeCruiseZoom,
        pitch: cruisePitch,
        bearing: 0,
        padding: pad1,
        duration: rotateMs,
        easing: easeInOutSine,
      });
      if (!okRotate) return;

      this.earlyTimer = setTimeout(revealArrival, Math.max(0, zoomInMs - 600));
      const okIn = await this.runCameraStage(token, {
        center: mem.coords,
        zoom: z1,
        pitch: p1,
        bearing: b1,
        padding: pad1,
        duration: zoomInMs,
        easing: easeInOutCubic,
      });
      if (!okIn) return;
    }

    revealArrival();
    this.syncPinVisibility();
    this.startLocalOrbit(mem, token);
  }

  // Serene native WebGL horizon drift while reading a memory (zero per-frame JS setBearing jitter)
  startLocalOrbit(mem, token = this.flightToken) {
    if (this.flightToken !== token || !this.map) return;
    const baseBearing = typeof mem?.bearing === 'number' ? mem.bearing : this.map.getBearing();
    this.programmatic = true;
    this.map.easeTo({
      bearing: baseBearing + 4.5,
      duration: 16000,
      easing: (t) => t,
      essential: true,
    });
    this.programmatic = false;
  }

  stopOrbit() {
    clearTimeout(this.earlyTimer);
    if (this.stageCleanup) {
      const fn = this.stageCleanup;
      this.stageCleanup = null;
      fn();
    }
    this.map?.stop();
  }

  // Warm golden-hour ground ripple & drifting meadow pollen motes on arrival
  triggerArrivalBloom(coords, accent = '#c96a3b') {
    const sparks = [];
    const count = 22;
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 + (Math.random() - 0.5) * 0.35;
      const speed = 16 + Math.random() * 42;
      sparks.push({
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed * 0.55 - (16 + Math.random() * 28),
        size: 1.5 + Math.random() * 2.1,
        life: 0.95 + Math.random() * 0.65,
      });
    }
    this.blooms.push({
      coords,
      accent,
      t0: performance.now(),
      duration: 2100,
      sparks,
    });
    if (!this.fxRaf) this.loopFx();
  }

  loopFx() {
    const step = (now) => {
      const ctx = this.fxCtx;
      const w = this.container.clientWidth || window.innerWidth;
      const h = this.container.clientHeight || window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      this.blooms = this.blooms.filter((b) => now - b.t0 < b.duration);
      for (const b of this.blooms) {
        const pt = this.map.project(b.coords);
        const elapsed = (now - b.t0) / 1000;
        const p = Math.min(1, (now - b.t0) / b.duration);
        const easeOut = 1 - (1 - p) ** 3;

        // Soft warm trailhead ground ripple (foreshortened ellipse on the hillside)
        ctx.save();
        ctx.strokeStyle = '#fff5e0';
        ctx.lineWidth = 1.6 * (1 - p);
        ctx.globalAlpha = Math.max(0, 0.6 * (1 - p));
        ctx.beginPath();
        ctx.ellipse(pt.x, pt.y, 12 + easeOut * 84, (12 + easeOut * 84) * 0.52, 0, 0, Math.PI * 2);
        ctx.stroke();

        if (p > 0.14) {
          const p2 = (p - 0.14) / 0.86;
          ctx.strokeStyle = b.accent;
          ctx.globalAlpha = Math.max(0, 0.45 * (1 - p2));
          ctx.beginPath();
          ctx.ellipse(pt.x, pt.y, 8 + (1 - (1 - p2) ** 3) * 52, (8 + (1 - (1 - p2) ** 3) * 52) * 0.52, 0, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Gently rising golden-hour dust/pollen motes
        for (const s of sparksOf(b)) {
          const sp = elapsed / s.life;
          if (sp >= 1) continue;
          const x = pt.x + s.vx * elapsed * 0.7 + Math.sin(elapsed * 3 + s.size) * 4;
          const y = pt.y + s.vy * elapsed * 0.72;
          const alpha = Math.sin(sp * Math.PI);
          ctx.globalAlpha = alpha * 0.82;
          ctx.fillStyle = sp < 0.5 ? '#fff8e6' : '#f0c987';
          ctx.beginPath();
          ctx.arc(x, y, s.size * (1 - sp * 0.3), 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      if (this.blooms.length > 0) {
        this.fxRaf = requestAnimationFrame(step);
      } else {
        this.fxRaf = 0;
      }
    };
    this.fxRaf = requestAnimationFrame(step);
  }
}

function sparksOf(b) {
  return b.sparks || [];
}
