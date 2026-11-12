---
name: Réception événementielle
description: Design system mobile-first pour le contrôle d'accès événementiel et la gestion SaaS
colors:
  primary: "#0b5d4b"
  primary-deep: "#073d31"
  primary-soft: "#dcefe7"
  primary-dark: "#36c79b"
  neutral-bg: "#edf2ef"
  neutral-surface: "#ffffff"
  neutral-surface-2: "#f5f8f6"
  neutral-ink: "#10231c"
  neutral-ink-2: "#4a6157"
  neutral-ink-3: "#7b9187"
  neutral-line: "#d9e4de"
  accent-cobalt: "#2f55d4"
  accent-cobalt-soft: "#e2e9fb"
  status-ok: "#0f8a5b"
  status-ok-soft: "#d9f2e6"
  status-warn: "#a96a00"
  status-warn-soft: "#fbebc6"
  status-bad: "#c4343f"
  status-bad-soft: "#fbe1e3"
typography:
  display:
    fontFamily: "Bricolage, ui-rounded, Segoe UI, system-ui, sans-serif"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "DMSans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
rounded:
  sm: "10px"
  md: "14px"
  lg: "20px"
  xl: "28px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "14px"
  lg: "18px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    height: "48px"
  button-tonal:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    height: "48px"
  button-danger:
    backgroundColor: "{colors.status-bad-soft}"
    textColor: "{colors.status-bad}"
    rounded: "{rounded.md}"
    height: "48px"
  card:
    backgroundColor: "{colors.neutral-surface}"
    rounded: "{rounded.lg}"
    padding: "16px"
---

# Design System — Réception événementielle

## Overview

Interface applicative SaaS (« mode Operate ») optimisée en priorité pour les téléphones mobiles manipulés à une seule main par les agents de contrôle à l'entrée des réceptions et conférences (journée en plein soleil ou nuit tamisée), tout en s'adaptant confortablement au bureau pour les organisateurs et superadministrateurs. Thème clair par défaut, thème sombre automatique ou commutable, palette signature « malachite ».

## Colors

- **Marque (Malachite)** :
  - Claire : primaire `#0b5d4b`, profond `#073d31`, adouci `#dcefe7`, texte blanc `#ffffff`.
  - Sombre : primaire `#36c79b`, profond `#0d3a2e`, adouci `#13352b`, texte sombre `#04201a`.
- **Neutres** :
  - Clair : fond `#edf2ef`, surface `#ffffff`, surface secondaire `#f5f8f6`, encres `#10231c`, `#4a6157`, `#7b9187`, séparateurs `#d9e4de`.
  - Sombre : fond `#0a1411`, surface `#121f1a`, surface secondaire `#182621`, encres `#e6f1ec`, `#98ada3`, `#69807a`, séparateurs `#243630`.
- **États & Alertes** :
  - Succès : `#0f8a5b` (fond adouci `#d9f2e6`) / mode sombre `#3fd49b` (`#10382a`).
  - Avertissement : `#a96a00` (fond adouci `#fbebc6`) / mode sombre `#f0b445` (`#3a2d0f`).
  - Erreur / Quota plein : `#c4343f` (fond adouci `#fbe1e3`) / mode sombre `#ff7b84` (`#401b20`).
  - Information / Focus : Cobalt `#2f55d4` (fond adouci `#e2e9fb`) / mode sombre `#7d9bff` (`#1a2547`).

## Typography

- **Polices auto-hébergées (zéro CDN)** :
  - **Titres / Chiffres (Display)** : `Bricolage` (`/static/fonts/display.woff2`), graisse 650, espacement négatif `-0.02em`. Chiffres tabulaires sur les compteurs et jauges (`tabular-nums`).
  - **Corps / Interface (Body)** : `DMSans` (`/static/fonts/body.woff2`), taille de base 15px/1.5. Graisses 400 (normal), 600 (semi-gras) et 650 (accentué).
- **Échelle typographique** :
  - H1 : 1.65rem (26px), interligne 1.15
  - H2 : 1.25rem (20px), interligne 1.15
  - H3 : 1.02rem (16px), interligne 1.2
  - Corps : 0.95rem – 1.0rem
  - Méta / Petit : 0.78rem – 0.84rem
  - Minuscule / Badges : 0.70rem – 0.75rem

## Layout

- **Mobile (< 900px)** :
  - Barre d'application supérieure collante (`.appbar`), hauteur 56px + encoche système (`env(safe-area-inset-top)`).
  - Barre d'onglets inférieure fixe (`.tabbar`), hauteur 64px + encoche système (`env(safe-area-inset-bottom)`).
  - Bouton central « Scanner » mis en avant avec disque surélevé (`.puck`, 54×54px).
  - Largeur maximale du contenu : 760px centré.
- **Bureau (≥ 900px)** :
  - Barre latérale d'onglets à gauche (largeur 92px), fixe de haut en bas.
  - Espace de travail avec marge gauche de 92px, largeur maximale 980px.
  - Grilles à deux colonnes (`.grid-2`) pour équilibrer formulaires et aperçus.

## Elevation & Depth

- **Superposition sobre sans ombres superflues** :
  - Ombres réservées aux éléments flottants : barres d'onglets (`0 -8px 24px rgba(8,30,24,.06)`), modales/feuilles (`0 -20px 60px rgba(0,0,0,.28)`), notifications (`0 18px 50px rgba(0,0,0,.2)`).
  - Fond de scène malachite texturé par un motif radial discret (`repeating-radial-gradient`) pour la signature visuelle des cartes « Hero » et des écrans d'authentification.
  - Modales en feuilles coulissantes depuis le bas de l'écran sur mobile (`dialog.sheet`), centrées sur écran large avec fond flouté (`backdrop-filter: blur(3px)`).

## Shapes

- **Rayons de courbure (Border Radius)** :
  - Petits éléments (badges, boutons réduits) : `--r-s: 10px`
  - Boutons, champs de saisie, items de liste : `--r-m: 14px`
  - Cartes principales : `--r-l: 20px`
  - Feuilles modales, cartes hero, cadre du scanner : `--r-xl: 28px`
  - Pilules / Puces (chips, compteurs) : `border-radius: 99px`

## Components

- **Boutons (`.btn`)** :
  - Hauteur minimale tactile : 48px (38px pour les boutons compacts `.btn.sm`).
  - Variantes : `.primary` (fond malachite, texte blanc), `.tonal` (fond adouci, texte malachite), `.ghost` (fond blanc/surface, bordure neutre), `.danger` (fond rouge adouci, texte rouge).
  - Retour tactile immédiat au clic : compression subtile (`transform: scale(0.97)`).
  - État de chargement : classe `.busy` avec micro-indicateur rotatif CSS pur.
- **Champs de formulaire (`.field`, `.input`, `.select`, `.textarea`)** :
  - Hauteur minimale : 48px, bordure 1.5px, rayon 14px.
  - Anneau de focus accessible : contour cobalt 3px avec décalage de 2px.
- **Cartes & Listes** :
  - `.card` et `.tile` pour les blocs d'information et statistiques clés (KPIs).
  - `.item` pour les listes de participants/invitations avec avatar coloré selon l'état d'entrée (vert complet, orange partiel).
- **Scanner & Contrôle d'accès** :
  - Viseur carré (`.viewfinder`) avec réticule lumineux (`#7ff0c6`), ligne de balayage animée et bouton de lampe torche / changement de caméra.
  - Verdict visuel pleine largeur (`.verdict.ok`, `.verdict.bad`, `.verdict.warn`) immédiatement compréhensible à plusieurs mètres.
- **Notifications & Toasts** :
  - Toasts non intrusifs en bas d'écran (`.toasts`, `.toast.ok`, `.toast.bad`), annoncés vocalement par `aria-live`.

## Do's and Don'ts

### Do's
- Conserver des cibles tactiles supérieures ou égales à 44×44px pour chaque action mobile.
- Utiliser les variables CSS thématiques (`var(--brand)`, `var(--surface)`, `var(--ink)`) plutôt que des couleurs en dur.
- Respecter scrupuleusement la CSP stricte : aucun style inline dynamique de logique, aucun script inline, aucun `onclick=`.
- Toujours associer un code couleur à un symbole textuel ou une icône explicite (pour l'accessibilité daltonienne).
- Respecter les préférences de mouvement réduit (`prefers-reduced-motion: reduce`).

### Don'ts
- Ne jamais ajouter de bibliothèque UI externe (pas de React, pas de Vue, pas de Tailwind, pas de CDN tiers).
- Ne jamais surcharger l'écran du scanner avec des données superflues qui ralentiraient le flux d'entrée.
- Ne jamais masquer le bouton de passage manuel ou de recherche en cas d'échec de lecture optique du QR code.
- Ne pas introduire d'éléments graphiques purement décoratifs qui diminueraient le contraste en plein soleil.
