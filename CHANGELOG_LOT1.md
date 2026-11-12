# Lot 1 — rendre le SaaS réel

## Mise en service (ordre important)
1. Sauvegarder la base (`scripts/backup_db.py`).
2. `alembic upgrade head` (applique `0003_saas_accounts`, idempotente).
3. Démarrer l'application (`main.py` n'amorce plus qu'après la migration et échoue avec un message clair sinon).
4. `pytest` — la suite `tests/test_saas_lot1.py` couvre chaque point ci-dessous. **Non exécutée avant livraison.**

## Ce qui change
| # | Avant | Maintenant |
|---|---|---|
| 1.1 | Rôle/organisation crus depuis le cookie ou le JWT | Base relue à chaque requête : compte actif, `token_version`, organisation non suspendue. Désactivation, changement de rôle ou de mot de passe = effet immédiat (cookie et JWT) |
| 1.2 | `Organization.status` ignoré | `PATCH /superadmin/api/organizations/{id}/status` (active/suspended) ; connexion et API bloquées (403) |
| 1.3 | Abonnement vérifié à la création d'événement seulement | États `active / grace (7 j) / readonly`. Écritures bloquées en lecture seule ; exports et consultation OK ; retirer un accès reste possible ; scan d'un événement « en cours » jamais interrompu |
| 1.4 | `advanced_features` décoratif | Requis pour créer une conférence et pour les PDF personnalisés en lot |
| 1.5 | Essai illimité, inscription sans e-mail | Essai limité (`TRIAL_EVENT_LIMIT`, 2 par défaut), e-mail obligatoire, **unique** (un essai par adresse), à confirmer avant de créer un événement |
| 1.6 | Superadmin dans « Organisation principale » | `organization_id = NULL` ; l'organisation héritée reçoit une formule `internal` de 10 ans |
| 1.7 | Admin sans gestion d'équipe | `PATCH /admin/api/users/{id}` (nom, rôle, actif, e-mail, mot de passe), création d'un autre admin, protection du dernier admin et de soi-même, changement de mot de passe (`/api/me/password`), mot de passe oublié (`/forgot-password`) |
| — | Statut d'événement sans effet | Contrôle d'accès uniquement si l'événement est « En cours » (en ligne, hors ligne synchronisé, badges conférence) |
| — | Invitation non révocable | `POST …/invitations/{id}/revoke`, `/restore`, `/regenerate-token` |
| — | Lien de vérification en GET avec effet | GET = page de confirmation, POST = consommation |
| — | Journal sans actions plateforme | Création/suspension d'organisation, abonnement, comptes : journalisés |

## Changements de comportement à connaître
- **Les événements existants en « Brouillon » ne peuvent plus être scannés** : les passer à « En cours » (modifier l'événement).
- Le superadmin ne crée plus d'événements ni de comptes sans préciser une organisation (`organization_id`).
- Les utilisateurs existants sont considérés comme e-mail validé (aucun blocage rétroactif) ; le plan `trial` existant passe de « illimité » à 2 événements.
- Les sessions et JWT émis avant la mise à jour restent valides (version 0) jusqu'à la première révocation.

## Pas encore fait (lots suivants)
Interface de révocation d'invitation et de suspension d'organisation (API prête), écran de quota avant création, unicité `(organisation, identifiant)`, CSRF/CSP, rate limit derrière proxy, `occurred_at` hors ligne, migration 0001 figée, file d'envoi d'e-mails, pagination.
