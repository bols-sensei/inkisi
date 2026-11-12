/* File d'attente hors ligne : IndexedDB (même base que la version précédente), anomalies locales, cache d'événement. */
import { api } from './core.js';

const DB = 'invitation-offline-v1';
const open = () => new Promise((res, rej) => {
  const r = indexedDB.open(DB, 1);
  r.onupgradeneeded = () => r.result.createObjectStore('entries', { keyPath: 'client_id' });
  r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
});
const tx = async (mode, fn) => { const db = await open(); return new Promise((res, rej) => { const r = fn(db.transaction('entries', mode).objectStore('entries')); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); };

export const queue = {
  all: () => tx('readonly', s => s.getAll()).catch(() => []),
  put: item => tx('readwrite', s => s.put(item)),
  del: id => tx('readwrite', s => s.delete(id)),
  async count() { return (await this.all()).length; },
};
const notify = async () => document.dispatchEvent(new CustomEvent('ia:queue', { detail: { count: await queue.count() } }));
export async function enqueue(item) { await queue.put(item); await notify(); if ('serviceWorker' in navigator) navigator.serviceWorker.ready.then(r => r.sync?.register('ia-checkin-sync')).catch(() => {}); }

/* Anomalies (conflits / rejets) conservées localement pour que l'agent les voie */
const IK = 'ia-issues';
export const issues = {
  all() { try { return JSON.parse(localStorage.getItem(IK) || '[]'); } catch { return []; } },
  add(list) { try { localStorage.setItem(IK, JSON.stringify([...list, ...this.all()].slice(0, 100))); } catch { } },
  remove(id) { try { localStorage.setItem(IK, JSON.stringify(this.all().filter(i => i.client_id !== id))); } catch { } },
  clear() { try { localStorage.removeItem(IK); } catch { } },
};

let syncing = false;
const syncChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('ia-offline-sync') : null;
export async function syncQueue() {
  if (navigator.locks?.request) return navigator.locks.request('ia-checkin-sync', () => runSync());
  return runSync();
}
async function runSync() {
  if (syncing) return null;
  const entries = await queue.all();
  if (!entries.length) return { synced: 0, issues: [], total: 0 };
  syncing = true;
  try {
    const clean = entries.map(({ client_id, event_id, token, quantity, method, occurred_at, user_id }) => ({ client_id, event_id, token, quantity, method, occurred_at, user_id }));
    const out = { synced: 0, issues: [], total: entries.length };
    for (let i = 0; i < clean.length; i += 200) {            // lots de 200 (max serveur : 500)
      const data = await api('/checkin/api/sync', { method: 'POST', json: { entries: clean.slice(i, i + 200) } });
      for (const r of data.results || []) {
        if (r.status === 'synced' || r.status === 'already_synced') { out.synced++; await queue.del(r.client_id); }
        else if (r.status === 'deferred') { out.deferred = (out.deferred || 0) + 1; } // reste en file : appartient à un autre compte
        else { // conflit ou rejet : on retire de la file et on garde une trace lisible
          const src = entries.find(e => e.client_id === r.client_id);
          out.issues.push({ client_id: r.client_id, status: r.status, reference: r.reference || '', reason: r.reason || '', event_id: src?.event_id, at: src?.occurred_at, quantity: src?.quantity });
          await queue.del(r.client_id);
        }
      }
    }
    if (out.issues.length) issues.add(out.issues);
    syncChannel?.postMessage({ type: 'sync-complete', synced: out.synced, issues: out.issues.length });
    return out;
  } finally { syncing = false; await notify(); }
}

/* Cache de l'événement pour recherche hors ligne */
export const cache = {
  get(id) { try { return JSON.parse(localStorage.getItem('ia-event-' + id) || 'null'); } catch { return null; } },
  set(id, data) { try { localStorage.setItem('ia-event-' + id, JSON.stringify({ at: Date.now(), data })); } catch { } },
};
