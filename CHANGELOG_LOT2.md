# Lot 2 — sécurité et intégrité

## Reprise Codex — QR et recherche
- Les recherches par QR exposent désormais aussi les invitations révoquées, afin que le scanner affiche un refus explicite au lieu de les présenter comme inconnues. La recherche textuelle ordinaire reste limitée aux invitations actives.
- Le scanner conférence affiche les statuts non autorisés (attente e-mail, liste d’attente, refus ou annulation) avant toute action d’entrée.
- Le contrôle des invitations revalide une clé idempotente après verrouillage de la ligne, pour reconnaître un scan concurrent déjà validé avant de recalculer le quota ou l’état de l’événement.
- Révision Alembic 0006 raccourcie pour respecter la limite PostgreSQL de 32 caractères ; la chaîne 0007 référence la nouvelle révision.
- Ajout de tests de recherche par identité, e-mail et téléphone pour inscriptions publiques et manuelles, d'isolation par événement, de validation QR, de révocation et de scans de badge simultanés.

## Mise en service
1. Sauvegarder la base, puis `alembic upgrade head` (applique `0004_integrity_audit`, idempotente).
2. **Définir `ENVIRONMENT`** : `development` en local, `production` ailleurs. Sans valeur, l'application démarre en production et refuse de démarrer si les secrets, PostgreSQL, Redis, SMTP, `ALLOWED_HOSTS` ne sont pas configurés.
3. Derrière un reverse proxy : `TRUSTED_PROXY_COUNT=1` (sinon toutes les requêtes semblent venir de la même IP).
4. `pytest` — `tests/test_saas_lot2.py`. **Non exécuté avant livraison** (voir ci-dessous ce qui a été vérifié).

## Ce qui change
| Réf. | Avant | Maintenant |
|---|---|---|
| S1 | Noms injectés bruts dans les PDF ReportLab (erreur 500, balises interprétées) | Échappés (`services/safe.py`) — vérifié avec ReportLab : le texte brut provoque une `ValueError`, le texte échappé génère le PDF |
| S2 | `=…` dans un nom → formule Excel | Cellules forcées en texte — vérifié avec openpyxl : aucune balise `<f>` dans le fichier |
| S3 | Limite par IP seule, IP du proxy partagée | IP réelle via `TRUSTED_PROXY_COUNT` ; échecs de connexion limités par (compte, IP) : 5 / 15 min, et par compte : 30 / h ; API 1 500 req/min/IP |
| S4 | Mode « développement » par défaut | Mode « production » par défaut ; valeur invalide refusée |
| S5 | Pas de CSRF | Contrôle `Origin`/`Referer`/`Sec-Fetch-Site` sur toute requête modifiante ; appels Bearer exemptés |
| S6 | Pas de CSP | CSP stricte (`script-src 'self'`) : plus aucun script en ligne (`boot.js`, `theme-init.js`, `sw-register.js`, `conference_public.js`) |
| S7 | « Déjà inscrit » révélait l'existence d'une adresse | Réponse identique ; le propriétaire de l'adresse reçoit un lien par e-mail |
| S8 | Lien de vérification conférence en GET destructif | GET = page de confirmation, POST = consommation ; la vérification n'écrase plus le statut de modération |
| S10 | Journal sans lecture | `GET /admin/api/audit` (filtres `event_id`, `action`, pagination `before_id`) + écran « Journal d'activité » ; `organization_id` rempli automatiquement ; actions plateforme rattachées au client |
| S12 | File hors ligne synchronisable par un autre compte | Chaque passage porte son `user_id` ; un autre compte reçoit `deferred` (le passage reste en file) ; la déconnexion efface le cache d'invités |
| D2 | `occurred_at` ignoré | Date réelle conservée dans `created_at` (si valide : ni futur, ni > 14 jours), `synced_at` = réception |
| D3 | Clé d'idempotence unique pour toute la plateforme | Unique par `(événement, clé)` (entrées et badges conférence) |
| D1 | SQLite possible en production | Refusé en production (PostgreSQL obligatoire) ; `with_for_update` devient effectif |

## Points d'attention
- **Les liens de vérification déjà envoyés pour les conférences** continuent de fonctionner, mais affichent désormais une page de confirmation.
- Le limiteur en mémoire (développement) n'est pas partagé entre processus ; la production exige Redis.
- Les passages hors ligne **déjà en file** avant la mise à jour n'ont pas de `user_id` : ils restent synchronisables par n'importe quel compte.
- La CSP autorise les styles en ligne (`style-src 'unsafe-inline'`), nécessaires aux attributs `style=` existants. Les retirer demande un chantier d'interface séparé.

## Pas encore fait (lot 3)
Migration `0001` figée, seeds hors du code d'import (partiellement fait au lot 1), file d'envoi d'e-mails et de notifications, pagination des listes, requêtes agrégées (N+1), export/suppression des données d'un client ou d'un participant, unicité `(organisation, identifiant)`.

## Ajout : tests par type de compte
`tests/test_roles_matrix.py` : 49 routes × {superadmin, admin, superviseur, agent} + anonyme, isolation entre organisations (404),
désactivation et suspension par rôle, changement de mot de passe par rôle, parcours du participant public.
Correction : les tests de scan appelaient `/api/events/…` au lieu de `/checkin/api/events/…` (corrigé dans `test_saas_lot1.py` et `test_saas_lot2.py`).
