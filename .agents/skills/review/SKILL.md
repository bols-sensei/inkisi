---
name: review
description: Relecture indépendante du diff de code contre les 14 invariants architecturaux et sécuritaires de GEMINI.md.
---

# Skill : review

## Rôle
Relecteur de code et garant de la sécurité architecturale.
Règle stricte : **lecture seule** — aucun fichier n'est modifié par ce skill.

## Méthode de vérification

1. **Extraction du diff Git** :
   Analyser les modifications via `git diff master...HEAD` ou `git diff`.

2. **Audit systématique des 14 Invariants de GEMINI.md** :
   - [ ] **1. Isolation des organisations** : toute requête vérifie l'appartenance de la ressource. Toute violation répond `404 Not Found` (jamais 403 ni redirection informative).
   - [ ] **2. Identité relue depuis la base** : `current_user` réinterroge la base à chaque requête. Tout changement de rôle, de mot de passe ou désactivation appelle `revoke_sessions`.
   - [ ] **3. Abonnements & Formules** : écritures protégées par `ensure_can_write`, fonctionnalités par `ensure_feature`. La désactivation d'un compte ou le scan d'un événement actif n'est jamais interrompu par l'abonnement.
   - [ ] **4. Contrôle d'accès** : subordonné à `event.status == 'active'` (`ensure_event_active`), après dédoublonnage idempotent.
   - [ ] **5. Idempotence** : clé unique par `(event_id, idempotency_key)`, jamais globale.
   - [ ] **6. Neutralisation des entrées tierces** : PDF via `pdf_text()`, Excel via `append_text_row()`, HTML auto-échappé via Jinja ou `esc()` en JS.
   - [ ] **7. CSP stricte (`script-src 'self'`)** : aucun `<script>` inline, aucun gestionnaire `onclick=` ou équivalent dans le DOM.
   - [ ] **8. Protection CSRF** : toute mutation passe par POST/PUT/PATCH/DELETE ; aucun effet de bord sur un GET.
   - [ ] **9. Détection d'environnement** : utilisation exclusive de `app.config.is_production()`. Zéro secret ou clé API en dur dans le code.
   - [ ] **10. Migrations de schéma** : aucune modification de migration existante. Toute nouvelle migration doit être idempotente et compatible SQLite/PostgreSQL.
   - [ ] **11. Cache Service Worker** : incrémentation de `STATIC` dans `sw.js` pour tout asset modifié ; nouveaux fichiers ajoutés à `SHELL`.
   - [ ] **12. Couverture de test & Matrice** : tout changement s'accompagne d'un test. Toute nouvelle route est ajoutée à `tests/test_roles_matrix.py` pour chaque rôle.
   - [ ] **13. Qualité des messages** : interface et messages en français clair, direct, avec action de reprise.
   - [ ] **14. Confidentialité des journaux** : aucune donnée personnelle (PII), jeton ou secret dans les logs ou retours d'erreurs.

3. **Exécution des vérifications automatisées** :
   - `pytest -q`
   - `python -m compileall -q app tests alembic`
   - `for f in app/static/js/*.js app/static/sw.js; do node --check "$f"; done`

## Livrables attendus
- Rapport d'analyse du diff ligne par ligne.
- Liste des constats classés : `BLOQUANT`, `IMPORTANT`, `MINEUR` avec référence `fichier:ligne` et invariant concerné.
- Verdict explicite : `FUSIONNABLE`, `FUSIONNABLE APRÈS CORRECTIFS`, ou `À REFAIRE`.
