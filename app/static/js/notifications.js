/* Notifications internes : cloche avec compteur, panneau, « tout lire », activation des push. */
import { api, esc, icon, toast, rel } from './core.js';

const key = v => { const raw = atob((v + '='.repeat((4 - v.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/')); return Uint8Array.from(raw, c => c.charCodeAt(0)); };
let rows = [];

async function enablePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return toast('Les notifications push ne sont pas prises en charge ici.', 'bad');
  try {
    const { public_key } = await api('/api/push/public-key');
    if (!public_key) throw new Error('Notifications push non configurées.');
    if (await Notification.requestPermission() !== 'granted') return toast('Autorisation de notification refusée.', 'bad');
    const reg = await navigator.serviceWorker.ready, applicationServerKey = key(public_key);
    let sub = await reg.pushManager.getSubscription();
    const currentKey = sub?.options?.applicationServerKey;
    const currentBytes = currentKey && new Uint8Array(currentKey);
    const sameKey = currentBytes && currentBytes.length === applicationServerKey.length && currentBytes.every((byte, i) => byte === applicationServerKey[i]);
    if (sub && !sameKey) {
      try { await api('/api/push/subscribe', { method: 'DELETE', json: { endpoint: sub.endpoint } }); }
      finally { await sub.unsubscribe(); }
      sub = null;
    }
    const created = !sub;
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
    try { await api('/api/push/subscribe', { method: 'POST', json: sub.toJSON() }); }
    catch (e) { if (created) await sub.unsubscribe(); throw e; }
    toast('Notifications push activées sur cet appareil.', 'ok');
  } catch (e) { toast(e.message || 'Configuration push indisponible.', 'bad'); }
}
async function disablePush({ silent = false } = {}) {
  try {
    const reg = await navigator.serviceWorker.getRegistration('/');
    const sub = await reg?.pushManager?.getSubscription();
    if (!sub) return;
    try { await api('/api/push/subscribe', { method: 'DELETE', json: { endpoint: sub.endpoint } }); }
    finally { await sub.unsubscribe(); }
    if (!silent) toast('Notifications push désactivées sur cet appareil.', 'ok');
  } catch (e) { if (!silent) toast(e.message || 'Désactivation push impossible.', 'bad'); }
}
async function load() { try { rows = await api('/api/notifications'); } catch { rows = []; } badge(); return rows; }
function badge() { const n = rows.filter(r => !r.read).length, b = document.getElementById('ia-bell-n'); if (b) { b.textContent = n > 9 ? '9+' : n; b.hidden = !n; } }
async function panel() {
  const old = document.getElementById('ia-notification-panel'); if (old) { old.remove(); return; }
  await load(); const p = document.createElement('section'); p.id = 'ia-notification-panel'; p.className = 'ia-notifications'; p.setAttribute('aria-label', 'Notifications');
  const unread = rows.filter(r => !r.read).length;
  const reg = await navigator.serviceWorker?.getRegistration('/').catch(() => null);
  const subscribed = !!(await reg?.pushManager?.getSubscription().catch(() => null));
  p.innerHTML = `<div class="ia-notifications-head"><strong>Notifications</strong><div class="row">${unread ? '<button type="button" data-read-all>Tout lire</button>' : ''}<button type="button" data-push-${subscribed ? 'disable' : 'enable'}>${subscribed ? 'Désactiver les push' : 'Activer les push'}</button><button type="button" data-np-close aria-label="Fermer">${icon('x', 'sm')}</button></div></div>`
    + (rows.length ? rows.map(n => `<article class="ia-notification ${n.read ? '' : 'unread'}"><div class="grow"><strong>${esc(n.title)}</strong><p>${esc(n.body)}</p><small>${rel(n.created_at)}</small></div><div class="col tight">${n.event_id ? `<a class="btn sm ghost" href="/event/${n.event_id}" data-link data-read="${n.id}">Ouvrir</a>` : ''}${n.read ? '' : `<button type="button" data-read="${n.id}">Lu</button>`}</div></article>`).join('') : '<p class="muted" style="padding:18px 4px;text-align:center">Aucune notification pour l’instant.</p>');
  document.body.append(p);
}
export function initNotifications() {
  const install = () => {
    const actions = document.getElementById('barActions');
    if (actions && !document.getElementById('ia-notification-button')) {
      const b = document.createElement('button'); b.type = 'button'; b.id = 'ia-notification-button'; b.className = 'btn icon ghost'; b.setAttribute('aria-label', 'Notifications');
      b.innerHTML = `${icon('bell', 'sm')}<span id="ia-bell-n" class="bell-n" hidden></span>`; b.addEventListener('click', panel); actions.prepend(b); badge();
    }
  };
  new MutationObserver(install).observe(document.getElementById('app') || document.body, { childList: true, subtree: true }); install();
  load(); setInterval(() => { if (!document.hidden && navigator.onLine) load(); }, 60000);
  document.addEventListener('click', async e => {
    if (e.target.closest('[data-np-close]')) return document.getElementById('ia-notification-panel')?.remove();
    if (e.target.closest('[data-push-enable]')) { await enablePush(); document.getElementById('ia-notification-panel')?.remove(); return panel(); }
    if (e.target.closest('[data-push-disable]')) { await disablePush(); document.getElementById('ia-notification-panel')?.remove(); return panel(); }
    try {
      if (e.target.closest('[data-read-all]')) { await Promise.all(rows.filter(r => !r.read).map(r => api(`/api/notifications/${r.id}/read`, { method: 'POST' }))); document.getElementById('ia-notification-panel')?.remove(); await load(); return panel(); }
      const r = e.target.closest('[data-read]'); if (r) { await api(`/api/notifications/${r.dataset.read}/read`, { method: 'POST' }); if (r.tagName === 'A') document.getElementById('ia-notification-panel')?.remove(); else { document.getElementById('ia-notification-panel')?.remove(); await load(); panel(); } }
    } catch (err) { toast(err.message, 'bad'); }
  });
  document.addEventListener('submit', async e => {
    if (e.target.id !== 'lo' || e.defaultPrevented) return;
    e.preventDefault();
    await disablePush({ silent: true });
    HTMLFormElement.prototype.submit.call(e.target);
  });
}
