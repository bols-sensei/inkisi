---
name: design-init
description: Initialise et maintient le contexte de design Impeccable (PRODUCT.md, DESIGN.md) à partir de la charte existante.
---

# Skill : design-init

## Rôle
Designer-intégrateur responsable de l'alignement de la documentation de design système avec les surfaces réelles du produit.

## Règles impératives
- Ne pas lancer de refonte graphique arbitraire.
- Capturer l'existant : jetons, variables CSS, composants, typographies locales et palettes de `app/static/css/app.css` et des gabarits Jinja `app/views/`.

## Procédure

1. **Vérification de l'environnement Impeccable** :
   Vérifier la disponibilité de l'exécutable Impeccable (`.gemini/skills/impeccable/scripts/bin/windows-x64/impeccable.exe` ou `npx impeccable`).

2. **Alignement avec la vision produit** :
   Consulter la section « Contexte produit pour Impeccable » de [GEMINI.md](../../../GEMINI.md) et [PRODUCT.md](../../../PRODUCT.md).
   Valider que les rôles, les contraintes de terrain (plein soleil, usage à une main, CSP stricte, zéro CDN) sont fidèlement transcrits.

3. **Capture et documentation du Design System (`DESIGN.md`)** :
   Vérifier la conformité de [DESIGN.md](../../../DESIGN.md) :
   - Frontmatter YAML structuré (couleurs primaires/neutres/statuts, typographie display et body, rayons de courbure, espacements, composants boutons/cartes).
   - Sections canoniques : Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and Don'ts.

4. **Diagnostic de dérive** :
   Exécuter `impeccable doctor` pour s'assurer de l'absence de dérive entre les déclarations et les fichiers de styles du projet.

## Livrables attendus
- Rapport de validation de `PRODUCT.md` et `DESIGN.md`.
- Sortie de `impeccable doctor`.
- Recommandations éventuelles pour les lots d'interface à venir.
