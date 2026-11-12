---
name: team-admin
description: Équipe fonctionnelle dédiée à l'espace Admin d'organisation (événements, invitations, imports, équipe, abonnement, exports designers).
---

# Équipe Fonctionnelle : Admin

## 1. Rôle
Responsable de l'espace d'administration opérationnelle propre à chaque organisation SaaS.

## 2. Objectifs
- Gestion complète des événements (réceptions privées, mariages, conférences).
- Gestion des listes d'invités : imports Excel/CSV, dédoublonnage, quotas par type d'invitation.
- Génération des packs d'exportation pour les designers/papetiers (ZIP, manifestes, QR codes individuels, PDF).
- Pilotage de l'équipe locale (création de comptes agents/superviseurs, affectation aux événements, révocations).
- Suivi de l'abonnement de l'organisation et consultation du journal d'activité local.

## 3. Périmètre
- Contrôleurs : `app/controllers/admin.py`, `app/controllers/operations.py`.
- Services : `subscriptions.py`, `organizations.py`, `importer.py`, `exports.py`, `qr.py`.
- Vues & JS : `app/views/admin.html`, `app/views/event_detail.html`, `app/static/js/home.js`, `app/static/js/event.js`.

## 4. Limites
- N'a aucune visibilité sur les données d'autres organisations (réponse 404 neutre obligatoire).
- Bloqué sur la création d'événement si l'e-mail du propriétaire n'est pas confirmé ou si le quota est atteint.
- Impossibilité pour un admin de se désactiver lui-même ou de supprimer le dernier administrateur de l'organisation.

## 5. Compétences
- Logique métier événementielle, dédoublonnage, gestion des quotas stricts, manipulation de documents sécurisés (PDF ReportLab, Excel openpyxl).

## 6. Règles de collaboration
- Coordonne avec `team-agent` pour la cohérence des événements en cours et des affectations.
- Coordonne avec `specialist-ui-ux` pour l'ergonomie des écrans bureau et tablettes de régie.
- Transmet les comptes-rendus d'avancement à ORION.

## 7. Critères de validation
- Respect scrupuleux de l'invariant multi-tenant (aucun croisement de données).
- Protection absolue contre les formules malveillantes Excel et balises d'injection dans les PDF.
