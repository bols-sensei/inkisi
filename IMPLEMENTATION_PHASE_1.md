# Implémentation — Phase 1 : organisations et abonnements

## Objectif

Faire évoluer le MVP existant vers une base multi-organisation sans remplacer son architecture MVC, ses écrans, son CSS local, ses flux d'invitations ni son contrôle QR.

## Fonctionnalités ajoutées

- Modèles `Organization`, `Plan` et `Subscription`.
- Liaison `organization_id` sur les comptes et les événements.
- Migration additive au démarrage : les anciens comptes et événements sont rattachés à `Organisation principale`; aucune table métier existante n'est supprimée.
- Promotion du compte `ADMIN_USERNAME` en `superadmin` lors de la migration initiale.
- Inscription publique d'une organisation via `POST /api/organizations/register`.
- Création d'organisation par le superadministrateur via `/superadmin/api/organizations`.
- Essai gratuit de 14 jours créé automatiquement avec le plan `trial` et les fonctionnalités avancées activées.
- Création de formules avec quota d'événements et indicateur de fonctionnalités avancées.
- Activation, suspension et expiration manuelles des abonnements par le superadministrateur.
- Vérification du quota côté serveur à la création d'un événement.
- Comptabilisation de tous les événements créés pendant la période d'abonnement, même s'ils sont ensuite terminés ou archivés.
- Isolation des données : un administrateur d'organisation ne peut pas lire les événements ni les comptes d'une autre organisation. Les routes de contrôle et de synchronisation vérifient aussi l'organisation.
- Compatibilité des anciennes sessions et anciens jetons sans `organization_id` : l'identité est rechargée depuis la base pendant la transition.
- Interface de connexion : formulaire d'inscription d'organisation.
- Accueil superadministrateur : onglet Organisations, création d'organisation, création de formules et gestion des abonnements.

## Règles appliquées

- Essai : 14 jours.
- `event_limit = -1` : quota illimité.
- Le quota concerne les événements créés pendant la période courante, pas seulement les événements actifs.
- Après expiration ou suspension, la création de nouveaux événements est bloquée.
- Les événements déjà créés restent consultables et utilisables pour ne pas interrompre une réception en cours.
- Aucun paiement en ligne n'est ajouté dans cette phase : l'activation reste manuelle.

## Vérifications effectuées

- Compilation Python (`compileall`).
- Vérification syntaxique des scripts JavaScript modifiés.
- Démarrage de l'application sur une base SQLite de test.
- Vérification de la création du superadministrateur et du plan d'essai.
- Vérification de l'inscription de deux organisations et de l'essai de 14 jours.
- Vérification de la création d'événement dans une organisation.
- Vérification qu'un administrateur d'une autre organisation reçoit une réponse 404 en tentant de consulter cet événement.
- Vérification de la migration d'une ancienne base : événement conservé, compte conservé, organisation attribuée et ancienne session actualisée.

La dépendance `pwdlib` n'étant pas disponible dans l'environnement de vérification, les tests d'intégration ont utilisé un adaptateur temporaire local uniquement pour contourner l'absence de cette dépendance pendant les tests. Cet adaptateur n'est pas inclus dans le projet; le projet conserve son mécanisme Argon2 existant et ses dépendances d'origine.

## Éléments non encore implémentés

Cette livraison constitue la première tranche, pas la totalité du cahier des charges :

1. Gestion complète des invitations mariage (types individuel, couple, famille, groupe, personnalisé) et génération PDF en lot.
2. Inscription publique conférence, validation, liste d'attente et badges individuels sécurisés.
3. Programme de l'événement et export PDF.
4. Affectation de tâches/responsabilités à l'équipe et historique détaillé.
5. Notifications internes et push.
6. Renforcement du mode hors ligne et stratégie de synchronisation multi-appareils.
7. Tests de sécurité, limitation de débit, vérification e-mail, sauvegardes et configuration de production.

## Démarrage

La procédure existante reste la même :

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Avant un déploiement réel, remplacer impérativement les secrets et mots de passe par des valeurs fortes et sauvegarder la base existante avant la première migration.
