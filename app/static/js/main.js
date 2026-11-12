/* Point d'entrée : routage léger (History API) entre l'accueil et la page d'un événement. */
import { $ } from './core.js';
import { Home } from './home.js';
import { EventView } from './event.js';
import { initNotifications } from './notifications.js';

const user = window.BOOT.user;
let view = null;

function route() {
  const m = location.pathname.match(/^\/event\/(\d+)\/?$/), tab = location.hash.slice(1);
  if (m) {
    const id = +m[1];
    if (!(view instanceof EventView) || view.id !== id) { view?.destroy(); view = new EventView(id, user); view.mount($('#app')); }
  } else if (!(view instanceof Home)) { view?.destroy(); view = new Home(user); view.mount($('#app')); }
  view.setTab(tab);
}

document.addEventListener('click', e => {
  const a = e.target.closest('a[data-link]');
  if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
  const u = new URL(a.href, location.href);
  if (u.origin !== location.origin || u.pathname === location.pathname) return;   // même page : le hash suffit
  e.preventDefault(); history.pushState(null, '', u.pathname + u.hash); route();
});
addEventListener('popstate', route);
addEventListener('hashchange', route);
addEventListener('beforeinstallprompt', e => { e.preventDefault(); window._ia_install = e; document.getElementById('install')?.classList.remove('hidden'); });

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(regs => {
    const legacyScope = new URL('/static/', location.href).href;
    regs.find(reg => reg.scope === legacyScope)?.unregister();
  }).catch(() => { });
  navigator.serviceWorker.register('/sw.js').catch(() => { });
}
initNotifications();
route();
