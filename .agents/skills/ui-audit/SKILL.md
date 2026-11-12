---
name: ui-audit
description: Réalise un audit d'accessibilité, d'ergonomie et de qualité d'interface (lecture seule) avec les règles Impeccable.
---

# Skill : ui-audit

## Rôle
Auditeur d'interface et d'expérience utilisateur.
Règle stricte : **lecture seule** — aucune modification du code source n'est autorisée lors de cet audit.

## Objectifs et Périmètre
Évaluer la cohérence, l'accessibilité et la maniabilité des surfaces applicatives :
- Page de connexion / inscription
- Tableau de bord administrateur
- Détail d'événement et gestion des invitations
- Interface du scanner d'accès mobile
- Gestion de l'équipe et des permissions
- Vue abonnement et quotas
- Console superadmin
- Page publique d'inscription conférence

## Critères d'évaluation terrain (GEMINI.md)
1. **Conditions extrêmes** : lisibilité en plein soleil et dans la pénombre nocturne. Contrastes WCAG AA minimum.
2. **Usage à une main** : cibles tactiles interactives d'au moins 44×44px, zone d'action accessible au pouce.
3. **Retour immédiat** : verdicts d'entrée (vert/rouge/orange) distincts avec annonce `aria-live` pour l'accessibilité cognitive et visuelle.
4. **Intégrité CSP** : absence totale de scripts inline ou d'attributs `onclick=`.

## Procédure

1. **Détection statique des anti-patterns** :
   Exécuter `impeccable detect` sur les feuilles de style et gabarits.
   Identifier les bordures artificielles d'IA, les contrastes affaiblis ou les typographies minuscules.

2. **Examen des gabarits et interactions** :
   - Présence d'attributs ARIA (`aria-live`, `aria-current="page"`, `aria-pressed`).
   - Piège de focus dans les modales et feuilles coulissantes (`dialog.sheet`).
   - Respect de `prefers-reduced-motion`.

## Livrables attendus
- Rapport d'audit classé par sévérité : `BLOQUANT`, `IMPORTANT`, `MINEUR`.
- Emplacement précis (`fichier:ligne`) pour chaque constat.
- Proposition de correctif conforme à la charte et sans introduction de framework lourd.
