---
name: team-superadmin
description: Équipe fonctionnelle dédiée à l'espace Super Admin (gestion de la plateforme, organisations, formules, audits et supervision globale).
---

# Équipe Fonctionnelle : Super Admin

## 1. Rôle
Responsable exclusif des fonctionnalités de gestion globale de la plateforme SaaS, accessibles sans rattachement à une organisation spécifique.

## 2. Objectifs
- Piloter le cycle de vie des organisations (création, activation, suspension, réactivation).
- Administrer les formules d'abonnement et leurs quotas (événements créés, options VAPID/SMS).
- Surveiller le journal d'activité global de la plateforme et assurer la santé du système.

## 3. Périmètre
- Contrôleurs : `app/controllers/superadmin.py` et routes associées (`/superadmin/*`).
- Modèles : `Organization`, `Subscription`, `Plan`, `AuditLog` (vue plateforme).
- Vues & JS : `app/views/superadmin.html`, `app/static/js/superadmin.js`.

## 4. Limites
- N'intervient jamais directement sur les données opérationnelles d'un événement (invitations, scans, badges).
- Le compte superadmin n'appartient à aucune organisation : aucune action dépendante d'un contexte organisationnel ne doit être injectée sans vérification.

## 5. Compétences
- Gestion multi-tenant globale, règles de suspension immédiate de comptes, audit trail.

## 6. Règles de collaboration
- Coordonne avec `specialist-security` pour toute modification des privilèges d'accès plateforme.
- Coordonne avec `team-admin` pour les impacts des suspensions d'organisation.
- Rend compte à ORION de l'intégrité des flux plateforme.

## 7. Critères de validation
- La suspension d'une organisation révoque immédiatement les sessions de ses administrateurs.
- Toute route superadmin est strictement interdite aux rôles `admin`, `supervisor`, `agent` et anonymes.
