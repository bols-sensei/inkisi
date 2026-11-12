/* Service worker : coque applicative disponible hors ligne. Les API ne sont jamais mises en cache. */
const STATIC = 'ia-static-v32', PAGES = 'ia-pages-v1';
const SHELL = ['/static/css/app.css', '/static/js/main.js', '/static/js/boot.js', '/static/js/theme-init.js', '/static/js/member_badge.js', '/static/js/conference_public.js', '/static/js/core.js', '/static/js/home.js', '/static/js/event.js', '/static/js/scanner.js', '/static/js/offline.js', '/static/js/auth.js', '/static/js/notifications.js', '/static/js/extras.js', '/static/js/superadmin.js', '/static/js/sw-register.js', '/static/js/vendor/jsqr.js',
  '/static/fonts/display.woff2', '/static/fonts/body.woff2', '/static/icons/icon.svg', '/static/icons/icon-180.png', '/static/icons/icon-192.png', '/static/icons/icon-512.png', '/static/icons/icon-maskable-512.png', '/static/manifest.webmanifest'];

self.addEventListener('install', e => { e.waitUntil(caches.open(STATIC).then(c => Promise.allSettled(SHELL.map(async u => { const r = await fetch(new Request(u, { cache: 'reload' })); if (!r.ok) throw new Error(`Shell asset ${u}: ${r.status}`); await c.put(u, r); }))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(n => ![STATIC, PAGES].includes(n)).map(n => caches.delete(n)))).then(() => self.clients.claim())); });
self.addEventListener('message', e => { if (e.data === 'clear-pages') e.waitUntil(caches.delete(PAGES)); });

self.addEventListener('fetch', e => {
  const req = e.request, u = new URL(req.url);
  if (req.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/static/')) {                       // stale-while-revalidate
    e.respondWith(caches.open(STATIC).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  if (req.mode === 'navigate') {                                  // rÃ©seau d'abord, copie de secours hors ligne
    e.respondWith(fetch(req).then(r => {
      if (r.ok && !r.redirected && (u.pathname === '/' || u.pathname.startsWith('/event/'))) { const copy = r.clone(); caches.open(PAGES).then(c => c.put(req, copy)); }
      return r;
    }).catch(async () => (await caches.match(req)) || (await caches.match('/')) || Response.error()));
  }
});


self.addEventListener('push', event => {
  let data = {}; try { data = event.data ? event.data.json() : {}; } catch { data = { body: event.data?.text() || '' }; }
  event.waitUntil(self.registration.showNotification(data.title || 'Notification', { body: data.body || '', icon: '/static/icons/icon-192.png', badge: '/static/icons/icon-192.png', data: { url: data.url || '/' } }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  let destination = '/';
  try { const candidate = new URL(event.notification.data?.url || '/', self.location.origin); if (candidate.origin === self.location.origin) destination = candidate.pathname + candidate.search + candidate.hash; } catch { }
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    const existing = list.find(c => new URL(c.url).origin === self.location.origin);
    if (existing) return existing.navigate(destination).then(c => (c || existing).focus());
    return clients.openWindow(destination);
  }));
});


// Background Sync: only successful/idempotent records are removed. Conflicts stay
// in IndexedDB for the foreground UI to explain to the operator.
function openOfflineDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('invitation-offline-v1', 1);
    req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
  });
}
function readQueued(db) {
  return new Promise((resolve, reject) => { const req = db.transaction('entries','readonly').objectStore('entries').getAll(); req.onsuccess=()=>resolve(req.result||[]); req.onerror=()=>reject(req.error); });
}
function removeQueued(db,id) {
  return new Promise((resolve,reject) => { const req=db.transaction('entries','readwrite').objectStore('entries').delete(id); req.onsuccess=()=>resolve(); req.onerror=()=>reject(req.error); });
}
self.addEventListener('sync', event => {
  if (event.tag === 'ia-checkin-sync') event.waitUntil((async () => {
    const db=await openOfflineDb();
    try {
      const rows=await readQueued(db);
      for(let i=0;i<rows.length;i+=200) {
        const batch=rows.slice(i,i+200).map(({client_id,event_id,token,quantity,method,occurred_at,user_id})=>({client_id,event_id,token,quantity,method,occurred_at,user_id}));
        const response=await fetch('/checkin/api/sync',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({entries:batch})});
        if(!response.ok) throw new Error('Background sync failed');
        const result=await response.json();
        for(const item of result.results||[]) if(item.status==='synced'||item.status==='already_synced') await removeQueued(db,item.client_id);
      }
    } finally { db.close(); }
  })());
});
