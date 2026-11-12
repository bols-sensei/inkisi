# Invitation & Access Control â€” MVP MVC

Application web de gestion d'Ã©vÃ©nements, invitations, QR codes et contrÃ´le d'accÃ¨s.

## Stack
- Backend : Python, FastAPI, SQLAlchemy
- Architecture : MVC (models / views HTML / controllers), avec services mÃ©tier sÃ©parÃ©s
- Frontend : HTML, CSS et JavaScript natifs
- Base de donnÃ©es par dÃ©faut : SQLite (simple pour dÃ©marrer; PostgreSQL recommandÃ© en production)
- Import Excel/CSV : openpyxl / csv
- PDF de rÃ©fÃ©rence : ReportLab
- QR codes : qrcode

## DÃ©marrage (Windows PowerShell)
```powershell
cd invitations_mvc
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Configurez d'abord .env, puis appliquez les migrations
alembic upgrade head
uvicorn app.main:app --reload
```
Ouvrir http://127.0.0.1:8000. Documentation API : http://127.0.0.1:8000/docs

Au premier dÃ©marrage, un compte administrateur est crÃ©Ã© Ã  partir de `.env` :
- `ADMIN_USERNAME` (dÃ©faut `admin`)
- `ADMIN_PASSWORD` (dÃ©faut `ChangeMe-123!` â€” Ã  changer immÃ©diatement)

## Import Excel
La premiÃ¨re feuille doit contenir une ligne d'en-tÃªte. Colonnes reconnues (accents/casse tolÃ©rÃ©s) :
- `nom` ou `invite` (obligatoire)
- `type` (individuelle, couple, groupe; facultatif, dÃ©duit du quota)
- `nombre` ou `quota` ou `personnes` (obligatoire, entier >= 1)
- `table` (facultatif)

L'ordre des lignes est conservÃ©. Une fois l'import confirmÃ©, les rÃ©fÃ©rences sont attribuÃ©es dans cet ordre (`INV-0001`, `INV-0002`...). Les rÃ©fÃ©rences existantes ne sont pas renumÃ©rotÃ©es lors des ajouts ultÃ©rieurs.

## Exports pour le designer
Dans la page d'un Ã©vÃ©nement, utiliser **GÃ©nÃ©rer le dossier designer**. L'archive ZIP contient :
- `manifest_invitations.xlsx` : liste et rÃ©fÃ©rences dans l'ordre de production
- `reference_invitations.pdf` : liste imprimable avec rÃ©fÃ©rence, invitÃ©, type, quota, table et QR correspondant
- `QR_CODES/INV-xxxx.png` : image PNG de chaque QR code
- `instructions_designer.txt`

Le QR code contient un jeton alÃ©atoire opaque, pas le nom ou le quota. Le PDF/Excel sont les documents de correspondance. Le jeton est un identifiant de validation et ne remplace pas les contrÃ´les serveur.

## RÃ´les MVP
- `admin` : crÃ©er les Ã©vÃ©nements, importer les invitÃ©s, crÃ©er les comptes agents/superviseurs, affecter les agents, gÃ©nÃ©rer les exports.
- `supervisor` : consulter les entrÃ©es et agents, vÃ©rifier les invitations, enregistrer des exceptions avec motif.
- `agent` : vÃ©rifier une invitation et enregistrer des entrÃ©es dans un quota autorisÃ©.

## Format d'import exemple
Un fichier `examples/invites_exemple.csv` est fourni. Excel `.xlsx` et CSV sont pris en charge.

## Important avant production
Ce dÃ©pÃ´t est un MVP fonctionnel de dÃ©part, pas un dÃ©ploiement de production certifiÃ©. Avant un vrai Ã©vÃ©nement :
1. DÃ©finir `SECRET_KEY` robuste et modifier le mot de passe admin.
2. Utiliser HTTPS, une base PostgreSQL et des sauvegardes.
3. La limitation de dÃ©bit et les tests de sÃ©curitÃ© sont renforcÃ©s dans la phase suivante; utiliser Redis en production.
4. Le mode hors ligne ne garantit pas une validation globale entre appareils isolÃ©s : les contrÃ´les hors ligne sont en attente de synchronisation.
5. Les exports contiennent des donnÃ©es personnelles; les transmettre uniquement aux destinataires autorisÃ©s et les supprimer selon la politique de conservation.


## SÃ©curitÃ© et contrÃ´le mobile (mise Ã  jour)
- Jetons JWT Bearer disponibles via `POST /api/auth/token` avec JSON `{"username":"...","password":"..."}`. Les routes API acceptent JWT Bearer et la session web existante. Les nouveaux contrÃ´les de supervision affichent lâ€™activitÃ© des agents et la file dâ€™exceptions.
- Validation des payloads par Pydantic v2.
- Hash des mots de passe via `pwdlib[argon2]` (Argon2id si la dÃ©pendance est installÃ©e).
- Scan QR avec `BarcodeDetector` natif lorsquâ€™il est disponible; camÃ©ra exige HTTPS ou localhost.
- Lecture NFC via Web NFC sur navigateurs/appareils compatibles, gÃ©nÃ©ralement Chrome Android; pas prise en charge universelle sur iPhone/desktop.
- Service worker pour mettre en cache les fichiers statiques et file dâ€™attente IndexedDB pour les scans hors ligne. La synchronisation est idempotente et signale les conflits de quota.
- Supervision : tableau de bord existant, agents affectÃ©s, historique des passages, journal dâ€™audit et endpoint de synchronisation des entrÃ©es diffÃ©rÃ©es.

### Limites importantes du mode hors ligne
Le cache ne permet pas de tÃ©lÃ©charger automatiquement une liste complÃ¨te des invitÃ©s ni de valider sÃ»rement les quotas sans serveur. Un contrÃ´le enregistrÃ© hors ligne reste **en attente**, et peut Ãªtre rejetÃ© ou signalÃ© en conflit Ã  la synchronisation. Deux tÃ©lÃ©phones dÃ©connectÃ©s ne peuvent pas se coordonner pour empÃªcher instantanÃ©ment quâ€™un mÃªme QR soit acceptÃ© deux fois. Pour une exploitation Ã©vÃ©nementielle, prÃ©charger un manifeste signÃ© sur chaque appareil, limiter les zones de contrÃ´le par agent, puis synchroniser avec PostgreSQL et des transactions/contraintes atomiques. La concurrence de production doit Ãªtre testÃ©e.

### Authentification JWT
```http
POST /api/auth/token
Content-Type: application/json

{"username":"admin","password":"votre-mot-de-passe"}
```
Utilisez `Authorization: Bearer <access_token>` pour les requÃªtes API. RÃ©glez `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES` et `SECRET_KEY` dans `.env`.

## Frontend (refonte mobile first)
Interface en HTML/CSS/JS natifs (modules ES), sans build. ThÃ¨me clair/sombre, polices auto-hÃ©bergÃ©es, PWA installable.
- `app/views/` : `base.html` (coque), `dashboard.html` et `event.html` (Ã©tendent `base`), `login.html`.
- `app/static/js/` : `core.js` (API, composants), `home.js` (Ã©vÃ©nements, Ã©quipe, profil), `event.js` (aperÃ§u, invitÃ©s, suivi, gestion), `scanner.js` (camÃ©ra, NFC, saisie, hors ligne), `offline.js` (file IndexedDB, cache), `vendor/jsqr.js` (lecteur QR de secours pour iPhone/Firefox).
- `app/static/sw.js` est servi Ã  la racine par la route `/sw.js` (ajoutÃ©e dans `main.py`) pour que le mode hors ligne couvre `/` et `/event/...`.
- Onglets selon le rÃ´le : agent (AperÃ§u, Scanner, InvitÃ©s), superviseur (+ Suivi), administrateur (+ GÃ©rer).

## QR codes indÃ©pendants par Ã©vÃ©nement
- Contenu du QR : `IA1.<id_evenement>.<jeton>`. Le jeton reste alÃ©atoire et unique ; l'identifiant d'Ã©vÃ©nement le rattache Ã  son Ã©vÃ©nement (`app/services/qr.py`).
- Au contrÃ´le (`/lookup`) et Ã  la synchronisation (`/sync`), un QR d'un autre Ã©vÃ©nement est refusÃ© avec un message explicite (409 / `rejected`). L'interface le dÃ©tecte aussi hors ligne.
- Dans le dossier designer, les images sont nommÃ©es `QR_CODES/E<id Ã©vÃ©nement sur 3 chiffres>_INV-xxxx.png` : deux Ã©vÃ©nements ne peuvent plus se mÃ©langer. L'Excel, le PDF et les instructions indiquent le numÃ©ro d'Ã©vÃ©nement.
- CompatibilitÃ© : les QR dÃ©jÃ  imprimÃ©s (jeton seul) restent valides pour leur Ã©vÃ©nement. RÃ©gÃ©nÃ©rer le dossier produit des images au nouveau format.


## Organisations et abonnements (premiÃ¨re tranche multi-organisation)

- Les donnÃ©es des Ã©vÃ©nements et des comptes sont rattachÃ©es Ã  une organisation (`organization_id`). Les Ã©vÃ©nements et comptes de l'ancienne base sont conservÃ©s et rattachÃ©s Ã  **Organisation principale** lors de la migration additive au dÃ©marrage.
- Le compte administrateur initial (`ADMIN_USERNAME`) est promu superadministrateur lors de cette migration. Il peut consulter les organisations et gÃ©rer les abonnements.
- Une organisation peut Ãªtre crÃ©Ã©e par le superadministrateur depuis l'onglet **Organisations**, ou s'inscrire depuis l'Ã©cran de connexion. Chaque crÃ©ation dÃ©clenche un essai de 14 jours avec les fonctionnalitÃ©s avancÃ©es.
- L'administrateur d'une organisation ne peut consulter que les Ã©vÃ©nements et les comptes de son organisation. Les contrÃ´les d'accÃ¨s sont appliquÃ©s cÃ´tÃ© API, pas seulement dans l'interface.
- Les Ã©vÃ©nements crÃ©Ã©s pendant une pÃ©riode d'abonnement sont comptabilisÃ©s, y compris lorsqu'ils sont terminÃ©s ou archivÃ©s. Le quota bloque uniquement la crÃ©ation de nouveaux Ã©vÃ©nements ; les Ã©vÃ©nements existants restent consultables et exploitables aprÃ¨s expiration.
- Le superadministrateur dÃ©finit les formules (quota d'Ã©vÃ©nements, fonctionnalitÃ©s avancÃ©es), puis active manuellement un abonnement pour une organisation. `event_limit = -1` signifie illimitÃ©.

### Routes principales de cette tranche

- `POST /api/organizations/register` : inscription publique d'une organisation et crÃ©ation de son compte administrateur (essai de 14 jours).
- `GET /superadmin/api/organizations` : liste globale des organisations et abonnements.
- `POST /superadmin/api/organizations` : crÃ©ation d'une organisation par le superadministrateur.
- `GET /superadmin/api/plans` et `POST /superadmin/api/plans` : consultation et crÃ©ation des formules.
- `PUT /superadmin/api/organizations/{organization_id}/subscription` : activation, suspension ou clÃ´ture manuelle d'un abonnement.
- `POST /admin/api/events` : crÃ©ation d'un Ã©vÃ©nement dans l'organisation du compte (le superadministrateur peut prÃ©ciser `organization_id`). Le quota est vÃ©rifiÃ© cÃ´tÃ© serveur.

Les migrations sont additives et ne suppriment pas les tables existantes. Avant de dÃ©ployer sur une base rÃ©elle, effectuer une sauvegarde. Cette premiÃ¨re tranche ne remplace pas encore un audit de sÃ©curitÃ© de production : prÃ©voir notamment limitation de dÃ©bit sur l'inscription/connexion, vÃ©rification d'adresse e-mail, politique de rÃ©cupÃ©ration de compte et tests de sÃ©curitÃ©.


---

# Phase 2 â€” modules mÃ©tier, sÃ©curitÃ© et migrations Alembic

## Migration de base de donnÃ©es (obligatoire)

Le schÃ©ma n'est plus crÃ©Ã© automatiquement au dÃ©marrage. **Alembic est la source de vÃ©ritÃ© des migrations.** Avant `uvicorn`, exÃ©cutez :

```powershell
alembic upgrade head
alembic current
```

- `0001_bootstrap` adopte aussi une base MVP existante non versionnÃ©e : il crÃ©e les tables manquantes et ajoute les colonnes manquantes sans supprimer les Ã©vÃ©nements, utilisateurs, invitations ou passages.
- `0002_badge_token` sÃ©pare le jeton de gestion personnelle du jeton prÃ©sent dans le QR du badge.
- Pour une base existante, faites une sauvegarde avant la migration. La migration d'adoption a Ã©tÃ© testÃ©e sur le schÃ©ma de l'archive MVP initiale.
- Pour une nouvelle installation, `alembic upgrade head` crÃ©e toutes les tables. Ne relancez pas `Base.metadata.create_all()` manuellement.
- Les downgrades du socle sont volontairement non destructifs; pour revenir en arriÃ¨re, restaurez une sauvegarde validÃ©e plutÃ´t que de supprimer des donnÃ©es mÃ©tier.

## 1. Invitations de mariage

Types gÃ©rÃ©s : individuelle, couple, famille, groupe et type personnalisÃ©. Une invitation possÃ¨de une rÃ©fÃ©rence, un QR opaque et un quota indÃ©pendant; les passages restent progressifs et ne peuvent dÃ©passer ce quota.

- CrÃ©ation manuelle : `POST /admin/api/events/{event_id}/invitations`.
- Modification : `PATCH /admin/api/events/{event_id}/invitations/{invitation_id}` (le quota ne peut pas passer sous le nombre dÃ©jÃ  entrÃ©).
- Import Excel/CSV : `POST /admin/api/events/{event_id}/import`.
- PDF consolidÃ© : `GET /admin/api/events/{event_id}/invitations.pdf`.
- PDF personnalisÃ©s par invitation regroupÃ©s dans un ZIP : `GET /admin/api/events/{event_id}/invitations/batch-pdf`.
- Dossier designer existant : `GET /admin/api/events/{event_id}/designer-pack`.

Chaque PDF personnalisÃ© contient le nom, le type, la rÃ©fÃ©rence, le quota, la date/lieu et le QR unique de l'invitation.

## 2. ConfÃ©rences : inscription, validation, liste d'attente et badges

Ã€ la crÃ©ation d'un Ã©vÃ©nement, choisir `event_type=conference` et dÃ©finir Ã©ventuellement `capacity`. L'administrateur ouvre ou ferme le formulaire via `PATCH /admin/api/events/{event_id}/conference`. Le lien public est `/conference/{registration_token}`.

- Inscription publique : `POST /api/public/conferences/{registration_token}/register`.
- VÃ©rification d'e-mail Ã  usage unique, valable 24 heures : `GET /api/public/conferences/verify/{token}`.
- Liste et modÃ©ration : `GET /admin/api/events/{event_id}/registrations`, puis `PATCH /admin/api/events/{event_id}/registrations/{registration_id}`.
- Ajout manuel : `POST /admin/api/events/{event_id}/registrations/manual`.
- Import Excel/CSV : `POST /admin/api/events/{event_id}/registrations/import` (colonnes `nom_complet` et `email` obligatoires; tÃ©lÃ©phone, organisation et catÃ©gorie facultatifs).
- Badge PDF individuel : `GET /api/public/conferences/badge/{public_token}`.
- ContrÃ´le du QR badge : `POST /checkin/api/conferences/{event_id}/scan`. Le badge utilise un jeton distinct du lien de gestion personnelle.

**RÃ¨gle de capacitÃ© actuelle :** seules les inscriptions `accepted` rÃ©servent une place. `pending`, `rejected`, `cancelled` et `waitlist` ne consomment pas de place. Une acceptation demandÃ©e lorsque la capacitÃ© est pleine est placÃ©e automatiquement en liste d'attente. Lorsqu'une place acceptÃ©e est annulÃ©e ou refusÃ©e, le premier participant de la liste d'attente est promu automatiquement. Cette rÃ¨gle reste configurable dans une Ã©volution ultÃ©rieure.

Les badges sont des PDF individuels. Le contrÃ´le de badge exige une connexion rÃ©seau; contrairement aux scans d'invitations mariage, aucun badge confÃ©rence n'est acceptÃ© hors ligne.

## 3. Programme de l'Ã©vÃ©nement

- Consultation par les membres affectÃ©s : `GET /api/events/{event_id}/program`.
- CrÃ©ation / modification / suppression par administrateur : `POST`, `PUT`, `DELETE /admin/api/events/{event_id}/program[/{item_id}]`.
- Export PDF : `GET /api/events/{event_id}/program.pdf`.
- Le programme chronologique est aussi visible sur le formulaire public de confÃ©rence.

Chaque sÃ©quence comporte titre, description, dÃ©but, fin, salle/lieu et intervenant.

## 4. Ã‰quipe, tÃ¢ches et historique

- Affecter un membre : `POST /admin/api/events/{event_id}/assignments`.
- Retirer un membre : `DELETE /admin/api/events/{event_id}/assignments/{user_id}`. Les tÃ¢ches de ce membre sont dÃ©sassignÃ©es et l'action est historisÃ©e.
- Lister les tÃ¢ches : `GET /api/events/{event_id}/tasks`.
- CrÃ©er : `POST /admin/api/events/{event_id}/tasks`. L'utilisateur doit d'abord Ãªtre affectÃ© Ã  l'Ã©quipe de l'Ã©vÃ©nement.
- Mettre Ã  jour : `PATCH /api/events/{event_id}/tasks/{task_id}`. Un agent ne peut changer que le statut de ses propres tÃ¢ches.
- Historique dÃ©taillÃ© : `GET /api/events/{event_id}/tasks/{task_id}/history`.

Les actions sont aussi inscrites dans le journal d'audit gÃ©nÃ©ral.

## 5. Notifications internes et push

- Liste : `GET /api/notifications`.
- Marquer comme lue : `POST /api/notifications/{notification_id}/read`.
- ClÃ© publique VAPID : `GET /api/push/public-key`.
- Enregistrer / retirer un appareil : `POST` / `DELETE /api/push/subscribe`.

Le panneau de notifications est ajoutÃ© Ã  l'interface existante. L'utilisateur doit autoriser les notifications du navigateur. Les notifications internes fonctionnent sans VAPID; les push nÃ©cessitent `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` et le paquet `pywebpush`. Aucun service d'envoi d'e-mail n'est configuré; les e-mails servent uniquement de coordonnées.

## 6. Hors ligne et synchronisation multi-appareils

- Les fichiers statiques, polices, icÃ´nes et ressources de l'application sont servis localement et mis en cache par le service worker. Les API mÃ©tier ne sont jamais mises en cache comme si elles Ã©taient Ã  jour.
- Les passages mariage hors ligne sont stockÃ©s dans IndexedDB et synchronisÃ©s avec un identifiant client unique. Le verrou `navigator.locks` Ã©vite deux synchronisations concurrentes dans plusieurs onglets du mÃªme navigateur lorsqu'il est disponible.
- La base impose l'unicitÃ© des identifiants idempotents; le serveur reconnaÃ®t les renvois dÃ©jÃ  reÃ§us et signale les conflits au lieu de masquer un dÃ©passement de quota.
- PostgreSQL et `SELECT ... FOR UPDATE` sont requis pour la sÃ©rialisation correcte des contrÃ´les simultanÃ©s sur plusieurs appareils. SQLite reste adaptÃ© au dÃ©veloppement mono-instance, pas Ã  la validation de quota Ã  fort parallÃ©lisme.
- Deux tÃ©lÃ©phones totalement dÃ©connectÃ©s ne peuvent pas connaÃ®tre le scan de l'autre en temps rÃ©el. Un passage hors ligne reste provisoire jusqu'Ã  sa synchronisation. Les badges confÃ©rence nÃ©cessitent le rÃ©seau.

## 7. SÃ©curitÃ© et production

- Hachage des mots de passe Argon2id (pwdlib, avec repli Argon2id natif si pwdlib n'est pas installÃ©).
- Les inscriptions publiques sont modérées par l'organisateur; le lien de suivi est remis sur la page après l'inscription.
- Limitation de dÃ©bit sur login, crÃ©ation d'organisation et endpoints publics. En production, elle utilise Redis partagÃ©; le repli mÃ©moire est rÃ©servÃ© au dÃ©veloppement.
- En-tÃªtes de sÃ©curitÃ©, cookies de session `Secure` en production, HSTS, contrÃ´le des hÃ´tes autorisÃ©s.
- En production, l'application refuse de dÃ©marrer sans secrets robustes, PostgreSQL, Redis, HTTPS dans `PUBLIC_BASE_URL` et `ALLOWED_HOSTS`.
- Sauvegarde : `python scripts/backup_db.py`. Pour PostgreSQL, `pg_dump` doit Ãªtre disponible. Planifiez cette commande (Task Scheduler/cron), chiffrez et testez rÃ©guliÃ¨rement les restaurations.
- Tests : `python -m pytest -q`; syntaxe JS : `node --check` sur les modules.

### Variables de production Ã  renseigner

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB
SECRET_KEY=<secret aleatoire 32+ caracteres>
JWT_SECRET_KEY=<autre secret aleatoire 32+ caracteres>
RATE_LIMIT_REDIS_URL=redis://HOST:6379/0
ALLOWED_HOSTS=app.example.com
PUBLIC_BASE_URL=https://app.example.com
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:admin@example.com
```

**Ã‰tat de validation :** migrations Alembic testÃ©es sur une base neuve et sur l'ancienne structure MVP; tests unitaires et tests d'intÃ©gration des principaux parcours exÃ©cutÃ©s localement. Cela ne remplace pas un audit de pÃ©nÃ©tration, un test de charge multi-appareils ni une recette push VAPID sur les domaines de production.

La synchronisation de fond `Background Sync` est utilisÃ©e quand le navigateur le prend en charge; les conflits restent en file locale pour Ãªtre expliquÃ©s Ã  l'opÃ©rateur lors de la prochaine ouverture. Les QR de confÃ©rence ne sont jamais acceptÃ©s hors ligne.

## Mise en production

Utilisez [`.env.production.example`](.env.production.example) comme inventaire, puis configurez chaque valeur dans le gestionnaire de secrets de l'hÃ©bergeur. Ne dÃ©ployez pas les valeurs `REPLACE_*` et ne commitez jamais de vrai fichier `.env`.

### Variables obligatoires

| Variable | Valeur attendue |
|---|---|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY`, `JWT_SECRET_KEY` | Deux secrets alÃ©atoires distincts d'au moins 32 caractÃ¨res |
| `DATABASE_URL` | PostgreSQL accessible depuis l'application (`postgresql+psycopg://...`) |
| `RATE_LIMIT_REDIS_URL` | Redis partagÃ© et accessible ; `rediss://` si le fournisseur active TLS |
| `PUBLIC_BASE_URL` | URL HTTPS publique complÃ¨te |
| `ALLOWED_HOSTS` | Noms d'hÃ´te exacts, sans `https://`, chemin ni joker |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Identifiants initiaux explicites ; mot de passe unique d'au moins 16 caractÃ¨res |

`ADMIN_EMAIL` est une coordonnÃ©e de contact uniquement : aucun courriel sortant n'est envoyÃ©. `ADMIN_SYNC_PASSWORD=false` Ã©vite que le mot de passe du gestionnaire de secrets remplace celui du superadministrateur Ã  chaque redÃ©marrage. Les trois variables VAPID activent les notifications push Web ; laissez les clÃ©s publiques et privÃ©es vides pour dÃ©sactiver cette fonction. GÃ©nÃ©rez des clÃ©s VAPID de production distinctes des clÃ©s de test.

### DÃ©ploiement

1. CrÃ©ez PostgreSQL et Redis privÃ©s, configurez leurs sauvegardes et autorisez uniquement le rÃ©seau de l'application.
2. CrÃ©ez deux secrets alÃ©atoires indÃ©pendants pour `SECRET_KEY` et `JWT_SECRET_KEY` (par exemple avec `python -c "import secrets; print(secrets.token_urlsafe(48))"`, deux fois). CrÃ©ez un mot de passe superadministrateur unique et stockez ces valeurs dans le gestionnaire de secrets.
3. Ajoutez le domaine public au DNS et activez TLS sur le reverse proxy. Configurez `PUBLIC_BASE_URL`, `ALLOWED_HOSTS` et `TRUSTED_PROXY_COUNT` en fonction de l'infrastructure rÃ©elle. Le proxy doit transmettre `Host`, `X-Forwarded-For` et `X-Forwarded-Proto`; n'exposez pas directement le port applicatif Ã  Internet.
4. Utilisez Python 3.12, installez `requirements.txt`, puis lancez `alembic upgrade head` comme tÃ¢che de dÃ©ploiement avant de dÃ©marrer la nouvelle version.
5. DÃ©marrez l'application avec un processus ASGI, par exemple `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1`. Remplacez l'adresse de proxy par l'adresse ou le CIDR rÃ©el du proxy ; n'utilisez pas `*` si le port n'est pas isolÃ© par le rÃ©seau.
6. L'application valide la configuration et teste la connexion Redis au dÃ©marrage. VÃ©rifiez la page de connexion, les inscriptions publiques, le scan, les journaux et le push si activÃ©, puis programmez des sauvegardes PostgreSQL chiffrÃ©es et un essai de restauration.

Ne copiez pas la base SQLite locale en production. Les mots de passe ne peuvent pas Ãªtre rÃ©cupÃ©rÃ©s par e-mail : prÃ©voyez un administrateur de secours et une procÃ©dure d'assistance. Le dÃ©ploiement reste Ã  finaliser avec les vrais domaines, identifiants PostgreSQL/Redis, secrets, TLS, sauvegardes et tests de recette de l'hÃ©bergeur.
