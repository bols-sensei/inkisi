---
name: lot4-ui
description: Implémente les chantiers d'interface du Lot 4 (quotas avant création, révocation/régénération QR, accessibilité, VAPID) avec Impeccable.
---

# Skill : lot4-ui

## Rôle
Designer-intégrateur d'interface utilisateur en Vanilla ES Modules et HTML5/CSS3 natif.

## Prérequis et Contraintes
- [GEMINI.md](../../../GEMINI.md) (invariants 6, 7, 11, 13).
- [PRODUCT.md](../../../PRODUCT.md) et [DESIGN.md](../../../DESIGN.md) doivent faire référence.
- Contraintes techniques absolues : aucun framework JS (pas de React/Vue), aucun build, aucun script inline ni écouteur `onclick=` (CSP stricte `script-src 'self'`), polices auto-hébergées, cibles tactiles ≥ 44px.
- Utilisation de la méthodologie Impeccable (`shape` → implémentation → `harden` → `polish`).

## Chantiers du Lot 4

### A. Écran « Mon abonnement » et Quotas
- Affichage clair du quota d'événements restants AVANT l'action de création d'événement.
- Explication pédagogique des états de grâce et de lecture seule (non-bloquant pour le contrôle d'accès en cours).

### B. Gestion unitaire des invitations
- Intégration des boutons d'action : `Révoquer`, `Réactiver`, `Régénérer le QR` reliés aux routes API existantes (`/admin/api/events/{id}/invitations/{id}/*`).
- Modale de confirmation explicite pour toute action destructive avec avertissement de réimpression papier obligatoire.

### C. Console Superadmin
- Ajout des actions de suspension et réactivation d'organisation (`PATCH /superadmin/api/organizations/{id}/status`).
- Filtre du journal d'audit par organisation sélectionnée.

### D. Accessibilité & Ergonomie
- Annonces d'état par `aria-live` pour les toasts et les listes dynamiques.
- Piège de focus dans les modales et feuilles coulissantes (`dialog.sheet`).
- Contrastes validés en mode clair et sombre pour lecture plein soleil / pénombre.
- Respect de `prefers-reduced-motion: reduce`.

### E. Service Worker & PWA Shell
- Incrémentation de la variable `STATIC` dans `app/static/sw.js` lors de la modification des assets.
- Ajout de toute nouvelle ressource d'interface dans la liste `SHELL`.

## Livrables attendus
- Écrans intégrés et documentés.
- Validation `node --check` sur tous les scripts JS.
- Maintien des tests API et de la matrice de rôles.
- Mise à jour de `CHANGELOG_LOT4.md`.
