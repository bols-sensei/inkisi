# Rapport d'implÃ©mentation â€” Phase 2

Date : 31 octobre 2026  
Base : archive `reception_evenementielle_phase1.zip`  
Version applicative : 0.3.0

## RÃ©sumÃ©

La phase 2 ajoute les huit axes demandÃ©s au MVP, en conservant FastAPI, SQLAlchemy, les vues HTML/JS existantes, la feuille CSS locale et le parcours d'invitations dÃ©jÃ  en place. Les Ã©volutions sont additives; aucune refonte globale du design n'a Ã©tÃ© faite.

## 1. Invitations mariage

- Types gÃ©rÃ©s : individuelle, couple, famille, groupe et type personnalisÃ©.
- CrÃ©ation et modification manuelles depuis l'interface de gestion.
- Import CSV/XLSX conservÃ©; les types personnalisÃ©s sont prÃ©servÃ©s.
- GÃ©nÃ©ration d'un PDF par invitation, avec QR propre Ã  l'invitation, rÃ©fÃ©rence et quota.
- Les PDF individuels sont regroupÃ©s dans une archive ZIP.
- Le PDF consolidÃ© et le dossier designer existants restent disponibles.
- Le quota ne peut pas Ãªtre abaissÃ© sous le nombre de personnes dÃ©jÃ  entrÃ©es.

## 2. ConfÃ©rences

- CrÃ©ation d'un Ã©vÃ©nement de type confÃ©rence avec capacitÃ© optionnelle.
- Ouverture/fermeture du formulaire public et lien d'inscription partageable.
- Inscription publique individuelle avec catÃ©gories et vÃ©rification e-mail.
- Ajout manuel et import CSV/XLSX des participants.
- DÃ©tection d'une adresse dÃ©jÃ  inscrite sans rÃ©vÃ©ler le lien privÃ© de gestion.
- Lien de gestion personnel permettant de consulter et modifier les informations (l'adresse e-mail reste verrouillÃ©e sans nouvelle vÃ©rification).
- Badge PDF individuel et jeton QR distinct du lien personnel.
- Route de contrÃ´le des badges et refus des badges non vÃ©rifiÃ©s/non acceptÃ©s.
- Liste d'attente et promotion automatique au premier siÃ¨ge libÃ©rÃ©.

**RÃ¨gle de capacitÃ© appliquÃ©e :** seuls les statuts `accepted` rÃ©servent une place. `pending`, `rejected`, `cancelled` et `waitlist` ne consomment pas la capacitÃ©. Une demande d'acceptation quand la capacitÃ© est atteinte devient `waitlist`. L'annulation/refus d'une inscription acceptÃ©e libÃ¨re le siÃ¨ge et promeut la premiÃ¨re inscription vÃ©rifiÃ©e de la liste d'attente.

## 3. Programme

- CrÃ©ation, modification, suppression et consultation des sÃ©quences.
- DonnÃ©es : titre, description, date/heure de dÃ©but et de fin, salle/lieu, intervenant.
- Affichage chronologique dans l'interface de l'Ã©vÃ©nement.
- Programme visible aussi sur la page publique de la confÃ©rence.
- Export PDF.

## 4. TÃ¢ches et responsabilitÃ©s

- CrÃ©ation de tÃ¢ches liÃ©es Ã  un Ã©vÃ©nement.
- Affectation Ã  un membre dÃ©jÃ  affectÃ© Ã  l'Ã©vÃ©nement.
- Statuts, prioritÃ© et Ã©chÃ©ance.
- Les agents ne peuvent modifier que le statut de leurs propres tÃ¢ches.
- Historique dÃ©taillÃ© des crÃ©ations et modifications.
- Retrait d'un membre de l'Ã©vÃ©nement; ses tÃ¢ches sont dÃ©sassignÃ©es et historisÃ©es.
- Les affectations et changements pertinents dÃ©clenchent des notifications internes.

## 5. Notifications

- Notifications internes consultables et marquables comme lues.
- Panneau de notifications ajoutÃ© dans l'en-tÃªte de l'application.
- Enregistrement d'un abonnement push par appareil.
- Push Web via VAPID/pywebpush lorsque les clÃ©s et le consentement navigateur sont disponibles.
- Envoi d’e-mails désactivé ; les notifications restent internes ou push Web.

## 6. Hors ligne et synchronisation

- Service worker avec cache versionnÃ© des fichiers statiques locaux.
- File de passages mariage dans IndexedDB.
- Background Sync lorsque le navigateur le supporte.
- Verrou de synchronisation entre onglets via `navigator.locks` lorsqu'il est disponible.
- ClÃ©s idempotentes uniques cÃ´tÃ© base; les renvois dÃ©jÃ  traitÃ©s sont reconnus et les collisions sont signalÃ©es.
- Les conflits restent visibles dans l'interface au retour au premier plan.
- Les scans de badges confÃ©rence exigent le rÃ©seau.

**Limite conservÃ©e :** deux appareils complÃ¨tement dÃ©connectÃ©s ne peuvent pas se coordonner. Un passage hors ligne reste provisoire jusqu'Ã  validation par le serveur. PostgreSQL et les verrous de lignes sont nÃ©cessaires pour sÃ©rialiser correctement les contrÃ´les simultanÃ©s.

## 7. SÃ©curitÃ© et production

- Les parcours ne dépendent pas d'un service d'e-mail sortant.
- Limitation de dÃ©bit sur les routes d'authentification et les routes publiques.
- Redis partagÃ© obligatoire en production; limitation mÃ©moire locale uniquement pour dÃ©veloppement.
- En-tÃªtes de sÃ©curitÃ©, cookie Secure, HSTS et contrÃ´le des hÃ´tes en production.
- Refus de dÃ©marrer en production si les secrets, PostgreSQL, Redis, HTTPS ou les hÃ´tes autorisÃ©s ne sont pas configurÃ©s.
- Script de sauvegarde SQLite et PostgreSQL (`scripts/backup_db.py`).
- Tests unitaires des rÃ¨gles de capacitÃ©, import CSV, types personnalisÃ©s et hachage de mot de passe.

## 8. Alembic

- Ajout de `alembic.ini`, `alembic/env.py` et des rÃ©visions versionnÃ©es.
- `0001_bootstrap` crÃ©e les tables manquantes et ajoute les colonnes manquantes sans effacer les donnÃ©es d'une base MVP non versionnÃ©e.
- `0002_badge_token` garantit la sÃ©paration du jeton de badge et du jeton de gestion.
- Le `create_all()` et les migrations SQL ad hoc ont Ã©tÃ© retirÃ©s du dÃ©marrage applicatif : la commande obligatoire est `alembic upgrade head`.
- `alembic check` retourne `No new upgrade operations detected` sur une base neuve.

## Tests exÃ©cutÃ©s

- `python -m pytest -q` : **13 tests rÃ©ussis**.
- `python -m compileall -q app alembic scripts tests` : rÃ©ussi.
- `node --check` sur les modules JavaScript (hors bundle jsQR tiers) : rÃ©ussi.
- `alembic upgrade head` sur une base neuve : rÃ©ussi.
- `alembic check` sur une base neuve : aucun Ã©cart dÃ©tectÃ©.
- Migration d'adoption d'une base construite avec le schÃ©ma de l'archive MVP initiale : rÃ©ussie; compte et Ã©vÃ©nement historiques conservÃ©s et rattachÃ©s Ã  l'organisation principale au dÃ©marrage.
- Test d'intÃ©gration des principaux parcours : invitations et ZIP PDF, affectation et tÃ¢ches, inscription confÃ©rence, vÃ©rification e-mail, capacitÃ©/liste d'attente/promotion, badge et scan, programme PDF, notifications : rÃ©ussi.

## Installation / mise Ã  jour

AprÃ¨s installation des dÃ©pendances et configuration de `.env` :

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Pour une base dÃ©jÃ  utilisÃ©e, faire une sauvegarde avant la premiÃ¨re migration. Le script de sauvegarde peut Ãªtre exÃ©cutÃ© avec :

```powershell
python scripts/backup_db.py
```

## Ã€ faire avant production rÃ©elle

- Renseigner et tester les paramètres VAPID du domaine rÃ©el.
- DÃ©ployer PostgreSQL et Redis; tester les contrÃ´les concurrents sur plusieurs appareils.
- Planifier les sauvegardes, conserver une copie hors serveur et effectuer des essais de restauration.
- Faire une recette manuelle sur les navigateurs/tÃ©lÃ©phones ciblÃ©s, notamment camÃ©ra, push et Background Sync.
- Effectuer un audit de sÃ©curitÃ© et un test de charge/pÃ©nÃ©tration indÃ©pendant. Les tests de cette phase ne constituent pas une certification de sÃ©curitÃ©.

