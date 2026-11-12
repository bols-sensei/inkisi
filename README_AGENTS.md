# Dispositif d'agents Gemini CLI

## Installation
1. Copier `GEMINI.md` et le dossier `.gemini/commands/` à la racine du projet (ne pas écraser un `.gemini/` existant : fusionner).
2. Installer Impeccable pour Gemini (depuis la racine du projet) :
   ```
   npx impeccable            # choisir le fournisseur « gemini », portée « projet »
   ```
   Alternative manuelle (README d'Impeccable) : `cp -r dist/gemini/.gemini <projet>/`.
   Les « skills » de Gemini CLI doivent être activés : `npm i -g @google/gemini-cli@preview`, puis `/settings` → *Skills*,
   puis `/skills list` pour vérifier que `impeccable` apparaît.
3. Lancer `gemini` à la racine du projet.

## MCP navigateur (essais réels)
Deux outils complémentaires, trois serveurs dans `.gemini/settings.example.json` :
| Serveur | Sert à | Pourquoi |
|---|---|---|
| `chrome-devtools` | Diagnostic : console (violations CSP), réseau, hors ligne, service worker, performance | Voit ce que le navigateur bloque en silence |
| `playwright-admin` | Parcours scénarisés, session administrateur | Pilote l'interface comme un utilisateur |
| `playwright-agent` | Seconde session indépendante (agent de terrain) | Les onglets d'un même serveur partagent leurs cookies : il faut deux serveurs pour tester « désactivé ici, coupé là » |

1. Copier le bloc dans `.gemini/settings.json` (projet) ou `~/.gemini/settings.json`.
2. Relancer `gemini`, puis `/mcp` : les trois serveurs doivent apparaître connectés. Si une option est refusée par votre version,
   `npx chrome-devtools-mcp@latest --help` ou `npx @playwright/mcp@latest --help`, puis ajuster `args`.
   Le premier lancement de Playwright peut demander d'installer ses navigateurs.
3. Lancer `/e2e` (ou `/e2e hors ligne`, `/e2e conférence`…).
Sécurité : ces serveurs donnent à l'agent le contrôle d'un navigateur. Gardez `--isolated`, une base jetable et aucun compte réel.

## Ordre conseillé
| # | Commande | Rôle | Modifie le code ? |
|---|---|---|---|
| 1 | `/fix-tests` | Lance la suite, corrige les échecs des lots 1 et 2 (jamais exécutés) | oui |
| 2 | `/review` | Relecture indépendante du diff contre les invariants de `GEMINI.md` | non |
| 3 | `/lot3-backend [sujet]` | Fiabilité : migration, pagination, N+1, e-mails, RGPD | oui |
| 4 | `/design-init` | Crée le contexte Impeccable (`PRODUCT.md`, `DESIGN.md`) | oui (docs) |
| 5 | `/lot4-ui [sujet]` | Interface avec Impeccable | oui |
| 6 | `/ui-audit` | Audit Impeccable de l'interface | non |
| + | `/e2e-roles [compte]` | Essais navigateur par type de compte (superadmin, admin, superviseur, agent, participant public, autre organisation) | non |
| + | `/e2e [parcours]` | Essais réels dans Chrome (console CSP, hors ligne, parcours) | non |

Après chaque agent qui modifie le code : `/review`, puis vous relisez le diff (`git diff`) avant de fusionner.

## Tests par type de compte
- **API (pytest)** : `tests/test_roles_matrix.py` essaie chaque route avec chaque rôle (49 routes × 4 rôles + anonyme), vérifie l'isolation entre
  organisations (404, jamais 403), la désactivation et la suspension pour chaque rôle, et les endpoints publics du participant.
  Quand une route est ajoutée, **l'ajouter à la matrice** : c'est la règle n° 12 de `GEMINI.md`.
- **Navigateur** : `/e2e-roles` vérifie que l'interface respecte cette matrice (boutons visibles, URL interdites, console propre).
