---
name: e2e-roles
description: Exécute les essais dans le navigateur par type de compte (superadmin, admin, superviseur, agent, participant public, organisation tierce).
---

# Skill : e2e-roles

## Rôle
Testeur de bout en bout spécialisé dans la conformité des rôles et des permissions dans l'interface utilisateur.
Règle stricte : **lecture seule du code** — aucun fichier de l'application n'est modifié par ce skill.

## Référence de vérité
- [GEMINI.md](../../../GEMINI.md) (section « Essais dans le navigateur »).
- [tests/test_roles_matrix.py](../../../tests/test_roles_matrix.py) : la matrice des droits côté API fait foi ; l'interface doit lui être rigoureusement fidèle.

## Environnement et Outils
- Serveurs MCP :
  - `playwright-admin` : session administrateur / superadmin.
  - `playwright-agent` : session agent / superviseur indépendante (permet de tester l'invalidation immédiate inter-sessions).
  - `chrome-devtools` : diagnostic console (violations CSP), requêtes réseau (statuts HTTP, en-têtes CSP) et émulation mobile (390×844) puis bureau.
- Base de test jetable :
  - `ENVIRONMENT=development`
  - `DATABASE_URL=sqlite:///./e2e.db`
  - `RATE_LIMIT_DISABLED=true`

## Parcours par rôle à vérifier

Pour **chaque compte**, contrôler 3 aspects :
1. **Ce qui est VISIBLE** : boutons, onglets, actions affichées.
2. **Ce qui est INTERDIT** : accès direct par URL ou formulaire manipulé (attendu : refus clair ou 404, jamais de boucle de redirection ni de crash).
3. **Qualité d'exécution** : console JS vierge de toute violation CSP, aucun appel HTTP 5xx ou 4xx inattendu.

### 1. Superadmin (Plateforme)
- Accès à l'onglet Organisations.
- Création d'une organisation, suspension et réactivation (vérifier coupure immédiate de l'admin lié).
- Modification de formule d'abonnement.
- Consultation du journal d'activité plateforme.
- Absence d'action d'événement direct (pas d'échec silencieux).

### 2. Admin (Organisation A)
- Tableau de bord et jauges de quota.
- Création d'événement (bloquée tant que l'e-mail n'est pas confirmé).
- Importation d'invités CSV/Excel.
- Gestion des invitations : création, révocation, réactivation, régénération de QR.
- Gestion d'équipe : création, changement de rôle, désactivation, réinitialisation de mot de passe (impossibilité de se désactiver soi-même ou de retirer le dernier admin).
- Changement de mot de passe provoquant la révocation immédiate des autres sessions.

### 3. Superviseur
- Périmètre restreint aux événements affectés.
- Consultation du tableau de bord d'accueil, agents en poste, journal d'activité.
- Dérogation / exception d'accès avec motif obligatoire.
- Refus strict d'accès à l'équipe, à l'abonnement, à la création d'événements et aux imports.

### 4. Agent (Terrain)
- Périmètre restreint à ses événements en cours.
- Recherche manuelle et passage d'invités.
- Mode hors-ligne PWA (2 passages enregistrés), reconnexion et synchronisation IndexedDB.
- Interdiction de modification des tâches d'autres agents ; refus sur toute route d'administration.
- Désactivation par l'admin : coupure immédiate dès l'appel suivant.

### 5. Participant public (Sans compte)
- Page publique de conférence.
- Formulaire d'inscription (tolérance à la double inscription sans doublon).
- Parcours de confirmation d'e-mail par lien sécurisé unique.
- Consultation du statut et téléchargement du badge individuel.
- Aucune surface administrative accessible.

### 6. Organisation tierce (Organisation B)
- Tentative d'accès aux URL et identifiants de l'organisation A : réponse **404 neutre** (« Introuvable »), aucune information divulguée.

## Livrables attendus
- Tableau récapitulatif par compte : `Visible` / `Interdit` / `Console CSP`.
- Liste des écarts vis-à-vis de `test_roles_matrix.py`.
- Signalement des anomalies classées : `BLOQUANT`, `IMPORTANT`, `MINEUR`.
