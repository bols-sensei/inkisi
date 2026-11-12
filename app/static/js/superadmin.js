/* Console superadministrateur : tableau de bord plateforme, organisations, formules, comptes. */
import { $, $$, esc, icon, api, toast, sheet, sheetHead, busy, plural, norm, empty, skeletons, meter, debounce, dateFr, initials, roleLabel } from './core.js';

const LAB = { trial: ['Essai', 'brand'], active: ['Actif', 'ok'], suspended: ['Suspendu', 'warn'], expired: ['Expiré', 'bad'], none: ['Sans abonnement', ''] };
const eff = o => { const s = o.subscription; if (!s) return 'none'; if (s.status === 'suspended') return 'suspended'; return new Date(s.ends_at) <= Date.now() ? 'expired' : s.status; };
const left = o => o.subscription ? Math.ceil((new Date(o.subscription.ends_at) - Date.now()) / 864e5) : null;
const gen = () => { const a = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789', r = crypto.getRandomValues(new Uint8Array(12)); return [...r].map(x => a[x % a.length]).join(''); };
const soon = o => { const d = left(o); return d !== null && eff(o) !== 'suspended' && d <= 7; };
const eventLimit = n => n < 0 ? 'Illimité' : `${n} événement${n === 1 ? '' : 's'} par période`;
let filter = 'toutes', query = '', subscriptionFilter = 'toutes', subscriptionQuery = '';

export async function renderConsole(home, force) {
  const v = home.view;
  if (!home.organizations || !home.plans || !home.stats2 || force) {
    v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(1, 220)}${skeletons(3, 100)}</div>`;
    try { [home.organizations, home.plans, home.stats2] = await Promise.all([api('/superadmin/api/organizations'), api('/superadmin/api/plans'), api('/superadmin/api/stats')]); }
    catch (e) { v.innerHTML = empty('wifioff', 'Chargement impossible', e.message, '<button class="btn primary" data-act="reload-orgs">Réessayer</button>'); return; }
  }
  const O = home.organizations, S = home.stats2, n = k => O.filter(o => eff(o) === k).length, urgent = O.filter(o => soon(o) || eff(o) === 'expired');
  const orgActive = O.filter(o => o.status === 'active').length, orgSuspended = O.filter(o => o.status === 'suspended').length;
  v.innerHTML = `<div class="col loose" style="margin-top:8px">
    <section class="hero"><div class="row between"><span class="live"><i></i><span>Plateforme</span></span><span class="badge" style="background:rgba(255,255,255,.16);color:#fff">Superadministrateur</span></div>
      <h1 style="margin-top:12px">Pilotage de la plateforme</h1><p class="muted small">Organisations clientes, accès et échéances d’abonnement.</p>
      <div class="kpis" style="margin-top:16px;grid-template-columns:repeat(2,1fr)">${[[O.length, 'Organisations'], [orgActive, 'Organisations actives'], [orgSuspended, 'Organisations suspendues'], [n('active'), 'Abonnements actifs'], [n('expired'), 'Abonnements expirés'], [n('suspended'), 'Abonnements suspendus'], [n('trial'), 'Essais en cours'], [urgent.length, 'Échéances à traiter']].map(([a, b]) => `<div class="kpi"><strong class="num">${a}</strong><span>${b}</span></div>`).join('')}</div></section>
    <section class="card col"><div class="row between"><h2 style="font-size:1.05rem">Nouvelles organisations</h2><span class="small muted">6 derniers mois</span></div>${(() => { const rows = S.organization_signups || [], max = Math.max(1, ...rows.map(x => x.count)); return rows.map(x => `<div class="bar-row"><span>${esc(x.label)}</span>${meter(x.count, max)}<strong class="num">${x.count}</strong></div>`).join(''); })()}</section>
    <div class="row"><button class="btn primary grow" data-act="new-org">${icon('plus', 'sm')}Nouvelle organisation</button></div>
    <section class="card col"><h2 style="font-size:1.05rem">Organisations par formule</h2><div class="list">${[...new Set(O.map(o => o.subscription?.plan).filter(Boolean))].map(name => `<div class="item"><span class="grow">${esc(name)}</span><strong class="num">${O.filter(o => o.subscription?.plan === name).length}</strong></div>`).join('') || '<p class="small muted">Aucune formule attribuée.</p>'}</div></section>
    ${urgent.length ? `<section class="card col"><h2 style="font-size:1.05rem">À traiter</h2><div class="list">${urgent.map(o => `<div class="item"><div class="grow"><div class="title ellipsis">${esc(o.name)}</div><div class="small muted">${o.status === 'suspended' ? 'Organisation suspendue' : eff(o) === 'expired' ? 'Abonnement expiré' : `Expire ${left(o) <= 0 ? 'aujourd’hui' : `dans ${plural(left(o), 'jour')}`}`}</div></div>${o.status === 'suspended' ? `<button class="btn sm tonal" data-act="sa" data-do="open" data-org="${o.id}">Examiner</button>` : `<button class="btn sm primary" data-act="sa" data-do="extend" data-org="${o.id}" data-days="30">+30 j</button>`}</div>`).join('')}</div></section>` : ''}
    <section class="col"><div class="searchbox">${icon('search', 'sm')}<input class="input" id="oq" type="search" placeholder="Rechercher une organisation" value="${esc(query)}" aria-label="Rechercher une organisation"></div>
      <div class="chips org-filters" role="group" aria-label="Filtrer">${[['toutes', 'Toutes', O.length], ['trial', 'Essai', n('trial')], ['active', 'Abonnement actif', n('active')], ['expired', 'Abonnement expiré', n('expired')], ['suspended', 'Abonnement suspendu', n('suspended')], ['org_active', 'Organisation active', orgActive], ['org_suspended', 'Organisation suspendue', orgSuspended]].map(([k, l, c]) => `<button class="chip" data-act="sa" data-do="filter" data-k="${k}" aria-pressed="${filter === k}">${l} <span class="n num">${c}</span></button>`).join('')}</div>
      <div class="col" id="orgList"></div></section>
    </div>`;
  const paint = () => {
    const rows = O.filter(o => (filter === 'toutes' || (filter === 'org_suspended' ? o.status === 'suspended' : filter === 'org_active' ? o.status === 'active' : eff(o) === filter)) && (!query || norm(o.name + ' ' + o.slug + ' ' + (o.admin?.name || '') + ' ' + (o.admin?.username || '')).includes(query)));
    $('#orgList', v).innerHTML = rows.length ? rows.map(card).join('') : empty('building-2', 'Aucune organisation', 'Changez de filtre ou créez un nouvel espace.');
  };
  const card = o => {
    const k = eff(o), [lab, cls] = LAB[k], s = o.subscription, d = left(o), total = s ? Math.max(1, (new Date(s.ends_at) - new Date(s.starts_at)) / 864e5) : 1;
    return `<article class="card org-card">
      <header class="org-card-head"><h3>${esc(o.name)}</h3><span class="badge ${o.status === 'active' ? 'ok' : 'bad'}">Organisation ${o.status === 'active' ? 'active' : 'suspendue'}</span></header>
      <div class="org-card-facts">
        <p><span class="org-card-label">Administrateur</span><strong>${o.admin ? `${esc(o.admin.name)} <span class="org-card-username">(${esc(o.admin.username)})</span>` : 'Aucun administrateur'}</strong></p>
        <p><span class="org-card-label">Comptes</span><strong>${plural(o.users, 'compte')}</strong></p>
        <p><span class="org-card-label">Événements</span><strong>${plural(o.events, 'événement')}</strong></p>
        <p><span class="org-card-label">Abonnement</span><span class="org-card-plan"><span class="badge ${cls}">${lab}</span>${s ? `<strong>${esc(s.plan)}</strong>` : ''}</span></p>
      </div>
      <p class="org-card-date">Inscrite le ${new Date(o.created_at).toLocaleDateString('fr-FR')}${o.upcoming_subscription ? ` <span>·</span> Prochaine période le ${new Date(o.upcoming_subscription.starts_at).toLocaleDateString('fr-FR')}` : ''}</p>
      ${s ? `<div class="org-card-period">${meter(Math.max(0, total - Math.max(0, d)), total)}<p class="small ${d <= 7 ? 'org-card-urgent' : 'muted'}">${d > 0 ? `${plural(d, 'jour')} restant${d > 1 ? 's' : ''}` : 'Expiré'} · fin le ${new Date(s.ends_at).toLocaleDateString('fr-FR')}</p></div>` : ''}
      <div class="org-card-actions"><button class="btn tonal" data-act="sa" data-do="open" data-org="${o.id}">Détails</button><button class="btn ghost" data-act="sa" data-do="extend" data-org="${o.id}" data-days="30">+30 j</button></div></article>`;
  };
  paint();
  $('#oq', v).addEventListener('input', debounce(e => { query = norm(e.target.value); paint(); }, 120));
}

export const setFilter = (home, k) => { filter = k; return renderConsole(home); };

export async function renderPlans(home, force = false) {
  const v = home.view;
  if (!home.plans || force || !home.organizations) {
    v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(3, 100)}</div>`;
    try { [home.plans, home.organizations] = await Promise.all([api('/superadmin/api/plans'), api('/superadmin/api/organizations')]); }
    catch (e) { v.innerHTML = empty('wifioff', 'Formules indisponibles', e.message, '<button class="btn primary" data-act="reload-orgs">Réessayer</button>'); return; }
  }
  v.innerHTML = `<div class="col loose" style="margin-top:8px"><section><h1>Formules</h1><p class="muted">Les formules définissent le quota d’événements et les options incluses.</p><div class="banner info" role="note">Les prix, les factures et les paiements ne sont pas enregistrés ici ; aucun revenu n’est calculé.</div></section>
    <button class="btn primary block" data-act="new-plan">${icon('plus', 'sm')}Créer une formule</button>
    <div class="col">${home.plans.map(p => { const assigned = home.organizations.filter(o => o.subscription?.plan_code === p.code).length, fixed = ['trial', 'internal'].includes(p.code); return `<article class="card col"><div class="row between"><h2>${esc(p.name)}</h2><span class="badge ${p.active ? 'ok' : 'bad'}">${fixed ? 'Système' : p.active ? 'Active' : 'Inactive'}</span></div><p class="small muted">Code : <strong>${esc(p.code)}</strong></p><div class="row between"><span>Quota d’événements</span><strong>${eventLimit(p.event_limit)}</strong></div><div class="row between"><span>Options conférences et PDF personnalisés en lot</span><strong>${p.advanced_features ? 'Incluses' : 'Non incluses'}</strong></div><p class="small muted">Autorise la création de conférences et l’export de PDF personnalisés en lot.</p><div class="row between"><span>Organisations avec cette formule</span><strong class="num">${assigned}</strong></div><p class="small muted">${fixed ? 'Formule système protégée.' : 'Désactiver une formule bloque les nouvelles attributions sans changer les droits des abonnements existants.'}</p><div class="row"><button class="btn tonal grow" data-act="plan-edit" data-plan="${p.id}" ${fixed ? 'disabled title="Formule système protégée."' : ''}>Modifier</button><button class="btn ${p.active ? 'ghost' : 'primary'}" data-act="plan-toggle" data-plan="${p.id}" data-active="${p.active ? '1' : '0'}" ${fixed ? 'disabled title="Formule système protégée."' : ''}>${fixed ? 'Protégée' : p.active ? 'Désactiver' : 'Activer'}</button></div></article>`; }).join('') || empty('layers', 'Aucune formule')}</div></div>`;
}

export async function renderSubscriptions(home, force = false) {
  const v = home.view;
  if (!home.subscriptions || force) {
    v.innerHTML = `<div class="col" style="margin-top:8px">${skeletons(4, 90)}</div>`;
    try { home.subscriptions = await api('/superadmin/api/subscriptions'); }
    catch (e) { v.innerHTML = empty('wifioff', 'Abonnements indisponibles', e.message, '<button class="btn primary" data-act="reload-orgs">Réessayer</button>'); return; }
  }
  const rows = [...home.subscriptions].sort((a, b) => b.starts_at.localeCompare(a.starts_at));
  const stateOf = s => new Date(s.starts_at) > Date.now() ? 'upcoming' : s.status === 'suspended' ? 'suspended' : s.status === 'expired' || new Date(s.ends_at) <= Date.now() ? 'expired' : s.status === 'trial' ? 'trial' : 'active';
  const labels = { upcoming: 'À venir', active: 'Actif', trial: 'Essai', suspended: 'Suspendu', expired: 'Expiré' };
  const counts = Object.fromEntries(['toutes', 'upcoming', 'active', 'trial', 'suspended', 'expired'].map(k => [k, k === 'toutes' ? rows.length : rows.filter(s => stateOf(s) === k).length]));
  const shown = rows.filter(s => (subscriptionFilter === 'toutes' || stateOf(s) === subscriptionFilter) && (!subscriptionQuery || norm(`${s.organization} ${s.plan}`).includes(subscriptionQuery)));
  v.innerHTML = `<div class="col loose" style="margin-top:8px"><section><h1>Abonnements</h1><p class="muted">Chaque ligne est une période historisée. Les statuts de l’organisation et de l’abonnement sont indépendants.</p><p class="small muted">Aucune facture ni transaction n’est enregistrée par le système actuel.</p></section><div class="searchbox">${icon('search', 'sm')}<input class="input" id="subscriptionSearch" type="search" placeholder="Rechercher une organisation ou un plan" value="${esc(subscriptionQuery)}" aria-label="Rechercher une organisation ou un plan"></div><div class="chips" role="group" aria-label="Filtrer les abonnements">${[['toutes','Toutes'],['active','Actifs'],['trial','Essais'],['suspended','Suspendus'],['expired','Expirés'],['upcoming','À venir']].map(([k,l]) => `<button class="chip" data-act="subscription-filter" data-k="${k}" aria-pressed="${subscriptionFilter === k}">${l} <span class="n num">${counts[k]}</span></button>`).join('')}</div><div class="col">${shown.map(s => {
    const stateKey = stateOf(s), upcoming = stateKey === 'upcoming';
    const state = [labels[stateKey], stateKey === 'active' ? 'ok' : stateKey === 'trial' || stateKey === 'upcoming' ? 'brand' : stateKey === 'suspended' ? 'warn' : 'bad'];
    const period = upcoming ? 'Période future' : s.current ? 'Période actuelle' : 'Historique';
    return `<article class="card col"><div class="row between"><h2>${esc(s.organization)}</h2><span class="badge ${s.organization_status === 'active' ? 'ok' : 'bad'}">Organisation ${s.organization_status === 'active' ? 'active' : 'suspendue'}</span></div><div class="row wrap"><span class="badge ${state[1]}">Abonnement ${state[0].toLowerCase()}</span><span class="badge">${period}</span><strong>${esc(s.plan)}</strong></div><div class="row between"><span class="muted">Début</span><strong>${new Date(s.starts_at).toLocaleDateString('fr-FR')}</strong></div><div class="row between"><span class="muted">Fin</span><strong>${new Date(s.ends_at).toLocaleDateString('fr-FR')}</strong></div><p class="small muted">${eventLimit(s.event_limit)} · Conférences et PDF personnalisés en lot : ${s.advanced_features ? 'inclus' : 'non inclus'}.</p><button class="btn tonal" data-act="sub-org" data-org="${s.organization_id}">Attribuer une nouvelle période</button></article>`;
  }).join('') || empty('clock', subscriptionQuery || subscriptionFilter !== 'toutes' ? 'Aucun résultat' : 'Aucun abonnement enregistré', 'Modifiez la recherche ou le filtre pour afficher les autres périodes.')}</div></div>`;
  $('#subscriptionSearch', v).addEventListener('input', debounce(e => { subscriptionQuery = norm(e.target.value); renderSubscriptions(home); }, 120));
}

export const setSubscriptionFilter = (home, key) => { subscriptionFilter = key; return renderSubscriptions(home); };

export async function extend(home, id, days) {
  const o = home.organizations.find(x => x.id === id), s = o?.upcoming_subscription || o?.subscription; if (!o) return;
  const now = Date.now(), base = s && new Date(s.ends_at) > now ? new Date(s.ends_at) : new Date(now);
  try {
    await api(`/superadmin/api/organizations/${id}/subscription`, { method: 'PUT', json: { plan_code: s?.plan_code || 'trial', starts_at: base.toISOString(), ends_at: new Date(base.getTime() + days * 864e5).toISOString(), status: 'active' } });
    toast(`${o.name} : +${days} jours.`, 'ok'); await renderConsole(home, true);
  } catch (e) { toast(e.message, 'bad'); }
}

export async function openOrg(home, id) {
  const o = home.organizations.find(x => x.id === id); if (!o) return;
  let det; try { det = await api(`/superadmin/api/organizations/${id}/detail`); } catch (e) { return toast(e.message, 'bad'); }
  const [lab, cls] = LAB[eff(o)], s = o.subscription;
  const d = sheet(`${sheetHead(o.name, o.slug)}<div class="sheet-body">
    <div class="row wrap"><span class="badge ${o.status === 'active' ? 'ok' : 'bad'}">Organisation ${o.status === 'active' ? 'active' : 'suspendue'}</span><span class="badge ${cls}">Abonnement ${lab.toLowerCase()}</span>${s ? `<span class="badge">${esc(s.plan)}</span><span class="badge">${s.event_limit < 0 ? 'Illimité' : plural(s.event_limit, 'événement')}</span>` : ''}</div>
    <button class="btn ${o.status === 'active' ? 'danger' : 'primary'} block" data-toggle-org="${o.status === 'active' ? 'suspended' : 'active'}">${o.status === 'active' ? 'Suspendre l’organisation' : 'Réactiver l’organisation'}</button>
    <div class="row wrap">${[14, 30, 90].map(n => `<button class="btn sm ghost" data-x="${n}">+${n} jours</button>`).join('')}<button class="btn sm primary" data-sub>Gérer l’abonnement</button></div>
    <h3>Comptes</h3><div class="list">${det.users.map(u => `<div class="item"><div class="avatar">${esc(initials(u.full_name))}</div><div class="grow"><div class="title ellipsis">${esc(u.full_name)}</div><div class="meta"><span>${esc(u.username)}</span><span>${roleLabel(u.role)}</span>${u.active ? '' : '<span class="badge bad">Désactivé</span>'}</div></div><button class="btn sm ghost" data-pw="${u.id}" aria-label="Réinitialiser le mot de passe de ${esc(u.full_name)}">${icon('key', 'sm')}</button><button class="btn sm ghost" data-tg="${u.id}" data-on="${u.active ? 1 : 0}">${u.active ? 'Désactiver' : 'Réactiver'}</button></div>`).join('') || empty('users', 'Aucun compte')}</div>
    <p class="small muted">La consultation des événements clients se fait dans un parcours de support dédié.</p></div>`);
  d.addEventListener('click', async e => {
    const x = e.target.closest('[data-x]'); if (x) { d.close(); return extend(home, id, +x.dataset.x); }
    if (e.target.closest('[data-sub]')) { d.close(); return home.editSubscription(id); }
    const toggle = e.target.closest('[data-toggle-org]'); if (toggle) {
      const status = toggle.dataset.toggleOrg, action = status === 'suspended' ? 'Suspendre l’organisation' : 'Réactiver l’organisation';
      const reasonSheet = sheet(`${sheetHead(action, o.name)}<form class="sheet-body" id="orgStatusForm"><label class="field">Motif ${status === 'suspended' ? '(obligatoire)' : '(facultatif)'}<textarea class="textarea" id="orgStatusReason" name="reason" maxlength="500" ${status === 'suspended' ? 'required minlength="3"' : ''}></textarea></label><div id="orgStatusError"></div><button class="btn ${status === 'suspended' ? 'danger' : 'primary'} block" type="submit">${action}</button></form>`);
      $('#orgStatusForm', reasonSheet).onsubmit = async ev => {
        ev.preventDefault(); const button = $('button[type=submit]', ev.target), reason = $('#orgStatusReason', reasonSheet).value.trim(); busy(button, true);
        try { await api(`/superadmin/api/organizations/${id}/status`, { method: 'PATCH', json: { status, reason } }); reasonSheet.close(); d.close(); home.organizations = null; home.stats2 = null; toast(status === 'active' ? 'Organisation réactivée.' : 'Organisation suspendue.', 'ok'); await renderConsole(home, true); }
        catch (er) { busy(button, false); $('#orgStatusError', reasonSheet).innerHTML = `<div class="banner bad" role="alert">${esc(er.message)}</div>`; }
      };
      return;
    }
    const tg = e.target.closest('[data-tg]'); if (tg) { busy(tg, true); try { await api(`/superadmin/api/users/${tg.dataset.tg}`, { method: 'PATCH', json: { active: tg.dataset.on !== '1' } }); d.close(); toast('Compte mis à jour.', 'ok'); openOrg(home, id); } catch (er) { busy(tg, false); toast(er.message, 'bad'); } return; }
    const pw = e.target.closest('[data-pw]'); if (pw) {
      const u = det.users.find(z => z.id === +pw.dataset.pw), password = gen();
      if (!confirm(`Générer un nouveau mot de passe pour ${u.full_name} ?`)) return;
      try { await api(`/superadmin/api/users/${u.id}`, { method: 'PATCH', json: { password } }); d.close(); home.credentials({ username: u.username, full_name: u.full_name, password }); } catch (er) { toast(er.message, 'bad'); }
    }
  });
}
