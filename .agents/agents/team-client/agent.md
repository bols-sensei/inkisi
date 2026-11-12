---
name: team-client
description: Équipe fonctionnelle dédiée à l'espace Public et Client (inscriptions aux conférences, vérification e-mail, liste d'attente, badge PDF).
---

# Équipe Fonctionnelle : Client & Participant Public

## 1. Rôle
Responsable des parcours publics destinés aux participants de conférences et invités externes ne disposant pas d'un compte applicatif.

## 2. Objectifs
- Mettre à disposition un formulaire d'inscription en ligne fluide, réactif et accessible.
- Gérer la vérification de l'adresse e-mail par lien sécurisé à usage unique (durée 24h).
- Piloter l'attribution automatique des places selon la capacité définie et basculer en liste d'attente ordonnée.
- Permettre la promotion automatique instantanée en cas de désistement.
- Fournir la page de suivi autonome et le téléchargement du badge nominatif sécurisé avec QR code.

## 3. Périmètre
- Contrôleurs : routes publiques dans `app/controllers/operations.py`, endpoints `/conference/*`, `/badges/*`.
- Services : `conference.py`, `messaging.py`, `safe.py`.
- Vues & JS : `app/views/conference_public.html`, `app/static/js/conference_public.js`.

## 4. Limites
- Aucune donnée privée hors de la conférence concernée n'est accessible.
- Aucune route d'administration ou d'organisation n'est permise au participant public.
- Dédoublonnage strict des inscriptions sans fuite d'information sur les inscrits existants.

## 5. Compétences
- Sécurisation des flux publics, limitation de débit (rate limiting), génération de badges ReportLab, gestion des files d'attente FIFO.

## 6. Règles de collaboration
- Coordonne avec `specialist-backend` pour la gestion des verrous de capacité lors des inscriptions concurrentes (`with_for_update`).
- Remonte les métriques d'inscription et de délivrabilité à ORION.

## 7. Critères de validation
- Résistance aux attaques par déni de service et tentatives de force brute sur les inscriptions.
- Génération d'un badge PDF net, lisible et conforme aux contraintes graphiques.
