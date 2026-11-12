# Changelog Lot 3 — Fiabilité backend

## File d’envoi Web Push

- Les notifications internes et leurs jobs Web Push sont écrits dans la même transaction.
- L’envoi fournisseur quitte le cycle de requête HTTP ; un worker lancé avec l’application traite la file en arrière-plan.
- Les jobs sont isolés par abonnement d’appareil, revendiqués atomiquement entre workers et repris après un délai exponentiel (8 tentatives maximum).
- Les abonnements expirés (`404`/`410`) et leurs jobs en attente sont supprimés. Les résultats terminaux sont purgés après 30 jours.
- Le délai d’appel au fournisseur est limité à 10 secondes. `PUSH_OUTBOX_POLL_SECONDS` règle l’intervalle de scrutation (2 secondes par défaut, borné entre 0,25 et 30).
- Migration idempotente : `0011_push_outbox`.
- Validation locale : 11 tests push réussis, compilation Python réussie et migration SQLite jusqu’à `0011_push_outbox` vérifiée. Le fournisseur est simulé ; aucune notification réelle n’a été envoyée.

### Exploitation

#### Courriels sortants d?sactiv?s

- Suppression de la d?pendance SMTP/Resend et de la validation e-mail au d?marrage en production.
- Les comptes peuvent utiliser l?application sans confirmation e-mail ; les inscriptions publiques affichent leur lien de suivi apr?s cr?ation.
- La r?cup?ration de mot de passe passe par un administrateur et aucun lien secret n?est retourn? publiquement.
Le worker démarre et s’arrête avec le cycle de vie FastAPI. Chaque processus applicatif peut donc traiter la file ; la revendication conditionnelle évite qu’un job soit livré simultanément par plusieurs processus.
