# Déploiement sur Render

Le fichier `render.yaml` décrit le service Web, PostgreSQL et Key Value (compatible Redis). Les trois services sont placés à Francfort pour utiliser les connexions privées Render dans la même région. Les plans choisis sont payants et minimaux pour démarrer : confirme leur prix dans le tableau de bord Render avant de créer les ressources.

## Création du Blueprint

1. Ouvre Render, puis **New → Blueprint** et connecte `bols-sensei/inkisi`.
2. Sélectionne la branche `production-ready`, qui contient l’instantané propre poussé depuis ce projet.
3. Render détecte `render.yaml`. Vérifie les ressources et les plans avant de sélectionner **Apply**.
4. À la demande de Render, saisis un mot de passe superadministrateur unique d’au moins 16 caractères. Render génère automatiquement `SECRET_KEY` et `JWT_SECRET_KEY` séparément.
5. Attends le provisionnement des services. Le premier déploiement installe les dépendances, exécute `alembic upgrade head`, puis démarre Uvicorn.
6. Ouvre l’URL `onrender.com` affichée sur la page du service et connecte-toi avec `ADMIN_USERNAME=platform-admin` et le mot de passe fourni au Blueprint.

Le Blueprint réutilise automatiquement l’URL publique et le nom d’hôte Render du service pour `PUBLIC_BASE_URL` et `ALLOWED_HOSTS`. La connexion PostgreSQL est normalisée vers le pilote psycopg 3. Redis et PostgreSQL refusent les connexions publiques ; l’application les joint via le réseau privé Render.

## Après le premier déploiement

- Dans **Events**, vérifie que le déploiement est `Live` et que le contrôle de santé `/` réussit.
- Dans **Environment**, vérifie que `ENVIRONMENT=production`, que les secrets ont été générés et que le `DATABASE_URL` et `RATE_LIMIT_REDIS_URL` sont liés aux services du Blueprint. Ne copie jamais les chaînes de connexion dans un dépôt ou un message.
- Configure la sauvegarde PostgreSQL et vérifie la procédure de restauration avant les données réelles.
- Le fichier local ignoré `.env.render` contient une paire VAPID générée pour ce déploiement. Remplace d’abord son mot de passe provisoire, puis utilise **Environment → Add from .env** sur le service Web pour importer le fichier. `VAPID_SUBJECT` est repris automatiquement de l’URL Render. Conserve une copie privée des clés ; ne les régénère pas après que les navigateurs se sont abonnés.
- Si tu ajoutes un domaine personnalisé, règle `PUBLIC_BASE_URL` sur son URL HTTPS et ajoute son nom exact à `ALLOWED_HOSTS`, puis redéploie.
- Un commit poussé sur `production-ready` déclenche un nouveau déploiement. Les migrations s’exécutent avant la mise en service.

## Opérations

- Les migrations sont lancées par `preDeployCommand`; ne les lance pas en parallèle depuis plusieurs shells.
- Le service démarre avec un seul worker Uvicorn. C’est volontaire : le démarrage initialise aussi les données plateforme et le worker Web Push.
- Les courriels sortants sont désactivés dans l’application; aucune variable SMTP n’est nécessaire.
- Render Key Value est configuré sans accès externe. L’application l’utilise uniquement par son URL privée.

Références officielles : [Blueprint YAML](https://render.com/docs/blueprint-spec), [versions Python](https://render.com/docs/python-version), [PostgreSQL](https://render.com/docs/postgresql), [Key Value](https://render.com/docs/key-value).
