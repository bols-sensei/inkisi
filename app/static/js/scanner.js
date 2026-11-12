/* Contrôle d'accès : caméra (BarcodeDetector ou jsQR), NFC, saisie manuelle, verdict, hors ligne. */
import { $, esc, icon, api, toast, sheet, sheetHead, busy, uuid, feedback, prefs, plural, meter, rel, empty } from './core.js';
import { enqueue, queue, issues, syncQueue } from './offline.js';

export function scanToken(value) {
  let v = String(value || '').replace(/[\s\u200B-\u200D\uFEFF]/g, '').trim();
  if (v.includes('token:')) v = v.slice(v.indexOf('token:') + 6).trim();
  if (/^(?:BADGE:|IA1\.|CONF:)/i.test(v)) return v;
  try { const u = new URL(v); v = u.searchParams.get('token') || u.searchParams.get('code') || u.pathname.split('/').filter(Boolean).pop() || v; } catch { }
  return v;
}
const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const parseBadgeQr = value => {
  const v = scanToken(value);
  let m = /^BADGE:(.+)$/i.exec(v);
  if (m) return UUID4.test(m[1]) ? { reference: m[1].toLowerCase(), format: 'badge' } : { invalid: true };
  if (UUID4.test(v)) return { reference: v.toLowerCase(), format: 'uuid' };
  m = /^IA1\.(\d{1,9})\.([A-Za-z0-9_-]{16,128})$/.exec(v);
  if (m) return { eventId: +m[1], token: m[2], reference: UUID4.test(m[2]) ? m[2].toLowerCase() : null, format: 'legacy-invitation' };
  m = /^CONF:(\d{1,9}):([A-Za-z0-9_-]{20,128})$/.exec(v);
  if (m) return { eventId: +m[1], token: m[2], reference: UUID4.test(m[2]) ? m[2].toLowerCase() : null, format: 'legacy-conference' };
  if (/^(?:IA1\.|CONF:)/i.test(v)) return { invalid: true };
  return null;
};
export const parseQr = v => { const parsed = parseBadgeQr(v); return parsed?.format === 'legacy-invitation' ? { eventId: parsed.eventId, token: parsed.token } : null; };
export const parseConferenceQr = v => { const parsed = parseBadgeQr(v); return parsed?.format === 'legacy-conference' ? { eventId: parsed.eventId, badgeReference: parsed.reference || parsed.token } : null; };
const classify = (v, method) => /^INV-/i.test(v) ? 'ref' : (/^(?:BADGE:|IA1\.)/i.test(v) || UUID4.test(v)) ? 'token' : (/^[A-Za-z0-9_-]{24,}$/.test(v) || (method !== 'manual' && /^\S{12,}$/.test(v))) ? 'token' : 'name';
const loadScript = src => new Promise((ok, ko) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = ko; document.head.appendChild(s); });

export function mountScanner(root, ctx) {
  const eid = ctx.eventId;
  let stream = null, detector = null, timer = null, paused = false, working = false, lastCode = '', lastAt = 0, nfcAbort = null, canvas = null;
  const history = [];

  root.innerHTML = `<div class="col loose">
    <div id="scNet"></div>
    <div class="viewfinder" id="vf"></div>
    <form class="manual" id="manual" role="search">
      <input class="input" id="mIn" placeholder="Référence, nom ou code" autocomplete="off" autocapitalize="none" enterkeyhint="search" aria-label="Référence, nom ou code">
      <button class="btn primary icon" aria-label="Vérifier">${icon('search')}</button>
    </form>
    <div class="row wrap"><button class="btn ghost sm" id="nfcBtn">${icon('nfc', 'sm')}Lire une carte NFC</button></div>
    <div id="scQueue"></div><div id="scIssues"></div><div id="scHistory"></div></div>`;
  const vf = $('#vf', root);

  /* ---------- Viseur ---------- */
  function idle() {
    vf.innerHTML = `<div class="idle">${icon('camera')}<div><strong style="font:650 1.15rem var(--font-display)">Prêt à scanner</strong><p class="small" style="opacity:.8;margin-top:2px">Cadrez le QR code ${ctx.conference ? 'du badge participant' : 'de l’invitation'}.</p></div><button class="btn primary" id="camBtn">Activer la caméra</button></div>`;
    $('#camBtn', vf).onclick = startCam;
  }
  let currentFacing = 'environment';
  async function startCam() {
    if (!navigator.mediaDevices?.getUserMedia) {
      toast('Caméra indisponible : ouvrez l’application en HTTPS (ou sur localhost).', 'bad', 5200);
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: currentFacing }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
    } catch (e) {
      toast(e.name === 'NotAllowedError' ? 'Autorisez l’accès à la caméra dans le navigateur.' : 'Impossible d’ouvrir la caméra.', 'bad', 4800);
      return;
    }
    const track = stream.getVideoTracks()[0];
    const canTorch = !!(track.getCapabilities && track.getCapabilities().torch);
    vf.innerHTML = `<video playsinline muted autoplay></video><div class="reticle"></div><div class="sweep"></div>
      <div class="tools">
        <button class="btn icon" id="flipCam" aria-label="Changer de caméra" title="Changer de caméra">${icon('refresh')}</button>
        ${canTorch ? `<button class="btn icon" id="torch" aria-label="Lampe" aria-pressed="false">${icon('bolt')}</button>` : ''}
        <button class="btn icon" id="stopCam" aria-label="Arrêter la caméra">${icon('x')}</button>
      </div>`;
    const video = $('video', vf); video.srcObject = stream;
    try { await video.play(); } catch { toast('La caméra est ouverte, mais son flux vidéo ne démarre pas. Réessayez.', 'bad', 4800); stopCam(); return; }
    $('#stopCam', vf).onclick = stopCam;
    $('#flipCam', vf).onclick = () => {
      currentFacing = currentFacing === 'environment' ? 'user' : 'environment';
      stopCam();
      startCam();
    };
    if (canTorch) {
      let on = false;
      $('#torch', vf).onclick = async e => {
        on = !on;
        try { await track.applyConstraints({ advanced: [{ torch: on }] }); e.currentTarget.setAttribute('aria-pressed', on); } catch { }
      };
    }
    if ('BarcodeDetector' in window) { try { detector = new BarcodeDetector({ formats: ['qr_code'] }); } catch { detector = null; } }
    if (!window.jsQR) { try { await loadScript('/static/js/vendor/jsqr.js'); } catch { if (!detector) { toast('Lecteur QR indisponible.', 'bad'); stopCam(); return; } } }
    tick(video);
  }
  function tick(video) {
    if (!stream) return;
    const next = () => { timer = setTimeout(() => tick(video), 110); };
    if (paused || video.readyState < 2) return next();
    (async () => {
      try {
        let val = null;
        if (detector) { try { const c = await detector.detect(video); val = c[0]?.rawValue; } catch { detector = null; } }
        if (!val && window.jsQR) {
          const w = Math.min(1280, video.videoWidth), h = Math.round(w * video.videoHeight / video.videoWidth);
          canvas = canvas || document.createElement('canvas'); canvas.width = w; canvas.height = h;
          const cx = canvas.getContext('2d', { willReadFrequently: true }); cx.drawImage(video, 0, 0, w, h);
          const img = cx.getImageData(0, 0, w, h); val = window.jsQR(img.data, w, h, { inversionAttempts: 'attemptBoth' })?.data;
        }
        if (val) { vf.classList.add('flash'); setTimeout(() => vf.classList.remove('flash'), 500); handle(val, 'qr'); }
      } catch (e) { console.debug('Échec ponctuel du décodage QR, nouvelle tentative au prochain frame.', e); }
      next();
    })();
  }
  function stopCam() {
    clearTimeout(timer); timer = null;
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null; idle();
  }
  const onVis = () => { if (document.hidden && stream) stopCam(); };
  document.addEventListener('visibilitychange', onVis);

  /* ---------- Traitement d'un code ---------- */
  async function handle(raw, method) {
    const v = scanToken(raw); if (!v || working) return;
    const now = Date.now(); if (v === lastCode && now - lastAt < 2500) return;
    lastCode = v; lastAt = now; working = true; paused = true;
    const parsed = parseBadgeQr(v);
    if (parsed?.invalid) return invalidQr();
    if (parsed?.eventId && parsed.eventId !== eid) return unrecognizedQr();
    try {
      if (ctx.conference) {
        if (parsed) await resolveConferenceBadge(parsed.reference, parsed);
        else await resolveConferenceManual(v, method);
      } else {
        await resolve(parsed ? (parsed.reference || parsed.token) : v, method);
      }
    } finally {
      working = false;
    }
  }
  const resume = () => { paused = false; working = false; };

  async function resolveConferenceBadge(reference, parsed) {
    if (!navigator.onLine) {
      feedback('warn');
      sheet(`<div class="verdict warn"><div class="ico">${icon('wifioff','lg')}</div><h2>Connexion requise</h2><p>Un badge conférence ne peut pas être validé hors ligne. Reconnectez-vous avant d’autoriser l’entrée.</p><button class="btn primary block" data-close>Compris</button></div>`, { onClose: resume });
      return;
    }
    try {
      const result = await api(`/checkin/api/conferences/${eid}/scan`, {
        method: 'POST',
        json: parsed.format.startsWith('legacy-')
          ? { badge_token: parsed.format === 'legacy-conference' ? `CONF:${parsed.eventId}:${parsed.token}` : `IA1.${parsed.eventId}.${parsed.token}`, idempotency_key: uuid(), method: 'qr' }
          : { badge_reference: reference, idempotency_key: uuid(), method: 'qr' }
      });
      showConferenceResult(result);
    } catch(e) {
      feedback('bad');
      remember('bad', 'Badge refusé', e.message);
      sheet(`<div class="verdict bad"><div class="ico">${icon('x','lg')}</div><h2>Badge refusé</h2><p>${esc(e.message)}</p><button class="btn primary block" data-close>Scanner un autre badge</button></div>`, { onClose: resume });
    }
  }

  function showConferenceResult(result) {
    const timeStr = result.checked_in_at ? new Date(result.checked_in_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const isOk = result.status === 'checked_in';
    const photoHtml = result.photo_data
      ? `<img src="${esc(result.photo_data)}" alt="Photo" style="width:72px;height:72px;border-radius:16px;object-fit:cover;border:2px solid var(--accent);box-shadow:0 4px 12px rgba(0,0,0,.15);margin:0 auto 10px">`
      : `<div class="avatar" style="width:72px;height:72px;font-size:1.8rem;border-radius:16px;margin:0 auto 10px;background:var(--accent-soft);color:var(--accent)">${esc((result.name || result.first_name || '?')[0].toUpperCase())}</div>`;

    if (isOk) {
      feedback('ok');
      remember('ok', result.name || 'Participant', `Entrée validée à ${timeStr}`);
      sheet(`
        <div class="verdict ok">
          <div class="ico">${icon('check','lg')}</div>
          <h2>Entrée validée</h2>
          <p class="small muted num" style="margin-top:2px">Heure de passage : ${esc(timeStr)}</p>
        </div>
        <div class="sheet-body" style="text-align:center">
          ${photoHtml}
          <h3 style="font-size:1.2rem;margin-bottom:4px">${esc(result.name || `${result.first_name || ''} ${result.last_name || ''}`.trim())}</h3>
          <div class="row wrap justify-center" style="margin-bottom:8px">
            <span class="badge brand">${esc((result.category || 'participant').toUpperCase())}</span>
            ${result.profession ? `<span class="badge">${esc(result.profession)}</span>` : ''}
            ${result.organization_name ? `<span class="badge cobalt">${esc(result.organization_name)}</span>` : ''}
          </div>
          <button class="btn primary block" data-close autofocus style="min-height:50px;margin-top:10px">Scanner le suivant</button>
        </div>
      `, { onClose: resume });
    } else {
      feedback('warn');
      remember('warn', result.name || 'Déjà enregistré', `Passage antérieur à ${timeStr}`);
      sheet(`
        <div class="verdict warn">
          <div class="ico">${icon('alert','lg')}</div>
          <h2>Déjà enregistré</h2>
          <p class="small" style="margin-top:2px">Ce participant a déjà été validé à ${esc(timeStr)}.</p>
        </div>
        <div class="sheet-body" style="text-align:center">
          ${photoHtml}
          <h3 style="font-size:1.15rem;margin-bottom:4px">${esc(result.name || 'Participant')}</h3>
          <div class="row wrap justify-center" style="margin-bottom:8px">
            <span class="badge brand">${esc((result.category || 'participant').toUpperCase())}</span>
          </div>
          <p class="small muted">Un badge ne peut pas être validé deux fois.</p>
          <button class="btn primary block" data-close autofocus style="min-height:50px;margin-top:10px">Compris / Scanner le suivant</button>
        </div>
      `, { onClose: resume });
    }
  }

  async function resolveConferenceManual(v, method) {
    if (!navigator.onLine) {
      feedback('warn');
      toast('Connexion requise pour la recherche de badge.', 'bad');
      return resume();
    }
    let rows;
    try {
      rows = await api(`/checkin/api/events/${eid}/lookup?q=${encodeURIComponent(v)}`);
    } catch(e) {
      feedback('bad');
      toast(e.message, 'bad');
      return resume();
    }
    if (!rows.length) return notFound(v);
    if (rows.length === 1) return conferenceParticipantVerdict(rows[0]);
    conferencePicker(rows);
  }

  function conferencePicker(rows) {
    const d = sheet(`${sheetHead('Participants trouvés', 'Sélectionnez le participant à contrôler.')}
      <div class="sheet-body">
        <div class="list">
          ${rows.map((r, i) => `
            <button class="item" data-i="${i}">
              ${r.photo_data ? `<img src="${esc(r.photo_data)}" alt="" style="width:40px;height:40px;border-radius:10px;object-fit:cover">` : `<div class="avatar ${r.entered ? 'done' : ''}">${esc((r.guest_name || '?')[0].toUpperCase())}</div>`}
              <div class="grow" style="text-align:left">
                <div class="title ellipsis"><strong>${esc(r.guest_name)}</strong></div>
                <div class="meta"><span>${esc(r.category || 'participant')}</span><span>${esc(r.email || r.phone || '')}</span></div>
              </div>
              <div class="qty num">${r.entered ? '<span class="badge ok">Entré</span>' : '<span class="badge ghost">Attendu</span>'}</div>
            </button>
          `).join('')}
        </div>
      </div>
    `, { onClose: () => { if (!d._picked) resume(); } });

    d.addEventListener('click', e => {
      const b = e.target.closest('[data-i]');
      if (b) {
        d._picked = true;
        d.close();
        conferenceParticipantVerdict(rows[+b.dataset.i]);
      }
    });
  }

  function conferenceParticipantVerdict(r) {
    const photoHtml = r.photo_data
      ? `<img src="${esc(r.photo_data)}" alt="Photo" style="width:80px;height:80px;border-radius:18px;object-fit:cover;border:2px solid var(--accent);margin:0 auto 10px;box-shadow:0 4px 14px rgba(0,0,0,.12)">`
      : `<div class="avatar" style="width:80px;height:80px;font-size:2rem;border-radius:18px;margin:0 auto 10px;background:var(--accent-soft);color:var(--accent)">${esc((r.guest_name || '?')[0].toUpperCase())}</div>`;

    if (r.status !== 'accepted') {
      const reasons = { pending: 'Inscription en attente de vérification.', waitlist: 'Personne en liste d’attente, entrée non autorisée.', rejected: 'Inscription refusée.', cancelled: 'Inscription annulée.' };
      feedback('bad'); remember('bad', r.guest_name, 'Inscription non autorisée');
      sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>Entrée non autorisée</h2><p>${esc(r.guest_name)}</p></div>
        <div class="sheet-body" style="text-align:center">${photoHtml}<p class="small muted">${esc(reasons[r.status] || 'Cette inscription ne permet pas l’accès à l’événement.')}</p><button class="btn primary block" data-close>Scanner un autre badge</button></div>`, { onClose: resume });
      return;
    }

    if (r.entered > 0) {
      feedback('warn');
      const timeStr = r.checked_in_at ? new Date(r.checked_in_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : 'plus tôt';
      sheet(`
        <div class="verdict warn">
          <div class="ico">${icon('alert','lg')}</div>
          <h2>Déjà entré</h2>
          <p>Passage validé à ${esc(timeStr)}.</p>
        </div>
        <div class="sheet-body" style="text-align:center">
          ${photoHtml}
          <h3>${esc(r.guest_name)}</h3>
          <p class="small muted">${esc(r.profession || '')} ${r.organization_name ? '· ' + esc(r.organization_name) : ''}</p>
          <div class="row wrap justify-center" style="margin:10px 0">
            <span class="badge brand">${esc((r.category || 'participant').toUpperCase())}</span>
            <span class="badge ok">Entrée déjà validée</span>
          </div>
          <button class="btn primary block" data-close>Fermer</button>
        </div>
      `, { onClose: resume });
      return;
    }

    const d = sheet(`
      <div class="verdict ok">
        <div class="ico">${icon('check','lg')}</div>
        <h2>Participant vérifié</h2>
        <p>Identité retrouvée dans la base officielle.</p>
      </div>
      <div class="sheet-body" style="text-align:center">
        ${photoHtml}
        <h3 style="font-size:1.2rem;margin-bottom:2px">${esc(r.guest_name)}</h3>
        <p class="small muted">${esc(r.profession || '')} ${r.organization_name ? '· ' + esc(r.organization_name) : ''}</p>
        <div class="row wrap justify-center" style="margin:8px 0 14px">
          <span class="badge brand">${esc((r.category || 'participant').toUpperCase())}</span>
          ${r.email ? `<span class="badge">${esc(r.email)}</span>` : ''}
          ${r.phone ? `<span class="badge">${esc(r.phone)}</span>` : ''}
        </div>
        <div id="vConfErr"></div>
        <button class="btn primary block" id="valConfEntry" style="min-height:54px;font-size:1.05rem">Valider l’entrée</button>
        <button class="btn ghost block" data-close>Annuler</button>
      </div>
    `, { onClose: resume });

    const btn = $('#valConfEntry', d);
    btn.onclick = async () => {
      busy(btn, true);
      try {
        const res = await api(`/checkin/api/conferences/${eid}/scan`, {
          method: 'POST',
          json: { registration_id: r.id, idempotency_key: uuid(), method: 'manual' }
        });
        d.close();
        showConferenceResult(res);
      } catch(err) {
        busy(btn, false);
        $('#vConfErr', d).innerHTML = `<div class="banner bad" role="alert">${esc(err.message)}</div>`;
      }
    };
  }

  async function resolve(v, method) {
    const kind = classify(v, method);
    if (!navigator.onLine) { if (ctx.conference) { feedback('warn'); toast('Le contrôle des badges conférence exige une connexion réseau.', 'bad'); return resume(); } return offlineFlow(v, kind, method); }
    let rows;
    try { rows = await api(`/checkin/api/events/${eid}/lookup?q=${encodeURIComponent(kind === 'token' ? 'token:' + v : v)}`); }
    catch (e) { if (e.network) return offlineFlow(v, kind, method); feedback('bad'); toast(e.message, 'bad'); return resume(); }
    if (!rows.length) return notFound(v);
    const exact = rows.find(r => r.reference.toLowerCase() === v.toLowerCase());
    if (rows.length === 1 || exact || kind === 'token') return verdict(exact || rows[0], { method, token: kind === 'token' ? v : '' });
    picker(rows, method);
  }

  function picker(rows, method) {
    const d = sheet(`${sheetHead('Plusieurs invités trouvés', 'Choisissez la bonne invitation.')}<div class="sheet-body"><div class="list">${rows.map((r, i) => `<button class="item" data-i="${i}"><div class="avatar ${r.remaining === 0 ? 'done' : ''}">${esc((r.guest_name || '?')[0].toUpperCase())}</div><div class="grow"><div class="title ellipsis">${esc(r.guest_name)}</div><div class="meta"><span>${esc(r.reference)}</span><span>${esc(r.invitation_type)}</span></div></div><div class="qty num">${r.entered}/${r.quota}<small>entrés</small></div></button>`).join('')}</div></div>`, { onClose: () => { if (!d._picked) resume(); } });
    d.addEventListener('click', e => { const b = e.target.closest('[data-i]'); if (b) { d._picked = true; verdict(rows[+b.dataset.i], { method }); } });
  }

  function unrecognizedQr() {
    feedback('bad'); remember('bad', 'QR non reconnu', 'Vérification impossible.');
    sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>QR non reconnu</h2><p>Impossible de vérifier ce code pour l’événement sélectionné.</p></div>
      <div class="sheet-body"><button class="btn primary block" data-close>Scanner un autre code</button></div>`, { onClose: resume });
  }

  function invalidQr() {
    feedback('bad'); remember('bad', 'QR invalide', 'Format de badge non reconnu.');
    sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>QR invalide</h2><p>Ce code ne contient pas une référence de badge reconnue.</p></div><div class="sheet-body"><button class="btn primary block" data-close>Scanner un autre code</button></div>`, { onClose: resume });
  }

  function notFound(v) {
    feedback('bad'); remember('bad', 'Invitation introuvable', v.length > 18 ? v.slice(0, 8) + '…' : v);
    const d = sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>Invitation introuvable</h2><p>Ce code ne correspond à aucune invitation active de cet événement.</p></div>
      <div class="sheet-body"><button class="btn primary block" data-close>Scanner un autre code</button></div>`, { onClose: resume });
  }

  async function register(inv, qty, method) {
    return api(`/checkin/api/events/${eid}/entry`, { method: 'POST', json: { invitation_id: inv.id, quantity: qty, method, idempotency_key: uuid() } });
  }

  function verdict(inv, { method = 'qr', token = '' } = {}) {
    if (inv.status !== 'active') {
      feedback('bad'); remember('bad', inv.guest_name, 'Invitation révoquée');
      sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>Invitation révoquée</h2><p>${esc(inv.guest_name)} · ${esc(inv.reference)}</p></div>
        <div class="sheet-body"><p class="small muted">Ce QR code n’autorise plus l’entrée. Demandez confirmation à un superviseur.</p><button class="btn primary block" data-close>Scanner un autre code</button></div>`, { onClose: resume });
      return;
    }
    const api_method = method === 'nfc' ? 'nfc' : method === 'manual' ? 'manual' : 'qr';
    const badges = `<div class="row wrap"><span class="badge brand">${esc(inv.reference)}</span><span class="badge">${esc(inv.invitation_type)}</span>${inv.table_name ? `<span class="badge cobalt">${icon('table', 'sm')}Table ${esc(inv.table_name)}</span>` : ''}</div>`;
    if (inv.remaining <= 0) {
      feedback('bad'); remember('bad', inv.guest_name, 'Quota atteint');
      const d = sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>Quota atteint</h2><p>${esc(inv.guest_name)}</p></div>
        <div class="sheet-body">${badges}${meter(inv.entered, inv.quota)}<p class="small muted">Les ${inv.quota} personne${inv.quota > 1 ? 's' : ''} de cette invitation sont déjà entrées. Ne laissez pas passer sans accord d’un superviseur.</p>
        ${ctx.role === 'supervisor' ? `<button class="btn tonal block" id="exBtn">${icon('flag', 'sm')}Signaler une exception</button>` : ''}
        <button class="btn primary block" data-close>Compris</button></div>`, { onClose: resume });
      const ex = $('#exBtn', d); if (ex) ex.onclick = () => { d.close(); ctx.exception(inv); };
      return;
    }
    // Entrée automatique pour une invitation individuelle (option du profil)
    if (prefs.get().autoSingle && inv.quota === 1 && method !== 'manual') return quick(inv, api_method);
    let qty = 1;
    const d = sheet(`<div class="verdict ok"><div class="ico">${icon('check', 'lg')}</div><h2>Invitation valide</h2><p>${esc(inv.guest_name)}</p></div>
      <div class="sheet-body">${badges}
        <div class="col tight">${meter(inv.entered, inv.quota)}<p class="small muted num">${inv.entered} sur ${inv.quota} déjà entré${inv.entered > 1 ? 's' : ''}, ${inv.remaining} restant${inv.remaining > 1 ? 's' : ''}</p></div>
        ${inv.remaining > 1 ? `<div><p class="small muted" style="text-align:center;margin-bottom:6px">Combien de personnes entrent ?</p><div class="stepper"><button id="m" aria-label="Moins">−</button><output id="q" class="num">1</output><button id="p" aria-label="Plus">+</button></div></div>` : ''}
        <div id="vErr"></div>
        <button class="btn primary block" id="go" style="min-height:56px;font-size:1.05rem">Enregistrer 1 entrée</button>
        <button class="btn ghost block" data-close>Annuler</button></div>`, { onClose: resume });
    const upd = () => { $('#q', d) && ($('#q', d).textContent = qty); $('#go', d).textContent = `Enregistrer ${qty} entrée${qty > 1 ? 's' : ''}`; };
    $('#m', d) && ($('#m', d).onclick = () => { qty = Math.max(1, qty - 1); upd(); });
    $('#p', d) && ($('#p', d).onclick = () => { qty = Math.min(inv.remaining, qty + 1); upd(); });
    $('#go', d).onclick = async e => {
      const b = e.currentTarget; busy(b, true); $('#vErr', d).innerHTML = '';
      try {
        const res = await register(inv, qty, api_method);
        feedback('ok'); remember('ok', inv.guest_name, `${qty} entrée${qty > 1 ? 's' : ''}`);
        toast(`${res.reference} : ${plural(qty, 'entrée')} enregistrée${qty > 1 ? 's' : ''}. Restant : ${res.remaining}`, 'ok');
        ctx.onEntry(inv.id, res); d.close();
      } catch (err) {
        busy(b, false);
        if (err.network && token) { d.close(); return offlineFlow(token, 'token', method); }
        feedback('bad'); $('#vErr', d).innerHTML = `<div class="banner bad" role="alert">${icon('alert', 'sm')}<span>${esc(err.message)}</span></div>`;
        if (err.status === 409) ctx.onEntry(inv.id, null);
      }
    };
  }

  async function quick(inv, m) {
    try {
      const res = await register(inv, 1, m);
      feedback('ok'); remember('ok', inv.guest_name, '1 entrée'); ctx.onEntry(inv.id, res);
      const d = sheet(`<div class="verdict ok"><div class="ico">${icon('check', 'lg')}</div><h2>Entrée enregistrée</h2><p>${esc(inv.guest_name)}${inv.table_name ? ' — table ' + esc(inv.table_name) : ''}</p></div>`, { onClose: resume });
      setTimeout(() => d.open && d.close(), 1500);
    } catch (e) { feedback('bad'); toast(e.message, 'bad'); resume(); }
  }

  /* ---------- Hors ligne ---------- */
  async function offlineFlow(v, kind, method) {
    if (kind !== 'token') {
      const c = ctx.cached(); const hit = c.find(i => i.reference.toLowerCase() === v.toLowerCase()) || c.find(i => i.guest_name.toLowerCase().includes(v.toLowerCase()));
      feedback('warn');
      sheet(`<div class="verdict warn"><div class="ico">${icon('wifioff', 'lg')}</div><h2>Vérification impossible hors ligne</h2><p>${hit ? esc(hit.guest_name) : 'Sans réseau, seul un QR code ou une carte NFC peut être mis en attente.'}</p></div>
        <div class="sheet-body">${hit ? `<div class="row wrap"><span class="badge brand">${esc(hit.reference)}</span><span class="badge">Dernier état connu : ${hit.entered}/${hit.quota} entrés</span></div>` : ''}
        <p class="small muted">Le QR code contient le jeton de l’invitation. Scannez-le pour l’enregistrer en attente ; il sera contrôlé dès que le réseau revient.</p><button class="btn primary block" data-close>Compris</button></div>`, { onClose: resume });
      return;
    }
    const dup = (await queue.all()).find(e => e.token === v && e.event_id === eid);
    if (dup) {
      feedback('bad'); remember('bad', 'Déjà en attente', 'Scanné sur cet appareil');
      sheet(`<div class="verdict bad"><div class="ico">${icon('x', 'lg')}</div><h2>Déjà scanné</h2><p>Ce code est déjà en attente sur cet appareil.</p></div><div class="sheet-body"><button class="btn primary block" data-close>Compris</button></div>`, { onClose: resume });
      return;
    }
    feedback('warn'); let qty = 1;
    const d = sheet(`<div class="verdict warn"><div class="ico">${icon('wifioff', 'lg')}</div><h2>Hors ligne</h2><p>Le contrôle sera mis en attente, puis vérifié à la synchronisation.</p></div>
      <div class="sheet-body"><div><p class="small muted" style="text-align:center;margin-bottom:6px">Nombre de personnes</p><div class="stepper"><button id="m" aria-label="Moins">−</button><output id="q" class="num">1</output><button id="p" aria-label="Plus">+</button></div></div>
      <button class="btn primary block" id="go" style="min-height:56px">Mettre en attente</button><button class="btn ghost block" data-close>Annuler</button></div>`, { onClose: resume });
    $('#m', d).onclick = () => { qty = Math.max(1, qty - 1); $('#q', d).textContent = qty; };
    $('#p', d).onclick = () => { qty = Math.min(50, qty + 1); $('#q', d).textContent = qty; };
    $('#go', d).onclick = async () => {
      await enqueue({ client_id: uuid(), event_id: eid, token: v, quantity: qty, method: method === 'nfc' ? 'nfc' : method === 'manual' ? 'manual' : 'qr', occurred_at: new Date().toISOString(), user_id: window.BOOT?.user?.id });
      remember('warn', 'En attente', plural(qty, 'personne')); toast('Contrôle mis en attente.', ''); d.close();
    };
  }

  /* ---------- NFC ---------- */
  async function startNfc() {
    if (!('NDEFReader' in window)) { toast('NFC indisponible ici. Essayez Chrome sur Android, ou scannez le QR.', 'bad', 4500); return; }
    if (nfcAbort) { nfcAbort.abort(); nfcAbort = null; $('#nfcBtn', root).lastChild.textContent = 'Lire une carte NFC'; return; }
    try {
      nfcAbort = new AbortController(); const r = new NDEFReader(); await r.scan({ signal: nfcAbort.signal });
      $('#nfcBtn', root).lastChild.textContent = 'NFC actif, approchez la carte'; toast('Approchez la carte NFC du téléphone.');
      r.onreading = ev => {
        for (const rec of ev.message.records) {
          if (rec.recordType === 'text' || rec.recordType === 'url') { handle(new TextDecoder(rec.encoding || 'utf-8').decode(rec.data), 'nfc'); return; }
        }
        toast('Aucun jeton lisible sur cette carte.', 'bad');
      };
    } catch (e) { nfcAbort = null; toast('Lecture NFC impossible : ' + e.message, 'bad', 4500); }
  }

  /* ---------- Saisie manuelle ---------- */
  $('#manual', root).onsubmit = e => { e.preventDefault(); const i = $('#mIn', root); const v = i.value.trim(); if (v) { handle(v, 'manual'); i.value = ''; i.blur(); } };
  $('#nfcBtn', root).onclick = startNfc;

  /* ---------- Historique de session, file, anomalies ---------- */
  function remember(kind, title, sub) { history.unshift({ kind, title, sub, at: new Date() }); history.length = Math.min(history.length, 8); renderHistory(); }
  function renderHistory() {
    $('#scHistory', root).innerHTML = history.length ? `<div><div class="section-title" style="margin-top:6px"><h2>Derniers contrôles</h2></div><div class="card" style="padding:4px 14px"><div class="feed">${history.map(h => `<div class="f"><div class="dot" style="${h.kind === 'bad' ? 'background:var(--bad-soft);color:var(--bad)' : h.kind === 'warn' ? 'background:var(--warn-soft);color:var(--warn)' : ''}">${icon(h.kind === 'ok' ? 'check' : h.kind === 'warn' ? 'clock' : 'x', 'sm')}</div><div class="grow"><div class="title ellipsis" style="font-weight:650">${esc(h.title)}</div><div class="small muted">${esc(h.sub)}</div></div><span class="tiny faint">${rel(h.at)}</span></div>`).join('')}</div></div></div>` : '';
  }
  async function renderQueue() {
    const n = await queue.count(); const off = !navigator.onLine;
    $('#scNet', root).innerHTML = off ? `<div class="banner warn" role="status">${icon('wifioff', 'sm')}<span>Hors ligne. Les QR codes scannés sont mis en attente puis vérifiés au retour du réseau.</span></div>` : '';
    $('#scQueue', root).innerHTML = n ? `<div class="banner info"><span class="grow">${icon('clock', 'sm')} ${plural(n, 'contrôle')} en attente de synchronisation</span><button class="btn sm primary" id="syncBtn" ${off ? 'disabled' : ''}>Synchroniser</button></div>` : '';
    const sb = $('#syncBtn', root); if (sb) sb.onclick = () => doSync(true);
    const list = issues.all().filter(i => i.event_id === eid);
    $('#scIssues', root).innerHTML = list.length ? `<div class="card flat col"><div class="row between"><h3>À vérifier avec un superviseur</h3><button class="btn sm ghost" id="clrIssues">Tout effacer</button></div>${list.map(i => `<div class="banner ${i.status === 'conflict' ? 'warn' : 'bad'}" style="align-items:flex-start">${icon('alert', 'sm')}<div class="grow"><strong>${esc(i.reference || 'Code inconnu')}</strong> ${i.quantity ? '(' + plural(i.quantity, 'personne') + ')' : ''}<div class="small">${esc(i.reason)}</div></div><button class="btn icon sm ghost" data-issue="${esc(i.client_id)}" aria-label="Ignorer" style="width:34px;min-height:34px">${icon('x', 'sm')}</button></div>`).join('')}</div>` : '';
    root.querySelectorAll('[data-issue]').forEach(b => b.onclick = () => { issues.remove(b.dataset.issue); renderQueue(); });
    const c = $('#clrIssues', root); if (c) c.onclick = () => { list.forEach(i => issues.remove(i.client_id)); renderQueue(); };
  }
  async function doSync(manual) {
    if (!navigator.onLine) return;
    try {
      const r = await syncQueue(); if (!r || !r.total) { if (manual) toast('Rien à synchroniser.'); return; }
      toast(`${r.synced} synchronisé${r.synced > 1 ? 's' : ''}${r.issues.length ? `, ${r.issues.length} à vérifier` : ''}.`, r.issues.length ? '' : 'ok');
      if (r.issues.length) feedback('warn'); ctx.onEntry(null, null);
    } catch (e) { if (manual || !e.network) toast('Synchronisation impossible : ' + e.message, 'bad'); }
    renderQueue();
  }
  const onNet = () => { renderQueue(); if (navigator.onLine) doSync(false); };
  addEventListener('online', onNet); addEventListener('offline', onNet);
  document.addEventListener('ia:queue', renderQueue);

  idle(); renderQueue(); if (navigator.onLine) doSync(false);

  return {
    destroy() {
      stopCam(); if (nfcAbort) nfcAbort.abort();
      removeEventListener('online', onNet); removeEventListener('offline', onNet);
      document.removeEventListener('ia:queue', renderQueue); document.removeEventListener('visibilitychange', onVis);
    },
    handle,
  };
}
