/* Interfaces des fonctions déjà présentes côté serveur : inscriptions, édition d'invitation et d'événement, export CSV. */
import { $, $$, esc, icon, api, toast, sheet, sheetHead, busy, empty, norm, debounce, plural } from './core.js';

export const REG = { pending: ['En attente', 'warn'], accepted: ['Acceptée', 'ok'], waitlist: ['Liste d’attente', 'cobalt'], rejected: ['Refusée', 'bad'], cancelled: ['Annulée', ''] };
export const TASK = { todo: 'À faire', in_progress: 'En cours', done: 'Terminée', blocked: 'Bloquée' };
export const PRIO = { low: 'Basse', normal: 'Normale', high: 'Haute', urgent: 'Urgente' };
export const dt = s => s ? new Date(s).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
export const daysTo = s => { if (!/^\d{4}-\d{2}-\d{2}/.test(s || '')) return null; const n = Math.round((new Date(s.slice(0, 10) + 'T12:00:00') - new Date()) / 864e5); return n; };
export const countdown = s => { const n = daysTo(s); return n === null ? '' : n > 1 ? `J-${n}` : n === 1 ? 'Demain' : n === 0 ? 'Aujourd’hui' : ''; };
const err = m => `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(m)}</span></div>`;

/* ---------- Inscriptions de conférence ---------- */
export async function registrations(view) {
  let data, f = 'tous', q = '';
  try { data = await api(`/admin/api/events/${view.id}/registrations`); } catch (e) { return toast(e.message, 'bad'); }
  const d = sheet(`${sheetHead('Inscriptions', '')}<div class="sheet-body"><div class="searchbox">${icon('search', 'sm')}<input class="input" id="rq" type="search" placeholder="Nom ou e-mail" aria-label="Rechercher un participant"></div><div class="chips" id="rc"></div><div class="list" id="rl"></div></div>`);
  const act = (r) => {
    const b = (s, l, c = 'ghost') => `<button class="btn sm ${c}" data-reg="${r.id}" data-status="${s}">${l}</button>`;
    if (r.status === 'pending') return b('accepted', 'Accepter', 'primary') + b('waitlist', 'Attente') + b('rejected', 'Refuser');
    if (r.status === 'waitlist') return b('accepted', 'Accepter', 'primary') + b('rejected', 'Refuser');
    if (r.status === 'accepted') return b('cancelled', 'Annuler la place');
    return b('pending', 'Remettre en attente');
  };
  const paint = () => {
    const rows = data.registrations, base = rows.filter(r => !q || norm(r.name + ' ' + r.email).includes(q));
    const n = k => base.filter(r => k === 'tous' || r.status === k).length;
    $('#rc', d).innerHTML = [['tous', 'Tous'], ...Object.entries(REG).map(([k, v]) => [k, v[0]])].map(([k, l]) => `<button class="chip" data-f="${k}" aria-pressed="${f === k}">${l} <span class="n num">${n(k)}</span></button>`).join('');
    const list = base.filter(r => f === 'tous' || r.status === f);
    $('#rl', d).innerHTML = list.length ? list.map(r => { const [lab, cls] = REG[r.status] || [r.status, '']; return `<article class="item" style="align-items:flex-start"><div class="avatar">${esc((r.name || '?')[0].toUpperCase())}</div><div class="grow col tight"><div class="row between"><strong class="ellipsis">${esc(r.name)}</strong><span class="badge ${cls}">${lab}</span></div><div class="small muted ellipsis">${esc(r.email)}</div><div class="small muted">${esc(r.category)} · ${r.verified ? 'adresse confirmée (ancien flux)' : 'adresse de contact non confirmée'}</div><div class="row wrap" style="margin-top:4px">${act(r)}</div></div></article>`; }).join('') : empty('users', rows.length ? 'Aucun résultat' : 'Aucune inscription', rows.length ? '' : 'Partagez le lien public ou ajoutez des participants.');
    $('.sheet-head p', d) || $('.sheet-head .grow', d).insertAdjacentHTML('beforeend', '<p class="muted small"></p>');
    $('.sheet-head p', d).textContent = `${data.accepted_count} acceptée(s) sur ${data.capacity || 'places illimitées'}`;
  };
  d.addEventListener('input', debounce(e => { if (e.target.id === 'rq') { q = norm(e.target.value); paint(); } }, 120));
  d.addEventListener('click', async e => {
    const c = e.target.closest('[data-f]'); if (c) { f = c.dataset.f; return paint(); }
    const b = e.target.closest('[data-reg]'); if (!b) return; busy(b, true);
    try { await api(`/admin/api/events/${view.id}/registrations/${b.dataset.reg}`, { method: 'PATCH', json: { status: b.dataset.status } }); data = await api(`/admin/api/events/${view.id}/registrations`); paint(); view.refresh(true); toast('Décision enregistrée.', 'ok'); }
    catch (x) { busy(b, false); toast(x.message, 'bad'); }
  });
  paint();
}

/* ---------- Modifier une invitation ---------- */
export function editInvitation(view, i) {
  const d = sheet(`${sheetHead('Modifier l’invitation', i.reference)}<form class="sheet-body" id="ei">
    <label class="field">Nom / destinataire<input class="input" name="guest_name" required maxlength="200" value="${esc(i.guest_name)}"></label>
    <label class="field">Type<input class="input" name="invitation_type" list="types" required maxlength="30" value="${esc(i.invitation_type)}"><datalist id="types"><option>individuelle</option><option>couple</option><option>famille</option><option>groupe</option></datalist></label>
    <label class="field">Quota de personnes <small>${i.entered ? `Minimum ${i.entered} : déjà entré${i.entered > 1 ? 's' : ''}.` : ''}</small><input class="input" name="quota" type="number" min="${Math.max(1, i.entered)}" max="10000" required value="${i.quota}"></label>
    <label class="field">Table<input class="input" name="table_name" maxlength="80" value="${esc(i.table_name || '')}"></label>
    <div id="ee"></div><button class="btn primary block" type="submit">Enregistrer les changements</button></form>`);
  $('#ei', d).onsubmit = async e => {
    e.preventDefault(); const b = $('button[type=submit]', e.target), data = Object.fromEntries(new FormData(e.target)); data.quota = +data.quota; busy(b, true);
    try { await api(`/admin/api/events/${view.id}/invitations/${i.id}`, { method: 'PATCH', json: data }); d.close(); toast('Invitation mise à jour.', 'ok'); await view.refresh(true); }
    catch (x) { busy(b, false); $('#ee', d).innerHTML = err(x.message); }
  };
}

/* ---------- Modifier un participant conférence / invité manuel ---------- */
export function editConferenceParticipant(view, p) {
  const d = sheet(`${sheetHead('Modifier le participant / invité', p.guest_name || p.name)}<form class="sheet-body" id="ep">
    <div class="row">
      <label class="field grow">Prénom<input class="input" name="first_name" value="${esc(p.first_name || '')}"></label>
      <label class="field grow">Nom<input class="input" name="last_name" value="${esc(p.last_name || '')}"></label>
    </div>
    <label class="field">Profession / Fonction<input class="input" name="profession" value="${esc(p.profession || '')}"></label>
    <div class="row">
      <label class="field grow">E-mail<input class="input" name="email" type="email" value="${esc(p.email && !p.email.includes('@conference.local') ? p.email : '')}"></label>
      <label class="field grow">Téléphone<input class="input" name="phone" type="tel" value="${esc(p.phone || '')}"></label>
    </div>
    <div class="row">
      <label class="field grow">Organisation<input class="input" name="organization_name" value="${esc(p.organization_name || '')}"></label>
      <label class="field grow">Catégorie
        <select class="select" name="category">
          ${['participant', 'invité', 'vip', 'organisateur', 'staff', 'presse'].map(c => `<option value="${c}" ${(p.category || '').toLowerCase() === c ? 'selected' : ''}>${c.toUpperCase()}</option>`).join('')}
        </select>
      </label>
    </div>
    <label class="field" style="flex-direction:row;align-items:center;gap:10px;margin-top:6px">
      <input type="checkbox" name="regenerate_qr" value="true">
      <span>Régénérer et révoquer le QR code actuel</span>
    </label>
    <div id="epe"></div>
    <button class="btn primary block" type="submit" style="margin-top:10px">Enregistrer les modifications</button>
  </form>`);

  $('#ep', d).onsubmit = async e => {
    e.preventDefault();
    const b = $('button[type=submit]', e.target);
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd);
    payload.regenerate_qr = fd.get('regenerate_qr') === 'true';
    busy(b, true);
    try {
      const res = await api(`/admin/api/events/${view.id}/registrations/${p.id}/details`, {
        method: 'PATCH',
        json: payload
      });
      d.close();
      toast(res.message || 'Informations mises à jour.', 'ok');
      await view.refresh(false);
    } catch(err) {
      busy(b, false);
      $('#epe', d).innerHTML = `<div class="banner bad">${esc(err.message)}</div>`;
    }
  };
}

/* ---------- Informations et état de l'événement ---------- */
export function editEvent(view) {
  const ev = view.detail;
  const d = sheet(`${sheetHead('Informations de l’événement')}<form class="sheet-body" id="ev">
    <label class="field">Nom de l’événement<input class="input" name="name" required maxlength="180" value="${esc(ev.name)}"></label>
    <div class="row wrap" style="gap:10px">
      <label class="field grow">Date de début<input class="input" type="date" name="start_date" value="${esc(ev.start_date || '')}"></label>
      <label class="field" style="width:130px">Heure début<input class="input" type="time" name="start_time" value="${esc(ev.start_time || '')}"></label>
    </div>
    <div class="row wrap" style="gap:10px">
      <label class="field grow">Date de fin<input class="input" type="date" name="end_date" value="${esc(ev.end_date || '')}"></label>
      <label class="field" style="width:130px">Heure fin<input class="input" type="time" name="end_time" value="${esc(ev.end_time || '')}"></label>
    </div>
    <label class="field">Lieu<input class="input" name="venue" maxlength="240" value="${esc(ev.venue || '')}"></label>
    <div id="ee"></div><button class="btn primary block" type="submit">Enregistrer</button></form>`);
  $('#ev', d).onsubmit = async e => {
    e.preventDefault(); const b = $('button[type=submit]', e.target); busy(b, true);
    try { await api(`/admin/api/events/${view.id}`, { method: 'PATCH', json: Object.fromEntries(new FormData(e.target)) }); d.close(); toast('Événement mis à jour.', 'ok'); await view.load(); view.renderManage(); }
    catch (x) { busy(b, false); $('#ee', d).innerHTML = err(x.message); }
  };
}

/* ---------- Export CSV de la liste et des présences ---------- */
export function exportCsv(view) {
  const rows = view.invs(), cell = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = '\ufeff' + [['Référence', 'Invité', 'Type', 'Table', 'Quota', 'Entrés', 'Restants'], ...rows.map(i => [i.reference, i.guest_name, i.invitation_type, i.table_name, i.quota, i.entered, i.remaining])].map(r => r.map(cell).join(';')).join('\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = `presences_evenement_${view.id}.csv`;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); toast(`${plural(rows.length, 'ligne')} exportée${rows.length > 1 ? 's' : ''}.`, 'ok');
}
