# Organisation Multi-Agents — Réception Événementielle (SaaS)

Ce document établit la structure hiérarchique, les périmètres de responsabilité, le protocole de coordination et les registres opérationnels de l'équipe multi-agents Antigravity pour le projet SaaS de réception événementielle.

---

## 1. Hiérarchie et Rôles

```
                            ┌───────────────────────────────────┐
                            │    ORION (Coordinateur Principal) │
                            │     Direction, arbitrage, synth.   │
                            └─────────────────┬─────────────────┘
                                              │
        ┌───────────────────┬─────────────────┴─────────────────┬───────────────────┐
        │                   │                                   │                   │
┌───────┴──────┐    ┌───────┴──────┐                    ┌───────┴──────┐    ┌───────┴──────┐
│  ÉQUIPE      │    │  ÉQUIPE      │                    │  ÉQUIPE      │    │  ÉQUIPE      │
│  SUPERADMIN  │    │  ADMIN       │                    │  AGENT       │    │  CLIENT      │
│  Plateforme  │    │  Organisation│                    │  Terrain/Scan│    │  Public/Conf │
└───────┬──────┘    └───────┬──────┘                    └───────┬──────┘    └───────┬──────┘
        │                   │                                   │                   │
        └───────────────────┴─────────────────┬─────────────────┴───────────────────┘
                                              │
                            ┌─────────────────┴─────────────────┐
                            │      SPÉCIALISTES TECHNIQUES      │
                            │  Backend · Frontend · UI/UX       │
                            │  QA/Test · Sécurité · DevOps      │
                            └───────────────────────────────────┘
```

### 1.1 Coordinateur Principal : ORION
- **Rôle** : Point unique d'arbitrage, de planification et d'intégration.
- **Missions** : Réception des objectifs du directeur de projet, découpage des chantiers, attribution des tâches, revue des diffs, validation des tests et émission des rapports de synthèse économiques en tokens.

### 1.2 Équipes Fonctionnelles (Métier)
1. **Équipe Super Admin (`team-superadmin`)** : Administration globale de la plateforme, gestion des organisations (création, activation, suspension, réactivation), formules d'abonnement et audit global.
2. **Équipe Admin (`team-admin`)** : Gestion de l'organisation locataire : événements, invitations, imports CSV/Excel, équipe locale, exports designers (ZIP/PDF/QR) et journal d'audit local.
3. **Équipe Agent & Superviseur (`team-agent`)** : Expérience terrain : scan rapide de QR codes, recherche manuelle, contrôle des quotas, dérogations superviseur, mode hors-ligne PWA et synchronisation IndexedDB.
4. **Équipe Client & Public (`team-client`)** : Parcours publics : inscriptions aux conférences, confirmation d'e-mail par jeton unique, gestion de la liste d'attente automatique et téléchargement de badges individuels sécurisés.

### 1.3 Spécialistes Techniques (Transverses)
- **Backend Specialist (`specialist-backend`)** : FastAPI, SQLAlchemy 2, migrations Alembic idempotentes, PostgreSQL/SQLite, requêtes N+1 et intégrité transactionnelle.
- **Frontend Specialist (`specialist-frontend`)** : JavaScript Vanilla en modules ES natifs, HTML5, PWA (Service Workers, CacheStorage, IndexedDB), zéro build, zéro CDN.
- **UI/UX Designer (`specialist-ui-ux`)** : Design System « malachite », ergonomie mobile-first plein soleil / nuit, accessibilité (cibles ≥ 44px, contrastes, `aria-live`, Impeccable).
- **QA / Test Engineer (`specialist-qa`)** : Suite pytest, matrice des 49 routes × 4 rôles, simulations réelles dans le navigateur via les serveurs MCP Playwright et Chrome DevTools.
- **Architecture & Security Specialist (`specialist-security`)** : Respect des 14 invariants de `GEMINI.md`, isolation multi-tenant stricte (404 systématique), CSP stricte (`script-src 'self'`), CSRF et gestion des sessions.
- **DevOps Specialist (`specialist-devops`)** : Environnements d'exécution (`.venv`, `requirements.txt`), scripts utilitaires, sauvegardes et configuration de production.

---

## 2. Règles de Collaboration et Communication

1. **Autorité et Délégation** : ORION distribue les chantiers. Chaque agent intervient exclusivement dans son périmètre défini.
2. **Préservation du Code et Invariants** : Tout développement doit respecter les 14 invariants de [GEMINI.md](GEMINI.md).
3. **Prévention des Conflits de Fichiers** : Aucune modification concurrente d'un même fichier sans coordination préalable par ORION.
4. **Validation par la Preuve** : Aucun succès n'est proclamé sans exécution et affichage de la sortie des commandes de contrôle :
   ```powershell
   & .venv/Scripts/pytest.exe -q
   & .venv/Scripts/python.exe -m compileall -q app tests alembic
   Get-ChildItem -Path app/static/js/*.js, app/static/sw.js | ForEach-Object { node --check $_.FullName }
   ```
5. **Économie de Tokens** : Communications concises, synthèses techniques courtes (< 30 lignes pour les rapports finaux), réutilisation des Skills sans recopie verbeuse de code.

---

## 3. Registre des Agents

| Identifiant | Rôle | Périmètre Principal | Fichier Définition |
|---|---|---|---|
| `orion` | Coordinateur Principal | Projet global, arbitrage, intégration | [.agents/agents/orion/agent.md](.agents/agents/orion/agent.md) |
| `team-superadmin` | Équipe Super Admin | `/superadmin/*`, abonnements, organisations | [.agents/agents/team-superadmin/agent.md](.agents/agents/team-superadmin/agent.md) |
| `team-admin` | Équipe Admin | `/admin/*`, événements, invitations, équipe | [.agents/agents/team-admin/agent.md](.agents/agents/team-admin/agent.md) |
| `team-agent` | Équipe Agent/Superviseur | `/checkin/*`, `/supervisor/*`, scanner PWA | [.agents/agents/team-agent/agent.md](.agents/agents/team-agent/agent.md) |
| `team-client` | Équipe Client/Public | `/conference/*`, `/badges/*`, inscriptions | [.agents/agents/team-client/agent.md](.agents/agents/team-client/agent.md) |
| `specialist-backend` | Spécialiste Backend | `app/models.py`, `app/services/`, Alembic | [.agents/agents/specialist-backend/agent.md](.agents/agents/specialist-backend/agent.md) |
| `specialist-frontend` | Spécialiste Frontend | `app/static/js/`, `app/static/sw.js` | [.agents/agents/specialist-frontend/agent.md](.agents/agents/specialist-frontend/agent.md) |
| `specialist-ui-ux` | Designer UI/UX | `app/static/css/`, `DESIGN.md`, Impeccable | [.agents/agents/specialist-ui-ux/agent.md](.agents/agents/specialist-ui-ux/agent.md) |
| `specialist-qa` | Ingénieur QA/Test | `tests/`, `tests/test_roles_matrix.py` | [.agents/agents/specialist-qa/agent.md](.agents/agents/specialist-qa/agent.md) |
| `specialist-security`| Spécialiste Sécurité | `app/middleware.py`, `app/security.py`, CSP | [.agents/agents/specialist-security/agent.md](.agents/agents/specialist-security/agent.md) |
| `specialist-devops`  | Spécialiste DevOps | `requirements.txt`, scripts, sauvegardes | [.agents/agents/specialist-devops/agent.md](.agents/agents/specialist-devops/agent.md) |

---

## 4. Registre des Skills Antigravity

Emplacement : `.agents/skills/<nom>/SKILL.md`

| # | Nom du Skill | Rôle et Action Principale | Fichier Source |
|---|---|---|---|
| 1 | `fix-tests` | Diagnostic et correction des échecs de tests (Lots 1 & 2) sans refonte | [.agents/skills/fix-tests/SKILL.md](.agents/skills/fix-tests/SKILL.md) |
| 2 | `e2e-roles` | Tests navigateur par type de compte (superadmin, admin, agent, client) | [.agents/skills/e2e-roles/SKILL.md](.agents/skills/e2e-roles/SKILL.md) |
| 3 | `design-init` | Initialisation et maintien de `PRODUCT.md` et `DESIGN.md` via Impeccable | [.agents/skills/design-init/SKILL.md](.agents/skills/design-init/SKILL.md) |
| 4 | `ui-audit` | Audit de conformité ergonomique et accessibilité terrain (lecture seule) | [.agents/skills/ui-audit/SKILL.md](.agents/skills/ui-audit/SKILL.md) |
| 5 | `lot3-backend` | Implémentation fiabilité Lot 3 (migrations figées, pagination, N+1, outbox) | [.agents/skills/lot3-backend/SKILL.md](.agents/skills/lot3-backend/SKILL.md) |
| 6 | `lot4-ui` | Implémentation interface Lot 4 (quotas pré-création, révocation QR, ARIA) | [.agents/skills/lot4-ui/SKILL.md](.agents/skills/lot4-ui/SKILL.md) |
| 7 | `e2e` | Parcours utilisateurs complets en conditions réelles avec serveurs MCP | [.agents/skills/e2e/SKILL.md](.agents/skills/e2e/SKILL.md) |
| 8 | `review` | Relecture du diff Git contre les 14 invariants de `GEMINI.md` | [.agents/skills/review/SKILL.md](.agents/skills/review/SKILL.md) |

---

## 5. Registre des Serveurs MCP

Configuration : [.agents/mcp_config.json](.agents/mcp_config.json) et [.gemini/settings.json](.gemini/settings.json)

| Serveur MCP | Commande & Arguments | Usage Opérationnel | État |
|---|---|---|---|
| `chrome-devtools` | `npx -y chrome-devtools-mcp@latest --isolated --viewport=390x844` | Diagnostic console (CSP), réseau, service worker, captures mobile | `DÉMARRABLE / TESTÉ` |
| `playwright-admin` | `npx -y @playwright/mcp@latest --isolated` | Navigation réelle, formulaires, session Superadmin & Admin | `DÉMARRABLE / TESTÉ` |
| `playwright-agent` | `npx -y @playwright/mcp@latest --isolated` | Deuxième session concurrente indépendante (Agent terrain / déconnexion) | `DÉMARRABLE / TESTÉ` |

---

## 6. Tableau de Suivi des Tâches

| ID Tâche | Chantier / Description | Équipe Responsable | Statut | Observations |
|---|---|---|---|---|
| T-001 | Audit et installation environnement multi-agents Antigravity | ORION | `OPÉRATIONNEL` | Architecture multi-agents, 8 skills, 3 MCPs, Impeccable, Git initialisé |
| T-002 | Capture du Design System (`DESIGN.md`) et audit Impeccable | `specialist-ui-ux` | `OPÉRATIONNEL` | `DESIGN.md` créé conformément à la spécification, validé par `impeccable doctor` |
| T-003 | Stabilisation de la suite de tests (`fix-tests`) | `specialist-qa` / `backend` | `À CORRIGER` | 31 fails, 273 errors identifiés lors de l'audit (header Host TestClient sous Starlette / SQLite) |
| T-004 | Lot 3 : Fiabilité backend (DDL 0001, pagination, N+1, outbox) | `specialist-backend` | `À PLANIFIER` | Planifié suite à stabilisation des tests |
| T-005 | Lot 4 : Interface & Accessibilité (quotas, boutons QR, ARIA) | `specialist-frontend` | `À PLANIFIER` | Planifié suite au Lot 3 |
| T-006 | Campagne d'essais réels navigateur 4 rôles (`e2e-roles`) | `specialist-qa` | `À PLANIFIER` | Nécessite base jetable `e2e.db` et serveur local démarré |

---

## 7. Registre des Décisions Techniques

| Date | ID | Objet | Décision Retenue | Justification |
|---|---|---|---|---|
| 2026-11-09 | D-001 | Architecture des agents | Hybride Antigravity : ORION permanent + équipes fonctionnelles et spécialistes réutilisables | Respect des conventions natives Antigravity sans surcharge artificielle |
| 2026-11-09 | D-002 | Emplacement des Skills | Centralisation sous `.agents/skills/<nom>/SKILL.md` avec frontmatter YAML | Découverte progressive Antigravity standard et compatibilité CLI |
| 2026-11-09 | D-003 | Configuration MCP | Double déclaration : `.agents/mcp_config.json` et synchronisation `.gemini/settings.json` | Prise en charge des deux modes de découverte Antigravity / Gemini CLI |
| 2026-11-09 | D-004 | Capture du Design System | Création de `DESIGN.md` calqué sur `app.css` sans aucune modification de styles | Préservation de la charte graphique existante sans refonte arbitraire |
| 2026-11-09 | D-005 | Isolation des sessions E2E | Utilisation de 2 serveurs Playwright distincts (`admin` et `agent`) | Permet de simuler des sessions indépendantes sans partage de cookies de session |

---

## 8. Registre des Dépendances et Conflits

| Composant A | Composant B | Type de Dépendance / Risque | Protocole d'Arbitrage |
|---|---|---|---|
| `app/models.py` | `alembic/versions/` | Tout changement de modèle exige une nouvelle migration idempotente | `specialist-backend` rédige la migration, `specialist-security` valide la compatibilité PostgreSQL/SQLite |
| `app/static/js/*.js` | `app/static/sw.js` | Toute modification d'un script client en cache exige l'incrémentation de `STATIC` | `specialist-frontend` met à jour `STATIC` dans le même commit que le script JS |
| `app/middleware.py` | `app/controllers/*.py` | La CSP stricte bloque tout script inline ou attribut onclick | `specialist-security` et `specialist-frontend` vérifient systématiquement via la console DevTools |
| Matrice des droits | Routes API nouvelles | Toute nouvelle route doit être ajoutée à `tests/test_roles_matrix.py` | `specialist-qa` bloque toute intégration de route orpheline de test de rôle |

---

## 9. Historique des Validations

| Date | Phase | Périmètre Validé | Validateur | Verdict |
|---|---|---|---|---|
| 2026-11-09 | Audit & Setup | Environnement multi-agents, 8 Skills, 3 MCPs, Impeccable, Git, DESIGN.md | ORION | `OPÉRATIONNEL` |
| 2026-11-09 | Contrôle Code | Compilation Python (`compileall`) et syntaxe JS (`node --check`) | DevOps | `CONFORME (0 erreur)` |
| 2026-11-09 | Suite Tests | Pytest initial (lots 1 & 2 non stabilisés) | QA | `À CORRIGER (31 échecs, 273 erreurs)` |
