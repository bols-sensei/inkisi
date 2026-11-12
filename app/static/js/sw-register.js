try {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(regs => {
      const legacyScope = new URL('/static/', location.href).href;
      regs.find(reg => reg.scope === legacyScope)?.unregister();
    }).catch(() => {});
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
} catch (e) { /* non bloquant */ }
