---
name: e2e
description: Exécute les parcours utilisateurs complets dans le navigateur réel via Playwright et Chrome DevTools MCP.
---

# Skill : e2e

## Rôle
Ingénieur de test bout en bout (E2E) réalisant des simulations réelles dans le navigateur via les serveurs MCP.
Règle stricte : **lecture seule du code** — aucun fichier source n'est modifié par ce skill.

## Dispositif de test navigateur
- `playwright-admin` : navigation scriptée de la session administrateur / organisateur.
- `playwright-agent` : session concurrente indépendante de l'agent de terrain (cookies isolés).
- `chrome-devtools` : diagnostic console (écoute des violations CSP), inspection réseau (codes HTTP, latences), simulation réseau hors-ligne et inspection IndexedDB/Service Worker.

## Environnement de simulation
- Base SQLite jetable dédiée :
  ```powershell
  $env:ENVIRONMENT="development"
  $env:DATABASE_URL="sqlite:///./e2e.db"
  $env:RATE_LIMIT_DISABLED="true"
  $env:ADMIN_USERNAME="root"
  $env:ADMIN_PASSWORD="RootPassword-123"
  $env:SECRET_KEY="e2e-secret-key"
  $env:PUBLIC_BASE_URL="http://localhost:8000"
  ```
- Initialisation et lancement du serveur en tâche d'arrière-plan :
  ```powershell
  if (Test-Path e2e.db) { Remove-Item e2e.db }
  & .venv/Scripts/alembic.exe upgrade head
  & .venv/Scripts/uvicorn.exe app.main:app --port 8000
  ```

## 8 Parcours utilisateurs complets à exécuter

1. **Inscription organisation & cycle de confirmation** :
   Inscription d'une nouvelle organisation → récupération du lien de confirmation renvoyé en mode développement → tentative de création d'événement avant confirmation (bloqué) → confirmation → création réussie.

2. **Cycle de vie de l'équipe & révocation immédiate** :
   Création d'un agent depuis l'interface admin → connexion concurrente sur la 2ème session `playwright-agent` → désactivation de l'agent depuis la session admin → rechargement de la session agent (la session doit mourir immédiatement sans boucle de redirection).

3. **Contrôle d'accès & Quotas** :
   Import CSV de 3 invités sur un événement « Brouillon » → tentative de scan (refus explicite) → passage de l'événement à « En cours » → validation par recherche manuelle → incrémentation du passage → blocage au dépassement de quota.

4. **Résilience des invitations & sécurité des exports** :
   Révocation d'une invitation → tentative de scan (refusé) → réactivation → régénération de jeton QR (l'ancien jeton est rendu invalide) → téléchargement du pack designer et PDF avec des données de test contenant des balises (`<b>`) et des formules Excel (`=1+1`) sans corruption.

5. **Mode Hors-ligne PWA & Synchronisation** :
   Événement en cours → coupure réseau simulée via Chrome DevTools → enregistrement de 2 passages locaux dans IndexedDB → rétablissement du réseau → vérification de la synchronisation (l'horodatage conservé est celui du scan réel). Déconnexion puis reconnexion d'un autre utilisateur : aucune fuite de file d'attente d'un autre compte.

6. **Conférence publique & Désistement** :
   Création d'une conférence avec jauge limitée → ouverture de la page publique sans session → inscription en double exemplaire (réponses identiques, pas de doublon) → ouverture du lien sécurisé de confirmation → validation de l'inscription et génération du badge PDF.

7. **Supervision plateforme** :
   Suspension d'une organisation depuis la console superadmin → vérification du blocage immédiat de l'administrateur associé → réactivation → consultation du journal d'audit.

8. **Expiration & grâce d'abonnement** :
   Passage de l'abonnement en période de grâce puis en lecture seule → vérification que la création d'événement est bloquée mais que le contrôle d'accès sur l'événement en cours reste totalement opérationnel.

## Livrables attendus
- Tableau d'exécution des 8 parcours : `Parcours` → `Résultat (OK / ÉCHEC)`.
- Relevé des erreurs console (notamment CSP) ou réseau.
- Liste des écrans présentant des défauts de lisibilité mobile ou plein soleil.
