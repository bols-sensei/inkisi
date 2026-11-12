---
name: lot3-backend
description: Implémente les chantiers de fiabilité backend du Lot 3 (migrations figées, pagination curseur, N+1, file d'attente, RGPD).
---

# Skill : lot3-backend

## Rôle
Ingénieur backend spécialisé dans la robustesse, la scalabilité et l'intégrité des données sous FastAPI et SQLAlchemy 2.

## Référence et Invariants
- [GEMINI.md](../../../GEMINI.md) (invariants 1 à 14).
- [AUDIT_SAAS.md](../../../AUDIT_SAAS.md) (sections 3, 4 et 5) et [CHANGELOG_LOT2.md](../../../CHANGELOG_LOT2.md).
- Travail sur branche dédiée : `agent/lot3-backend`.
- Un commit atomique par sous-chantier, accompagné de son test automatisé dédié.

## Chantiers du Lot 3

### A. Migration 0001 figée
- Remplacer l'appel `create_all` dans `alembic/versions/0001_bootstrap.py` par un DDL explicite du schéma de référence phase 2.
- Conserver les migrations `0002` à `0004` strictement idempotentes (vérification d'existence avant ajout de colonnes/tables).
- Preuve exigée : base neuve → head ET base issue de la révision 0002 → head aboutissent à un schéma rigoureusement identique sous SQLite et PostgreSQL.

### B. Pagination avec curseur
- Implémenter une pagination efficace (`limit` + curseur) pour les listes volumineuses : invitations, inscriptions conférences et notifications.
- Maintenir la rétrocompatibilité des retours JSON et adapter les contrôleurs JS clients (`core.js`, `event.js`).

### C. Éradication des requêtes N+1
- Optimiser les routes critiques : `event_detail`, `lookup`, `overview` via des jointures préchargées (`joinedload`/`selectinload`) ou des agrégats SQL directs.
- Ajouter un test mesurant le nombre exact de requêtes SQL exécutées.

### D. File d'envoi asynchrone (Outbox)
- Création d'une table `outbox` pour découpler l'envoi des e-mails transactionnels et notifications Web Push du cycle de requête HTTP.
- Gestion de reprise sur incident avec compteur et plafond de tentatives.

### E. Unicité `(organisation, identifiant)`
- Prise en charge de l'unicité des identifiants au niveau de l'organisation plutôt que globale.
- Gestion du sélecteur d'organisation à la connexion si un même identifiant existe sur plusieurs tenants.

### F. Conformité RGPD & Export
- Fonctionnalité d'exportation complète des données d'une organisation au format ZIP.
- Procédure de purge / anonymisation irréversible des données personnelles d'un participant sur demande.

## Livrables attendus
- Code implémenté et testé pour chaque chantier.
- Mise à jour de `CHANGELOG_LOT3.md`.
- Validation complète des commandes de conformité : `pytest -q`, `compileall`, `node --check`.
