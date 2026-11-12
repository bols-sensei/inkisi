/* Page d'un événement : Aperçu, Invités, Scanner, Suivi (superviseur/admin), Gérer (admin). */
import { $, $$, esc, icon, api, toast, sheet, sheetHead, busy, dateFr, initials, plural, norm, roleLabel, methodLabel, pct, meter, ring, animateRings, empty, skeletons, shellHTML, setActiveTab, setBadge, rel, clock, parseTs, feedback, uuid, debounce, watchScroll } from './core.js';
import { cache, queue } from './offline.js';
import { mountScanner } from './scanner.js';
import { registrations, editInvitation, editConferenceParticipant, editEvent, exportCsv, TASK, PRIO, dt } from './extras.js';

const STATUS = { draft: 'Brouillon', active: 'En cours', closed: 'Terminé' };
const DEC = { review: ['À examiner', 'warn'], pending: ['À examiner', 'warn'], approve: ['Approuvée', 'ok'], approved: ['Approuvée', 'ok'], reject: ['Rejetée', 'bad'], rejected: ['Rejetée', 'bad'] };

export class EventView {
  constructor(id, user) {
    this.id = id; this.user = user; this.role = user.role; this.tab = null;
    this.detail = null; this.dash = null; this.activity = null; this.exceptions = null; this.agents = null; this.program = []; this.tasks = [];
    this.stale = false; this.scanner = null; this.timer = null; this.memberBadgeLogoData = null;
    this.g = { q: '', status: 'tous', type: 'tous', shown: 40 }; this.seg = 'agents'; this.exFilter = 'tous';
  }
  get isAdmin() { return this.role === 'admin' || this.role === 'superadmin'; }
  get canFollow() { return this.role === 'supervisor' || this.isAdmin; }
  get tabs() {
    const t = {
      apercu: { id: 'apercu', label: 'Aperçu', icon: 'home', href: '#apercu' },
      invites: { id: 'invites', label: 'Invités', icon: 'list', href: '#invites' },
      scan: { id: 'scan', label: 'Scanner', icon: 'scan', href: '#scan', scan: true },
      suivi: { id: 'suivi', label: 'Suivi', icon: 'pulse', href: '#suivi' },
      gerer: { id: 'gerer', label: 'Gérer', icon: 'sliders', href: '#gerer' },
      badges: { id: 'badges', label: 'Badges', icon: 'ticket', href: '#badges' },
    };
    const conf = this.detail?.event_type === 'conference', inv = conf ? (this.isAdmin ? [{ id: 'invites', label: 'Inscrits', icon: 'users', href: '#invites' }] : []) : [t.invites];
    if (this.isAdmin) return [t.apercu, ...inv, t.scan, t.suivi, t.gerer, t.badges];
    if (this.role === 'supervisor') return [t.apercu, ...inv, t.scan, t.suivi];
    return [t.apercu, t.scan, ...inv];
  }

  mount(app) {
    this.app = app;
    app.innerHTML = shellHTML({
      tabs: this.tabs, active: '', title: 'Événement',
      back: `<a class="btn icon ghost" href="/" data-link aria-label="Retour aux événements">${icon('back')}</a>`,
      actions: `<button class="btn icon ghost" data-act="reload" aria-label="Actualiser">${icon('refresh', 'sm')}</button>`,
    });
    this.view = $('#view'); watchScroll();
    this.onClick = e => this.click(e); this.view.addEventListener('click', this.onClick);
    this.onNet = () => { this.updateNet(); if (navigator.onLine) this.refresh(true); };
    addEventListener('online', this.onNet); addEventListener('offline', this.onNet);
    this.onQueue = async () => setBadge('scan', await this.queueCount());
    document.addEventListener('ia:queue', this.onQueue);
    this.view.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(1, 250)}${skeletons(2, 80)}</div>`;
    this.ready = this.load().then(ok => { if (ok) this.setTab(this.tab || ''); });
    this.timer = setInterval(() => { if (!document.hidden && navigator.onLine && this.detail) this.refresh(true); }, 15000);
    this.onQueue();
  }
  destroy() {
    clearInterval(this.timer); this.scanner?.destroy(); this.scanner = null;
    this.view?.removeEventListener('click', this.onClick);
    removeEventListener('online', this.onNet); removeEventListener('offline', this.onNet);
    document.removeEventListener('ia:queue', this.onQueue);
  }
  async queueCount() { return (await queue.all()).filter(i => i.event_id === this.id).length; }

  /* ---------- Données ---------- */
  async load() {
    try {
      this.detail = await api(`/admin/api/events/${this.id}`); this.stale = false; cache.set(this.id, this.detail);
      await this.loadDash(); await this.loadEventTools();
    } catch (e) {
      const c = cache.get(this.id);
      if (e.network && c) { this.detail = c.data; this.stale = true; this.cachedAt = c.at; }
      else { this.view.innerHTML = empty(e.status === 403 ? 'shield' : 'wifioff', e.status === 403 ? 'Événement non attribué' : e.status === 404 ? 'Événement introuvable' : 'Chargement impossible', e.message, `<a class="btn primary" href="/" data-link>Retour aux événements</a>`); return false; }
    }
    $('#barTitle').innerHTML = `${esc(this.detail.name)}<span class="sub ellipsis">${esc(dateFr(this.detail.event_date, false))}${this.detail.venue ? ', ' + esc(this.detail.venue) : ''}</span>`;
    document.title = this.detail.name + ' — Invitations';
    return true;
  }
  async loadDash() {
    if (this.isAdmin) { try { this.activity = await api(`/supervisor/api/events/${this.id}/activity`); } catch (e) { if (!e.network) this.activity = []; } return; }
    try { this.dash = await api(`/supervisor/api/events/${this.id}/dashboard`); } catch (e) { if (!e.network) this.dash = null; }
  }
  async loadEventTools() {
    const [program,tasks]=await Promise.allSettled([api(`/api/events/${this.id}/program`),api(`/api/events/${this.id}/tasks`)]);
    if(program.status==='fulfilled')this.program=program.value;
    if(tasks.status==='fulfilled')this.tasks=tasks.value;
  }
  async refresh(silent) {
    try {
      this.detail = await api(`/admin/api/events/${this.id}`); this.stale = false; cache.set(this.id, this.detail); await this.loadDash(); await this.loadEventTools();
      if (this.canFollow && this.tab === 'suivi') await this.loadFollow();
    } catch (e) { if (!silent) toast(e.network ? 'Hors ligne : données du dernier chargement.' : e.message, 'bad'); this.stale = !!e.network; }
    this.updateNet();
    if (this.tab === 'apercu') this.renderOverview(); else if (this.tab === 'invites') this.paintGuests(); else if (this.tab === 'suivi') this.paintFollow();
    else if (this.tab === 'gerer' && !silent) this.renderManage();
  }
  invs() { return this.detail?.invitations || []; }
  stats() {
    if (this.detail?.event_type === 'conference') { const d=this.detail, count=d.registrations_count||0, accepted=d.accepted_registrations||0, entered=d.checked_in_registrations||0, expected=accepted; return {count,expected,entered,arrived:entered,complete:entered,partial:0,types:{},tables:{},remaining:Math.max(0,expected-entered),pct:pct(entered,expected)}; }
    const inv = this.invs(), S = { count: inv.length, expected: 0, entered: 0, arrived: 0, complete: 0, partial: 0, types: {}, tables: {} };
    for (const i of inv) {
      S.expected += i.quota; S.entered += i.entered; if (i.entered > 0) S.arrived++; if (i.remaining === 0) S.complete++; else if (i.entered > 0) S.partial++;
      const t = (S.types[i.invitation_type] ||= { n: 0, q: 0, e: 0 }); t.n++; t.q += i.quota; t.e += i.entered;
      if (i.table_name) { const b = (S.tables[i.table_name] ||= { q: 0, e: 0 }); b.q += i.quota; b.e += i.entered; }
    }
    S.remaining = Math.max(0, S.expected - S.entered); S.pct = pct(S.entered, S.expected); return S;
  }

  /* ---------- Navigation d'onglets ---------- */
  setTab(t) {
    if (!this.detail) { this.tab = t; return; }
    const ids = this.tabs.map(x => x.id);
    if (!ids.includes(t)) t = this.role === 'agent' ? 'scan' : 'apercu';
    const changed = t !== this.tab; this.tab = t; setActiveTab(t);
    if (this.scanner && t !== 'scan') { this.scanner.destroy(); this.scanner = null; }
    if (!changed && this.view.dataset.tab === t) return;
    this.view.dataset.tab = t; scrollTo(0, 0);
    ({ apercu: () => this.renderOverview(), invites: () => this.renderGuests(), scan: () => this.renderScan(), suivi: () => this.renderFollow(), gerer: () => this.renderManage(), badges: () => this.renderBadgeDesign() })[t]();
  }
  eventStatusPanel() {
    if (!['admin', 'superadmin', 'supervisor'].includes(this.role)) return '';
    const status = this.detail?.status || 'draft';
    const labels = { draft: 'Brouillon', active: 'En cours', closed: 'Terminé' };
    const action = status === 'draft'
      ? `<button class="btn primary" data-act="start-event">Lancer l’événement</button>`
      : status === 'active' && this.isAdmin
        ? `<button class="btn danger" data-act="close-event">Clôturer l’événement</button>`
        : status === 'closed' && this.isAdmin
          ? `<button class="btn ghost" data-act="reopen-event">Relancer l’événement</button>` : '';
    const guidance = status === 'draft'
      ? 'Le contrôle des entrées reste bloqué tant que l’événement n’est pas lancé.'
      : status === 'active'
        ? (this.isAdmin ? 'Le scanner est actif. Vous pouvez clôturer l’événement quand l’accueil est terminé.' : 'Le scanner est actif. Seul un administrateur peut clôturer l’événement.')
        : 'L’événement est clôturé. Seul un administrateur peut le relancer.';
    return `<section class="card event-status-card" id="eventStatusControl"><div class="row between wrap"><div class="grow"><div class="row wrap"><h2>État de l’événement</h2><span class="badge ${status === 'active' ? 'ok' : status === 'closed' ? 'bad' : 'warn'}">${labels[status]}</span></div><p class="small muted">${guidance}</p></div>${action}</div></section>`;
  }
  async changeEventStatus(status) {
    try {
      const result = await api(`/admin/api/events/${this.id}/status`, { method: 'PATCH', json: { status } });
      this.detail.status = result.status;
      toast(result.status === 'active' ? 'Événement lancé. Le scanner est actif.' : result.status === 'closed' ? 'Événement clôturé.' : 'Événement relancé.', 'ok');
      if (this.view.dataset.tab === 'scan') this.renderScan();
      else if (this.view.dataset.tab === 'apercu') this.renderOverview();
    } catch (e) { toast(e.message, 'bad'); }
  }
  updateNet() {
    const l = $('.live', this.view); if (!l) return;
    const off = !navigator.onLine || this.stale; l.classList.toggle('off', off); l.classList.toggle('is-live', !off);
    l.lastChild.textContent = off ? (this.cachedAt ? 'Données du ' + rel(new Date(this.cachedAt)) : 'Hors ligne') : 'En direct';
  }

  /* ---------- Aperçu ---------- */
  async renderOverview() {
    const d = this.detail, S = this.stats(), v = this.view; v.dataset.tab = 'apercu';
    const off = !navigator.onLine || this.stale, q = await this.queueCount();
    const types = Object.entries(S.types).sort((a, b) => b[1].q - a[1].q), tables = Object.entries(S.tables).sort((a, b) => b[1].e - a[1].e || b[1].q - a[1].q).slice(0, 8);
    const recent = this.dash?.recent_entries || [];
    v.innerHTML = `<div class="col loose" style="margin-top:8px">
      <section class="hero"><div class="row between"><span class="live ${off ? 'off' : 'is-live'}"><i></i><span>${off ? (this.cachedAt ? 'Données du ' + rel(new Date(this.cachedAt)) : 'Hors ligne') : 'En direct'}</span></span>${this.role !== 'agent' && d.status && d.status !== 'draft' ? `<span class="badge" style="background:rgba(255,255,255,.16);color:#fff">${esc(STATUS[d.status] || d.status)}</span>` : ''}</div>
        <h1 style="margin-top:12px">${esc(d.name)}</h1>
        <p class="muted small row wrap" style="margin-top:4px;gap:4px 14px"><span class="row" style="gap:5px">${icon('calendar', 'sm')}${esc(dateFr(d.event_date))}</span>${d.venue ? `<span class="row" style="gap:5px">${icon('pin', 'sm')}${esc(d.venue)}</span>` : ''}</p>
        <div class="hero-grid">${ring(S.pct)}<div class="kpis"><div class="kpi"><strong class="num">${S.entered}</strong><span>${d.event_type === 'conference' ? 'Participants entrés' : 'Présents'}</span></div><div class="kpi"><strong class="num">${S.remaining}</strong><span>${d.event_type === 'conference' ? 'Acceptés non entrés' : 'Restants'}</span></div><div class="kpi"><strong class="num">${S.expected}</strong><span>${d.event_type === 'conference' ? 'Inscriptions acceptées' : 'Attendus'}</span></div><div class="kpi"><strong class="num">${S.count}</strong><span>${d.event_type === 'conference' ? 'Inscriptions' : 'Invitations'}</span></div></div></div>${d.event_type === 'conference' ? `<p class="small muted">Capacité maximale : ${d.capacity ?? 'non définie'} place(s)</p>` : ''}</section>
      ${this.eventStatusPanel()}
      ${q ? `<a class="banner info" href="#scan" data-link>${icon('clock', 'sm')}<span class="grow">${plural(q, 'contrôle')} en attente de synchronisation</span><strong>Voir</strong></a>` : ''}
      ${d.event_type === 'conference' ? `<section class="card col"><strong>Conférence</strong><p class="small muted">${d.registration_open ? 'Inscriptions ouvertes' : 'Inscriptions fermées'} · ${d.accepted_registrations || 0} acceptée(s)</p><a class="btn ghost block" href="/conference/${esc(d.registration_token || '')}" target="_blank" rel="noopener">Voir le formulaire public</a></section>` : ''}
      ${this.program.length ? `<section class="card col"><div class="row between"><h2 style="font-size:1.05rem">Programme</h2><a class="btn sm ghost" href="/api/events/${this.id}/program.pdf">PDF</a></div>${this.program.map(x=>`<div class="item"><div class="grow"><strong>${esc(x.title)}</strong><div class="meta">${dt(x.starts_at)} – ${new Date(x.ends_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })} · ${esc(x.location||'')}</div>${x.speaker?`<p class="small muted">${esc(x.speaker)}</p>`:''}</div></div>`).join('')}</section>` : ''}
      <div class="tiles"><div class="tile"><strong class="num">${S.arrived}<span class="faint" style="font-size:.95rem"> / ${S.count}</span></strong><span>${d.event_type === 'conference' ? 'Participants entrés' : 'Invitations arrivées'}</span></div><div class="tile"><strong class="num">${S.complete}</strong><span>${d.event_type === 'conference' ? 'Acceptées' : 'Invitations complètes'}</span></div></div>
      ${!S.count ? `<div class="card">${empty(d.event_type === 'conference' ? 'users' : 'upload', d.event_type === 'conference' ? 'Aucune inscription' : 'Aucune invitation', d.event_type === 'conference' ? 'Les inscriptions de cette conférence apparaîtront ici.' : (this.isAdmin ? 'Importez la liste des invités pour démarrer.' : 'La liste des invités n’a pas encore été importée.'), this.isAdmin ? '<a class="btn primary" href="#gerer" data-link>Gérer l’événement</a>' : '')}</div>` : ''}
      ${types.length > 1 ? `<section class="card col"><h2 style="font-size:1.05rem">Par type d’invitation</h2><div class="bars">${types.map(([k, t]) => `<div class="bar-row"><span class="ellipsis">${esc(k)}</span>${meter(t.e, t.q)}<span class="num small muted">${t.e}/${t.q}</span></div>`).join('')}</div></section>` : ''}
      ${tables.length ? `<section class="card col"><h2 style="font-size:1.05rem">Tables</h2><div class="bars">${tables.map(([k, t]) => `<div class="bar-row"><span class="ellipsis">Table ${esc(k)}</span>${meter(t.e, t.q)}<span class="num small muted">${t.e}/${t.q}</span></div>`).join('')}</div></section>` : ''}
      ${this.isAdmin ? this.activityCard() : `<section class="card"><div class="row between"><h2 style="font-size:1.05rem">Dernières entrées</h2><span class="tiny faint">${recent.length ? 'Les ' + recent.length + ' plus récentes' : ''}</span></div>${recent.length ? `<div class="feed">${recent.map(r => `<div class="f"><div class="dot">+${r.quantity}</div><div class="grow"><div class="title ellipsis" style="font-weight:650">${esc(r.guest_name)}</div><div class="small muted row wrap" style="gap:2px 10px"><span>${esc(r.reference)}</span><span>${esc(r.agent)}</span><span class="badge">${methodLabel(r.method)}</span></div></div><div class="tiny faint" style="text-align:right">${clock(r.created_at)}<br>${rel(r.created_at)}</div></div>`).join('')}</div>` : empty('ticket', 'Aucune entrée pour l’instant', 'Les entrées apparaissent ici dès qu’un contrôle est enregistré.')}</section>`}
    </div>`;
    animateRings(v);
  }
  activityCard() {
    const a = this.activity || [];
    return `<section class="card"><h2 style="font-size:1.05rem">Activité des agents</h2>${a.length ? `<div class="feed">${[...a].sort((x, y) => (y.last_activity || '').localeCompare(x.last_activity || '')).map(x => `<div class="f"><div class="dot" style="background:var(--brand-soft);color:var(--brand)">${esc(initials(x.full_name))}</div><div class="grow"><div class="title" style="font-weight:650">${esc(x.full_name)}</div><div class="small muted">${plural(x.entries, 'contrôle')} pour ${plural(x.people, 'personne')}</div></div><span class="tiny faint">${rel(x.last_activity)}</span></div>`).join('')}</div>` : empty('pulse', 'Aucune activité', 'Les contrôles des agents apparaîtront ici.')}</section>`;
  }

  /* ---------- Invités & Participants ---------- */
  renderGuests() {
    const isConf = this.detail.event_type === 'conference';
    this.view.dataset.tab = 'invites';
    const S = this.stats(), types = Object.keys(S.types);
    const searchPlaceholder = isConf ? 'Nom, prénom, email, téléphone ou référence...' : 'Nom, référence ou table...';

    this.view.innerHTML = `<div class="col" style="margin-top:8px">
      ${isConf ? `
        <div class="row wrap between" style="gap:8px;margin-bottom:4px">
          <button class="btn sm primary" data-act="manual-registration">${icon('plus', 'sm')}Ajouter un invité manuel</button>
          <div class="row" style="gap:6px">
            <button class="btn sm ghost" data-act="registrations">${icon('users', 'sm')}Inscriptions</button>
            <button class="btn sm ghost" data-act="participants-pdf">${icon('download', 'sm')}Répertoire PDF</button>
          </div>
        </div>
      ` : (this.isAdmin ? `
        <div class="row wrap" style="gap:8px;margin-bottom:4px">
          <button class="btn sm primary" data-act="new-invitation">${icon('plus', 'sm')}Nouvelle invitation</button>
        </div>
      ` : '')}
      <div class="searchbox">${icon('search', 'sm')}<input class="input" id="gq" type="search" placeholder="${searchPlaceholder}" value="${esc(this.g.q)}" aria-label="Rechercher" autocomplete="off"></div>
      <div class="chips" id="gChips" role="group" aria-label="Filtrer par état"></div>
      ${!isConf && types.length > 1 ? `<div class="chips" id="gTypes" role="group" aria-label="Filtrer par type"></div>` : ''}
      <p class="small muted" id="gCount" aria-live="polite"></p>
      <div class="list" id="gList"></div>
      <button class="btn ghost block hidden" id="gMore">Afficher plus</button>
    </div>`;

    $('#gq').addEventListener('input', debounce(e => {
      this.g.q = e.target.value;
      this.g.shown = 40;
      this.paintGuests();
    }, 150));

    $('#gMore').onclick = () => {
      this.g.shown += 60;
      this.paintGuests();
    };

    this.paintGuests();
  }

  async paintGuests() {
    if (!$('#gList')) return;
    if (this.detail.event_type === 'conference') {
      return this.paintConferenceGuests();
    }

    const all = this.invs(), q = norm(this.g.q);
    const st = i => i.remaining === 0 ? 'complets' : i.entered > 0 ? 'encours' : 'attendus';
    const base = all.filter(i => (this.g.type === 'tous' || i.invitation_type === this.g.type) && (!q || norm(`${i.guest_name} ${i.reference} ${i.table_name}`).includes(q)));
    const count = k => base.filter(i => k === 'tous' || st(i) === k).length;
    $('#gChips').innerHTML = [['tous', 'Tous'], ['attendus', 'Attendus'], ['encours', 'En cours'], ['complets', 'Complets']].map(([k, l]) => `<button class="chip" data-gs="${k}" aria-pressed="${this.g.status === k}">${l} <span class="n num">${count(k)}</span></button>`).join('');
    const tc = $('#gTypes'); if (tc) tc.innerHTML = ['tous', ...Object.keys(this.stats().types)].map(k => `<button class="chip" data-gt="${esc(k)}" aria-pressed="${this.g.type === k}">${k === 'tous' ? 'Tous les types' : esc(k)}</button>`).join('');
    const rows = base.filter(i => this.g.status === 'tous' || st(i) === this.g.status);
    $('#gCount').textContent = rows.length === all.length ? plural(all.length, 'invitation') : `${plural(rows.length, 'résultat')} sur ${all.length}`;
    $('#gList').innerHTML = rows.length ? rows.slice(0, this.g.shown).map(i => `<button class="item" data-guest="${i.id}"><div class="avatar ${i.remaining === 0 ? 'done' : i.entered > 0 ? 'part' : ''}">${i.remaining === 0 ? icon('check', 'sm') : esc((i.guest_name || '?')[0].toUpperCase())}</div><div class="grow"><div class="title ellipsis">${esc(i.guest_name)}</div><div class="meta"><span>${esc(i.reference)}</span><span>${esc(i.invitation_type)}</span>${i.table_name ? `<span>${icon('table', 'sm')}${esc(i.table_name)}</span>` : ''}</div></div><div class="qty num">${i.entered}/${i.quota}<small>entrés</small></div></button>`).join('') : (all.length ? empty('search', 'Aucun invité trouvé', 'Essayez un autre nom, une référence ou changez de filtre.') : empty('list', 'Aucune invitation', this.isAdmin ? 'Importez la liste depuis l’onglet Gérer.' : ''));
    $('#gMore').classList.toggle('hidden', rows.length <= this.g.shown); $('#gMore').textContent = `Afficher plus (${rows.length - this.g.shown} restants)`;
  }

  async paintConferenceGuests() {
    const listEl = $('#gList');
    if (!listEl) return;
    const qStr = (this.g.q || '').trim();
    $('#gChips').innerHTML = [
      ['tous', 'Tous'],
      ['entres', 'Entrés'],
      ['attendus', 'Attendus'],
      ['manuels', 'Invités manuels']
    ].map(([k, l]) => `<button class="chip" data-cs="${k}" aria-pressed="${this.g.status === k}">${l}</button>`).join('');

    $('#gChips').querySelectorAll('[data-cs]').forEach(b => {
      b.onclick = () => {
        this.g.status = b.dataset.cs;
        this.paintConferenceGuests();
      };
    });

    try {
      const qParam = qStr || ' ';
      const rows = await api(`/checkin/api/events/${this.id}/lookup?q=${encodeURIComponent(qParam)}`);
      this._confRows = rows;

      let filtered = rows;
      if (this.g.status === 'entres') filtered = rows.filter(r => r.entered > 0);
      else if (this.g.status === 'attendus') filtered = rows.filter(r => r.entered === 0);
      else if (this.g.status === 'manuels') filtered = rows.filter(r => r.is_manual);

      $('#gCount').textContent = qStr
        ? `${plural(filtered.length, 'résultat')} pour « ${esc(qStr)} »`
        : `${plural(filtered.length, 'participant')}`;

      if (!filtered.length) {
        listEl.innerHTML = empty('search', 'Aucun participant trouvé', qStr ? 'Vérifiez l’orthographe du nom, de l’e-mail ou du numéro de téléphone.' : 'Aucun participant ne correspond à ce filtre.');
        $('#gMore').classList.add('hidden');
        return;
      }

      listEl.innerHTML = filtered.slice(0, this.g.shown).map(r => `
        <button class="item" data-conf-guest="${r.id}">
          ${r.photo_data ? `<img src="${esc(r.photo_data)}" alt="" style="width:44px;height:44px;border-radius:12px;object-fit:cover;border:1.5px solid var(--accent)">` : `<div class="avatar ${r.entered ? 'done' : ''}">${esc((r.guest_name || '?')[0].toUpperCase())}</div>`}
          <div class="grow" style="text-align:left">
            <div class="title ellipsis">
              <strong>${esc(r.guest_name)}</strong>
              ${r.is_manual ? `<span class="badge" style="margin-left:6px;font-size:.7rem">Manuel</span>` : ''}
            </div>
            <div class="meta">
              <span class="badge brand">${esc((r.category || 'participant').toUpperCase())}</span>
              ${r.profession ? `<span>${esc(r.profession)}</span>` : ''}
              ${r.email && !r.email.includes('@conference.local') ? `<span>${esc(r.email)}</span>` : ''}
              ${r.phone ? `<span>${esc(r.phone)}</span>` : ''}
            </div>
          </div>
          <div class="qty num">
            ${r.entered ? `<span class="badge ok">${icon('check', 'sm')} Entré</span>` : `<span class="badge ghost">Attendu</span>`}
          </div>
        </button>
      `).join('');

      $('#gMore').classList.toggle('hidden', filtered.length <= this.g.shown);
      $('#gMore').textContent = `Afficher plus (${filtered.length - this.g.shown} restants)`;

      listEl.querySelectorAll('[data-conf-guest]').forEach(b => {
        b.onclick = () => {
          const item = this._confRows.find(x => x.id === +b.dataset.confGuest);
          if (item) this.openConferenceGuest(item);
        };
      });
    } catch(err) {
      listEl.innerHTML = `<div class="banner bad">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`;
    }
  }

  openConferenceGuest(r) {
    const photoHtml = r.photo_data
      ? `<img src="${esc(r.photo_data)}" alt="Photo" style="width:84px;height:84px;border-radius:18px;object-fit:cover;border:2px solid var(--accent);margin:0 auto 10px;box-shadow:0 4px 14px rgba(0,0,0,.15)">`
      : `<div class="avatar" style="width:84px;height:84px;font-size:2.2rem;border-radius:18px;margin:0 auto 10px;background:var(--accent-soft);color:var(--accent)">${esc((r.guest_name || '?')[0].toUpperCase())}</div>`;

    const statusBadge = r.entered
      ? `<span class="badge ok">${icon('check', 'sm')} Entré à ${r.checked_in_at ? new Date(r.checked_in_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : 'plus tôt'}</span>`
      : `<span class="badge ghost">Non encore entré</span>`;

    const d = sheet(`
      <div class="sheet-head" style="padding:8px 18px 0">
        <div class="grow">
          <h2>${esc(r.guest_name)}</h2>
          <div class="row wrap" style="margin-top:4px">
            <span class="badge brand">${esc((r.category || 'participant').toUpperCase())}</span>
            ${r.is_manual ? `<span class="badge">Ajout manuel</span>` : `<span class="badge">Inscription publique</span>`}
            ${statusBadge}
          </div>
        </div>
        <button class="btn icon ghost" data-close aria-label="Fermer">${icon('x')}</button>
      </div>
      <div class="sheet-body" style="text-align:center">
        ${photoHtml}
        <h3 style="font-size:1.2rem;margin-bottom:2px">${esc(r.guest_name)}</h3>
        ${r.profession ? `<p style="font-weight:600;color:var(--accent)">${esc(r.profession)}</p>` : ''}
        ${r.organization_name ? `<p class="small muted">${esc(r.organization_name)}</p>` : ''}

        <div class="card flat col" style="text-align:left;margin:12px 0;padding:12px 14px">
          ${r.email && !r.email.includes('@conference.local') ? `<div class="row between"><span class="small muted">E-mail</span><strong>${esc(r.email)}</strong></div>` : ''}
          ${r.phone ? `<div class="row between"><span class="small muted">Téléphone</span><strong>${esc(r.phone)}</strong></div>` : ''}
          <div class="row between"><span class="small muted">Référence</span><span class="num">${esc(r.reference)}</span></div>
          <div class="row between"><span class="small muted">Statut</span><span>${esc(r.status)}</span></div>
        </div>

        <div id="cgErr"></div>

        ${!r.entered ? `
          <button class="btn primary block" id="cgVal" style="min-height:52px;font-size:1.05rem;margin-bottom:8px">
            ${icon('check', 'sm')} Valider l’entrée
          </button>
        ` : ''}

        ${r.badge_url ? `
          <div class="row" style="gap:8px;margin-bottom:8px">
            <a class="btn ghost grow" href="${esc(r.badge_url)}" download target="_blank" rel="noopener">
              ${icon('download', 'sm')} Télécharger le badge
            </a>
            <a class="btn ghost grow" href="${esc(r.badge_url)}" target="_blank" rel="noopener">
              Voir le badge
            </a>
          </div>
        ` : ''}

        ${this.isAdmin ? `
          <button class="btn tonal block" id="cgEdit" style="margin-bottom:8px">
            ${icon('edit', 'sm')} Modifier les informations
          </button>
        ` : ''}

        <button class="btn ghost block" data-close>Fermer</button>
      </div>
    `);

    const valBtn = $('#cgVal', d);
    if (valBtn) {
      valBtn.onclick = async () => {
        busy(valBtn, true);
        try {
          await api(`/checkin/api/conferences/${this.id}/scan`, {
            method: 'POST',
            json: { registration_id: r.id, idempotency_key: uuid(), method: 'manual' }
          });
          d.close();
          toast('Entrée validée pour ' + r.guest_name, 'ok');
          feedback('ok');
          this.paintConferenceGuests();
        } catch(err) {
          busy(valBtn, false);
          $('#cgErr', d).innerHTML = `<div class="banner bad">${esc(err.message)}</div>`;
        }
      };
    }

    const editBtn = $('#cgEdit', d);
    if (editBtn) {
      editBtn.onclick = () => {
        d.close();
        editConferenceParticipant(this, r);
      };
    }
  }

  openGuest(id) {
    const i = this.invs().find(x => x.id === id); if (!i) return;
    const online = navigator.onLine; let qty = 1;
    const d = sheet(`<div class="sheet-head" style="padding:6px 18px 0"><div class="grow"><h2>${esc(i.guest_name)}</h2><div class="row wrap" style="margin-top:6px"><span class="badge brand">${esc(i.reference)}</span><span class="badge">${esc(i.invitation_type)}</span>${i.table_name ? `<span class="badge cobalt">${icon('table', 'sm')}Table ${esc(i.table_name)}</span>` : ''}</div></div><button class="btn icon ghost" data-close aria-label="Fermer">${icon('x')}</button></div>
      <div class="sheet-body">
        <div class="col tight">${meter(i.entered, i.quota)}<p class="small muted num">${i.entered} sur ${i.quota} entrés, ${i.remaining} restant${i.remaining > 1 ? 's' : ''}</p></div>
        ${i.remaining > 0 ? (online ? `${i.remaining > 1 ? `<div class="stepper"><button id="m" aria-label="Moins">−</button><output id="q" class="num">1</output><button id="p" aria-label="Plus">+</button></div>` : ''}<div id="ge"></div><button class="btn primary block" id="go" style="min-height:56px;font-size:1.05rem">Enregistrer 1 entrée</button>` : `<div class="banner warn">${icon('wifioff', 'sm')}<span>Hors ligne : scannez le QR code de l’invité pour mettre l’entrée en attente.</span></div>`) : `<div class="banner ok">${icon('check', 'sm')}<span>Tous les invités de cette invitation sont entrés.</span></div>`}
        ${this.isAdmin ? `<button class="btn tonal block" id="ed">${icon('edit', 'sm')}Modifier l’invitation</button>` : ''}
        ${this.role === 'supervisor' ? `<button class="btn tonal block" id="ex">${icon('flag', 'sm')}Signaler une exception</button>` : ''}</div>`);
    const upd = () => { $('#q', d) && ($('#q', d).textContent = qty); $('#go', d).textContent = `Enregistrer ${qty} entrée${qty > 1 ? 's' : ''}`; };
    $('#m', d) && ($('#m', d).onclick = () => { qty = Math.max(1, qty - 1); upd(); });
    $('#p', d) && ($('#p', d).onclick = () => { qty = Math.min(i.remaining, qty + 1); upd(); });
    $('#go', d) && ($('#go', d).onclick = async e => {
      const b = e.currentTarget; busy(b, true);
      try {
        const res = await api(`/checkin/api/events/${this.id}/entry`, { method: 'POST', json: { invitation_id: i.id, quantity: qty, method: 'manual', idempotency_key: uuid() } });
        feedback('ok'); toast(`${res.reference} : ${plural(qty, 'entrée')} enregistrée${qty > 1 ? 's' : ''}.`, 'ok'); this.onEntry(i.id, res); d.close();
      } catch (err) { busy(b, false); feedback('bad'); $('#ge', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; if (err.status === 409) this.refresh(true); }
    });
    $('#ed', d) && ($('#ed', d).onclick = () => { d.close(); editInvitation(this, i); });
    $('#ex', d) && ($('#ex', d).onclick = () => { d.close(); this.exceptionSheet(i); });
  }
  onEntry(invId, res) {
    const i = invId && this.invs().find(x => x.id === invId);
    if (i && res) { i.entered = res.entered; i.remaining = res.remaining; cache.set(this.id, this.detail); }
    if (this.tab === 'invites') this.paintGuests();
    this.refresh(true);
  }

  renderRegs() {
    this.view.dataset.tab = 'invites'; const S = this.stats();
    this.view.innerHTML = `<div class="col loose" style="margin-top:8px"><div class="tiles"><div class="tile"><strong class="num">${S.count}</strong><span>Inscriptions</span></div><div class="tile"><strong class="num">${S.complete}</strong><span>Acceptées</span></div></div><button class="btn primary block" data-act="registrations">${icon('users', 'sm')}Gérer les inscriptions</button><button class="btn ghost block" data-act="manual-registration">${icon('plus', 'sm')}Ajouter un participant</button></div>`;
  }

  /* ---------- Scanner ---------- */
  renderScan() {
    this.view.dataset.tab = 'scan'; this.view.innerHTML = `<div class="col loose" style="margin-top:8px">${this.eventStatusPanel()}<div id="scanRoot"></div></div>`;
    this.scanner = mountScanner($('#scanRoot'), { eventId: this.id, role: this.role, conference: this.detail.event_type === 'conference', cached: () => this.invs(), onEntry: (id, r) => this.onEntry(id, r), exception: inv => { const i = this.invs().find(x => x.id === inv.id) || inv; this.exceptionSheet(i); } });
  }

  /* ---------- Exceptions ---------- */
  exceptionSheet(i, defaultDecision = 'review') {
    let decision = defaultDecision;
    const d = sheet(`${sheetHead('Exception', `${i.guest_name} (${i.reference})`)}<form class="sheet-body" id="xf">
      <div class="seg" role="group" aria-label="Décision">${[['review', 'À examiner'], ['approve', 'Approuver'], ['reject', 'Rejeter']].map(([k, l]) => `<button type="button" data-d="${k}" aria-pressed="${k === decision}">${l}</button>`).join('')}</div>
      <label class="field">Motif <small>8 caractères minimum, conservé dans le journal d’audit</small><textarea class="textarea" name="reason" required minlength="8" maxlength="1000" placeholder="Ex. Invité présent avec un accompagnant non prévu, accord de la famille"></textarea></label>
      <div id="xe"></div><button class="btn primary block" type="submit">Enregistrer la décision</button></form>`);
    $$('[data-d]', d).forEach(b => b.onclick = () => { decision = b.dataset.d; $$('[data-d]', d).forEach(x => x.setAttribute('aria-pressed', x === b)); });
    $('#xf', d).onsubmit = async e => {
      e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true);
      try { await api(`/checkin/api/events/${this.id}/exceptions`, { method: 'POST', json: { invitation_id: i.id, reason: new FormData(e.target).get('reason'), decision } }); toast('Décision enregistrée.', 'ok'); d.close(); this.exceptions = null; if (this.tab === 'suivi') this.renderFollow(); else this.loadFollow(); }
      catch (err) { busy(b, false); $('#xe', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; }
    };
  }

  /* ---------- Suivi ---------- */
  async loadFollow() {
    const [a, x, g] = await Promise.allSettled([
      api(`/supervisor/api/events/${this.id}/activity`), api(`/supervisor/api/events/${this.id}/exceptions`),
      this.isAdmin ? Promise.resolve(null) : api(`/supervisor/api/events/${this.id}/agents`)]);
    if (a.status === 'fulfilled') this.activity = a.value; if (x.status === 'fulfilled') this.exceptions = x.value; if (g.status === 'fulfilled' && g.value) this.agents = g.value;
    this.followErr = a.status === 'rejected' && x.status === 'rejected' ? (a.reason?.message || 'Erreur') : '';
    setBadge('suivi', this.groupExceptions().filter(g => g.current.status === 'pending').length);
  }
  groupExceptions() {
    const map = new Map();
    for (const e of this.exceptions || []) { if (!map.has(e.reference)) map.set(e.reference, []); map.get(e.reference).push(e); }
    return [...map.values()].map(list => { list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')); return { current: list[0], list }; }).sort((a, b) => (b.current.created_at || '').localeCompare(a.current.created_at || ''));
  }
  async renderFollow() {
    this.view.dataset.tab = 'suivi';
    this.view.innerHTML = `<div class="col" style="margin-top:8px"><div class="seg" role="group" aria-label="Section">${[['agents', 'Agents'], ['exceptions', 'Exceptions'], ['equipe', 'Équipe']].map(([k, l]) => `<button data-seg="${k}" aria-pressed="${this.seg === k}">${l}${k === 'exceptions' ? '<span class="badge warn hidden" id="exN" style="margin-left:6px"></span>' : ''}</button>`).join('')}</div><div id="fBody" class="col">${this.activity || this.exceptions ? '' : skeletons(3, 70)}</div></div>`;
    if (!this.activity || !this.exceptions || !this.agents) await this.loadFollow();
    this.paintFollow();
  }
  paintFollow() {
    const b = $('#fBody'); if (!b) return;
    $$('[data-seg]', this.view).forEach(x => x.setAttribute('aria-pressed', x.dataset.seg === this.seg));
    const groups = this.groupExceptions(), pend = groups.filter(g => g.current.status === 'pending').length, n = $('#exN'); if (n) { n.textContent = pend; n.classList.toggle('hidden', !pend); }
    if (this.followErr) { b.innerHTML = empty('wifioff', 'Suivi indisponible', this.followErr, '<button class="btn primary" data-act="reload-follow">Réessayer</button>'); return; }
    if (this.seg === 'agents') {
      const a = [...(this.activity || [])].sort((x, y) => (y.last_activity || '').localeCompare(x.last_activity || '')), max = Math.max(1, ...a.map(x => x.people));
      b.innerHTML = a.length ? `<div class="tiles"><div class="tile"><strong class="num">${a.length}</strong><span>Agent${a.length > 1 ? 's' : ''} actif${a.length > 1 ? 's' : ''}</span></div><div class="tile"><strong class="num">${a.reduce((s, x) => s + x.entries, 0)}</strong><span>Contrôles</span></div></div>
        <div class="list">${a.map(x => `<div class="item" style="align-items:flex-start"><div class="avatar">${esc(initials(x.full_name))}</div><div class="grow col tight"><div class="row between"><div class="title">${esc(x.full_name)}</div><strong class="num">${x.people}</strong></div><div class="meter"><i style="width:${pct(x.people, max)}%"></i></div><div class="small muted row wrap" style="gap:4px 10px">${plural(x.entries, 'contrôle')}<span>Dernier contrôle ${rel(x.last_activity)}</span>${(x.methods || []).map(m => `<span class="badge">${methodLabel(m)}</span>`).join('')}</div></div></div>`).join('')}</div>` : empty('pulse', 'Aucune activité pour l’instant', 'Les contrôles de chaque agent apparaîtront ici en direct.');
    } else if (this.seg === 'exceptions') {
      const rows = groups.filter(g => this.exFilter === 'tous' || (this.exFilter === 'pending' ? g.current.status === 'pending' : g.current.status !== 'pending'));
      b.innerHTML = `<div class="chips">${[['tous', 'Toutes'], ['pending', 'À examiner'], ['done', 'Traitées']].map(([k, l]) => `<button class="chip" data-ef="${k}" aria-pressed="${this.exFilter === k}">${l}</button>`).join('')}</div>
        ${this.isAdmin ? `<div class="banner info">${icon('shield', 'sm')}<span>Les décisions sont prises par les superviseurs.</span></div>` : ''}
        <div class="list">${rows.length ? rows.map(g => { const c = g.current, [lab, cls] = DEC[c.status] || [c.status, '']; return `<div class="item" style="align-items:flex-start"><div class="avatar part">${icon('flag', 'sm')}</div><div class="grow col tight"><div class="row between"><div class="title ellipsis">${esc(c.guest_name)}</div><span class="badge ${cls}">${lab}</span></div><div class="small muted"><span>${esc(c.reference)}</span> signalé par ${esc(c.agent)}, ${rel(c.created_at)}</div><p class="small">${esc(c.reason)}</p>${g.list.length > 1 ? `<p class="tiny faint">${plural(g.list.length, 'décision')} dans l’historique</p>` : ''}${this.role === 'supervisor' && c.status === 'pending' ? `<div class="row" style="margin-top:4px"><button class="btn sm primary" data-ex-do="${esc(c.reference)}">Décider</button></div>` : ''}</div></div>`; }).join('') : empty('flag', this.exceptions?.length ? 'Rien dans cette catégorie' : 'Aucune exception', 'Les cas particuliers signalés par les superviseurs apparaîtront ici.')}</div>`;
    } else {
      const team = this.isAdmin ? (this.detail.assignments || []).map(u => ({ name: u.full_name, username: u.username, role: u.role, active: true })) : (this.agents || []);
      b.innerHTML = `<div class="list">${team.length ? team.map(u => `<div class="item"><div class="avatar">${esc(initials(u.name))}</div><div class="grow"><div class="title ellipsis">${esc(u.name)}</div><div class="meta"><span>${esc(u.username)}</span></div></div><span class="badge ${u.role === 'supervisor' ? 'brand' : ''}">${roleLabel(u.role)}</span>${u.active ? '' : '<span class="badge bad">Inactif</span>'}</div>`).join('') : empty('users', 'Aucun agent affecté')}</div>`;
    }
  }

  async completeTask(taskId) {
    const task=this.tasks.find(x=>x.id===taskId);if(!task)return;
    try{await api(`/api/events/${this.id}/tasks/${taskId}`,{method:'PATCH',json:{...task,status:'done'}});await this.loadEventTools();this.renderOverview();toast('Responsabilité terminée.','ok');}catch(e){toast(e.message,'bad');}
  }
  /* ---------- Gérer (admin) ---------- */
  renderManage() {
    const d = this.detail, S = this.stats(); this.view.dataset.tab = 'gerer';
    const wedding = d.event_type !== 'conference';
    const eventTools = wedding ? `
      <section class="card col"><div class="row between"><div><h2 style="font-size:1.05rem">Invitations de mariage</h2><p class="small muted">Individuel, couple, famille, groupe ou format personnalisé.</p></div><button class="btn sm primary" data-act="new-invitation">${icon('plus','sm')}Ajouter</button></div>
        <div class="row wrap"><button class="btn primary grow" data-act="batch-pdf" ${S.count ? '' : 'disabled'}>${icon('file-pdf','sm')}PDF personnalisés en lot</button></div>
        <div><h3 class="small">Import Excel / CSV</h3><p class="small muted">Les références existantes ne changent jamais.</p></div>
        <label class="drop" id="drop" for="file">${icon('upload', 'lg')}<strong id="fname">Choisir un fichier</strong><span class="small">Colonnes : nom, nombre, type, table</span></label>
        <input type="file" id="file" class="sr-only" accept=".xlsx,.xlsm,.csv"><div id="imErr"></div>
        <div class="row wrap"><button class="btn primary grow" id="doImport" disabled>Importer</button><button class="btn ghost" data-act="template">${icon('download', 'sm')}Modèle CSV</button></div></section>
      <section class="card col"><h2 style="font-size:1.05rem">Dossier pour le designer</h2><p class="small muted">Manifeste Excel, PDF de référence et QR PNG des invitations.</p><button class="btn primary block" data-act="pack" ${S.count ? '' : 'disabled'}>${icon('download', 'sm')}Générer le dossier</button>
        <div class="row wrap"><a class="btn ghost grow" href="/admin/api/events/${this.id}/invitations.pdf" ${S.count ? '' : 'hidden'}>${icon('file-pdf', 'sm')}PDF de toutes les invitations</a><button class="btn ghost grow" data-act="csv" ${S.count ? '' : 'disabled'}>${icon('download', 'sm')}Présences (CSV)</button></div></section>` : `
      <section class="card col"><h2 style="font-size:1.05rem">Inscription publique</h2><p class="small muted">Capacité : ${d.capacity || 'illimitée'} · Lien ${d.registration_open ? 'ouvert' : 'fermé'}</p>
        <label class="field">Capacité maximale<input class="input" id="confCapacity" type="number" min="1" value="${d.capacity || ''}" placeholder="Sans limite"></label>
        <label class="row" style="align-items:center;gap:8px"><input id="confOpen" type="checkbox" ${d.registration_open ? 'checked' : ''}> Ouvrir les inscriptions</label>
        <button class="btn primary block" data-act="save-conference">Enregistrer et obtenir le lien</button><div id="conferenceLink" class="small"></div>
        <button class="btn ghost block" data-act="registrations">Gérer les inscriptions</button>
        <button class="btn ghost block" data-act="participants-pdf">${icon('file-pdf', 'sm')}Télécharger la liste des participants (PDF)</button>
        <button class="btn ghost block" data-act="reg-qr">QR du lien d’inscription</button>
        <button class="btn tonal block" data-act="manual-registration">Ajouter un participant manuellement</button>
        <label class="field">Importer des participants (.xlsx / .csv)<input class="input" type="file" id="participantFile" accept=".xlsx,.xlsm,.csv"></label>
        <button class="btn ghost block" data-act="import-participants">Importer la liste</button>
      </section>`;
    this.view.innerHTML = `<div class="col loose" style="margin-top:8px">
      <section class="card row between"><div><h2 style="font-size:1.05rem">Informations</h2><p class="small muted">Nom, date, lieu et état : ${esc(STATUS[d.status] || 'Brouillon')}</p></div><button class="btn sm primary" data-act="edit-event">${icon('edit', 'sm')}Modifier</button></section>
      <section class="card col"><div class="row between"><div><h2 style="font-size:1.05rem">Équipe affectée</h2><p class="small muted">${plural(d.assignments.length, 'compte')}</p></div><button class="btn sm primary" data-act="assign">${icon('plus', 'sm')}Affecter</button></div>
        <div class="list">${d.assignments.length ? d.assignments.map(u => `<div class="item"><div class="avatar">${esc(initials(u.full_name))}</div><div class="grow"><div class="title ellipsis">${esc(u.full_name)}</div><div class="meta"><span>${esc(u.username)}</span></div></div><span class="badge ${u.role === 'supervisor' ? 'brand' : ''}">${roleLabel(u.role)}</span><button class="btn sm ghost" data-unassign="${u.id}" aria-label="Retirer ${esc(u.full_name)}">Retirer</button></div>`).join('') : empty('users', 'Personne n’est affecté', 'Affectez des agents et des superviseurs pour qu’ils voient cet événement.')}</div></section>
      ${eventTools}
      <section class="card row between wrap"><div><h2 style="font-size:1.05rem">Design et QR des badges</h2><p class="small muted">Choix des couleurs, aperçu avant partage et QR publics ou réservés aux membres.</p></div><a class="btn primary" href="#badges" data-link>${icon('ticket','sm')}Configurer les badges</a></section>
      <p class="tiny faint">Les données sont enregistrées sur le serveur. Les actions sont historisées.</p></div>`;
    if (wedding) {
      const f = $('#file'); f.onchange = () => { const x = f.files[0]; $('#fname').textContent = x ? `${x.name} (${Math.max(1, Math.round(x.size / 1024))} Ko)` : 'Choisir un fichier'; $('#drop').classList.toggle('has', !!x); $('#doImport').disabled = !x; $('#imErr').innerHTML = ''; };
      $('#doImport').onclick = () => this.doImport();
    }
  }
  async newInvitation() {
    const d = sheet(`${sheetHead('Nouvelle invitation', 'Un QR code et un quota propres à cette invitation.')}<form class="sheet-body" id="if">
      <label class="field">Nom / destinataire<input class="input" name="guest_name" required maxlength="200"></label>
      <label class="field">Type<select class="select" name="invitation_type"><option value="individuelle">Individuelle</option><option value="couple">Couple</option><option value="famille">Famille</option><option value="groupe">Groupe</option><option value="personnalise">Personnalisé</option></select></label>
      <label class="field">Quota de personnes<input class="input" name="quota" type="number" min="1" max="10000" value="1" required></label>
      <label class="field">Nom personnalisé (si applicable)<input class="input" name="custom_type" maxlength="30" placeholder="Ex. Partenaires"></label>
      <label class="field">Table<input class="input" name="table_name" maxlength="80"></label><div id="ie"></div><button class="btn primary block" type="submit">Créer l’invitation</button></form>`);
    $('#if',d).onsubmit=async e=>{e.preventDefault();const form=e.target,data=Object.fromEntries(new FormData(form));if(data.invitation_type==='personnalise'&&data.custom_type.trim())data.invitation_type=data.custom_type.trim();delete data.custom_type;data.quota=+data.quota;const b=$('button[type=submit]',form);busy(b,true);try{const out=await api(`/admin/api/events/${this.id}/invitations`,{method:'POST',json:data});d.close();toast(`Invitation ${out.reference} créée.`, 'ok');await this.refresh(true);this.renderManage();}catch(err){busy(b,false);$('#ie',d).innerHTML=`<div class="banner bad">${esc(err.message)}</div>`;}};
  }
  async manualParticipant() {
    const d = sheet(`${sheetHead('Ajouter un invité / participant', 'Créez un badge officiel pour cet invité sans passer par l’inscription publique.')}
      <form id="mpf" class="sheet-body">
        <div class="row">
          <label class="field grow">Prénom *<input class="input" name="first_name" required placeholder="Jean"></label>
          <label class="field grow">Nom *<input class="input" name="last_name" required placeholder="Dupont"></label>
        </div>
        <label class="field">Profession ou fonction<input class="input" name="profession" placeholder="Directeur Général, Journaliste, etc."></label>
        <div class="row">
          <label class="field grow">E-mail (facultatif)<input class="input" name="email" type="email" placeholder="contact@example.com"></label>
          <label class="field grow">Téléphone (facultatif)<input class="input" name="phone" type="tel" placeholder="+33 6 12 34 56 78"></label>
        </div>
        <div class="row">
          <label class="field grow">Organisation / Société<input class="input" name="organization_name" placeholder="Entreprise ou organisme"></label>
          <label class="field grow">Catégorie *
            <select class="select" name="category" required>
              <option value="invité" selected>INVITÉ</option>
              <option value="participant">PARTICIPANT</option>
              <option value="vip">VIP</option>
              <option value="organisateur">ORGANISATEUR</option>
              <option value="staff">STAFF</option>
              <option value="presse">PRESSE</option>
            </select>
          </label>
        </div>
        <label class="field">Photo de profil (facultative)
          <input class="input" type="file" id="mpPhoto" accept="image/*">
          <input type="hidden" name="photo_data" id="mpPhotoData">
        </label>
        <div id="mpPhotoPreview" style="margin:4px auto;display:none;text-align:center">
          <img src="" alt="Aperçu" style="width:72px;height:72px;border-radius:14px;object-fit:cover;border:2px solid var(--accent)">
        </div>
        <div id="mpe"></div>
        <button class="btn primary block" style="min-height:50px;margin-top:8px">Générer le badge et ajouter l’invité</button>
      </form>
    `);

    const photoInput = $('#mpPhoto', d);
    if (photoInput) {
      photoInput.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = ev => {
          $('#mpPhotoData', d).value = ev.target.result;
          const prev = $('#mpPhotoPreview', d);
          $('img', prev).src = ev.target.result;
          prev.style.display = 'block';
        };
        reader.readAsDataURL(file);
      };
    }

    $('#mpf', d).onsubmit = async e => {
      e.preventDefault();
      const b = $('button[type=submit]', e.target);
      busy(b, true);
      $('#mpe', d).innerHTML = '';
      try {
        const payload = Object.fromEntries(new FormData(e.target));
        const out = await api(`/admin/api/events/${this.id}/registrations/manual`, {
          method: 'POST',
          json: payload
        });
        d.close();
        toast(out.message || 'Invité ajouté avec succès.', 'ok');
        await this.refresh(false);

        sheet(`${sheetHead('Badge officiel généré', 'L’invité est enregistré et son badge est immédiatement actif.')}
          <div class="sheet-body" style="text-align:center">
            <div class="banner ok" style="margin-bottom:12px">
              ${icon('check', 'sm')}
              <strong>${esc(out.full_name)}</strong> &nbsp;—&nbsp; <span class="badge brand">${esc((out.category || 'invité').toUpperCase())}</span>
            </div>
            <p class="small muted" style="margin-bottom:14px">Ce badge est déjà synchronisé et prêt pour le scan terrain.</p>
            <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
              <a class="btn primary" href="${esc(out.badge_url)}" download target="_blank" rel="noopener">${icon('download', 'sm')}Télécharger le badge</a>
              <a class="btn ghost" href="${esc(out.badge_url)}" target="_blank" rel="noopener">Voir le badge</a>
            </div>
            <button class="btn tonal block" data-close style="margin-top:14px">Fermer</button>
          </div>
        `);
      } catch(err) {
        busy(b, false);
        $('#mpe', d).innerHTML = `<div class="banner bad">${esc(err.message)}</div>`;
      }
    };
  }
  async importParticipants() {
    const file=$('#participantFile')?.files?.[0];if(!file){toast('Choisissez un fichier Excel ou CSV.','bad');return;}
    const fd=new FormData();fd.append('file',file);
    try{const out=await api(`/admin/api/events/${this.id}/registrations/import`,{method:'POST',form:fd});toast(`${out.created} participant(s) importé(s), ${out.skipped_duplicates.length} doublon(s) ignoré(s).`,'ok');}catch(e){toast(e.message,'bad');}
  }
  async participantsPDF(btn) {
    busy(btn, true);
    try {
      const response = await api(`/admin/api/events/${this.id}/participants.pdf`);
      const href = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = href;
      link.download = `participants_evenement_${this.id}.pdf`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 4000);
      toast('Répertoire PDF téléchargé.', 'ok');
    } catch (e) {
      toast(e.message, 'bad');
    } finally {
      busy(btn, false);
    }
  }

  async batchPDF(btn) {
    busy(btn,true);try{const r=await api(`/admin/api/events/${this.id}/invitations/batch-pdf`);const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`invitations_${this.id}.zip`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);toast('PDF personnalisés générés.','ok');}catch(e){toast(e.message,'bad');}finally{busy(btn,false);}
  }
  async conferenceSettings() {
    const capacity=$('#confCapacity')?.value;const registration_open=$('#confOpen')?.checked||false;
    try{const out=await api(`/admin/api/events/${this.id}/conference`,{method:'PATCH',json:{capacity:capacity?+capacity:null,registration_open}});const url=location.origin+`/conference/${out.registration_token}`;$('#conferenceLink').innerHTML=`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a> <button class="btn sm ghost" data-act="copy-conf">Copier</button>`;this.detail.capacity=out.capacity;this.detail.registration_open=out.registration_open;this.detail.registration_token=out.registration_token;toast('Paramètres de conférence enregistrés.','ok');}catch(e){toast(e.message,'bad');}
  }
  async renderBadgeDesign() {
    const v=this.view; v.dataset.tab='badges';
    v.innerHTML=`<div class="col loose badge-design-page" style="margin-top:8px"><div class="row between wrap"><div><h1>Design des badges</h1><p class="muted">Configurez le badge, vérifiez son rendu puis partagez le bon QR.</p></div><a class="btn ghost" href="#gerer" data-link>${icon('back','sm')}Retour à Gérer</a></div>
      <div class="badge-design-layout"><section class="card col" id="memberBadgeSettings"><h2>Configuration</h2><label class="field">Palette<select class="select" id="memberPalette"><option value="royal">Indigo royal</option><option value="malachite">Vert et cuivre</option><option value="graphite">Graphite et platine</option><option value="burgundy">Bordeaux champagne</option><option value="midnight">Bleu nuit champagne</option><option value="noir">Noir et or</option></select></label>
      <label class="field">Métal<select class="select" id="memberMetal"><option value="0">Or</option><option value="1">Cuivre</option><option value="2">Platine</option><option value="3">Champagne</option></select></label><label class="field">Forme de la photo<select class="select" id="memberShape"><option value="arche">Arche</option><option value="cercle">Cercle</option><option value="carre">Carré arrondi</option></select></label>
      <label class="field">Logo de l’événement (facultatif)<input class="input" id="memberBadgeLogo" type="file" accept="image/png,image/jpeg,image/webp"><small class="muted">PNG, JPEG ou WebP · 1 Mo maximum</small></label><img id="memberBadgeLogoPreview" class="hidden badge-logo-preview" alt="Aperçu du logo du badge"><button class="btn sm ghost" type="button" data-act="clear-member-logo">Retirer le logo</button>
      <label class="item"><span class="grow">Sceau holographique</span><input id="memberSeal" type="checkbox" checked></label><label class="field">Catégories (séparées par des virgules)<input class="input" id="memberCategories" value="Presse, Protocole, Équipe" maxlength="480"></label>
      <label class="item"><span class="grow">Lien de demande de badge membre activé</span><input id="memberBadgeEnabled" type="checkbox"></label><button class="btn primary block" data-act="save-member-badges">Enregistrer le design</button><div id="memberBadgeLink" class="small" aria-live="polite"></div><p class="tiny muted" id="badgePreviewState">Chargement de la configuration enregistrée…</p></section>
      <section class="card col badge-preview-card"><div><h2>Aperçu du badge</h2><p class="small muted">Le rendu reprend le design qui sera remis au membre.</p></div><img id="memberBadgePreview" class="badge-design-preview" alt="Aperçu premium du badge membre"></section></div>
      <section class="col"><h2>QR à partager</h2><p class="small muted">Les cartes distinguent clairement le formulaire accessible à tous du lien réservé aux membres et à l’équipe.</p><div class="qr-share-grid">${this.detail.event_type==='conference'?`<article class="card qr-share-card qr-public"><div><span class="badge cobalt">INSCRIPTION PUBLIQUE</span><h3>QR du formulaire participant</h3><p class="small muted">À partager avec les personnes qui s’inscrivent à la conférence.${this.detail.registration_open?' Inscriptions ouvertes.':' Le formulaire est actuellement fermé.'}</p></div><a class="qr-download" href="/admin/api/events/${this.id}/registration-qr.png" download="qr-inscription-publique.png"><img src="/admin/api/events/${this.id}/registration-qr.png" alt="QR du formulaire d’inscription publique"><span class="btn ghost">${icon('download','sm')}Télécharger le QR public</span></a></article>`:''}<article class="card qr-share-card qr-members" id="memberQrCard"><div><span class="badge brand">ACCÈS INTERNE</span><h3>QR de demande de badge membre</h3><p class="small muted">Réservé à l’équipe, au protocole et aux membres de l’organisation.</p></div><div id="memberQrContent"><p class="muted small">Activez le lien membre pour générer ce QR.</p></div></article></div></section></div>`;
    this.bindBadgePreviewDirtyState();
    await this.loadMemberBadgeSettings();
  }
  bindBadgePreviewDirtyState(){
    const state=$('#badgePreviewState'), inputs=['#memberPalette','#memberMetal','#memberShape','#memberSeal','#memberCategories','#memberBadgeEnabled','#memberBadgeLogo'];
    inputs.forEach(sel=>$(sel)?.addEventListener('input',()=>{if(state)state.textContent='Modifications non enregistrées · enregistrez pour actualiser l’aperçu.';}));
  }
  renderMemberBadgeQr(token){
    const box=$('#memberQrContent'); if(!box)return;
    box.innerHTML=token?`<a class="qr-download" href="/admin/api/events/${this.id}/member-badge-qr.png" download="qr-badge-membres.png"><img src="/admin/api/events/${this.id}/member-badge-qr.png" alt="QR du formulaire de badge membre"><span class="btn ghost">${icon('download','sm')}Télécharger le QR interne</span></a><p class="tiny muted">Ce QR ouvre le formulaire membre. Il ne sert pas au scan des entrées.</p>`:'<p class="muted small">Lien membre désactivé · activez-le dans la configuration pour générer le QR réservé à l’équipe.</p>';
  }
  async loadMemberBadgeSettings() {
    try {
      const s=await api(`/admin/api/events/${this.id}/member-badges`);
      const palette=$('#memberPalette'), cats=$('#memberCategories'), enabled=$('#memberBadgeEnabled'), link=$('#memberBadgeLink');
      if(!palette||!cats||!enabled||!link)return;
      palette.value=s.palette; cats.value=s.categories.join(', '); enabled.checked=s.enabled;
      $('#memberMetal').value=String(s.metal??0); $('#memberShape').value=s.shape||'arche'; $('#memberSeal').checked=s.seal!==false;
      this.memberBadgeLogoData=s.logo_data||null;
      const logoPreview=$('#memberBadgeLogoPreview');
      if(this.memberBadgeLogoData&&logoPreview){logoPreview.src=this.memberBadgeLogoData;logoPreview.classList.remove('hidden');}
      const preview=$('#memberBadgePreview'); if(preview)preview.src=`/admin/api/events/${this.id}/member-badges/preview.png?v=${Date.now()}`;
      const previewState=$('#badgePreviewState'); if(previewState)previewState.textContent='Aperçu du design actuellement enregistré.';
      this.renderMemberBadgeQr(s.token);
      $('#memberBadgeLogo').onchange=()=>{
        const file=$('#memberBadgeLogo').files?.[0]; if(!file)return;
        if(file.size>1024*1024){toast('Le logo doit faire 1 Mo maximum.','bad');$('#memberBadgeLogo').value='';return;}
        const reader=new FileReader();reader.onload=()=>{this.memberBadgeLogoData=reader.result;logoPreview.src=reader.result;logoPreview.classList.remove('hidden');};reader.readAsDataURL(file);
      };
      link.innerHTML=s.token?`Lien actif · ${s.request_count} demande(s)<br><a href="/member-badge/${esc(s.token)}" target="_blank" rel="noopener">${esc(location.origin)}/member-badge/${esc(s.token)}</a> <button class="btn sm ghost" data-act="copy-member-badge">Copier</button>`:'Le lien est désactivé.';
    } catch(e) { if(e.status!==404) toast(e.message,'bad'); }
  }
  async saveMemberBadges() {
    const categories=$('#memberCategories')?.value.split(',').map(x=>x.trim()).filter(Boolean)||[];
    try {
      const out=await api(`/admin/api/events/${this.id}/member-badges`,{method:'PUT',json:{palette:$('#memberPalette').value,metal:Number($('#memberMetal').value),shape:$('#memberShape').value,seal:$('#memberSeal').checked,logo_data:this.memberBadgeLogoData,categories,enabled:$('#memberBadgeEnabled').checked}});
      await this.loadMemberBadgeSettings();
      toast('Design et accès des badges enregistrés.','ok');
    } catch(e) { toast(e.message,'bad'); }
  }
  async showRegistrations() {
    try{const out=await api(`/admin/api/events/${this.id}/registrations`);const rows=out.registrations;const d=sheet(`${sheetHead('Inscriptions conférence',`${out.accepted_count} acceptée(s) / ${out.capacity||'sans limite'}`)}<div class="sheet-body"><div class="list">${rows.map(r=>`<article class="item"><div class="grow"><strong>${esc(r.name)}</strong><div class="meta">${esc(r.email)} · ${esc(r.category)} · ${r.verified?'e-mail vérifié':'e-mail non vérifié'}</div><span class="badge">${esc(r.status)}</span></div>${r.status==='pending'&&r.verified?`<button class="btn sm primary" data-reg="${r.id}" data-status="accepted">Accepter</button>`:''}${['pending','waitlist'].includes(r.status)?`<button class="btn sm ghost" data-reg="${r.id}" data-status="rejected">Refuser</button>`:''}</article>`).join('')||'<p>Aucune inscription.</p>'}</div></div>`);d.addEventListener('click',async e=>{const b=e.target.closest('[data-reg]');if(!b)return;try{await api(`/admin/api/events/${this.id}/registrations/${b.dataset.reg}`,{method:'PATCH',json:{status:b.dataset.status}});d.close();this.showRegistrations();}catch(err){toast(err.message,'bad');}});}catch(e){toast(e.message,'bad');}
  }
  async programManager() {
    try{const rows=await api(`/api/events/${this.id}/program`);const d=sheet(`${sheetHead('Programme de l’événement')}<div class="sheet-body"><div class="list">${rows.map(x=>`<article class="item"><div class="grow"><strong>${esc(x.title)}</strong><div class="meta">${dt(x.starts_at)} – ${new Date(x.ends_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })} · ${esc(x.location)}</div><p class="small">${esc(x.description)}</p></div><button class="btn sm ghost" data-program-delete="${x.id}">Supprimer</button></article>`).join('')||'<p>Aucune séquence.</p>'}</div><form id="pf" class="col"><label class="field">Titre<input class="input" name="title" required></label><label class="field">Description<textarea class="input" name="description"></textarea></label><label class="field">Début<input class="input" type="datetime-local" name="starts_at" required></label><label class="field">Fin<input class="input" type="datetime-local" name="ends_at" required></label><label class="field">Lieu / salle<input class="input" name="location"></label><label class="field">Intervenant<input class="input" name="speaker"></label><button class="btn primary block">Ajouter au programme</button></form></div>`);$('#pf',d).onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.starts_at=new Date(data.starts_at).toISOString();data.ends_at=new Date(data.ends_at).toISOString();try{await api(`/admin/api/events/${this.id}/program`,{method:'POST',json:data});d.close();this.programManager();toast('Séquence ajoutée.','ok');}catch(err){toast(err.message,'bad');}};d.addEventListener('click',async e=>{const b=e.target.closest('[data-program-delete]');if(!b)return;try{await api(`/admin/api/events/${this.id}/program/${b.dataset.programDelete}`,{method:'DELETE'});d.close();this.programManager();}catch(err){toast(err.message,'bad');}});}catch(e){toast(e.message,'bad');}
  }
  async taskManager() {
    try{const [rows,team]=await Promise.all([api(`/api/events/${this.id}/tasks`),api(`/admin/api/events/${this.id}`).then(x=>x.assignments)]);const d=sheet(`${sheetHead('Tâches et responsabilités')}<div class="sheet-body"><div class="list">${rows.map(x=>`<article class="item"><div class="grow"><strong>${esc(x.title)}</strong><div class="meta">${TASK[x.status] || esc(x.status)} · ${PRIO[x.priority] || esc(x.priority)} · ${x.due_at?dt(x.due_at):'Sans échéance'}</div><p class="small">${esc(x.description)}</p><button class="btn sm ghost" data-task-history="${x.id}">Historique</button></div></article>`).join('')||'<p>Aucune tâche.</p>'}</div><form id="tf" class="col"><label class="field">Responsabilité<input class="input" name="title" required></label><label class="field">Description<textarea class="input" name="description"></textarea></label><label class="field">Affecter à<select class="select" name="assigned_to"><option value="">Non affectée</option>${team.map(u=>`<option value="${u.id}">${esc(u.full_name)}</option>`).join('')}</select></label><label class="field">Priorité<select class="select" name="priority"><option>normal</option><option>low</option><option>high</option><option>urgent</option></select></label><label class="field">Échéance<input class="input" type="datetime-local" name="due_at"></label><button class="btn primary block">Créer la tâche</button></form></div>`);$('#tf',d).onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.assigned_to=data.assigned_to?+data.assigned_to:null;data.due_at=data.due_at?new Date(data.due_at).toISOString():null;try{await api(`/admin/api/events/${this.id}/tasks`,{method:'POST',json:data});d.close();this.taskManager();toast('Responsabilité créée.','ok');}catch(err){toast(err.message,'bad');}};d.addEventListener('click',async e=>{const b=e.target.closest('[data-task-history]');if(!b)return;try{const h=await api(`/api/events/${this.id}/tasks/${b.dataset.taskHistory}/history`);sheet(`${sheetHead('Historique de la tâche')}<div class="sheet-body">${h.map(x=>`<p><b>${esc(x.user)}</b> — ${esc(x.action)}<br><small>${dt(x.created_at)}</small><pre>${esc(x.new_value)}</pre></p>`).join('')||'Aucun historique.'}</div>`);}catch(err){toast(err.message,'bad');}});}catch(e){toast(e.message,'bad');}
  }

  async doImport() {
    const x = $('#file').files[0]; if (!x) return; const b = $('#doImport'); busy(b, true); $('#imErr').innerHTML = '';
    const fd = new FormData(); fd.append('file', x);
    try {
      const r = await api(`/admin/api/events/${this.id}/import`, { method: 'POST', form: fd }); feedback('ok');
      await this.refresh(true); this.renderManage();
      sheet(`<div class="verdict ok"><div class="ico">${icon('check', 'lg')}</div><h2>${plural(r.created, 'invitation')} importée${r.created > 1 ? 's' : ''}</h2><p>${esc(r.references[0] || '')}${r.references.length > 1 ? ' à ' + esc(r.references[r.references.length - 1]) : ''}</p></div><div class="sheet-body"><p class="small muted">${esc(r.message)}</p><a class="btn primary block" href="#invites" data-link data-close>Voir les invités</a><button class="btn ghost block" data-close>Fermer</button></div>`);
    } catch (e) {
      busy(b, false); const parts = String(e.message).split(/ ; |\. /).filter(Boolean);
      $('#imErr').innerHTML = `<div class="banner bad" role="alert" style="align-items:flex-start">${icon('alert', 'sm')}<div class="col tight">${parts.slice(0, 8).map(p => `<span>${esc(p)}</span>`).join('')}</div></div>`;
    }
  }
  async unassign(userId) {
    if(!confirm('Retirer ce compte de l’événement ? Les tâches qui lui sont affectées seront désassignées.'))return;
    try{await api(`/admin/api/events/${this.id}/assignments/${userId}`,{method:'DELETE'});toast('Affectation retirée.','ok');await this.refresh(true);this.renderManage();}catch(e){toast(e.message,'bad');}
  }
  async assign() {
    let users; try { users = await api('/admin/api/users'); } catch (e) { toast(e.message, 'bad'); return; }
    const taken = new Set(this.detail.assignments.map(a => a.id)), free = users.filter(u => u.active && u.role !== 'admin' && !taken.has(u.id));
    const d = sheet(`${sheetHead('Affecter à l’événement', this.detail.name)}<form class="sheet-body" id="af">${free.length ? `<div class="list">${free.map(u => `<label class="item" style="cursor:pointer"><div class="avatar">${esc(initials(u.full_name))}</div><div class="grow"><div class="title">${esc(u.full_name)}</div><div class="meta"><span>${esc(u.username)}</span></div></div><span class="badge ${u.role === 'supervisor' ? 'brand' : ''}">${roleLabel(u.role)}</span><input type="checkbox" name="u" value="${u.id}" style="width:22px;height:22px;accent-color:var(--brand)"></label>`).join('')}</div><button class="btn primary block" type="submit">Affecter la sélection</button>` : empty('users', 'Tous les comptes sont déjà affectés', 'Créez un nouveau compte depuis l’onglet Équipe de l’accueil.')}</form>`);
    const form = $('#af', d); form.onsubmit = async e => {
      e.preventDefault(); const ids = [...form.querySelectorAll('input:checked')].map(i => +i.value); if (!ids.length) { toast('Sélectionnez au moins un compte.'); return; }
      const b = $('button[type=submit]', form); busy(b, true); let ok = 0;
      for (const id of ids) { try { await api(`/admin/api/events/${this.id}/assignments`, { method: 'POST', json: { user_id: id } }); ok++; } catch (err) { toast(err.message, 'bad'); } }
      d.close(); if (ok) toast(`${plural(ok, 'compte')} affecté${ok > 1 ? 's' : ''}.`, 'ok'); await this.refresh(true); this.renderManage();
    };
  }
  async pack(btn) {
    busy(btn, true);
    try {
      const r = await api(`/admin/api/events/${this.id}/designer-pack`); const blob = await r.blob();
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `event_${this.id}_designer_pack.zip`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast(`Dossier généré (${Math.max(1, Math.round(blob.size / 1024))} Ko).`, 'ok');
    } catch (e) { toast(e.message, 'bad'); } finally { busy(btn, false); }
  }
  template() {
    const csv = '\ufeffnom;type;nombre;table\nFamille Mukendi;groupe;4;1\nJean Kabasele;individuelle;1;2\nMarie et Paul Ilunga;couple;2;3\n';
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = 'modele_invites.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  click(e) {
    const done=e.target.closest('[data-task-done]'); if(done) return this.completeTask(+done.dataset.taskDone);
    const unassign=e.target.closest('[data-unassign]'); if(unassign) return this.unassign(+unassign.dataset.unassign);
    const g = e.target.closest('[data-guest]'); if (g) return this.openGuest(+g.dataset.guest);
    const gs = e.target.closest('[data-gs]'); if (gs) { this.g.status = gs.dataset.gs; this.g.shown = 40; return this.paintGuests(); }
    const gt = e.target.closest('[data-gt]'); if (gt) { this.g.type = gt.dataset.gt; this.g.shown = 40; return this.paintGuests(); }
    const sg = e.target.closest('[data-seg]'); if (sg) { this.seg = sg.dataset.seg; return this.paintFollow(); }
    const ef = e.target.closest('[data-ef]'); if (ef) { this.exFilter = ef.dataset.ef; return this.paintFollow(); }
    const xd = e.target.closest('[data-ex-do]'); if (xd) { const i = this.invs().find(x => x.reference === xd.dataset.exDo); if (i) this.exceptionSheet(i, 'approve'); return; }
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'start-event') return this.changeEventStatus('active');
    if (a.dataset.act === 'close-event') return this.changeEventStatus('closed');
    if (a.dataset.act === 'reopen-event') return this.changeEventStatus('active');
    if (a.dataset.act === 'clear-member-logo') { this.memberBadgeLogoData=null; $('#memberBadgeLogo').value=''; $('#memberBadgeLogoPreview').classList.add('hidden'); return; }
    if (a.dataset.act === 'save-member-badges') return this.saveMemberBadges();
    if (a.dataset.act === 'copy-member-badge') return navigator.clipboard.writeText($('#memberBadgeLink a')?.href || '').then(() => toast('Lien copié.','ok'));
    ({ reload: () => this.refresh(false), 'reload-follow': () => this.renderFollow(), assign: () => this.assign(), pack: () => this.pack(a), template: () => this.template(), 'new-invitation': () => this.newInvitation(), 'batch-pdf': () => this.batchPDF(a), 'participants-pdf': () => this.participantsPDF(a), 'save-conference': () => this.conferenceSettings(), registrations: () => registrations(this), 'edit-event': () => editEvent(this), 'reg-qr': () => sheet(`${sheetHead('QR d’inscription', 'À afficher ou imprimer')}<div class="sheet-body" style="justify-items:center"><img src="/admin/api/events/${this.id}/registration-qr.png" alt="QR code du formulaire d’inscription" width="260" height="260" style="border-radius:16px;background:#fff;padding:10px"><button class="btn ghost block" data-close>Fermer</button></div>`), csv: () => exportCsv(this), 'manual-registration': () => this.manualParticipant(), 'import-participants': () => this.importParticipants(), program: () => this.programManager(), tasks: () => this.taskManager(), 'copy-conf': () => navigator.clipboard.writeText($('#conferenceLink a')?.href || '').then(() => toast('Lien copié.','ok')) })[a.dataset.act]?.();
  }
}
