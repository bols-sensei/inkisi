---
name: fix-tests
description: Exécute la suite de tests pytest et corrige les échecs des lots 1 et 2 en respectant les invariants de GEMINI.md.
---

# Skill : fix-tests

## Rôle
Agent de stabilisation et de résolution d'anomalies de tests.
Objectif : stabiliser la suite de tests automatisés (lots 1 et 2) sans introduire de nouvelle fonctionnalité ni de refactorisation hors périmètre.

## Prérequis et Contexte
- Lecture obligatoire de [GEMINI.md](../../../GEMINI.md), [CHANGELOG_LOT1.md](../../../CHANGELOG_LOT1.md), [CHANGELOG_LOT2.md](../../../CHANGELOG_LOT2.md).
- Le code des lots 1 et 2 a été écrit sans exécution préalable ; la suite contient des échecs à diagnostiquer à la racine.

## Procédure d'exécution

1. **Création de branche** :
   Travailler sur une branche Git dédiée `agent/fix-tests`.

2. **Exécution initiale des tests** :
   Lancer `pytest -q` (ou avec `.venv/Scripts/pytest.exe -q`).
   Si des dépendances manquent, s'assurer que `requirements.txt` est bien installé.

3. **Analyse et résolution des échecs** :
   Pour chaque échec :
   - Déterminer si le problème provient du code applicatif ou du test lui-même.
   - Si un test contredit un invariant de [GEMINI.md](../../../GEMINI.md) (ex: isolation des organisations avec 404 neutre, identité relue depuis la base, validation de l'état `active` de l'événement), corriger le test et justifier la non-conformité.
   - Si le code applicatif est en défaut, apporter la correction minimale ciblée sans effet de bord.
   - Ne jamais supprimer un test pour faire passer la suite.

4. **Vérifications de cohérence globale** :
   - Compilation Python : `python -m compileall -q app tests alembic`
   - Syntaxe JavaScript : `for f in app/static/js/*.js app/static/sw.js; do node --check "$f"; done`
   - Migrations Alembic sur base jetable : `alembic upgrade head` sur une base neuve ET sur une base au niveau 0002.

5. **Gestion des commits** :
   Un commit atomique par cause racine identifiée avec message explicatif (`fix(...) : explication`).

## Livrables attendus
- Tableau récapitulatif : `Échec` → `Cause racine` → `Correctif appliqué`.
- Sortie intégrale de `pytest -q` sans régression.
- Liste des points d'attention ou des vérifications non réalisables.
