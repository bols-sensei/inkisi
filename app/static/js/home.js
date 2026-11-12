/* Accueil : événements, équipe (administrateur), profil et préférences. */
import { $, $$, esc, icon, api, toast, sheet, sheetHead, busy, dateFr, initials, plural, norm, roleLabel, pct, meter, ring, animateRings, empty, skeletons, shellHTML, setActiveTab, setTheme, getTheme, prefs, debounce, watchScroll } from './core.js';
import { queue } from './offline.js';
import { countdown } from './extras.js';
import { renderConsole, renderPlans, renderSubscriptions, extend, openOrg, setFilter, setSubscriptionFilter } from './superadmin.js';

export class Home {
  constructor(user) { this.user = user; this.tab = user.role === 'superadmin' ? 'organisations' : 'evenements'; this.events = null; this.users = null; this.stats = {}; this.filter = 'tous'; }

  get isAdmin() { return this.user.role === 'admin' || this.user.role === 'superadmin'; }
  get isSuperAdmin() { return this.user.role === 'superadmin'; }
  get tabs() {
    return [...(this.isSuperAdmin ? [
      { id: 'organisations', label: 'Plateforme', icon: 'building-2', href: '/#organisations' },
      { id: 'plans', label: 'Formules', icon: 'layers', href: '/#plans' },
      { id: 'abonnements', label: 'Abonnements', icon: 'clock', href: '/#abonnements' },
    ] : [{ id: 'evenements', label: 'Événements', icon: this.user.role === 'agent' ? 'scan' : 'calendar', href: '/#evenements' }]),
      ...(this.isAdmin ? [{ id: 'support', label: 'Support', icon: 'help-circle', href: '/#support' }] : []),
      ...(this.user.role === 'admin' ? [{ id: 'equipe', label: 'Équipe', icon: 'users', href: '/#equipe' }, { id: 'abonnement', label: 'Abonnement', icon: 'clock', href: '/#abonnement' }] : []),
      { id: 'profil', label: 'Profil', icon: 'user', href: '/#profil' }];
  }

  mount(app) {
    this.app = app;
    app.innerHTML = shellHTML({ tabs: this.tabs, active: this.tab, title: 'Invitations', sub: roleLabel(this.user.role) });
    this.view = $('#view'); watchScroll();
    this.onClick = e => this.click(e); this.view.addEventListener('click', this.onClick);
  }
  destroy() { this.view && this.view.removeEventListener('click', this.onClick); }

  setTab(t) {
    this.tab = this.tabs.some(x => x.id === t) ? t : (this.isSuperAdmin ? 'organisations' : 'evenements');
    setActiveTab(this.tab);
    const titles = { evenements: [this.user.role === 'agent' ? 'Mon affectation' : 'Événements', roleLabel(this.user.role)], equipe: ['Équipe', 'Comptes et rôles'], abonnement: ['Mon abonnement', 'Plan et consommation'], organisations: ['Organisations', 'Pilotage de la plateforme SaaS'], plans: ['Formules', 'Fonctionnalités et quotas'], abonnements: ['Abonnements', 'Périodes et historique'], support: ['Support', 'Échange avec l’équipe plateforme'], profil: ['Profil', this.user.username] };
    const [t1, s1] = titles[this.tab]; $('#barTitle').innerHTML = `${esc(t1)}<span class="sub ellipsis">${esc(s1)}</span>`;
    $('#barActions').innerHTML = this.tab === 'evenements' ? `<button class="btn icon ghost" data-act="reload" aria-label="Actualiser">${icon('refresh', 'sm')}</button>` : ['organisations', 'plans', 'abonnements'].includes(this.tab) ? `<button class="btn icon ghost" data-act="reload-orgs" aria-label="Actualiser">${icon('refresh', 'sm')}</button>` : '';
    ({ evenements: () => this.renderEvents(), equipe: () => this.renderTeam(), abonnement: () => this.renderSubscription(), organisations: () => this.renderOrganizations(), plans: () => renderPlans(this), abonnements: () => renderSubscriptions(this), support: () => this.renderSupport(), profil: () => this.renderProfile() })[this.tab]();
    scrollTo(0, 0);
  }

  /* ---------- Événements ---------- */
  async renderEvents(force) {
    const v = this.view;
    if (!this.events || force) {
      v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(3, 110)}</div>`;
      try {
        if (this.user.role === 'admin') { const [d, s] = await Promise.all([api('/admin/api/overview'), api('/admin/api/subscription')]); this.events = d.events; this.userCount = d.users; this.subscription = s; }
        else this.events = await api('/supervisor/api/events');
      } catch (e) { v.innerHTML = empty('wifioff', e.network ? 'Connexion indisponible' : 'Chargement impossible', e.message, '<button class="btn primary" data-act="reload">Réessayer</button>'); return; }
    }
    const today = new Date().toISOString().slice(0, 10);
    const all = this.events;
    const dated = e => e.event_date && /^\d{4}/.test(e.event_date);
    const list = all.filter(e => this.filter === 'tous' ? true : this.filter === 'avenir' ? (!dated(e) || e.event_date >= today) : (dated(e) && e.event_date < today));
    const hello = (this.user.full_name || this.user.username || '').split(' ')[0];
    const agentExpected = all.reduce((n, e) => n + (e.expected || 0), 0), agentEntered = all.reduce((n, e) => n + (e.entered || 0), 0);
    const agentUpcoming = all.filter(e => !dated(e) || e.event_date >= today).length;
    const pendingExceptions = all.reduce((n, e) => n + (e.pending_exceptions || 0), 0);
    const agentAssignments = all.reduce((n, e) => n + (e.agent_count || 0), 0);
    const activeEvents = all.filter(e => e.status === 'active').length;
    const upcomingEvents = all.filter(e => !dated(e) || e.event_date >= today).length;
    const totalRegistrations = all.reduce((n, e) => n + (e.event_type === 'conference' ? (e.registrations || 0) : (e.invitations || 0)), 0);
    const remaining = this.subscription?.events_remaining;
    const canCreate = this.subscription?.state === 'active' && (remaining === null || remaining > 0);
    v.innerHTML = `<div class="col loose" style="margin-top:8px">
      <section><h1>Bonjour ${esc(hello)}</h1><p class="muted">${this.isAdmin ? 'Créez vos événements, importez les invités et suivez les entrées.' : 'Vos événements affectés et vos contrôles d’accès.'}</p></section>
      ${this.user.role === 'admin' ? `<section class="tiles" aria-label="Résumé de l’organisation"><div class="tile"><strong class="num">${all.length}</strong><span>Événement${all.length === 1 ? '' : 's'}</span></div><div class="tile"><strong class="num">${activeEvents}</strong><span>En cours</span></div><div class="tile"><strong class="num">${upcomingEvents}</strong><span>À venir</span></div><div class="tile"><strong class="num">${totalRegistrations}</strong><span>Invitations / inscriptions</span></div></section>
      ${this.subscription ? `<a class="banner ${this.subscription.state === 'active' ? 'info' : this.subscription.state === 'grace' ? 'warn' : 'bad'}" href="/#abonnement" data-link><span class="grow"><strong>${esc(this.subscription.plan || 'Abonnement indisponible')}</strong> · ${this.subscription.state === 'active' ? (remaining === null ? 'Événements illimités' : `${remaining} événement${remaining === 1 ? '' : 's'} disponible${remaining === 1 ? '' : 's'}`) : this.subscription.state === 'grace' ? 'Période de grâce : création suspendue' : 'Lecture seule ou aucun abonnement'}</span><span>Voir</span></a>` : ''}
      <button class="btn primary block" data-act="new-event" ${canCreate ? '' : 'disabled'}>${icon('plus', 'sm')}Nouvel événement</button>${!canCreate ? `<p class="small muted">La création nécessite un abonnement actif et un quota disponible.</p>` : ''}` : ''}
      ${this.user.role === 'agent' ? `<section class="tiles" aria-label="Résumé de mes affectations"><div class="tile"><strong class="num">${all.length}</strong><span>Événement${all.length === 1 ? '' : 's'} affecté${all.length === 1 ? '' : 's'}</span></div><div class="tile"><strong class="num">${agentUpcoming}</strong><span>À venir</span></div><div class="tile"><strong class="num">${agentEntered}</strong><span>Personnes contrôlées</span></div><div class="tile"><strong class="num">${Math.max(0, agentExpected - agentEntered)}</strong><span>Restantes</span></div></section>` : ''}
      ${this.user.role === 'supervisor' ? `<section class="tiles" aria-label="Résumé de supervision"><div class="tile"><strong class="num">${all.length}</strong><span>Événements suivis</span></div><div class="tile"><strong class="num">${agentAssignments}</strong><span>Affectations d’agents</span></div><div class="tile"><strong class="num">${pendingExceptions}</strong><span>Exceptions à examiner</span></div><div class="tile"><strong class="num">${agentEntered}</strong><span>Personnes contrôlées</span></div></section>${pendingExceptions ? `<div class="banner warn">${icon('alert', 'sm')}<span>${plural(pendingExceptions, 'exception')} en attente. Ouvrez le suivi de l’événement concerné pour décider.</span></div>` : ''}` : ''}
      ${all.length > 2 ? `<div class="chips" role="group" aria-label="Filtrer">${[['tous', 'Tous'], ['avenir', 'À venir'], ['passes', 'Passés']].map(([k, l]) => `<button class="chip" aria-pressed="${this.filter === k}" data-filter="${k}">${l}</button>`).join('')}</div>` : ''}
      <div class="col" id="evList">${list.length ? list.map(e => this.eventCard(e)).join('') : (all.length ? empty('calendar', 'Aucun événement dans cette catégorie') : (this.isAdmin ? empty('calendar', 'Aucun événement pour l’instant', 'Créez votre premier événement, puis importez la liste des invités.') : empty('shield', 'Aucun événement affecté', 'Demandez à l’administrateur de vous affecter à un événement.')))}</div></div>`;
    animateRings(v);
    if (this.isAdmin) this.loadStats(list);
  }
  eventCard(e) {
    const s = this.stats[e.id] || (e.expected != null ? { expected: e.expected, entered: e.entered } : null);
    const p = s ? pct(s.entered, s.expected) : 0;
    const adminStatus = this.user.role === 'admin' || this.user.role === 'superadmin';
    const supervisor = this.user.role === 'supervisor';
    const status = e.status || 'draft';
    const statusLabels = { draft: 'Brouillon', active: 'En cours', closed: 'Terminé' };
    const statusActions = adminStatus ? (status === 'draft' ? `<button class="btn sm primary" data-act="event-status" data-id="${e.id}" data-status="active">Lancer</button>` : status === 'active' ? `<button class="btn sm danger" data-act="event-status" data-id="${e.id}" data-status="closed">Clôturer</button>` : `<button class="btn sm ghost" data-act="event-status" data-id="${e.id}" data-status="active">Relancer</button>`) : supervisor && status === 'draft' ? `<button class="btn sm primary" data-act="event-status" data-id="${e.id}" data-status="active">Lancer</button>` : '';
    return `<article class="event-card" data-ev="${e.id}">
      <a class="event-card-main" href="/event/${e.id}${supervisor ? '#suivi' : ''}" data-link>
      <div class="row between"><span class="date">${esc(dateFr(e.event_date, false))}${countdown(e.event_date) ? ` <span class="badge brand">${countdown(e.event_date)}</span>` : ''}</span>${!this.isAdmin && !supervisor ? '' : `<span class="badge ${status === 'active' ? 'ok' : status === 'closed' ? 'bad' : 'warn'}">${esc(statusLabels[status] || status)}</span>`}</div>
      <div><h3 style="font-size:1.12rem">${esc(e.name)}</h3><p class="small muted row" style="margin-top:3px">${e.venue ? icon('pin', 'sm') + esc(e.venue) : '<span class="faint">Lieu à définir</span>'}</p></div>
      <div data-prog>${s && s.expected ? `${meter(s.entered, s.expected)}<div class="row between small" style="margin-top:6px"><span class="muted num">${s.entered} entrée${s.entered > 1 ? 's' : ''} sur ${s.expected}</span><strong class="num">${p}%</strong></div>` : `<p class="small muted">${e.event_type === 'conference' ? plural(e.registrations || 0, 'inscription') : plural(e.invitations || 0, 'invitation')}</p>`}</div>${this.user.role === 'agent' ? `<span class="btn primary block" style="margin-top:12px">${icon('scan', 'sm')}Ouvrir le scanner</span>` : supervisor ? `<div class="row wrap small muted" style="margin-top:12px"><span>${plural(e.agent_count || 0, 'agent affecté')}</span>${e.pending_exceptions ? `<span class="badge warn">${plural(e.pending_exceptions, 'exception')} à examiner</span>` : '<span class="badge ok">Aucune exception en attente</span>'}<span class="btn tonal">Ouvrir le suivi</span></div>` : ''}</a>${statusActions ? `<div class="event-status-actions"><span class="small muted">${statusLabels[status]}</span>${statusActions}</div>` : ''}</article>`;
  }
  async changeEventStatus(id, status, button) {
    busy(button, true);
    try {
      await api(`/admin/api/events/${id}/status`, { method: 'PATCH', json: { status } });
      this.events = this.events.map(event => event.id === id ? { ...event, status } : event);
      this.renderEvents();
      toast(status === 'active' ? 'Événement lancé.' : 'Événement clôturé.', 'ok');
    } catch (e) { busy(button, false); toast(e.message, 'bad'); }
  }
  async loadStats(list) {                       // l'aperçu admin ne donne pas les entrées : on lit le détail de chaque événement
    const todo = list.filter(e => !this.stats[e.id]).slice(0, 24);
    await Promise.allSettled(todo.map(async e => {
      const d = await api(`/admin/api/events/${e.id}`);
      this.stats[e.id] = d.event_type === 'conference' ? { expected: d.accepted_registrations || 0, entered: d.checked_in_registrations || 0 } : { expected: d.invitations.reduce((a, i) => a + i.quota, 0), entered: d.invitations.reduce((a, i) => a + i.entered, 0) };
      const card = $(`[data-ev="${e.id}"] [data-prog]`, this.view);
      if (card) { const s = this.stats[e.id]; card.innerHTML = s.expected ? `${meter(s.entered, s.expected)}<div class="row between small" style="margin-top:6px"><span class="muted num">${s.entered} entrée${s.entered > 1 ? 's' : ''} sur ${s.expected}</span><strong class="num">${pct(s.entered, s.expected)}%</strong></div>` : `<p class="small muted">Aucune invitation importée</p>`; }
    }));
  }

  /* ---------- Équipe ---------- */
  async renderTeam(force) {
    const v = this.view;
    if (!this.users || force) {
      v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(4, 64)}</div>`;
      try { this.users = await api('/admin/api/users'); } catch (e) { v.innerHTML = empty('wifioff', 'Chargement impossible', e.message, '<button class="btn primary" data-act="reload-team">Réessayer</button>'); return; }
    }
    const count = r => this.users.filter(u => u.role === r).length;
    v.innerHTML = `<div class="col loose" style="margin-top:8px">
      <div class="tiles"><div class="tile"><strong class="num">${count('agent')}</strong><span>Agents</span></div><div class="tile"><strong class="num">${count('supervisor')}</strong><span>Superviseurs</span></div></div>
      <button class="btn primary block" data-act="new-user">${icon('plus', 'sm')}Nouveau compte</button>
      <div class="searchbox">${icon('search', 'sm')}<input class="input" id="uq" type="search" placeholder="Rechercher un compte" aria-label="Rechercher un compte"></div>
      <div class="list" id="uList"></div></div>`;
    const paint = () => { const q = norm($('#uq').value); const rows = this.users.filter(u => !q || norm(u.full_name + ' ' + u.username).includes(q)); $('#uList').innerHTML = rows.map(u => `<div class="item" role="button" tabindex="0" data-act="edit-user" data-id="${u.id}" aria-label="Gérer ${esc(u.full_name)}" style="cursor:pointer"><div class="avatar">${esc(initials(u.full_name))}</div><div class="grow"><div class="title ellipsis">${esc(u.full_name)}</div><div class="meta"><span>${esc(u.username)}</span></div></div><span class="badge ${u.role === 'admin' ? 'cobalt' : u.role === 'supervisor' ? 'brand' : ''}">${roleLabel(u.role)}</span>${u.active ? '' : '<span class="badge bad">Désactivé</span>'}</div>`).join('') || empty('search', 'Aucun compte trouvé'); };
    $('#uq').addEventListener('input', debounce(paint, 120)); paint();
  }
  newUser() {
    const gen = () => { const a = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'; const r = crypto.getRandomValues(new Uint8Array(12)); return [...r].map(x => a[x % a.length]).join(''); };
    const d = sheet(`${sheetHead('Nouveau compte', 'Un agent contrôle les entrées, un superviseur suit l’activité.')}
      <form class="sheet-body" id="uf" autocomplete="off">
        <label class="field">Nom complet<input class="input" name="full_name" required autocomplete="off"></label>
        <label class="field">Identifiant<input class="input" name="username" required autocapitalize="none" autocomplete="off" spellcheck="false"></label>
        <label class="field">Mot de passe initial <small>10 caractères minimum</small><div class="manual"><input class="input" name="password" id="pw" required minlength="10" autocomplete="new-password" spellcheck="false"><button type="button" class="btn ghost" id="gen">${icon('key', 'sm')}Générer</button></div></label>
        <label class="field">Rôle<select class="select" name="role"><option value="agent">Agent de contrôle</option><option value="supervisor">Superviseur</option><option value="admin">Administrateur</option></select></label>
        <div id="ue"></div><button class="btn primary block" type="submit">Créer le compte</button></form>`);
    $('#gen', d).onclick = () => { $('#pw', d).value = gen(); };
    $('#uf', d).onsubmit = async e => {
      e.preventDefault(); const f = e.target, b = $('button[type=submit]', f), data = Object.fromEntries(new FormData(f)); busy(b, true);
      try {
        await api('/admin/api/users', { method: 'POST', json: data }); this.users = null;
        d.close(); this.credentials(data); if (this.tab === 'equipe') this.renderTeam(true);
      } catch (err) { busy(b, false); $('#ue', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; }
    };
  }
  credentials(u) {
    const txt = `Invitations — accès\nIdentifiant : ${u.username}\nMot de passe : ${u.password}\nAdresse : ${location.origin}`;
    const d = sheet(`${sheetHead('Compte créé', u.full_name)}<div class="sheet-body"><div class="card flat col tight"><div class="small muted">Identifiant</div><strong>${esc(u.username)}</strong><div class="small muted" style="margin-top:6px">Mot de passe</div><strong class="num" style="font-size:1.1rem">${esc(u.password)}</strong></div>
      <p class="small muted">Ce mot de passe ne sera plus affiché. Transmettez-le de façon sûre.</p>
      <button class="btn primary block" id="cp">${icon('copy', 'sm')}Copier les accès</button><button class="btn ghost block" data-close>Terminer</button></div>`);
    $('#cp', d).onclick = async () => { try { await navigator.clipboard.writeText(txt); toast('Accès copiés.', 'ok'); } catch { toast('Copie impossible, notez les accès.', 'bad'); } };
  }
  newEvent() {
    const today = new Date().toISOString().slice(0, 10);
    const conferenceAllowed = !!this.subscription?.advanced_features;
    const d = sheet(`${sheetHead('Nouvel événement', 'Renseignez les détails essentiels pour créer votre événement.')}<form class="sheet-body" id="ef">
      <label class="field">Nom de l’événement *<input class="input" name="name" required maxlength="180" placeholder="Ex. Sommet Annuel de l’Innovation"></label>
      <div class="row wrap" style="gap:10px">
        <label class="field grow">Date de début *<input class="input" type="date" name="start_date" value="${today}" required></label>
        <label class="field" style="width:130px">Heure début<input class="input" type="time" name="start_time" value="09:00"></label>
      </div>
      <div class="row wrap" style="gap:10px">
        <label class="field grow">Date de fin<input class="input" type="date" name="end_date" value="${today}"></label>
        <label class="field" style="width:130px">Heure fin<input class="input" type="time" name="end_time" value="18:00"></label>
      </div>
      <label class="field">Lieu de réception<input class="input" name="venue" maxlength="240" placeholder="Ex. Palais des Congrès, Salle A"></label>
      <label class="field">Type d’événement<select class="select" name="event_type"><option value="conference" ${conferenceAllowed ? '' : 'disabled'}>Conférence (inscriptions & badges)${conferenceAllowed ? '' : ' — non incluse dans votre formule'}</option><option value="wedding" selected>Mariage / réception (invitations nominatives)</option></select>${conferenceAllowed ? '' : '<small>Les conférences nécessitent une formule avec fonctionnalités avancées.</small>'}</label>
      <label class="field" id="capacityField">Capacité maximale <small>facultatif</small><input class="input" type="number" name="capacity" min="1" max="100000" placeholder="Ex. 250"></label>
      <div id="ee"></div><button class="btn primary block" type="submit">Créer l’événement</button></form>`);
    $('#ef', d).elements.event_type.onchange = e => { $('#capacityField', d).hidden = e.target.value !== 'conference'; };
    $('#ef', d).onsubmit = async e => {
      e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true);
      const form = Object.fromEntries(new FormData(e.target)); form.capacity = form.event_type === 'conference' && form.capacity ? Number(form.capacity) : null;
      try { const r = await api('/admin/api/events', { method: 'POST', json: form }); toast('Événement créé avec succès.', 'ok'); d.close(); location.href = `/event/${r.id}#gerer`; }
      catch (err) { busy(b, false); $('#ee', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; }
    };
  }

  /* ---------- Organisations (superadministrateur) ---------- */
  async renderOrganizations(force = false) { return renderConsole(this, force); }
  async _legacyOrganizations(force = false) {
    const v = this.view;
    if (!this.organizations || force) {
      v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(3, 100)}</div>`;
      try { [this.organizations, this.plans] = await Promise.all([api('/superadmin/api/organizations'), api('/superadmin/api/plans')]); }
      catch (e) { v.innerHTML = empty('wifioff', 'Chargement impossible', e.message, '<button class="btn primary" data-act="reload-orgs">Réessayer</button>'); return; }
    }
    v.innerHTML = `<div class="col loose" style="margin-top:8px">
      <section><h1>Organisations</h1><p class="muted">Créez les espaces des organisateurs et gérez leurs périodes d’essai et abonnements.</p></section>
      <div class="row"><button class="btn primary grow" data-act="new-org">${icon('plus', 'sm')}Créer une organisation</button><button class="btn tonal" data-act="new-plan">Créer une formule</button></div>
      <div class="col" id="orgList">${this.organizations.map(o => `<article class="event-card"><div class="row between"><h3>${esc(o.name)}</h3><span class="badge ${o.subscription?.status === 'active' ? 'ok' : o.subscription?.status === 'trial' ? 'brand' : 'bad'}">${esc(({ active: 'Actif', trial: 'Essai', suspended: 'Suspendu', expired: 'Expiré' })[o.subscription?.status] || 'Sans abonnement')}</span></div><p class="small muted">${esc(o.slug)} · ${o.users} compte(s) · ${o.events} événement(s)</p>${o.subscription ? `<p class="small">Formule : <strong>${esc(o.subscription.plan)}</strong> · ${o.subscription.event_limit < 0 ? 'Événements illimités' : `${o.subscription.event_limit} événement(s)`}</p><p class="small muted">Expire le ${esc(new Date(o.subscription.ends_at).toLocaleDateString('fr-FR'))}</p>` : ''}<button class="btn tonal block" data-act="edit-sub" data-org="${o.id}">Gérer l’abonnement</button></article>`).join('') || empty('building-2', 'Aucune organisation')}</div>
    </div>`;
  }
  newOrganization() {
    const d = sheet(`${sheetHead('Créer une organisation', 'Un compte administrateur et un essai de 14 jours seront créés.')}<form class="sheet-body" id="orgForm" autocomplete="off">
      <label class="field">Nom de l’organisation<input class="input" name="name" required maxlength="180"></label>
      <label class="field">Nom complet de l’administrateur<input class="input" name="admin_full_name" required maxlength="160"></label>
      <label class="field">Identifiant administrateur<input class="input" name="admin_username" required minlength="3" maxlength="80" autocapitalize="none"></label>
      <label class="field">Mot de passe initial<input class="input" name="admin_password" type="password" required minlength="10" autocomplete="new-password"></label>
      <div id="orgError"></div><button class="btn primary block" type="submit">Créer et démarrer l’essai</button></form>`);
    $('#orgForm', d).onsubmit = async e => { e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true); const data = Object.fromEntries(new FormData(e.target));
      try { await api('/superadmin/api/organizations', { method: 'POST', json: data }); this.organizations = null; this.stats2 = null; d.close(); toast('Organisation créée. Essai de 14 jours activé.', 'ok'); this.renderOrganizations(true); }
      catch (err) { busy(b, false); $('#orgError', d).innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`; }
    };
  }
  newPlan(id = null) {
    const p = id ? this.plans?.find(x => x.id === id) : null; if (id && !p) return;
    const assignedCount = p ? (this.organizations || []).filter(o => o.subscription?.plan_code === p.code).length : 0;
    const d = sheet(`${sheetHead(p ? 'Modifier la formule' : 'Créer une formule', 'Les formules actuelles ne définissent ni prix ni facturation en ligne.')}<form class="sheet-body" id="planForm">
      ${p && assignedCount ? `<div class="banner warn" role="status">Les changements de quotas et de fonctionnalités prennent effet immédiatement pour ${assignedCount} organisation(s) actuellement abonnée(s) à cette formule.</div>` : ''}
      <label class="field">Nom de la formule<input class="input" name="name" required minlength="2" maxlength="100" value="${esc(p?.name || '')}" placeholder="Ex. Standard"></label>
      <label class="field">Code technique<input class="input" name="code" required minlength="2" maxlength="40" pattern="[a-z0-9_-]+" value="${esc(p?.code || '')}" placeholder="standard" autocapitalize="none" ${p ? 'readonly' : ''}></label>
      <label class="field">Événements créés pendant la période<input class="input" name="event_limit" type="number" min="-1" value="${p?.event_limit ?? 1}" required><small>-1 signifie illimité. Les événements déjà créés pendant la période sont comptés.</small></label>
      <label class="item"><span class="grow"><strong>Conférences et PDF personnalisés en lot</strong><small class="muted">Autorise la création de conférences et l’export de PDF personnalisés en lot pour les invitations.</small></span><input type="checkbox" name="advanced_features" value="true" aria-label="Inclure les conférences et les PDF personnalisés en lot" ${p?.advanced_features ? 'checked' : ''} style="width:22px;height:22px"></label>
      ${p ? `<label class="item"><span class="grow">Formule disponible pour de nouvelles attributions</span><input type="checkbox" name="active" value="true" ${p.active ? 'checked' : ''} ${p.code === 'trial' ? 'disabled checked' : ''} style="width:22px;height:22px"></label>` : ''}
      <div id="planError"></div><button class="btn primary block" type="submit">${p ? 'Enregistrer les changements' : 'Créer la formule'}</button></form>`);
    $('#planForm', d).onsubmit = async e => { e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true); const f = new FormData(e.target); const data = { name: f.get('name'), event_limit: Number(f.get('event_limit')), advanced_features: f.get('advanced_features') === 'true' };
      if (!p) data.code = f.get('code'); else data.active = p.code === 'trial' ? true : f.get('active') === 'true';
      try { await api(p ? `/superadmin/api/plans/${p.id}` : '/superadmin/api/plans', { method: p ? 'PUT' : 'POST', json: data }); this.plans = null; this.organizations = null; this.subscriptions = null; d.close(); toast(p ? 'Formule mise à jour.' : 'Formule créée.', 'ok'); if (this.tab === 'plans') renderPlans(this, true); else this.renderOrganizations(true); }
      catch (err) { busy(b, false); $('#planError', d).innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`; }
    };
  }
  async togglePlan(id, active) {
    const p = this.plans?.find(x => x.id === id); if (!p || p.code === 'trial' && !active) return;
    try { await api(`/superadmin/api/plans/${id}`, { method: 'PUT', json: { name: p.name, event_limit: p.event_limit, advanced_features: p.advanced_features, active } }); this.plans = null; this.organizations = null; this.subscriptions = null; toast(active ? 'Formule activée.' : 'Formule désactivée pour les nouvelles attributions.', 'ok'); await renderPlans(this, true); }
    catch (e) { toast(e.message, 'bad'); }
  }
  async editSubscription(id) {
    if (!this.organizations || !this.plans) {
      try { [this.organizations, this.plans] = await Promise.all([api('/superadmin/api/organizations'), api('/superadmin/api/plans')]); }
      catch (e) { toast(e.message, 'bad'); return; }
    }
    const org = this.organizations.find(x => x.id === id); if (!org) return;
    const start = new Date().toISOString().slice(0, 10);
    const end = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
    const options = (this.plans || []).filter(p => !['trial', 'internal'].includes(p.code) && p.active).map(p => `<option value="${esc(p.code)}">${esc(p.name)} — ${p.event_limit < 0 ? 'Illimité' : `${p.event_limit} événement(s)`}</option>`).join('');
    const d = sheet(`${sheetHead('Nouvelle période d’abonnement', org.name)}<div class="sheet-body"><p class="small muted">Cette attribution est ajoutée à l’historique. La période précédente est conservée.</p><form class="col" id="subForm">
      <label class="field">Formule<select class="select" name="plan_code" required>${options}</select></label>
      <div class="row wrap"><label class="field grow">Début<input class="input" type="date" name="starts_at" value="${start}" required></label><label class="field grow">Fin<input class="input" type="date" name="ends_at" value="${end}" required></label></div>
      <label class="field">Statut<select class="select" name="status"><option value="active">Actif</option><option value="suspended">Suspendu</option><option value="expired">Expiré</option></select></label>
      <div id="subError"></div><button class="btn primary block" type="submit" ${options ? '' : 'disabled'}>Attribuer cette période</button></form></div>`);
    $('#subForm', d).onsubmit = async e => { e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true); const data = Object.fromEntries(new FormData(e.target)); data.starts_at = `${data.starts_at}T00:00:00+00:00`; data.ends_at = `${data.ends_at}T23:59:59+00:00`;
      try { await api(`/superadmin/api/organizations/${id}/subscription`, { method: 'PUT', json: data }); this.organizations = null; this.subscriptions = null; d.close(); toast('Nouvelle période enregistrée.', 'ok'); if (this.tab === 'abonnements') renderSubscriptions(this, true); else this.renderOrganizations(true); }
      catch (err) { busy(b, false); $('#subError', d).innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`; }
    };
  }

  /* ---------- Profil ---------- */
  async renderProfile() {
    const p = prefs.get(), th = getTheme(), n = await queue.count();
    this.view.innerHTML = `<div class="col loose" style="margin-top:8px">
      <div class="card row"><div class="avatar" style="width:56px;height:56px;border-radius:18px;font-size:1.2rem">${esc(initials(this.user.full_name))}</div><div class="grow"><h2>${esc(this.user.full_name)}</h2><p class="muted small">${esc(this.user.username)}</p></div><span class="badge brand">${roleLabel(this.user.role)}</span></div>
      <section class="col"><h2 style="font-size:1.05rem">Apparence</h2>
        <div class="seg" role="group" aria-label="Thème">${[['auto', 'Auto'], ['light', 'Clair'], ['dark', 'Sombre']].map(([k, l]) => `<button data-theme="${k}" aria-pressed="${th === k}">${l}</button>`).join('')}</div></section>
      ${['agent', 'supervisor'].includes(this.user.role) ? `<section class="col"><h2 style="font-size:1.05rem">Contrôle d’accès</h2>
        ${[['sound', 'Signal sonore', 'Un bip confirme chaque contrôle'], ['vibrate', 'Vibration', 'Retour tactile sur mobile'], ['autoSingle', 'Entrée immédiate', 'Valide sans confirmation les invitations individuelles scannées']].map(([k, t, s]) => `<label class="item" style="cursor:pointer"><div class="grow"><div class="title">${t}</div><div class="small muted">${s}</div></div><input type="checkbox" data-pref="${k}" ${p[k] ? 'checked' : ''} style="width:22px;height:22px;accent-color:var(--brand)"></label>`).join('')}</section>
      ` : ''}
      <section class="col"><h2 style="font-size:1.05rem">Application</h2>
        <button class="btn ghost block ${window._ia_install ? '' : 'hidden'}" id="install">${icon('phone', 'sm')}Installer sur l’écran d’accueil</button>
        <div class="banner ${navigator.onLine ? 'ok' : 'warn'}">${icon(navigator.onLine ? 'check' : 'wifioff', 'sm')}<span>${navigator.onLine ? 'Connecté au serveur' : 'Hors ligne'}${n ? `, ${plural(n, 'contrôle')} en attente` : ''}</span></div>
        ${this.user.role === 'admin' || this.user.role === 'superadmin' ? `<button class="btn ghost block" data-act="audit">${icon('list', 'sm')}${this.user.role === 'superadmin' ? 'Journal de la plateforme' : 'Journal de l’organisation'}</button>` : ''}<button class="btn ghost block" data-act="change-pw">${icon('key', 'sm')}Changer mon mot de passe</button>
        <form action="/logout" method="post" id="lo"><button class="btn danger block" type="submit">${icon('logout', 'sm')}Se déconnecter</button></form></section></div>`;
    $('#install', this.view).onclick = async () => { const e = window._ia_install; if (!e) return; e.prompt(); await e.userChoice; window._ia_install = null; $('#install').classList.add('hidden'); };
    $('#lo', this.view).onsubmit = async e => {
      if (n && !confirm(`${plural(n, 'contrôle')} hors ligne ne sont pas encore synchronisés. Se déconnecter quand même ?`)) { e.preventDefault(); return; }
      navigator.serviceWorker?.controller?.postMessage('clear-pages');
      // Appareil partagé : on efface les listes d'invités mises en cache (la file hors ligne non synchronisée est conservée, liée à son compte).
      try { Object.keys(localStorage).filter(k => k.startsWith('ia-event-') || k === 'ia-issues').forEach(k => localStorage.removeItem(k)); } catch { }
    };
  }

  async renderSupport() {
    const v = this.view;
    v.innerHTML = `<div class="col loose support-page" style="margin-top:8px"><section><h1>Support plateforme</h1><p class="muted">${this.isSuperAdmin ? 'Répondez aux demandes des organisations.' : 'Échangez directement avec l’équipe superadmin.'}</p></section>${this.user.role === 'admin' ? `<form class="card col" id="supportNew"><h2>Nouvelle demande</h2><label class="field">Objet<input class="input" name="subject" maxlength="180" required></label><label class="field">Message<textarea class="input" name="body" maxlength="10000" rows="4" required></textarea></label><div id="supportError" aria-live="polite"></div><button class="btn primary block" type="submit">Envoyer au support</button></form>` : ''}<section class="card col"><h2>${this.isSuperAdmin ? 'Demandes reçues' : 'Mes demandes'}</h2><div id="supportTickets" class="list" aria-live="polite">Chargement…</div></section><section id="supportThread" class="card col hidden"></section></div>`;
    const list = $('#supportTickets', v);
    const load = async () => {
      try {
        const rows = await api('/support/api/tickets');
        list.innerHTML = rows.map(t => `<button class="item support-ticket" type="button" data-ticket="${t.id}"><span class="grow"><strong>${esc(t.subject)}</strong><span class="meta">${t.organization ? `${esc(t.organization)} · ` : ''}${esc(t.status)} · ${esc(new Date(t.updated_at).toLocaleString('fr-FR'))}</span></span><span aria-hidden="true">›</span></button>`).join('') || '<p class="muted">Aucune demande pour le moment.</p>';
      } catch (e) { list.textContent = e.message; }
    };
    const showTicket = async id => {
      const thread = $('#supportThread', v);
      try {
        const t = await api(`/support/api/tickets/${id}`);
        thread.innerHTML = `<div class="row between"><h2>${esc(t.subject)}</h2><button class="btn sm ghost" type="button" data-close-thread>Fermer</button></div><div class="support-messages">${t.messages.map(m => `<article class="support-message"><div class="meta"><strong>${esc(m.author)}</strong> · ${esc(m.role)} · ${esc(new Date(m.created_at).toLocaleString('fr-FR'))}</div><p>${esc(m.body)}</p></article>`).join('')}</div><form id="supportReply" data-ticket="${t.id}"><label class="field">Répondre<textarea class="input" name="body" maxlength="10000" rows="3" required></textarea></label><div id="supportReplyError" aria-live="polite"></div><button class="btn primary block" type="submit">Envoyer la réponse</button></form>`;
        thread.classList.remove('hidden'); thread.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (e) { toast(e.message, 'bad'); }
    };
    list.onclick = e => { const b = e.target.closest('[data-ticket]'); if (b) showTicket(b.dataset.ticket); };
    const create = $('#supportNew', v);
    if (create) create.addEventListener('submit', async e => {
      e.preventDefault(); const f = e.currentTarget;
      try { await api('/support/api/tickets', { method: 'POST', json: { subject: f.subject.value, body: f.body.value } }); f.reset(); $('#supportError').innerHTML = ''; toast('Demande envoyée au support.', 'ok'); await load(); }
      catch (err) { $('#supportError').innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`; }
    });
    v.onsubmit = async e => {
      if (e.target.id !== 'supportReply') return;
      e.preventDefault(); const f = e.target;
      try { await api(`/support/api/tickets/${f.dataset.ticket}/messages`, { method: 'POST', json: { body: f.body.value } }); await showTicket(f.dataset.ticket); await load(); }
      catch (err) { $('#supportReplyError').innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`; }
    };
    v.onclick = e => { if (e.target.closest('[data-close-thread]')) $('#supportThread', v).classList.add('hidden'); };
    await load();
  }

  async renderSubscription(force = false) {
    const v = this.view;
    if (force || !this.subscription) { v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(3, 110)}</div>`; try { this.subscription = await api('/admin/api/subscription'); } catch (e) { v.innerHTML = empty('wifioff', 'Abonnement indisponible', e.message, '<button class="btn primary" data-act="reload-subscription">Réessayer</button>'); return; } }
    const s = this.subscription;
    if (s.state === 'none') { v.innerHTML = `<div class="col loose" style="margin-top:8px"><section><h1>Mon abonnement</h1><p class="muted">État du service et des droits associés à votre organisation.</p></section><div class="banner bad" role="alert">${icon('alert', 'sm')}<span>Aucun abonnement n’est associé à votre organisation. Contactez le responsable de la plateforme pour régulariser l’accès.</span></div></div>`; return; }
    const labels = { active: 'Actif', grace: 'Période de grâce', readonly: 'Lecture seule' }, classes = { active: 'ok', grace: 'warn', readonly: 'bad' };
    const contractStatus = { trial: 'Essai', active: 'Actif', suspended: 'Suspendu', expired: 'Expiré' }[s.status] || s.status;
    const when = s.state === 'readonly' ? (s.status === 'suspended' ? 'Abonnement suspendu par la plateforme. Les modifications sont bloquées ; la consultation, les exports et le contrôle des événements en cours restent disponibles.' : 'Abonnement échu. Les modifications sont bloquées ; la consultation, les exports et le contrôle des événements en cours restent disponibles.') : s.state === 'grace' ? `Période de grâce : environ ${Math.max(0, s.grace_days + s.days_left)} jour(s) avant le passage en lecture seule. La création de nouveaux événements est déjà bloquée.` : `Échéance le ${new Date(s.ends_at).toLocaleDateString('fr-FR')} (${Math.max(0, s.days_left)} jour(s) restant(s)).`;
    const countEvents = n => `${n} événement${n === 1 ? '' : 's'}`;
    const quota = s.event_limit < 0 ? 'Illimité' : `${countEvents(s.events_used)} utilisé${s.events_used === 1 ? '' : 's'} · ${countEvents(s.events_remaining)} restant${s.events_remaining === 1 ? '' : 's'} sur ${s.event_limit}`;
    v.innerHTML = `<div class="col loose" style="margin-top:8px"><section><h1>Mon abonnement</h1><p class="muted">Plan, échéances, fonctionnalités et consommation de votre organisation.</p></section>
      <section class="hero"><div class="row between"><span class="badge" style="background:rgba(255,255,255,.16);color:#fff">${esc(s.plan)}</span><span class="badge ${classes[s.state]}">${labels[s.state]}</span></div><h2 style="margin-top:14px">${s.event_limit < 0 ? 'Événements illimités' : `${countEvents(s.events_remaining)} disponible${s.events_remaining === 1 ? '' : 's'}`}</h2><p class="muted small" style="margin-top:6px">${esc(when)}</p></section>
      <section class="card col"><h2>Votre période</h2><div class="row between"><span class="muted">Début</span><strong>${new Date(s.starts_at).toLocaleDateString('fr-FR')}</strong></div><div class="row between"><span class="muted">Fin</span><strong>${new Date(s.ends_at).toLocaleDateString('fr-FR')}</strong></div><div class="row between"><span class="muted">Statut de l’abonnement</span><span class="badge ${classes[s.state]}">${contractStatus}</span></div><div class="row between"><span class="muted">Droits d’accès effectifs</span><span class="badge ${classes[s.state]}">${labels[s.state]}</span></div></section>
      <section class="card col"><h2>Consommation</h2><div class="row between"><strong>Création d’événements</strong><span class="num">${quota}</span></div>${s.event_limit >= 0 ? meter(s.events_used, s.event_limit) : ''}<p class="small muted">Les événements comptabilisés sont ceux créés pendant la période courante.</p></section>
      <section class="card col"><h2>Fonctionnalités incluses</h2><div class="item"><div class="grow"><strong>Réceptions et invitations</strong><p class="small muted">Gestion des événements et contrôle d’accès.</p></div><span class="badge ok">Inclus</span></div><div class="item"><div class="grow"><strong>Conférences et PDF personnalisés en lot</strong><p class="small muted">Création d’événements conférence et export de PDF personnalisés en lot pour les invitations.</p></div><span class="badge ${s.advanced_features ? 'ok' : 'bad'}">${s.advanced_features ? 'Inclus' : 'Non inclus'}</span></div></section>
      <div class="banner info">${icon('info', 'sm')}<span>Les changements de formule et renouvellements sont gérés par la plateforme. Aucun paiement en ligne n’est configuré dans cet espace.</span></div></div>`;
  }
  editUser(id) {
    const u = this.users?.find(x => x.id === id); if (!u) return;
    const self = u.id === this.user.id;
    const d = sheet(`${sheetHead('Gérer le compte', u.full_name)}
      <form class="sheet-body" id="euf" autocomplete="off">
        <label class="field">Nom complet<input class="input" name="full_name" value="${esc(u.full_name)}" required></label>
        <label class="field">Rôle<select class="select" name="role" ${self ? 'disabled' : ''}>${[['agent', 'Agent de contrôle'], ['supervisor', 'Superviseur'], ['admin', 'Administrateur']].map(([v, l]) => `<option value="${v}" ${u.role === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
        <label class="field">Nouveau mot de passe <small>laisser vide pour ne pas changer</small><input class="input" name="new_password" minlength="10" autocomplete="new-password" spellcheck="false"></label>
        ${self ? '' : `<label class="item"><span class="grow">Compte actif <small class="muted">Désactiver coupe l’accès immédiatement</small></span><input type="checkbox" name="active" ${u.active ? 'checked' : ''} style="width:22px;height:22px"></label>`}
        <div id="eue"></div><button class="btn primary block" type="submit">Enregistrer</button></form>`);
    $('#euf', d).onsubmit = async e => {
      e.preventDefault(); const f = e.target, b = $('button[type=submit]', f); busy(b, true);
      const json = { full_name: f.full_name.value };
      if (!self) { json.role = f.role.value; json.active = f.active.checked; }
      if (f.new_password.value) json.new_password = f.new_password.value;
      try { await api(`/admin/api/users/${id}`, { method: 'PATCH', json }); this.users = null; d.close(); toast('Compte mis à jour.', 'ok'); if (this.tab === 'equipe') this.renderTeam(true); }
      catch (err) { busy(b, false); $('#eue', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; }
    };
  }
  changePassword() {
    const d = sheet(`${sheetHead('Changer mon mot de passe', 'Vos autres appareils seront déconnectés.')}
      <form class="sheet-body" id="pwf" autocomplete="off">
        <label class="field">Mot de passe actuel<input class="input" type="password" name="current_password" required autocomplete="current-password"></label>
        <label class="field">Nouveau mot de passe <small>10 caractères minimum</small><input class="input" type="password" name="new_password" required minlength="10" autocomplete="new-password"></label>
        <div id="pwe"></div><button class="btn primary block" type="submit">Enregistrer</button></form>`);
    $('#pwf', d).onsubmit = async e => {
      e.preventDefault(); const f = e.target, b = $('button[type=submit]', f); busy(b, true);
      try { await api('/api/me/password', { method: 'POST', json: { current_password: f.current_password.value, new_password: f.new_password.value } }); d.close(); toast('Mot de passe modifié.', 'ok'); }
      catch (err) { busy(b, false); $('#pwe', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`; }
    };
  }
  async showAudit(before, orgId = this._auditOrgId || '') {
    if (this.user.role === 'superadmin' && !this.organizations) {
      try { this.organizations = await api('/superadmin/api/organizations'); } catch (e) { toast(e.message, 'bad'); return; }
    }
    this._auditOrgId = orgId;
    const q = new URLSearchParams({ limit: '30' }); if (before) q.set('before_id', before); if (orgId) q.set('org_id', orgId);
    let data;
    try { data = await api(`/admin/api/audit?${q}`); } catch (e) { toast(e.message, 'bad'); return; }
    const rows = data.items.map(r => `<div class="item"><div class="grow"><div class="title ellipsis">${esc(r.action)}</div><div class="meta"><span>${esc(r.user.full_name)}</span>${r.organization ? `<span>${esc(r.organization)}</span>` : ''}<span>${esc(new Date(r.at).toLocaleString('fr-FR'))}</span></div>${r.details ? `<div class="small muted">${esc(r.details)}</div>` : ''}</div></div>`).join('') || '<p class="muted">Aucune activité enregistrée.</p>';
    if (before && this._auditSheet) {
      $('#auditList', this._auditSheet).insertAdjacentHTML('beforeend', rows);
      const more = $('#auditMore', this._auditSheet); if (!data.next_before_id) more.remove(); else more.dataset.before = data.next_before_id;
      return;
    }
    const platformFilter = this.user.role === 'superadmin' ? `<label class="field">Organisation<select class="select" id="auditOrg"><option value="">Toutes les organisations et actions plateforme</option>${this.organizations.map(o => `<option value="${o.id}" ${String(o.id) === String(orgId) ? 'selected' : ''}>${esc(o.name)}</option>`).join('')}</select></label>` : '';
    const title = this.user.role === 'superadmin' ? 'Journal de la plateforme' : 'Journal de l’organisation';
    const d = this._auditSheet = sheet(`${sheetHead(title, this.user.role === 'superadmin' ? 'Actions SaaS, filtrables par organisation' : 'Actions récentes de votre organisation')}<div class="sheet-body">${platformFilter}<div class="list" id="auditList">${rows}</div>${data.next_before_id ? `<button class="btn ghost block" id="auditMore" data-before="${data.next_before_id}">Voir plus</button>` : ''}</div>`);
    const orgSelect = $('#auditOrg', d); if (orgSelect) orgSelect.onchange = () => { const next = orgSelect.value; d.close(); this._auditSheet = null; this._auditOrgId = next; this.showAudit(); };
    const more = $('#auditMore', d); if (more) more.onclick = () => this.showAudit(more.dataset.before, this._auditOrgId);
  }

  click(e) {
    const f = e.target.closest('[data-filter]'); if (f) { this.filter = f.dataset.filter; this.renderEvents(); return; }
    const t = e.target.closest('[data-theme]'); if (t) { setTheme(t.dataset.theme); $$('[data-theme]', this.view).forEach(b => b.setAttribute('aria-pressed', b === t)); return; }
    const pr = e.target.closest('[data-pref]'); if (pr) { prefs.set(pr.dataset.pref, pr.checked); return; }
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'event-status') { e.preventDefault(); e.stopPropagation(); return this.changeEventStatus(Number(a.dataset.id), a.dataset.status, a); }
    if (a.dataset.act === 'plan-edit') { this.newPlan(Number(a.dataset.plan)); return; }
    if (a.dataset.act === 'plan-toggle') { this.togglePlan(Number(a.dataset.plan), a.dataset.active !== '1'); return; }
    if (a.dataset.act === 'sub-org') { this.editSubscription(Number(a.dataset.org)); return; }
    if (a.dataset.act === 'subscription-filter') { setSubscriptionFilter(this, a.dataset.k); return; }
    if (a.dataset.act === 'reload-orgs') {
      if (this.tab === 'plans') { this.plans = null; renderPlans(this, true); }
      else if (this.tab === 'abonnements') { this.subscriptions = null; renderSubscriptions(this, true); }
      else { this.organizations = null; this.stats2 = null; this.renderOrganizations(true); }
      return;
    }
    if (a.dataset.act === 'reload-subscription') { this.subscription = null; this.renderSubscription(true); return; }
    ({ 'new-event': () => this.newEvent(), 'new-user': () => this.newUser(), 'new-org': () => this.newOrganization(), 'new-plan': () => this.newPlan(), 'edit-sub': () => this.editSubscription(Number(a.dataset.org)), sa: () => ({ open: () => openOrg(this, +a.dataset.org), extend: () => extend(this, +a.dataset.org, +a.dataset.days), filter: () => setFilter(this, a.dataset.k) })[a.dataset.do]?.(), reload: () => { this.stats = {}; this.subscription = null; this.renderEvents(true); }, 'reload-team': () => this.renderTeam(true), 'edit-user': () => this.editUser(Number(a.dataset.id)), 'change-pw': () => this.changePassword(), 'audit': () => this.showAudit() })[a.dataset.act]?.();
  }
}
