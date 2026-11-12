try { var t = localStorage.getItem('ia-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* stockage indisponible */ }
