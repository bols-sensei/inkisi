# Lot 4 — Historique des changements

## Badges séparés pour les membres

- L’organisateur peut activer un lien membre indépendant du formulaire d’inscription public, choisir une palette et définir jusqu’à huit catégories.
- Les demandes membre sont persistées dans une table dédiée ; elles ne créent ni invitation ni inscription participant.
- Chaque demande génère un badge PNG coloré par catégorie, avec QR informatif non relié au scanner.
- Le lien peut être désactivé depuis la gestion de l’événement ; toute réactivation émet un nouveau lien.
- Migration idempotente ajoutée et cache statique incrémenté.

## Finition premium des badges participants

- Le PNG reprend les détails du fichier premium : dégradé indigo, guilloches, double cadre métallisé, portrait en arche et sceau holographique.
- Les informations participant et événement sont composées autour du QR sécurisé existant.
- L’aperçu après inscription et la page de gestion affichent le même PNG pour reproduire exactement le rendu téléchargé.
- L’organisateur peut ajuster les six palettes, le métal, la forme de photo, le logo et le sceau ; ces choix sont repris par le rendu participant.
- L’aperçu reprend l’inclinaison 3D et le reflet interactif du fichier de référence, avec respect de la préférence de réduction des mouvements.
- Cache statique incrémenté.

## Accueils contextualisés Super Admin et Agent

- L’accueil Super Admin s’ouvre sur le pilotage de la plateforme et ne présente plus la navigation événementielle ni la gestion d’équipe.
- Les indicateurs distinguent le statut de l’organisation de celui de son abonnement.
- Les liens directs vers les événements des organisations clientes ont été retirés de la console générale.
- L’accueil Agent résume ses événements affectés, les échéances à venir et la progression des contrôles, avec un accès explicite au scanner sur chaque événement.
- Les informations sont issues des API existantes ; aucune statistique commerciale ou donnée synthétique n’a été ajoutée.
- Version du cache statique incrémentée pour servir les nouveaux modules.

## Navigation, rôles et abonnements

- L’espace Admin dispose d’une page « Mon abonnement » avec état contractuel et droits effectifs, dates, limites consommées/restantes, fonctions incluses et explication de la période de grâce/lecture seule.
- Le tableau de bord Admin met en avant les événements, les échéances et le quota avant la création. Les conférences indisponibles sur la formule sont désactivées dans le formulaire; le backend reste l’autorité.
- L’espace Superviseur synthétise les événements affectés, les affectations d’agents, les exceptions ouvertes et les contrôles; les cartes ouvrent directement le suivi.
- Les totaux d’accès conférence utilisent les inscriptions acceptées et les check-ins réels, au lieu de comparer les passages à la capacité maximale.
- Le Super Admin dispose d’espaces Formules et Abonnements distincts. Les formules existantes sont modifiables et désactivables pour les nouvelles attributions; les formules système restent protégées.
- L’historique des périodes expose l’organisation, le statut organisation, le statut abonnement, les dates, le plan, les quotas et les fonctionnalités. Une période future est signalée comme telle.
- La fiche organisation distingue les accès de l’organisation de son abonnement, expose l’administrateur principal et permet suspension/réactivation avec motif journalisé.
- Le Super Admin dispose d’une évolution réelle des créations d’organisations sur six mois et d’un journal filtrable par organisation.
- Le modèle actuel ne possède ni prix/périodicité tarifaire ni passerelle de paiement; l’interface le dit explicitement et n’affiche aucun revenu inventé.

## Clarification fonctionnelle Super Admin

- Les plans et abonnements décrivent précisément l’option actuellement protégée par le droit `advanced_features` : création d’événements conférence et export de PDF personnalisés d’invitations en lot.
- La liste des abonnements est recherchable et filtrable par état (actif, essai, suspendu, expiré, période à venir), avec le nombre réel de périodes dans chaque filtre.
- L’action sur une période est libellée « Attribuer une nouvelle période », car l’API conserve l’historique et ajoute une période au lieu de modifier une période existante.
- L’absence de factures et transactions est rappelée dans cette vue ; aucun indicateur financier n’est simulé.
- Le formulaire de plan et l’espace abonnement Admin reprennent la même description de l’option afin de réduire les surprises de droits.
- Version du cache statique incrémentée.
# Badges membres et support plateforme
- Les membres ajoutent leur photo lors de la demande de badge ; la confirmation affiche l’aperçu premium complet et le téléchargement PNG.
- L’espace Support relie les administrateurs d’organisation au superadmin avec des fils de discussion isolés par organisation.
- Migration Alembic 0010 ajoute la photo membre et les tables de support ; cache statique incrémenté en v27.
- La configuration badge enregistrée est rechargée à chaque ouverture de la page de gestion de l’événement.
