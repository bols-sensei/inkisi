# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Agents de contrôle (terrain)** : Équipés d'un smartphone, debout à l'entrée de la réception ou de la conférence, souvent en conditions contraignantes (plein soleil, pénombre nocturne, réseau mobile intermittent ou absent, manipulation à une main). Mission : scanner les QR codes ou rechercher manuellement les invités, valider les entrées dans la limite des quotas et signaler les exceptions.
- **Superviseurs (terrain & régie)** : Gestion des agents affectés, validation des dérogations et exceptions avec motif obligatoire, suivi en temps réel du flux d'accès et traitement des conflits de synchronisation.
- **Organisateurs / Administrateurs (bureau & régie)** : Propriétaires d'organisations SaaS gérant des réceptions privées (mariages, galas) et conférences. Mission : paramétrer les événements, importer les listes d'invités (Excel/CSV), générer les packs d'exportation pour les designers et papetiers (ZIP, manifestes, QR codes individuels), piloter les inscriptions publiques et listes d'attente, suivre le journal d'activité et exporter les données.
- **Superadministrateurs (plateforme SaaS)** : Gestion des organisations clientes, attribution des formules et abonnements (quotas d'événements créés, fonctionnalités avancées) et surveillance de la plateforme.
- **Participants / Invités (publics)** : Inscription en ligne aux conférences, vérification d'adresse e-mail, consultation et mise à jour autonome de leurs informations, téléchargement de leur badge individuel sécurisé.

## Product Purpose
Plateforme SaaS multi-organisation dédiée à la gestion des invitations, du contrôle d'accès haute vitesse et des inscriptions pour réceptions privées (mariages, soirées) et conférences professionnelles. Le produit garantit l'intégrité absolue du contrôle d'accès : zéro intrusion, zéro fuite de données personnelles dans les QR codes, fonctionnement ininterrompu même en cas de coupure réseau complète, et collaboration fluide entre organisateurs, créateurs de papeterie et équipes d'accueil sur le terrain.

## Positioning
- **Sécurité et confidentialité par conception** : Le QR code ne contient aucune donnée personnelle en clair, uniquement un jeton opaque lié à l'événement (`IA1.<id_evenement>.<jeton>`).
- **Pont papeterie et design physique** : Génération d'un dossier designer prêt pour l'atelier (manifeste Excel, PDF de correspondance avec QR, images PNG unitaires nommées par référence) permettant l'impression sur mesure de faire-part et invitations de prestige.
- **Résilience hors-ligne opérationnelle** : PWA mobile-first conçue pour fonctionner avec un réseau dégradé ou absent (IndexedDB, Service Worker, rejeu idempotent par `(evenement_id, clé)`), avec détection immédiate des conflits à la reconnexion.
- **Souveraineté et légèreté technique** : Zéro CDN externe, zéro framework JavaScript lourd, CSP stricte, hébergement autonome ou SaaS privé sans dépendances tierces opaques.

## Operating Context
- **Terrain (Jour J)** : Hall d'accueil, sas d'entrée extérieur ou intérieur. Contrôle debout, smartphone dans une main. Forte luminosité extérieure le jour, obscurité ou éclairages tamisés la nuit. Débit rapide attendu (quelques secondes par invité ou groupe).
- **Préparation (J-30 à J-1)** : Importation de fichiers invités (Excel/CSV), dédoublonnage, attribution des tables et des quotas, export du pack designer pour impression papier.
- **Conférences** : Formulaire public d'inscription, vérification e-mail à jeton sécurisé à usage unique (24h), gestion automatique de la capacité avec bascule en liste d'attente et promotion instantanée lors d'un désistement, génération et contrôle de badges PDF individuels.

## Capabilities and Constraints
- **Capacités confirmées** :
  - Multi-tenant strict : isolation hermétique par organisation avec réponse 404 systématique sur toute tentative d'accès croisé.
  - Gestion des types d'invitations (individuelle, couple, famille, groupe, personnalisé) avec quota strict (impossibilité de réduire un quota sous le nombre de personnes déjà entrées).
  - Gestion de conférences avec capacité finie, liste d'attente ordonnée et promotion automatique au premier siège libéré.
  - Programme de l'événement avec export PDF et affichage public.
  - Affectation des agents et gestion des tâches par événement avec historique et notifications.
  - Notifications internes et Web Push (VAPID/pywebpush).
  - Journal d'audit complet des actions administrateur et des passages.
  - Mode hors-ligne PWA pour les passages d'invitations mariage (les badges conférence nécessitent le réseau).
- **Contraintes techniques** :
  - Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Jinja2.
  - Vanilla HTML5 / CSS3 / ES Modules natifs. Aucun outil de build (pas de Webpack/Vite/npm build), aucun CDN externe.
  - CSP stricte (`script-src 'self'`) : interdiction totale des scripts inline et des attributs `onclick=`. Données transmises via `<script type="application/json">` analysé par le JS.
  - Sécurité des données : sanitisation des entrées pour PDF ReportLab (`safe.pdf_text`) et exports Excel (`openpyxl`), échappement strict contre les injections CSV/formule.
  - Base de données : SQLite en développement/test, PostgreSQL en production avec verrous de lignes (`with_for_update`) et Redis pour le rate-limiting.
- **Faits explicitement ouverts / non tranchés** :
  - Nom commercial définitif non arrêté à ce stade (titre de travail fonctionnel : « Réception événementielle »).
  - Passerelle de paiement en ligne non intégrée (abonnements gérés manuellement par le superadmin).

## Brand Commitments
- **Nom de travail** : Réception événementielle (nom de marque final à définir).
- **Langue** : Français (`fr`) intégral pour l'interface, les messages système, les notifications et la documentation.
- **Ton de communication** : Sobre, professionnel, rassurant, direct et d'une grande rigueur. Aucune fioriture ni jargon inutile. Messages d'erreur explicites et toujours accompagnés d'une action de reprise concrète.
- **Identité visuelle** : Mode applicatif (« Operate »), polices locales auto-hébergées, thèmes clair et sombre, contraste élevé pour lisibilité en plein soleil ou de nuit.

## Evidence on Hand
- Fichiers d'exemples et jeux de données réels : `dataset_500.csv`, `evenement_250_villes.csv`.
- Base de code fonctionnelle complète : `app/` (contrôleurs, modèles, services, vues Jinja, statiques JS/CSS).
- Migrations de base de données Alembic : `alembic/versions/0001_bootstrap.py` à `0004_integrity_audit.py`.
- Suite de tests automatisés : `tests/test_capacity_rules.py`, `tests/test_importers_and_security.py`, `tests/test_roles_matrix.py`, `tests/test_saas_lot1.py`, `tests/test_saas_lot2.py`.

## Product Principles
- **L'intégrité de la porte prime sur tout** : Rien ne doit bloquer ou ralentir la validation d'un invité à l'entrée d'un événement en cours (pas d'expiration d'abonnement bloquante au scan, tolérance totale aux pannes réseau).
- **Zéro donnée personnelle exposée** : Les supports physiques (QR codes imprimés) ne transportent aucune donnée nominative en clair, protégeant la vie privée des invités.
- **Isolation étanche et silencieuse** : Une organisation ne doit avoir aucune visibilité sur une autre ; toute tentative de franchissement de frontière se solde par un 404 neutre.
- **Sobriété et robustesse logicielle** : Pas de dépendances volatiles, pas de CDN tiers, stack autonome, scripts légers en ES natif pour une vitesse d'exécution instantanée sur mobile.
- **Fidélité au terrain** : Chaque écran doit être utilisable à une main sur mobile par un agent debout, avec un contraste franc et des retours d'état immédiats et indiscutables.

## Accessibility & Inclusion
- **Ergonomie mobile-first** : Cibles tactiles d'au moins 44×44px, disposition pensée pour l'usage à une main.
- **Accessibilité visuelle** : Contrastes élevés adaptés aux conditions extérieures lumineuses et aux environnements sombres, respect de `prefers-reduced-motion` et `prefers-color-scheme`.
- **Accessibilité cognitive et technique** : Annonces des résultats de scan via `aria-live`, pièges de focus verrouillés dans les modales et retours haptiques au scan lorsque disponibles.
