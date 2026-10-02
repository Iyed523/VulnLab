# Autorisations de référence — à implémenter

M7 implémente les opérations tickets/commentaires dans `vulnerable-app` conformément à cette matrice ; voir [contrats et preuves M7](tickets-comments.md). Profil, recherche et fonctions administratives restent futurs. Inscription M6 refuse explicitement les champs sensibles, et les comptes désactivés sont invalidés sur les routes auth et tickets. Les mentions « futur » ci-dessous sont le cadrage historique.

Les tickets sont privés. Cette matrice définit le comportement attendu commun ; elle ne constitue pas une preuve de contrôle existant. Les éventuels écarts volontaires du laboratoire devront être associés à leur identifiant et test.

| Opération | Non connecté | `user` actif | `admin` actif |
| --- | --- | --- | --- |
| Inscription publique | Création d’un compte `user` uniquement | Aucun changement de rôle | Aucun changement de rôle |
| Créer un ticket | Authentification requise | Oui, propriétaire = soi | Oui, propriétaire = soi |
| Consulter, modifier, supprimer un ticket | Authentification requise | Ses tickets uniquement | Tous les tickets |
| Lister ou rechercher des tickets | Authentification requise | Ses tickets uniquement | Tous les tickets |
| Lire ou ajouter un commentaire | Authentification requise | Sur ses tickets uniquement | Sur tous les tickets |
| Modifier son profil | Authentification requise | Champs autorisés de son profil uniquement | Champs autorisés de son profil uniquement |
| Accéder aux fonctions administratives | Authentification requise | Interdit : `403` | Autorisé selon la fonction |

L’auteur d’un commentaire est toujours l’utilisateur connecté, même si un administrateur intervient sur le ticket d’autrui. Le propriétaire d’un ticket est immuable. Les champs éditables d’un ticket sont le titre, la description et le statut (`open`, `in_progress`, `closed`), jamais son propriétaire, son identifiant ou ses dates gérées par le serveur.

Les champs éditables du profil devront être définis par une liste explicite lors de la mission fonctionnelle. Par défaut, tout champ absent de cette liste est interdit. Aucun formulaire public ne permet de changer le rôle ou le statut actif ; l’inscription ignore toute prétention à un rôle administrateur et impose `user` côté serveur. Une future commande locale créera les administrateurs fictifs. L’accès administratif ne confère pas implicitement le droit d’éditer le profil d’un tiers.

Pour un utilisateur connecté, un ticket inexistant ou inaccessible produit `404`, y compris lors d’une opération sur ses commentaires, afin de ne pas révéler son existence. Une fonction administrative interdite produit `403`. Le comportement précis de connexion/redirection des visiteurs sera défini dans le contrat HTTP futur, sans exposer de données privées.

Les contrôles serveur s’appliquent à toutes les routes, listes, recherches et opérations sur les commentaires, sans se limiter aux boutons visibles. L’accès à un commentaire dépend de l’accès à son ticket parent ; un identifiant transmis par le client ne prouve aucun droit. La suppression du ticket entraîne celle de ses commentaires. L’édition ou la suppression individuelle des commentaires n’est pas une fonctionnalité validée à ce stade et ne confère aucun droit implicite.

Les comptes désactivés ne doivent plus accéder aux fonctions authentifiées ; le refus de connexion et l’invalidation des sessions devront être implémentés et testés. Il n’est pas prévu de suppression physique des comptes au départ.

Voir le [modèle métier](architecture.md) et le [modèle de menace](threat-model.md).
