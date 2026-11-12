/* Noyau partagé : accès API, composants UI, formats, préférences. */

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- Icônes (traits 24x24) ---------- */
const P = {
  home: 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  users: 'M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2.5 20c.6-3.4 3.2-5 6.5-5s5.9 1.6 6.5 5M16.5 4.3a3.5 3.5 0 010 6.4M18 15.2c2 .5 3.2 2 3.5 4.8',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c.8-4 4-6 8-6s7.2 2 8 6',
  scan: 'M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M4 12h16',
  list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  sliders: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4',
  search: 'M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-4.3-4.3',
  plus: 'M12 5v14M5 12h14',
  check: 'M5 12.5l4.5 4.5L19 7',
  x: 'M6 6l12 12M18 6L6 18',
  alert: 'M12 4l9.5 16h-19zM12 10v4M12 17.3h.01',
  info: 'M12 11v6M12 7h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  wifioff: 'M3 3l18 18M5 12.5a10 10 0 015-2.7M8.5 16a5 5 0 016-.8M12 20h.01M16.5 9.1A14 14 0 0122 12.5M2 8.8a15 15 0 015-3',
  refresh: 'M20 11a8 8 0 00-14.5-4M4 5v4h4M4 13a8 8 0 0014.5 4M20 19v-4h-4',
  download: 'M12 4v11M7.5 11L12 15.5 16.5 11M5 20h14',
  upload: 'M12 16V5M7.5 9L12 4.5 16.5 9M5 20h14',
  nfc: 'M6 8.5a6 6 0 010 7M10 6a10 10 0 010 12M14 4a14 14 0 010 16',
  bolt: 'M13 3L5 13.5h6L10 21l8-10.5h-6z',
  camera: 'M4 8h3l1.6-2.4h6.8L17 8h3v11H4zM12 16.5a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4z',
  logout: 'M10 4H5v16h5M15 8l4 4-4 4M19 12H9',
  sun: 'M12 16a4 4 0 100-8 4 4 0 000 8zM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8.5 8.5 0 119.5 4a7 7 0 0010.5 10.5z',
  back: 'M15 5l-7 7 7 7',
  chevron: 'M9 5l7 7-7 7',
  clock: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2',
  table: 'M3 6h18v4H3zM6 10v9M18 10v9',
  ticket: 'M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 100 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 100-4z',
  flag: 'M5 21V4M5 4h11l-2 4 2 4H5',
  shield: 'M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z',
  layers: 'M12 3 3 8l9 5 9-5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5',
  'help-circle': 'M9.6 9a2.5 2.5 0 114.2 1.8c-1.1 1-1.8 1.4-1.8 3.2M12 17.5h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  pin: 'M12 21s7-6.2 7-11.5A7 7 0 005 9.5C5 14.8 12 21 12 21zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  file: 'M7 3h7l5 5v13H7zM14 3v5h5',
  copy: 'M9 9h11v11H9zM5 15V4h11',
  key: 'M14 10a4 4 0 11-3-3.9M11 10l-8 8v3h3l1-1v-2h2l1.5-1.5M15.5 7.5h.01',
  phone: 'M8 3h8a1 1 0 011 1v16a1 1 0 01-1 1H8a1 1 0 01-1-1V4a1 1 0 011-1zM11 18h2',
  bell: 'M6 16v-5a6 6 0 0112 0v5l2 2H4zM10 20a2 2 0 004 0',
  edit: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',
  'building-2': 'M5 21V4h9v17M14 9h5v12M8 8h3M8 12h3M8 16h3M3 21h18',
  'file-pdf': 'M7 3h7l5 5v13H7zM14 3v5h5M9.5 16.5h5M9.5 13h5',
  qr: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 14h2v6h-4M14 18v2',
};
export const icon = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${P[n] || ''}"/></svg>`;

/* ---------- API ---------- */
export async function api(url, { method = 'GET', json, form, signal } = {}) {
  const headers = {};
  let body;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  else if (form) body = form;
  let r;
  try { r = await fetch(url, { method, headers, body, signal, credentials: 'same-origin' }); }
  catch (e) { if (e.name === 'AbortError') throw e; const err = new Error('Réseau indisponible'); err.network = true; throw err; }
  if (r.status === 401) { location.href = '/'; throw new Error('Session expirée'); }
  const ct = r.headers.get('content-type') || '';
  if (!r.ok) {
    const data = ct.includes('json') ? await r.json().catch(() => null) : null;
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? 'Données invalides : ' + d.map(x => (x.loc || []).slice(-1) + ' — ' + x.msg).join(' ; ') : 'Une erreur est survenue.';
    const e = new Error(msg); e.status = r.status; throw e;
  }
  if (ct.includes('json')) return r.json();
  return r;
}

/* ---------- Formats ---------- */
export const parseTs = s => { if (!s) return null; const t = /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z'; const d = new Date(t); return isNaN(d) ? null : d; };
const rtf = new Intl.RelativeTimeFormat('fr', { numeric: 'auto' });
export function rel(s) {
  const d = s instanceof Date ? s : parseTs(s); if (!d) return '—';
  const sec = Math.round((d - Date.now()) / 1000), a = Math.abs(sec);
  if (a < 45) return "à l'instant";
  if (a < 3600) return rtf.format(Math.round(sec / 60), 'minute');
  if (a < 86400) return rtf.format(Math.round(sec / 3600), 'hour');
  return rtf.format(Math.round(sec / 86400), 'day');
}
export const clock = s => { const d = parseTs(s); return d ? d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : '—'; };
export function dateFr(s, long = true) {
  if (!s) return 'Date à définir';
  const d = /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(s + 'T12:00:00') : new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString('fr-FR', long ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' } : { day: 'numeric', month: 'short' });
}
export const initials = n => (String(n || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('') || '?').toUpperCase();
export const plural = (n, w, pl) => `${n} ${n > 1 ? (pl || w + 's') : w}`;
export const norm = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export const roleLabel = r => ({ superadmin: 'Superadministrateur', admin: 'Administrateur', supervisor: 'Superviseur', agent: 'Agent' }[r] || r);
export const methodLabel = m => ({ qr: 'QR', nfc: 'NFC', manual: 'Manuel', offline: 'Hors ligne' }[m] || m);
export const pct = (a, b) => (b > 0 ? Math.round((a / b) * 100) : 0);
export function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16)); return [...b].map(x => x.toString(16).padStart(2, '0')).join('');
}
export function debounce(fn, ms = 180) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* ---------- Préférences & retours sensoriels ---------- */
const PREF_KEY = 'ia-prefs';
export const prefs = {
  get() { try { return { sound: true, vibrate: true, autoSingle: false, ...JSON.parse(localStorage.getItem(PREF_KEY) || '{}') }; } catch { return { sound: true, vibrate: true, autoSingle: false }; } },
  set(k, v) { try { localStorage.setItem(PREF_KEY, JSON.stringify({ ...this.get(), [k]: v })); } catch { } },
};
let actx;
export function feedback(kind) {
  const p = prefs.get();
  if (p.vibrate && navigator.vibrate) navigator.vibrate(kind === 'ok' ? 40 : kind === 'warn' ? [30, 40, 30] : [90, 60, 90]);
  if (!p.sound) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const seq = kind === 'ok' ? [[880, 0, .09]] : kind === 'warn' ? [[620, 0, .1], [620, .14, .1]] : [[220, 0, .16], [180, .2, .2]];
    for (const [f, t, d] of seq) {
      const o = actx.createOscillator(), g = actx.createGain();
      o.frequency.value = f; o.type = 'sine'; g.gain.value = .12;
      o.connect(g); g.connect(actx.destination);
      o.start(actx.currentTime + t); o.stop(actx.currentTime + t + d);
    }
  } catch { }
}
export function setTheme(t) {
  try { t === 'auto' ? localStorage.removeItem('ia-theme') : localStorage.setItem('ia-theme', t); } catch { }
  if (t === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
}
export const getTheme = () => { try { return localStorage.getItem('ia-theme') || 'auto'; } catch { return 'auto'; } };

/* ---------- Toasts ---------- */
export function toast(msg, type = '', ms = 3200) {
  const box = $('#toasts'); if (!box) return;
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.innerHTML = (type === 'ok' ? icon('check', 'sm') : type === 'bad' ? icon('alert', 'sm') : '') + `<span>${esc(msg)}</span>`;
  box.appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .25s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 260); }, ms);
}

/* ---------- Sheets ---------- */
export function sheet(html, { onClose } = {}) {
  $$('dialog.sheet').forEach(d => d.close());
  const d = document.createElement('dialog');
  d.className = 'sheet';
  d.innerHTML = `<div class="grab" aria-hidden="true"></div>${html}`;
  document.body.appendChild(d);
  d.addEventListener('close', () => { d.remove(); onClose && onClose(); });
  d.addEventListener('click', e => { if (e.target === d || e.target.closest('[data-close]')) d.close(); });
  d.showModal();
  return d;
}
export const sheetHead = (title, sub = '') => `<div class="sheet-head" style="padding:6px 18px 0"><div class="grow"><h2>${esc(title)}</h2>${sub ? `<p class="muted small">${esc(sub)}</p>` : ''}</div><button class="btn icon ghost" data-close aria-label="Fermer">${icon('x')}</button></div>`;
export function busy(btn, on = true) { if (btn) { btn.classList.toggle('busy', on); btn.disabled = on; } }

/* ---------- Gabarits communs ---------- */
export const empty = (ic, title, text = '', action = '') =>
  `<div class="empty">${icon(ic)}<strong>${esc(title)}</strong>${text ? `<p class="small">${esc(text)}</p>` : ''}${action}</div>`;
export const skeletons = (n = 3, h = 72) => Array.from({ length: n }, () => `<div class="skeleton" style="min-height:${h}px"></div>`).join('');
export function ring(p, label = 'présents') {
  const R = 54, C = 2 * Math.PI * R;
  return `<div class="ring" role="img" aria-label="${p} % ${esc(label)}"><svg viewBox="0 0 128 128"><circle class="track" cx="64" cy="64" r="${R}" fill="none" stroke-width="11"/><circle class="bar" cx="64" cy="64" r="${R}" fill="none" stroke-width="11" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-target="${C * (1 - Math.min(p, 100) / 100)}"/></svg><div class="center"><span class="pct num">${p}%</span><span class="cap">${esc(label)}</span></div></div>`;
}
export function animateRings(root = document) {
  requestAnimationFrame(() => requestAnimationFrame(() => $$('.ring .bar', root).forEach(c => { c.style.strokeDashoffset = c.dataset.target; })));
}
export const meter = (a, b) => { const p = pct(a, b); return `<div class="meter ${p >= 100 ? 'full' : ''}" role="progressbar" aria-valuenow="${a}" aria-valuemin="0" aria-valuemax="${b}"><i style="width:${p}%"></i></div>`; };

/* ---------- Coque applicative ---------- */
export function shellHTML({ tabs, active, title, sub = '', back = '', actions = '' }) {
  const tab = t => `<a class="tab ${t.scan ? 'scan' : ''}" href="${t.href}" data-link ${t.id === active ? 'aria-current="page"' : ''} data-tab="${t.id}">
    ${t.scan ? `<span class="puck">${icon(t.icon)}</span>` : icon(t.icon)}<span class="lbl">${esc(t.label)}</span>
    <span class="badge-dot ${t.badge ? '' : 'hidden'}" data-badge="${t.id}">${t.badge || ''}</span></a>`;
  return `<nav class="tabbar" aria-label="Navigation principale">${tabs.map(tab).join('')}</nav>
  <div class="stage"><header class="appbar" id="appbar">${back}<h1 class="ellipsis" id="barTitle">${esc(title)}${sub ? `<span class="sub ellipsis">${esc(sub)}</span>` : ''}</h1><div class="row" id="barActions">${actions}</div></header>
  <main class="main" id="view" tabindex="-1"></main></div>`;
}
export function setActiveTab(id) {
  $$('.tabbar .tab').forEach(a => { if (a.dataset.tab === id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
}
export function setBadge(id, n) { const b = $(`[data-badge="${id}"]`); if (!b) return; b.textContent = n || ''; b.classList.toggle('hidden', !n); }
export function watchScroll() { const bar = $('#appbar'); const f = () => bar && bar.classList.toggle('scrolled', scrollY > 4); addEventListener('scroll', f, { passive: true }); f(); }
