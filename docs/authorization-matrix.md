# Autorisations de référence

**Écart actuel M11 : [VULN-003](vulnerabilities/VULN-003.md) rend uniquement GET détail inter-utilisateur vulnérable, avec divulgation des commentaires rendus. HEAD et les autres opérations restent autorisés côté serveur. Les règles de référence et preuves antérieures ci-dessous décrivent le baseline correct, conservé par baseline-functional-v1.**

M7 implémente les tickets/commentaires ; M8 ajoute profil et administration minimale dans `vulnerable-app`. Voir les [contrats M7](tickets-comments.md) et [contrats M8](profile-admin.md). La recherche et le cycle de vie des administrateurs restent futurs. Aucun scénario volontairement vulnérable n'est introduit.

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

Le profil autorise **uniquement `display_name`**, 1–100 caractères sans NUL ; sa cible est la session. `username`, `password`, `password_hash`, `role`, `active`, `id`, `session_version`, `created_at` et `updated_at` sont interdits, comme tout champ inattendu ou dupliqué. L'inscription refuse les champs sensibles et impose `user`. Le seed local M5 crée l'administrateur fictif. Un administrateur ne peut pas éditer le profil d'un tiers.

La liste administrative expose uniquement `id`, `username`, `display_name`, `role`, `active`, par pages de 20 ordonnées par identifiant, avec page 1–1000. Seul un administrateur actif peut changer `active` via les deux POST dédiés. La cible est la route ; seules les cibles `role=user` sont autorisées. Modifier le statut d'un administrateur, soi-même inclus, produit 403. Aucun changement de rôle, suppression de compte ou changement de tickets/commentaires. Le statut répété est idempotent ; un compte absent produit 404 après vérification administrative. Les droits sont revérifiés sous verrou SQL dans les transactions d'opération.

Pour un utilisateur connecté, un ticket inexistant ou inaccessible produit `404`, y compris pour ses commentaires. Une fonction administrative interdite produit `403` avec requête valide ; CSRF absent/invalide produit 400. Un visiteur sur une route protégée est redirigé en 303 vers `/login?next=/account` avant CSRF, sans données privées. Aucun changement d'état par GET ; succès POST M8 vers `/account` ou `/admin/users` en 303.

Les contrôles serveur s’appliquent à toutes les routes, listes, recherches et opérations sur les commentaires, sans se limiter aux boutons visibles. L’accès à un commentaire dépend de l’accès à son ticket parent ; un identifiant transmis par le client ne prouve aucun droit. La suppression du ticket entraîne celle de ses commentaires. L’édition ou la suppression individuelle des commentaires n’est pas une fonctionnalité validée à ce stade et ne confère aucun droit implicite.

Chaque route protégée porte le même garde, qui vérifie Redis, l'échéance et l'identité SQL courante. La désactivation M8 incrémente atomiquement `session_version` : les anciens SID sont refusés à leur prochaine requête protégée, même après réactivation. La réactivation ne remet jamais cette version à zéro. Voir la portée et les limites de concurrence dans [M8](profile-admin.md). Aucune suppression physique des comptes.

Voir le [modèle métier](architecture.md) et le [modèle de menace](threat-model.md).
