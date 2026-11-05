// Main Application & Autorunning Landscape Memory Walk Controller

import { Globe3D } from './globe3d.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const fold = (s) =>
  String(s ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

const PACES = [
  { key: 'normal', label: 'Pace: Stroll', dwell: 1.0, flight: 1.0 },
  { key: 'slow', label: 'Pace: Unhurried', dwell: 1.45, flight: 1.35 },
  { key: 'fast', label: 'Pace: Brisk', dwell: 0.68, flight: 0.68 },
];

const state = {
  data: null,
  memories: [],
  chapters: new Map(),
  globe: null,

  index: -1,
  mode: 'overview', // 'overview' | 'flying' | 'dwelling' | 'paused'
  autoPlay: false,
  paceIdx: 0,
  cinema: false,
  audioUnlocked: false,
  mutedPref: false,

  // Active memory media gallery state
  slideIdx: 0,
  dwellStart: 0,
  dwellDuration: 8000,
  pausedRemaining: 0,
  dwellRaf: 0,
  chapterTimer: 0,
  navToken: 0,

  // Drawer filter state
  q: '',
  chapterFilter: 'all',
  wasAutoBeforeModal: false,
};

function currentPace() {
  return PACES[state.paceIdx];
}

function formatTopoStamp(mem) {
  const [lon, lat] = mem.coords || [0, 0];
  const toDM = (deg, posH, negH) => {
    const abs = Math.abs(deg);
    const d = Math.floor(abs);
    const m = Math.round((abs - d) * 60);
    const carry = m === 60 ? 1 : 0;
    return `${d + carry}°${String(m === 60 ? 0 : m).padStart(2, '0')}′${deg >= 0 ? posH : negH}`;
  };
  const coordPart = `${toDM(lat, 'N', 'S')} ${toDM(lon, 'E', 'W')}`;
  if (typeof mem.elevFt === 'number') {
    return `${coordPart} · ${mem.elevFt.toLocaleString()} FT ELEV.`;
  }
  return coordPart;
}

const preloadedUrls = new Set();
function preloadMemoryMedia(mem) {
  for (const item of mem?.media || []) {
    const src = item.type === 'video' ? item.poster : item.src;
    if (src && !preloadedUrls.has(src)) {
      preloadedUrls.add(src);
      const img = new Image();
      img.src = src;
    }
  }
}

function computeDwellMs(mem) {
  const words = (mem.text || '').trim().split(/\s+/).filter(Boolean).length;
  const readingMs = Math.max(7200, Math.min(13800, 4600 + words * 105));
  const media = mem.media || [];
  const video = media.find((m) => m.type === 'video');
  if (video && video.duration) {
    return Math.round((video.duration * 1000 + 1400) * currentPace().dwell);
  }
  const galleryMs = media.length > 1 ? media.length * 4200 : 0;
  return Math.round(Math.max(readingMs, galleryMs) * currentPace().dwell);
}

// ---------- UI Rendering ----------

function renderHero() {
  const { memories, data } = state;
  const photoCount = memories.reduce((n, m) => n + (m.media?.length || 0), 0);
  $('#memory-count').textContent = memories.length;
  $('#sheet-link').href = data.sheetUrl;
  $('#hero-summary').textContent =
    `${memories.length} trail stops and ${photoCount} photographs & videos across ${data.chapters.length} chapters—from Amarillo ballfields and San Juan elk camps to Haute-Loire and Ross, New Zealand.`;

  $('#hero-chapters').innerHTML = data.chapters
    .map(
      (c) => `<button class="chap-pill" type="button" data-chap="${esc(c.id)}" style="--c:${esc(c.color)}">
        <i></i><span>${esc(c.roman)} · ${esc(c.name)}</span>
      </button>`
    )
    .join('');
}

function renderDrawerChips() {
  const chips = [
    { id: 'all', label: 'All Stops' },
    { id: 'photos', label: 'With Photos' },
    ...state.data.chapters.map((c) => ({ id: c.id, label: `${c.roman} · ${c.name}` })),
  ];
  $('#drawer-chips').innerHTML = chips
    .map(
      (c) =>
        `<button class="f-chip${state.chapterFilter === c.id ? ' on' : ''}" type="button" data-filter="${esc(c.id)}">${esc(c.label)}</button>`
    )
    .join('');
}

function renderDrawerList() {
  const terms = fold(state.q).split(/\s+/).filter(Boolean);
  const filtered = state.memories.filter((m) => {
    if (state.chapterFilter === 'photos' && (!m.media || m.media.length === 0)) return false;
    if (state.chapterFilter !== 'all' && state.chapterFilter !== 'photos' && m.chapter !== state.chapterFilter) {
      return false;
    }
    if (!terms.length) return true;
    const hay = fold(`${m.title} ${m.place} ${m.text}`);
    return terms.every((t) => hay.includes(t));
  });

  if (!filtered.length) {
    $('#drawer-list').innerHTML = `<p style="padding:24px 8px;color:var(--muted);font-size:14px;">No field notes match that search.</p>`;
    return;
  }

  let lastChap = null;
  const html = [];
  for (const m of filtered) {
    if (m.chapter !== lastChap) {
      lastChap = m.chapter;
      const ch = state.chapters.get(m.chapter);
      if (ch) {
        html.push(`<div class="drawer-chap-heading">Chapter ${esc(ch.roman)} · ${esc(ch.name)}</div>`);
      }
    }
    const stopNum = String(state.memories.indexOf(m) + 1).padStart(2, '0');
    const firstMedia = m.media?.[0];
    const thumbSrc = firstMedia ? (firstMedia.type === 'video' ? firstMedia.poster : firstMedia.src) : null;
    const isActive = state.memories[state.index]?.id === m.id;
    const elevBadge = typeof m.elevFt === 'number' ? ` · ${m.elevFt.toLocaleString()} ft` : '';
    html.push(`
      <button class="mem-row${isActive ? ' active' : ''}" type="button" data-mem-id="${esc(m.id)}">
        <div>
          <p class="mem-row-place"><span class="mem-row-num">${stopNum}</span> ${esc(m.place)}${esc(elevBadge)}</p>
          <h3 class="mem-row-title">${esc(m.title)}</h3>
          <p class="mem-row-snip">${esc(m.text)}</p>
        </div>
        ${thumbSrc ? `<img class="mem-thumb" src="${esc(thumbSrc)}" alt="" loading="lazy">` : ''}
      </button>
    `);
  }
  $('#drawer-list').innerHTML = html.join('');
}

function showChapterBanner(chapterId) {
  const ch = state.chapters.get(chapterId);
  if (!ch) return;
  const el = $('#chapter-banner');
  $('#chapter-roman').textContent = `Chapter ${ch.roman}`;
  $('#chapter-name').textContent = ch.name;
  el.hidden = false;
  clearTimeout(state.chapterTimer);
  requestAnimationFrame(() => el.classList.add('visible'));
  state.chapterTimer = setTimeout(() => {
    el.classList.remove('visible');
    setTimeout(() => {
      if (!el.classList.contains('visible')) el.hidden = true;
    }, 550);
  }, 2900);
}

function renderMemoryCard(mem, idx) {
  const card = $('#memory-card');
  const ch = state.chapters.get(mem.chapter);
  $('#mc-chapter').textContent = ch ? `Chapter ${ch.roman} · ${ch.name}` : 'Field Note';
  $('#mc-step').textContent = `STOP ${String(idx + 1).padStart(2, '0')} / ${state.memories.length}`;
  $('#mc-title').textContent = mem.title;
  $('#mc-place-text').textContent = mem.place;
  $('#mc-coords').textContent = formatTopoStamp(mem);

  // Media gallery or video mounted on warm archival linen mat
  const media = mem.media || [];
  const mediaWrap = $('#mc-media');
  const stage = $('#mc-stage');
  const nav = $('#mc-gallery-nav');
  state.slideIdx = 0;

  $$('video', stage).forEach((v) => v.pause());

  if (media.length === 0) {
    mediaWrap.hidden = true;
    stage.innerHTML = '';
    card.classList.add('story-only');
  } else {
    card.classList.remove('story-only');
    mediaWrap.hidden = false;
    stage.innerHTML = media
      .map((item, k) => {
        if (item.type === 'video') {
          return `<div class="mc-slide${k === 0 ? ' active' : ''}" data-slide="${k}">
            <div class="mc-video-wrap">
              <video src="${esc(item.src)}" poster="${esc(item.poster)}" playsinline preload="metadata"></video>
              <button class="mc-mute-btn" type="button" data-act="toggle-mute">Sound on</button>
            </div>
          </div>`;
        }
        return `<div class="mc-slide${k === 0 ? ' active' : ''}" data-slide="${k}">
          <img class="mc-slide-fg" src="${esc(item.src)}" alt="${esc(mem.title)}" data-zoom="${esc(item.src)}">
        </div>`;
      })
      .join('');

    if (media.length > 1) {
      nav.hidden = false;
      $('#mc-dots').innerHTML = media
        .map((_, k) => `<button class="mc-dot${k === 0 ? ' on' : ''}" type="button" data-dot="${k}" aria-label="Photo ${k + 1}"></button>`)
        .join('');
      $('#mc-img-count').textContent = `1 / ${media.length}`;
    } else {
      nav.hidden = true;
    }
  }

  // Story typography scaled cleanly by text length
  const body = $('#mc-body');
  const paragraphs = (mem.text || '')
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const charLen = (mem.text || '').length;
  body.className = 'mc-body ' + (charLen < 120 ? 'quote-lg' : charLen < 260 ? 'quote-md' : 'quote-sm');
  body.innerHTML = paragraphs.map((p) => `<p>${esc(p)}</p>`).join('');
  body.scrollTop = 0;

  $('#mc-progress-bar').style.width = '0%';
  card.hidden = false;
  requestAnimationFrame(() => card.classList.add('in'));

  // Start video if present
  const vid = $('video', stage);
  if (vid) {
    vid.muted = state.mutedPref || !state.audioUnlocked;
    const muteBtn = $('[data-act="toggle-mute"]', stage);
    const syncMuteLabel = () => {
      if (muteBtn) muteBtn.textContent = vid.muted ? 'Tap for sound' : 'Sound on';
    };
    vid.play().then(syncMuteLabel).catch(() => {
      vid.muted = true;
      vid.play().catch(() => {});
      syncMuteLabel();
    });
    vid.addEventListener('ended', () => {
      if (state.autoPlay && state.mode === 'dwelling' && state.memories[state.index]?.id === mem.id) {
        nextStop();
      }
    });
  }
}

function hideMemoryCard() {
  const card = $('#memory-card');
  card.classList.remove('in');
  $$('video', card).forEach((v) => v.pause());
}

function setSlide(idx) {
  const mem = state.memories[state.index];
  if (!mem?.media?.length) return;
  const total = mem.media.length;
  state.slideIdx = ((idx % total) + total) % total;
  $$('.mc-slide', $('#mc-stage')).forEach((el, k) => el.classList.toggle('active', k === state.slideIdx));
  $$('.mc-dot', $('#mc-dots')).forEach((el, k) => el.classList.toggle('on', k === state.slideIdx));
  $('#mc-img-count').textContent = `${state.slideIdx + 1} / ${total}`;
}

function syncTransportUI() {
  const inOverview = state.mode === 'overview';
  $('#hero-card').hidden = !inOverview;
  $('#tour-bar').hidden = inOverview;

  const playBtn = $('#play-btn');
  const running = state.autoPlay && (state.mode === 'flying' || state.mode === 'dwelling');
  playBtn.innerHTML = running
    ? `<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg><span>Pause</span>`
    : `<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8 5v14l11-7z"/></svg><span>${state.index >= 0 ? 'Continue Walk' : 'Walk Trail'}</span>`;

  $('#pace-label').textContent = currentPace().label;
}

// ---------- Tour Engine ----------

function cancelDwellLoop() {
  cancelAnimationFrame(state.dwellRaf);
  state.dwellRaf = 0;
}

function startDwellTimer(mem, resumeMs = null) {
  cancelDwellLoop();
  const totalMs = computeDwellMs(mem);
  state.dwellDuration = totalMs;
  const elapsedAlready = resumeMs != null ? Math.max(0, totalMs - resumeMs) : 0;
  state.dwellStart = performance.now() - elapsedAlready;

  const mediaCount = mem.media?.length || 0;
  const hasVideo = mem.media?.some((m) => m.type === 'video');

  const tick = (now) => {
    if (!state.autoPlay || state.mode !== 'dwelling') return;
    const elapsed = now - state.dwellStart;
    const frac = Math.min(1, elapsed / state.dwellDuration);
    $('#mc-progress-bar').style.width = `${(frac * 100).toFixed(1)}%`;

    // Auto-advance multi-photo galleries evenly across the dwell period
    if (mediaCount > 1 && !hasVideo) {
      const targetSlide = Math.min(mediaCount - 1, Math.floor(frac * mediaCount));
      if (targetSlide !== state.slideIdx) setSlide(targetSlide);
    }

    if (frac >= 1 && !hasVideo) {
      nextStop();
      return;
    }
    state.dwellRaf = requestAnimationFrame(tick);
  };
  state.dwellRaf = requestAnimationFrame(tick);
}

function goToStop(idx, { auto = state.autoPlay, instant = false } = {}) {
  if (!state.memories.length) return;
  if (idx < 0) idx = state.memories.length - 1;
  if (idx >= state.memories.length) {
    // Completed all 37 places -> pull back to the full sunlit Earth overview!
    return returnToGlobe();
  }

  const token = ++state.navToken;
  cancelDwellLoop();

  const prevMem = state.index >= 0 ? state.memories[state.index] : null;
  const mem = state.memories[idx];
  const chapterChanged = !prevMem || prevMem.chapter !== mem.chapter;

  preloadMemoryMedia(mem);
  preloadMemoryMedia(state.memories[idx + 1]);

  state.index = idx;
  state.autoPlay = auto;
  state.mode = 'flying';
  history.replaceState(null, '', `${location.search}#${mem.id}`);

  hideMemoryCard();
  syncTransportUI();
  if (!$('#drawer').hidden) renderDrawerList();

  if (chapterChanged && !instant) {
    showChapterBanner(mem.chapter);
  }

  state.globe.flyToMemory(mem, prevMem, {
    visitedIndex: idx,
    speedMult: instant ? 0 : currentPace().flight,
    onArrive: () => {
      if (token !== state.navToken) return;
      renderMemoryCard(mem, idx);
      if (state.autoPlay) {
        state.mode = 'dwelling';
        syncTransportUI();
        startDwellTimer(mem);
      } else {
        state.mode = 'paused';
        state.pausedRemaining = computeDwellMs(mem);
        syncTransportUI();
      }
    },
  });
}

function beginTour(startIndex = 0) {
  state.audioUnlocked = true;
  goToStop(startIndex, { auto: true });
}

function pauseTour() {
  if (state.mode === 'overview') return;
  state.autoPlay = false;
  if (state.mode === 'dwelling') {
    const elapsed = performance.now() - state.dwellStart;
    state.pausedRemaining = Math.max(1500, state.dwellDuration - elapsed);
  } else {
    state.pausedRemaining = state.index >= 0 ? computeDwellMs(state.memories[state.index]) : 6000;
  }
  cancelDwellLoop();
  state.mode = 'paused';
  syncTransportUI();
}

function resumeTour() {
  state.audioUnlocked = true;
  if (state.index < 0 || state.mode === 'overview') {
    return beginTour(0);
  }
  state.autoPlay = true;
  const mem = state.memories[state.index];
  if (!$('#memory-card').classList.contains('in')) {
    return goToStop(state.index, { auto: true });
  }
  state.mode = 'dwelling';
  syncTransportUI();
  state.globe.startLocalOrbit(mem);
  startDwellTimer(mem, state.pausedRemaining || computeDwellMs(mem));
}

function togglePlayPause() {
  const running = state.autoPlay && (state.mode === 'flying' || state.mode === 'dwelling');
  if (running) pauseTour();
  else resumeTour();
}

function nextStop() {
  state.audioUnlocked = true;
  goToStop(state.index + 1, { auto: state.autoPlay });
}

function prevStop() {
  state.audioUnlocked = true;
  goToStop(Math.max(0, state.index - 1), { auto: state.autoPlay });
}

function returnToGlobe() {
  ++state.navToken;
  cancelDwellLoop();
  state.autoPlay = false;
  state.mode = 'overview';
  state.index = -1;
  history.replaceState(null, '', location.pathname + location.search);
  hideMemoryCard();
  setTimeout(() => {
    if (state.mode === 'overview') $('#memory-card').hidden = true;
  }, 450);
  syncTransportUI();
  state.globe.globeOverview({ center: [-98, 33], immediate: false });
}

function toggleCinema(force) {
  state.cinema = typeof force === 'boolean' ? force : !state.cinema;
  document.body.classList.toggle('cinema-mode', state.cinema);
  $('#cinema-exit').hidden = !state.cinema;
}

// ---------- Drawer & Lightbox ----------

function openDrawer() {
  state.wasAutoBeforeModal = state.autoPlay && (state.mode === 'dwelling' || state.mode === 'flying');
  if (state.wasAutoBeforeModal) pauseTour();
  renderDrawerChips();
  renderDrawerList();
  $('#scrim').hidden = false;
  $('#drawer').hidden = false;
  $('#memories-btn').setAttribute('aria-expanded', 'true');
}

function closeDrawer() {
  if ($('#drawer').hidden) return;
  $('#scrim').hidden = true;
  $('#drawer').hidden = true;
  $('#memories-btn').setAttribute('aria-expanded', 'false');
}

function openLightbox(src, caption) {
  state.wasAutoBeforeModal = state.autoPlay && state.mode === 'dwelling';
  if (state.wasAutoBeforeModal) pauseTour();
  $('#lightbox-img').src = src;
  $('#lightbox-caption').textContent = caption || '';
  $('#lightbox').hidden = false;
}

function closeLightbox() {
  if ($('#lightbox').hidden) return;
  $('#lightbox').hidden = true;
  $('#lightbox-img').src = '';
  if (state.wasAutoBeforeModal) resumeTour();
}

// ---------- Event Bindings & Boot ----------

function bindEvents() {
  $('#start-tour-btn').addEventListener('click', () => beginTour(0));
  $('#open-index-btn').addEventListener('click', openDrawer);
  $('#memories-btn').addEventListener('click', () => ($('#drawer').hidden ? openDrawer() : closeDrawer()));
  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#scrim').addEventListener('click', closeDrawer);
  $('#home-btn').addEventListener('click', returnToGlobe);
  $('#globe-btn').addEventListener('click', returnToGlobe);

  $('#cinema-btn').addEventListener('click', () => {
    toggleCinema(true);
    if (state.mode === 'overview') beginTour(0);
  });
  $('#cinema-exit').addEventListener('click', () => toggleCinema(false));

  $('#play-btn').addEventListener('click', togglePlayPause);
  $('#next-btn').addEventListener('click', nextStop);
  $('#prev-btn').addEventListener('click', prevStop);
  $('#pace-btn').addEventListener('click', () => {
    state.paceIdx = (state.paceIdx + 1) % PACES.length;
    syncTransportUI();
  });

  // Hero chapter pills jump right into that chapter with the walk running
  $('#hero-chapters').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-chap]');
    if (!btn) return;
    const idx = state.memories.findIndex((m) => m.chapter === btn.dataset.chap);
    if (idx >= 0) beginTour(idx);
  });

  // Memory card gallery & zoom actions
  $('#memory-card').addEventListener('click', (e) => {
    const zoomImg = e.target.closest('[data-zoom]');
    if (zoomImg) {
      const mem = state.memories[state.index];
      openLightbox(zoomImg.dataset.zoom, `${mem.title} · ${mem.place}`);
      return;
    }
    const dot = e.target.closest('[data-dot]');
    if (dot) {
      setSlide(Number(dot.dataset.dot));
      return;
    }
    const muteBtn = e.target.closest('[data-act="toggle-mute"]');
    if (muteBtn) {
      const vid = $('#mc-stage video');
      if (vid) {
        vid.muted = !vid.muted;
        state.mutedPref = vid.muted;
        state.audioUnlocked = true;
        muteBtn.textContent = vid.muted ? 'Tap for sound' : 'Sound on';
      }
    }
  });
  $('#mc-prev-img').addEventListener('click', () => setSlide(state.slideIdx - 1));
  $('#mc-next-img').addEventListener('click', () => setSlide(state.slideIdx + 1));

  // Drawer interactions
  $('#search-input').addEventListener('input', (e) => {
    state.q = e.target.value;
    renderDrawerList();
  });
  $('#drawer-chips').addEventListener('click', (e) => {
    const c = e.target.closest('[data-filter]');
    if (!c) return;
    state.chapterFilter = c.dataset.filter;
    renderDrawerChips();
    renderDrawerList();
  });
  $('#drawer-list').addEventListener('click', (e) => {
    const row = e.target.closest('[data-mem-id]');
    if (!row) return;
    const idx = state.memories.findIndex((m) => m.id === row.dataset.memId);
    closeDrawer();
    if (idx >= 0) goToStop(idx, { auto: false });
  });

  // Lightbox close
  $('#lightbox-close').addEventListener('click', closeLightbox);
  $('#lightbox').addEventListener('click', (e) => {
    if (e.target.id === 'lightbox') closeLightbox();
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    const typing = /input|textarea|select/i.test(document.activeElement?.tagName);
    if (typing) {
      if (e.key === 'Escape') document.activeElement.blur();
      return;
    }
    if (e.key === 'Escape') {
      if (!$('#lightbox').hidden) return closeLightbox();
      if (!$('#drawer').hidden) return closeDrawer();
      if (state.cinema) return toggleCinema(false);
      if (state.mode !== 'overview') return returnToGlobe();
    } else if (e.key === ' ') {
      e.preventDefault();
      state.mode === 'overview' ? beginTour(0) : togglePlayPause();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      state.mode === 'overview' ? beginTour(0) : nextStop();
    } else if (e.key === 'ArrowLeft' && state.mode !== 'overview') {
      e.preventDefault();
      prevStop();
    } else if (e.key === 'c' || e.key === 'C') {
      toggleCinema();
    } else if (e.key === 'm' || e.key === 'M') {
      $('#drawer').hidden ? openDrawer() : closeDrawer();
    }
  });
}

async function init() {
  bindEvents();
  const res = await fetch('data/memories.json', { cache: 'no-cache' });
  const data = await res.json();
  state.data = data;
  state.memories = data.memories;
  state.chapters = new Map(data.chapters.map((c) => [c.id, c]));
  renderHero();

  state.globe = new Globe3D($('#globe-canvas'), $('#fx-canvas'), {
    onSelectMemory: (id) => {
      const idx = state.memories.findIndex((m) => m.id === id);
      if (idx >= 0) goToStop(idx, { auto: false });
    },
    onUserInterrupt: () => {
      if (state.autoPlay) pauseTour();
    },
  });

  await state.globe.init();
  state.globe.setData(state.memories, data.chapters);
  $('#loader').classList.add('done');

  // Support deep link (#m03, #tour) or ?cinema=1
  const params = new URLSearchParams(location.search);
  if (params.get('cinema') === '1') toggleCinema(true);

  const hash = location.hash.replace(/^#/, '');
  if (hash === 'tour') {
    beginTour(0);
  } else if (hash) {
    const idx = state.memories.findIndex((m) => m.id === hash);
    if (idx >= 0) {
      goToStop(idx, { auto: false, instant: params.get('instant') === '1' });
      return;
    }
  }
  state.globe.globeOverview({ center: [-98, 33], immediate: true });
}

init().catch((err) => {
  console.error(err);
  $('#loader').textContent = `Could not load memories: ${err.message}`;
});
