// Données de page (JSON inerte, compatible CSP) exposées sous window.BOOT.
(function () {
  var el = document.getElementById('boot'), data = { user: null, eventId: null };
  try { if (el) data = JSON.parse(el.textContent); } catch (e) { /* page sans données */ }
  window.BOOT = data;
})();
