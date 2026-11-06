// Companion controller for walk.html:
// Synchronizes the sonic_ray Metal-pathtraced morphing landscape film with
// calm, stationary One-by-One Left/Right memory sanctuaries (default) +
// explicit geographic trail wayfinding & clickable full-resolution Lightbox.

const video = document.getElementById('walk-video');
const clusterLayer = document.getElementById('cluster-layer');
const tetherSvg = document.getElementById('tether-svg');
const introVeil = document.getElementById('intro-veil');
const beginBtn = document.getElementById('begin-btn');
const playBtn = document.getElementById('play-btn');
const iconPlay = document.getElementById('icon-play');
const iconPause = document.getElementById('icon-pause');
const scrubber = document.getElementById('scrubber');
const timeReadout = document.getElementById('time-readout');
const speedBtn = document.getElementById('speed-btn');
const densityBtn = document.getElementById('density-btn');

const cantoRoman = document.getElementById('canto-roman');
const cantoName = document.getElementById('canto-name');
const cantoEra = document.getElementById('canto-era');
const cantoTicks = document.getElementById('canto-ticks');
const cantoBanner = document.getElementById('canto-banner');

const lightbox = document.getElementById('lightbox');
const lbBackdrop = document.getElementById('lb-backdrop');
const lbClose = document.getElementById('lb-close');
const lbMedia = document.getElementById('lb-media');
const lbEra = document.getElementById('lb-era');
const lbPlace = document.getElementById('lb-place');
const lbTitle = document.getElementById('lb-title');
const lbQuote = document.getElementById('lb-quote');
const lbAuthor = document.getElementById('lb-author');

const DENSITY_MODES = [
  { mode: 'solo', maxCards: 1, label: 'One by One' },
  { mode: 'cluster', maxCards: 2, label: 'Focused Pair' },
  { mode: 'pure', maxCards: 0, label: 'Pure Landscape' },
];
const SPEEDS = [1, 1.5, 2];

const TERRAIN_Z_NODES = [
  { z: 0.0, lon: -101.86, lat: 35.20, code: 'TX', short: 'Amarillo, TX', label: 'Amarillo Plains, TX' },
  { z: -6.2, lon: -101.79, lat: 35.19, code: 'TX', short: 'Amarillo, TX', label: 'Amarillo & Palo Duro Rim, TX' },
  { z: -9.6, lon: -102.35, lat: 35.08, code: 'TX', short: 'Caprock Rim, TX', label: 'Caprock Escarpment, TX' },
  { z: -13.0, lon: -103.73, lat: 35.17, code: 'NM', short: 'Tucumcari, NM', label: 'Route 66 · Tucumcari, NM' },
  { z: -17.2, lon: -107.57, lat: 37.38, code: 'CO', short: 'Vallecito, CO', label: 'Vallecito Pines, CO' },
  { z: -24.0, lon: -104.85, lat: 39.02, code: 'CO', short: 'Colorado Foothills', label: 'Front Range Foothills, CO' },
  { z: -32.0, lon: 2.35, lat: 48.85, code: 'FR', short: 'France', label: 'Paris & Haute-Loire, France' },
  { z: -35.6, lon: 12.49, lat: 41.89, code: 'IT', short: 'Italy', label: 'Tuscany & Rome, Italy' },
  { z: -44.5, lon: -107.67, lat: 38.02, code: 'CO', short: 'San Juan Mtns, CO', label: 'San Juan Elk Country, CO' },
  { z: -54.5, lon: -106.05, lat: 39.48, code: 'CO', short: 'Breckenridge, CO', label: 'Tenmile Alpine Ridge, CO' },
  { z: -65.3, lon: -105.22, lat: 39.67, code: 'CO', short: 'Mount Morrison, CO', label: 'Red Rocks & Mount Morrison, CO' },
];

let walkData = null;
let memMap = new Map();
let wptMap = new Map();
let soloSchedule = new Map();
let domShades = new Map();
let wpSignpostEl = null;
let densityIdx = 0;
let speedIdx = 0;
let activeCantoKey = '';
let wasPlayingBeforeModal = false;
let scrubbing = false;

const escHtml = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const smoothstep = (e0, e1, x) => {
  if (e1 <= e0) return x >= e1 ? 1 : 0;
  const u = clamp((x - e0) / (e1 - e0));
  return u * u * (3 - 2 * u);
};

function fmtTime(sec) {
  const s = Math.max(0, Math.floor(sec || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function regionCodeFromPlace(placeStr, coords) {
  const p = String(placeStr || '').toLowerCase();
  const rules = [
    ['pennsylvania', 'PA'], ['new mexico', 'NM'], ['tucumcari', 'NM'],
    ['texas', 'TX'], ['amarillo', 'TX'], ['colorado', 'CO'],
    ['utah', 'UT'], ['moab', 'UT'], ['hawai', 'HI'], ['kaua', 'HI'],
    ['mexico', 'MX'], ['sint maarten', 'SXM'], ['france', 'FR'],
    ['italy', 'IT'], ['new zealand', 'NZ'],
  ];
  for (const [needle, code] of rules) {
    if (p.includes(needle)) return code;
  }
  if (!coords) return 'TX';
  const [lon, lat] = coords;
  if (lon >= 160 && lat < -30) return 'NZ';
  if (lon <= -150) return 'HI';
  if (lon >= -6 && lon <= 9 && lat >= 42) return 'FR';
  if (lon > 9 && lon <= 19 && lat >= 36) return 'IT';
  if (lon >= -82 && lon <= -74 && lat >= 39) return 'PA';
  if (lon >= -109.1 && lon <= -102.05 && lat >= 36.95) return 'CO';
  if (lon >= -109.1 && lon <= -103.0 && lat < 37.0) return 'NM';
  return 'TX';
}

function haversineMiles(lon1, lat1, lon2, lat2) {
  const r = 3958.8;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp * 0.5) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl * 0.5) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
}

function terrainAtTime(t) {
  const fullS = walkData?.full_walk_s || 300;
  const u = clamp(t / fullS);
  const uSmooth = 0.04 * (u * u * (3 - 2 * u)) + 0.96 * u;
  const zMid = clamp(-65.3 * uSmooth - 2.45, -65.3, 0.0);
  let best = TERRAIN_Z_NODES[0];
  let bestD = Infinity;
  for (const nd of TERRAIN_Z_NODES) {
    const d = Math.abs(nd.z - zMid);
    if (d < bestD) {
      bestD = d;
      best = nd;
    }
  }
  return best;
}

// Compute calm, strictly solo One-by-One Left/Right schedule across all 49 memories
function buildSoloSchedule(wd) {
  const durClip = wd.duration_s || 300;
  const tl = wd.timeline || [];
  const spans = new Map();
  const peaks = new Map();

  for (const row of tl) {
    const t = row.t;
    for (const mm of row.mems || []) {
      if (mm.w >= 0.05 && mm.u >= 0.01 && mm.u <= 0.99 && mm.v >= 0.03 && mm.v <= 0.97) {
        if (!spans.has(mm.id)) spans.set(mm.id, []);
        spans.get(mm.id).push(t);
        const prev = peaks.get(mm.id);
        if (!prev || mm.w > prev.w) peaks.set(mm.id, { w: mm.w, t, u: mm.u });
      }
    }
  }

  const ordered = (wd.memories || [])
    .filter((m) => spans.has(m.id))
    .sort((a, b) => (a.canto - b.canto) || (peaks.get(a.id).t - peaks.get(b.id).t));

  const n = ordered.length;
  const endCap = Math.min(durClip - 8.0, 292.0);
  const ideal = [];
  const targets = [];
  const loB = [];
  const hiB = [];

  for (const m of ordered) {
    const sp = spans.get(m.id);
    const pk = peaks.get(m.id);
    const dur = 5.0 + Math.min(2.8, (m.text || '').length / 190.0);
    const v0 = Math.max(0.7, sp[0] - 2.5);
    const v1 = Math.min(endCap, sp[sp.length - 1] + 13.5);
    ideal.push(dur);
    targets.push(clamp(pk.t, v0 + dur * 0.5, Math.max(v0 + dur * 0.5, v1 - dur * 0.5)));
    loB.push(v0);
    hiB.push(Math.max(v0 + 4.8, v1));
  }

  const eff = [...ideal];
  const centers = [...targets];
  const gap = 0.14;

  for (let it = 0; it < 500; it++) {
    for (let i = 0; i < n; i++) {
      centers[i] += 0.045 * (targets[i] - centers[i]);
      if (eff[i] < ideal[i]) eff[i] = Math.min(ideal[i], eff[i] + 0.012);
    }
    for (let i = 0; i < n - 1; i++) {
      const req = 0.5 * (eff[i] + eff[i + 1]) + gap;
      const diff = centers[i + 1] - centers[i];
      if (diff < req) {
        const push = 0.5 * (req - diff);
        centers[i] -= push;
        centers[i + 1] += push;
        if (req - diff > 0.05) {
          if (eff[i] > 4.7) eff[i] -= 0.018;
          if (eff[i + 1] > 4.7) eff[i + 1] -= 0.018;
        }
      }
    }
    for (let i = 0; i < n; i++) {
      eff[i] = Math.min(eff[i], Math.max(4.5, hiB[i] - loB[i]));
      centers[i] = clamp(centers[i], loB[i] + 0.5 * eff[i], hiB[i] - 0.5 * eff[i]);
    }
  }
  for (let i = 1; i < n; i++) {
    const lo = centers[i - 1] + 0.5 * (eff[i - 1] + eff[i]) + gap;
    if (centers[i] < lo) centers[i] = lo;
  }

  const out = new Map();
  let prevSide = null;
  ordered.forEach((m, i) => {
    const t0 = centers[i] - 0.5 * eff[i];
    const t1 = Math.min(endCap, centers[i] + 0.5 * eff[i]);
    const nat = peaks.get(m.id).u < 0.5 ? 'left' : 'right';
    const side = prevSide === nat ? (prevSide === 'left' ? 'right' : 'left') : nat;
    prevSide = side;
    out.set(m.id, { t0, t1, tMid: 0.5 * (t0 + t1), side });
  });
  return out;
}

function videoUvToScreen(u, v) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const vidAspect = (walkData?.width || 768) / (walkData?.height || 432);
  const winAspect = vw / vh;
  let drawW, drawH, offX, offY;
  if (winAspect > vidAspect) {
    drawW = vw;
    drawH = vw / vidAspect;
    offX = 0;
    offY = (vh - drawH) * 0.5;
  } else {
    drawH = vh;
    drawW = vh * vidAspect;
    offX = (vw - drawW) * 0.5;
    offY = 0;
  }
  return { x: offX + u * drawW, y: offY + v * drawH };
}

function sampleTimelineAt(t) {
  const tl = walkData?.timeline;
  if (!tl || tl.length === 0) return { mems: new Map(), wpts: [] };
  const dur = walkData.duration_s || 300;
  const tc = clamp(t, 0, dur);
  const fIdx = (tc / dur) * (tl.length - 1);
  const i0 = Math.max(0, Math.min(tl.length - 2, Math.floor(fIdx)));
  const alpha = fIdx - i0;
  const a = tl[i0];
  const b = tl[i0 + 1];

  const interpList = (listA, listB) => {
    const mA = new Map((listA || []).map((x) => [x.id, x]));
    const mB = new Map((listB || []).map((x) => [x.id, x]));
    const ids = new Set([...mA.keys(), ...mB.keys()]);
    const res = new Map();
    for (const id of ids) {
      const xa = mA.get(id);
      const xb = mB.get(id);
      const u = xa && xb ? xa.u * (1 - alpha) + xb.u * alpha : (xa || xb).u;
      const v = xa && xb ? xa.v * (1 - alpha) + xb.v * alpha : (xa || xb).v;
      const w = (xa ? xa.w : 0) * (1 - alpha) + (xb ? xb.w : 0) * alpha;
      res.set(id, { id, u, v, w });
    }
    return res;
  };

  return {
    mems: interpList(a.mems, b.mems),
    wpts: [...interpList(a.wpts, b.wpts).values()],
  };
}

function getOrCreateShade(id) {
  if (domShades.has(id)) return domShades.get(id);
  const m = memMap.get(id);
  const sl = soloSchedule.get(id);
  const tr = terrainAtTime(sl ? sl.tMid : 0);
  const coords = m.coords || [-101.83, 35.20];
  const memCode = regionCodeFromPlace(m.place || m.title, coords);
  const dist = haversineMiles(coords[0], coords[1], tr.lon, tr.lat);
  const isDistant = (memCode === 'FR' || memCode === 'IT') && memCode === tr.code
    ? false
    : (memCode !== tr.code || dist >= 90);

  const el = document.createElement('article');
  el.className = `mem-shade ${m.pal_type === 'klein' ? 'is-klein' : ''}`;
  const mediaList = m.media || [];
  const imgItem = mediaList.find((x) => x.type === 'image');
  const vidItem = !imgItem ? mediaList.find((x) => x.type === 'video') : null;
  const extraCount = mediaList.length > 1 ? `<span class="shade-count">+${mediaList.length - 1}</span>` : '';
  let photoHtml = '';
  if (imgItem) {
    photoHtml = `<div class="shade-media-wrap"><img class="shade-photo" src="${escHtml(imgItem.src)}" alt="${escHtml(m.title)}" loading="lazy">${extraCount}</div>`;
  } else if (vidItem) {
    photoHtml = `<div class="shade-media-wrap"><video class="shade-photo" src="${escHtml(vidItem.src)}#t=4" muted playsinline preload="metadata"></video></div>`;
  }

  const placeTxt = m.place || tr.short;
  const geoHtml = isDistant
    ? `<div class="shade-geo is-distant">◆ Memory in ${escHtml(placeTxt)}<span class="shade-geo-sub">Carried along the ${escHtml(tr.short)} trail below</span></div>`
    : `<div class="shade-geo">● ${escHtml(placeTxt)} · right here on the trail</div>`;

  const quoteHtml = m.text ? `<p class="shade-quote">“${escHtml(m.text)}”</p>` : '';
  const authorHtml = m.author ? `<p class="shade-author">— ${escHtml(m.author)}</p>` : '';
  el.innerHTML = `${photoHtml}<h3 class="shade-title">${escHtml(m.title)}</h3>${geoHtml}${quoteHtml}${authorHtml}`;
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    openLightbox(m);
  });
  clusterLayer.appendChild(el);
  const entry = { el, x: 0, y: 0, init: false };
  domShades.set(id, entry);
  return entry;
}

function getOrCreateWpSignpost() {
  if (wpSignpostEl) return wpSignpostEl;
  const el = document.createElement('div');
  el.className = 'wp-signpost';
  el.style.display = 'none';
  el.innerHTML = `<div class="wp-signpost-lbl"><span class="wp-diamond"></span><span id="wp-lbl-txt"></span></div><div class="wp-signpost-sub" id="wp-sub-txt"></div>`;
  clusterLayer.appendChild(el);
  wpSignpostEl = el;
  return el;
}

function renderOverlayFrame() {
  if (!walkData) return;
  const t = video.currentTime || 0;
  if (!scrubbing) scrubber.value = t;
  timeReadout.textContent = `${fmtTime(t)} / ${fmtTime(walkData.duration_s)}`;

  const canto = walkData.cantos.find((c) => t >= c.t0 && t <= c.t1) || walkData.cantos[walkData.cantos.length - 1];
  const trNow = terrainAtTime(t);
  const cKey = `${canto?.idx}:${trNow.label}`;
  if (canto && cKey !== activeCantoKey) {
    activeCantoKey = cKey;
    cantoRoman.textContent = canto.roman;
    cantoName.textContent = `${trNow.label}`;
    cantoEra.textContent = canto.era;
    document.querySelectorAll('.canto-tick').forEach((btn) => {
      btn.classList.toggle('active', Number(btn.dataset.idx) === canto.idx);
    });
    cantoBanner.hidden = true;
  }

  const modeObj = DENSITY_MODES[densityIdx];
  const { mems: activeMems, wpts: activeWpts } = sampleTimelineAt(t);
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const svgParts = [];
  const heroBoxes = [];

  if (modeObj.mode === 'solo') {
    // Calm, stationary One-by-One sanctuary mode (zero sliding/hovering motion!)
    let activeId = null;
    let activeSl = null;
    for (const [id, sl] of soloSchedule) {
      if (t >= sl.t0 && t <= sl.t1) {
        activeId = id;
        activeSl = sl;
        break;
      }
    }

    for (const [id, entry] of domShades) {
      if (id !== activeId) {
        entry.el.style.display = 'none';
        entry.init = false;
      }
    }

    if (activeId && activeSl) {
      const entry = getOrCreateShade(activeId);
      const el = entry.el;
      el.classList.add('is-solo');
      el.classList.remove('is-peak');
      el.style.display = 'block';

      const cardW = el.offsetWidth || 380;
      const cardH = el.offsetHeight || 260;
      const op = smoothstep(0, 0.68, t - activeSl.t0) * smoothstep(0, 0.68, activeSl.t1 - t);
      const marginX = vw <= 820 ? 18 : 28;
      const xPos = activeSl.side === 'left' ? marginX : Math.max(marginX, vw - cardW - marginX);
      const yPos = 76;

      el.style.opacity = op.toFixed(3);
      el.style.zIndex = '20';
      el.style.transform = `translate3d(${xPos.toFixed(1)}px, ${yPos.toFixed(1)}px, 0)`;
      heroBoxes.push({ x0: xPos - 14, y0: yPos - 10, x1: xPos + cardW + 14, y1: yPos + cardH + 14 });

      const bm = activeMems.get(activeId);
      if (bm && bm.w >= 0.06 && bm.u >= 0.04 && bm.u <= 0.96 && bm.v >= 0.14 && bm.v <= 0.90) {
        const anc = videoUvToScreen(bm.u, bm.v);
        const topX = clamp(anc.x, xPos + cardW * 0.22, xPos + cardW * 0.78);
        const topY = yPos + cardH;
        const ctrlX = topX * 0.45 + anc.x * 0.55;
        const ctrlY = topY * 0.55 + anc.y * 0.45 + 22;
        const tOp = (op * 0.62 * smoothstep(0.06, 0.22, bm.w)).toFixed(2);
        svgParts.push(
          `<path d="M ${topX.toFixed(1)} ${topY.toFixed(1)} Q ${ctrlX.toFixed(1)} ${ctrlY.toFixed(1)} ${anc.x.toFixed(1)} ${anc.y.toFixed(1)}" fill="none" stroke="rgba(165, 198, 255, 0.85)" stroke-width="1.35" opacity="${tOp}"/>`,
          `<circle cx="${anc.x.toFixed(1)}" cy="${anc.y.toFixed(1)}" r="4.5" fill="none" stroke="rgba(185, 212, 255, 0.9)" stroke-width="1.4" opacity="${tOp}"/>`
        );
      }
    }
  } else {
    // Focused Pair or Pure Landscape mode
    const visible = [...activeMems.values()]
      .filter((m) => m.w >= 0.14 && m.u >= 0.04 && m.u <= 0.96 && m.v >= 0.10 && m.v <= 0.92)
      .sort((p, q) => q.w - p.w)
      .slice(0, modeObj.maxCards);
    const visIds = new Set(visible.map((v) => v.id));

    for (const [id, entry] of domShades) {
      if (!visIds.has(id)) {
        entry.el.style.display = 'none';
        entry.init = false;
      }
    }

    const nodes = visible.map((item, idx) => {
      const entry = getOrCreateShade(item.id);
      const el = entry.el;
      el.classList.remove('is-solo');
      el.classList.toggle('is-peak', idx === 0);
      el.style.display = 'block';
      const cardW = el.offsetWidth || 220;
      const cardH = el.offsetHeight || 200;
      const anchor = videoUvToScreen(item.u, item.v);
      const tx = clamp(anchor.x - cardW * 0.5 + (idx === 0 ? -40 : 40), 18, vw - cardW - 18);
      const ty = clamp(anchor.y - cardH - 32, 78, vh - cardH - 92);
      return { item, entry, anchor, tx, ty, w: cardW, h: cardH };
    });

    for (const n of nodes) {
      if (!n.entry.init) {
        n.entry.x = n.tx;
        n.entry.y = n.ty;
        n.entry.init = true;
      } else {
        n.entry.x += (n.tx - n.entry.x) * 0.14;
        n.entry.y += (n.ty - n.entry.y) * 0.14;
      }
      const op = clamp((n.item.w - 0.14) / 0.4, 0, 0.96);
      n.entry.el.style.opacity = op.toFixed(3);
      n.entry.el.style.transform = `translate3d(${n.entry.x.toFixed(1)}px, ${n.entry.y.toFixed(1)}px, 0)`;
      heroBoxes.push({ x0: n.entry.x, y0: n.entry.y, x1: n.entry.x + n.w, y1: n.entry.y + n.h });
      svgParts.push(
        `<line x1="${(n.entry.x + n.w * 0.5).toFixed(1)}" y1="${(n.entry.y + n.h).toFixed(1)}" x2="${n.anchor.x.toFixed(1)}" y2="${n.anchor.y.toFixed(1)}" stroke="rgba(148, 186, 255, 0.6)" stroke-width="1.2" stroke-dasharray="3 3" opacity="${(op * 0.8).toFixed(2)}"/>`
      );
    }
  }

  // Render at most ONE non-overlapping 3D ground landmark signpost
  const wpEl = getOrCreateWpSignpost();
  let bestWp = null;
  for (const wp of activeWpts) {
    if (!wptMap.has(wp.id) || wp.w < 0.24 || wp.u < 0.12 || wp.u > 0.88 || wp.v < 0.36 || wp.v > 0.78) continue;
    const sc = videoUvToScreen(wp.u, wp.v);
    const box = { x0: sc.x - 130, y0: sc.y - 54, x1: sc.x + 130, y1: sc.y };
    const overlaps = heroBoxes.some((hb) => !(box.x1 < hb.x0 || box.x0 > hb.x1 || box.y1 < hb.y0 || box.y0 > hb.y1));
    if (!overlaps && (!bestWp || wp.w > bestWp.wp.w)) {
      bestWp = { wp, sc, meta: wptMap.get(wp.id) };
    }
  }

  if (bestWp && modeObj.mode !== 'pure') {
    wpEl.style.display = 'block';
    const wOp = smoothstep(0.24, 0.52, bestWp.wp.w) * 0.88;
    wpEl.style.opacity = wOp.toFixed(3);
    wpEl.style.left = `${bestWp.sc.x.toFixed(1)}px`;
    wpEl.style.top = `${(bestWp.sc.y - 12).toFixed(1)}px`;
    document.getElementById('wp-lbl-txt').textContent = bestWp.meta.label;
    document.getElementById('wp-sub-txt').textContent = bestWp.meta.sub;
    svgParts.push(
      `<line x1="${bestWp.sc.x.toFixed(1)}" y1="${(bestWp.sc.y - 12).toFixed(1)}" x2="${bestWp.sc.x.toFixed(1)}" y2="${bestWp.sc.y.toFixed(1)}" stroke="rgba(138, 182, 255, 0.7)" stroke-width="1.2" opacity="${wOp.toFixed(2)}"/>`,
      `<circle cx="${bestWp.sc.x.toFixed(1)}" cy="${bestWp.sc.y.toFixed(1)}" r="2.6" fill="rgba(168, 206, 255, 0.9)" opacity="${wOp.toFixed(2)}"/>`
    );
  } else {
    wpEl.style.display = 'none';
  }

  tetherSvg.innerHTML = svgParts.join('');
}

function openLightbox(m) {
  wasPlayingBeforeModal = !video.paused;
  video.pause();
  syncPlayIcons();

  lbEra.textContent = `Canto ${m.roman} · ${m.era}`;
  lbPlace.textContent = m.place || '';
  lbTitle.textContent = m.title;

  if (m.text) {
    lbQuote.textContent = m.text;
    lbQuote.hidden = false;
  } else {
    lbQuote.hidden = true;
  }

  if (m.author) {
    lbAuthor.textContent = `— ${m.author}`;
    lbAuthor.hidden = false;
  } else {
    lbAuthor.hidden = true;
  }

  const items = m.media || [];
  if (items.length > 0) {
    lbMedia.hidden = false;
    lbMedia.innerHTML = items
      .map((it) =>
        it.type === 'video'
          ? `<video src="${escHtml(it.src)}" controls playsinline></video>`
          : `<img src="${escHtml(it.src)}" alt="${escHtml(m.title)}">`
      )
      .join('');
  } else {
    lbMedia.hidden = true;
    lbMedia.innerHTML = '';
  }

  lightbox.hidden = false;
}

function closeLightbox() {
  if (lightbox.hidden) return;
  lbMedia.querySelectorAll('video').forEach((v) => v.pause());
  lightbox.hidden = true;
  if (wasPlayingBeforeModal) {
    video.play().catch(() => {});
    syncPlayIcons();
  }
}

function syncPlayIcons() {
  const paused = video.paused;
  iconPlay.hidden = !paused;
  iconPause.hidden = paused;
}

function togglePlay() {
  if (!introVeil.hidden) introVeil.hidden = true;
  if (video.paused) {
    video.play().catch(() => {});
  } else {
    video.pause();
  }
  syncPlayIcons();
}

async function init() {
  const res = await fetch('data/sonicray_walk.json');
  walkData = await res.json();
  scrubber.max = String(walkData.duration_s || 300);

  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
    try {
      const vRes = await fetch(video.getAttribute('src'));
      const blob = await vRes.blob();
      const wasPlaying = !video.paused;
      const tPrev = video.currentTime || 0;
      video.src = URL.createObjectURL(blob);
      video.currentTime = tPrev;
      if (wasPlaying) video.play().catch(() => {});
    } catch {}
  }

  for (const m of walkData.memories || []) memMap.set(m.id, m);
  for (const w of walkData.waypoints || []) wptMap.set(w.id, w);
  soloSchedule = buildSoloSchedule(walkData);

  cantoTicks.innerHTML = walkData.cantos
    .map(
      (c) =>
        `<button type="button" class="canto-tick" data-idx="${c.idx}" data-t="${c.t0}" title="${escHtml(c.title)} (${escHtml(c.era)})">${escHtml(c.roman)} · ${escHtml(c.title.split(',')[0].split('&')[0].trim())}</button>`
    )
    .join('');

  cantoTicks.querySelectorAll('.canto-tick').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!introVeil.hidden) introVeil.hidden = true;
      video.currentTime = Number(btn.dataset.t) + 0.5;
      video.play().catch(() => {});
      syncPlayIcons();
    });
  });

  beginBtn.addEventListener('click', () => {
    introVeil.hidden = true;
    video.play().catch(() => {});
    syncPlayIcons();
  });

  playBtn.addEventListener('click', togglePlay);
  video.addEventListener('play', syncPlayIcons);
  video.addEventListener('pause', syncPlayIcons);

  scrubber.addEventListener('input', () => {
    scrubbing = true;
    if (!introVeil.hidden) introVeil.hidden = true;
    video.currentTime = Number(scrubber.value);
    renderOverlayFrame();
  });
  scrubber.addEventListener('change', () => {
    scrubbing = false;
  });

  speedBtn.addEventListener('click', () => {
    speedIdx = (speedIdx + 1) % SPEEDS.length;
    video.playbackRate = SPEEDS[speedIdx];
    speedBtn.textContent = `${SPEEDS[speedIdx]}×`;
  });

  densityBtn.addEventListener('click', () => {
    densityIdx = (densityIdx + 1) % DENSITY_MODES.length;
    densityBtn.textContent = DENSITY_MODES[densityIdx].label;
    renderOverlayFrame();
  });

  lbBackdrop.addEventListener('click', closeLightbox);
  lbClose.addEventListener('click', closeLightbox);

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeLightbox();
    } else if (e.key === ' ' && lightbox.hidden) {
      e.preventDefault();
      togglePlay();
    }
  });

  const params = new URLSearchParams(window.location.search);
  if (window.location.hash === '#play' || params.get('autoplay') === '1') {
    introVeil.hidden = true;
    video.play().catch(() => {});
  }

  const loop = () => {
    renderOverlayFrame();
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

init();
