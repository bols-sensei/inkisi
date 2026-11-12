# Réception événementielle — contexte pour les agents

Application SaaS multi-organisations de gestion d'événements : invitations à QR code, contrôle d'accès hors ligne (PWA),
conférences avec inscriptions publiques et badges. Quatre rôles : `superadmin` (plateforme, sans organisation), `admin`
(propriétaire d'une organisation), `supervisor`, `agent` (terrain). Interface en **français**.

## Pile et structure
- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Jinja2. **Pas de framework JS, pas de build, pas de CDN** : JS en modules ES natifs.
- `app/config.py` (ENVIRONMENT, échec fermé) · `app/main.py` · `app/middleware.py` (débit, CSRF, CSP) · `app/security.py`
  (authentification) · `app/bootstrap.py` (données de référence) · `app/models.py` · `app/schemas.py`
- `app/controllers/` : `auth`, `admin`, `operations`, `checkin`, `supervisor`, `superadmin`
- `app/services/` : `subscriptions`, `accounts`, `organizations`, `ratelimit`, `safe`, `exports`, `importer`, `messaging`, `qr`, `conference`
- `app/views/*.html` (Jinja) · `app/static/js/*.js` · `app/static/sw.js` (service worker) · `alembic/versions/0001…0004`
- Tests : `tests/` (`conftest.py` crée une base SQLite jetable). Historique : `AUDIT_SAAS.md`, `CHANGELOG_LOT1.md`, `CHANGELOG_LOT2.md`.

## Commandes de vérification (à lancer avant toute conclusion)
```
pytest -q
python -m compileall -q app tests alembic
for f in app/static/js/*.js app/static/sw.js; do node --check "$f" || echo "ÉCHEC $f"; done
alembic upgrade head        # sur une base de test jetable
```
Ne jamais écrire « ça marche » sans avoir vu la sortie de ces commandes. Si une commande ne peut pas tourner, le dire.

## Invariants — ne jamais les casser
1. **Isolation des organisations** : toute lecture/écriture d'un objet métier passe par `ensure_event_organization`, `_scoped`
   ou un filtre `organization_id`. Une ressource d'une autre organisation répond **404**, jamais 403.
2. **L'identité vient de la base** : `current_user` relit l'utilisateur à chaque requête. Ne jamais croire le rôle ou
   l'organisation d'un cookie ou d'un JWT. Tout changement de rôle, d'état actif ou de mot de passe appelle `revoke_sessions`.
3. **Abonnement et formules** : écritures protégées par `ensure_can_write`, fonctionnalités par `ensure_feature`. Retirer un accès
   (désactiver un compte) n'est jamais bloqué par l'abonnement. Le scan d'un événement « en cours » n'est jamais interrompu.
4. **Contrôle d'accès** : uniquement si `event.status == 'active'` (`ensure_event_active`), après le rejeu idempotent.
5. **Idempotence** : unique par `(event_id, clé)`, jamais globale.
6. **Données saisies par des tiers** : PDF → `pdf_text()`, Excel → `append_text_row()`, HTML → autoescape Jinja / `esc()` en JS.
7. **CSP stricte** (`script-src 'self'`) : aucun `<script>` ni gestionnaire `onclick=` en ligne. Données de page via
   `<script type="application/json">` lu par un fichier JS. Les attributs `style=` sont tolérés, pas les scripts.
8. **CSRF** : toute modification passe par POST/PUT/PATCH/DELETE ; jamais d'effet de bord sur un GET.
9. **Configuration** : utiliser `app.config.is_production()`. Jamais `os.getenv("ENVIRONMENT", …)` ailleurs. Aucun secret en dur.
10. **Migrations** : ne jamais modifier une migration existante. Toute évolution de schéma = nouvelle migration **idempotente**
    (inspecter avant d'ajouter), car `0001` appelle `create_all`. Compatible SQLite et PostgreSQL.
11. **Service worker** : si un fichier statique en cache change, incrémenter `STATIC` dans `sw.js` ; tout nouveau fichier du shell
    est ajouté à `SHELL`.
12. **Chaque changement de comportement s'accompagne d'un test** et d'une entrée dans le CHANGELOG du lot. Toute **nouvelle route** est ajoutée à la matrice des droits (`tests/test_roles_matrix.py`) pour chaque rôle.
13. Messages utilisateur en français, clairs, sans reproche, avec une action de reprise.
14. Aucune donnée personnelle ni secret dans les logs ou les messages d'erreur.

## Règles de travail
- Une branche par chantier (`agent/<sujet>`), petits commits, un message qui explique le *pourquoi*.
- Lire le code existant avant de modifier ; changements chirurgicaux ; pas de refonte hors périmètre.
- Ne pas toucher à `.env`. Ne pas supprimer de tests pour les faire passer : corriger le code ou expliquer.
- En fin de tâche : résumé court (fichiers modifiés, tests lancés avec leur sortie, risques restants).

## Travail restant
- **Lot 3 (fiabilité)** : migration `0001` figée (DDL explicite), file d'envoi d'e-mails/notifications, pagination
  (invitations, inscriptions, notifications), suppression du N+1 (`event_detail`, `lookup`, `overview`), export/suppression
  des données d'un client et d'un participant, unicité `(organisation, identifiant)`.
- **Lot 4 (interface)** : écran quota avant création, boutons révocation/régénération d'invitation, suspension d'organisation
  côté superadmin, `aria-live`, contrastes, cibles tactiles, focus des feuilles modales, `prefers-reduced-motion`.

## Contexte produit pour Impeccable (design)
- Surface : **application** (mode « Operate »), PWA mobile-first utilisée **debout, à l'entrée d'un événement**, souvent en
  plein soleil ou de nuit, une main, réseau instable. Scan rapide, lisibilité immédiate du résultat (accepté / refusé / quota).
- Utilisateurs : agents de contrôle (terrain), superviseurs, organisateurs (admin), équipe plateforme (superadmin).
- Ton : sobre, fiable, rassurant ; pas de décoration gratuite. Français. Pas de dépendance externe (polices auto-hébergées).

## Essais dans le navigateur (MCP Chrome DevTools + Playwright)
- Toujours sur une **base jetable** (`sqlite:///./e2e.db`), `ENVIRONMENT=development`, `RATE_LIMIT_DISABLED=true` ; jamais de vraies données ni de vrais comptes.
- Playwright pour dérouler les parcours (deux serveurs = deux sessions indépendantes), Chrome DevTools pour la console, le réseau et le hors ligne.
- Utiliser une **fenêtre isolée** (`--isolated`) : ne jamais se connecter avec le profil Chrome personnel du propriétaire.
- Lire la console à chaque page : la CSP stricte fait échouer **en silence** tout script ou gestionnaire en ligne.
- La caméra ne peut pas scanner un vrai QR : tester le passage par **recherche manuelle** et par jeton (`/api/events/{id}/lookup?q=token:…`).
- Hors ligne : utiliser l'émulation réseau de Chrome DevTools, puis vérifier la file IndexedDB `invitation-offline-v1`.
- Les e-mails sortants sont d?sactiv?s : les mots de passe se r?initialisent via un administrateur et les inscriptions publiques affichent leur lien de suivi apr?s cr?ation.
