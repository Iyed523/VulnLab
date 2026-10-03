# Tickets privés et commentaires — M7

**Écart actuel M11 : [VULN-003](vulnerabilities/VULN-003.md) rend uniquement GET détail inter-utilisateur vulnérable, avec divulgation des commentaires rendus. HEAD et les autres opérations restent autorisés côté serveur. Les règles de référence et preuves antérieures ci-dessous décrivent le baseline correct, conservé par baseline-functional-v1.**

M6/M6.1 sont validées sur `4f1e244`. M7 part de ce SHA sur `codex/m7-tickets-comments`, avec PR brouillon vers `codex/m6-auth-sessions`. Les PR antérieures restent non fusionnées. Les modèles/migrations M5 et versions verrouillées sont conservés ; aucune faiblesse volontaire, fonction administrative ou implémentation dans `secure-app`.

## Contrats HTTP et politique

| Route | Comportement |
| --- | --- |
| GET /tickets | Liste et comptage filtrés : propriétaire courant, ou tous les tickets pour admin actif |
| GET/POST /tickets/new | Formulaire puis création ; propriétaire = acteur et statut open ; 303 vers détail |
| GET /tickets/id | Détail autorisé et commentaires paginés |
| GET/POST /tickets/id/edit | Formulaire puis modification de titre, description, statut seulement ; 303 vers détail |
| POST /tickets/id/delete | Suppression autorisée avec CSRF ; cascade SQL des commentaires ; 303 vers /tickets |
| POST /tickets/id/comments | Auteur = acteur, parent = ticket autorisé de la route ; 303 vers détail |

Tous les utilisateurs doivent être actifs et authentifiés. Les visiteurs, sessions déconnectées/expirées et comptes désactivés reçoivent 303 vers `/login?next=/account`, avant traitement des formulaires. Cette destination locale M6 est conservée : après connexion, la navigation account permet d'ouvrir Tickets. Aucune entrée `next` de ticket ne modifie les redirections de succès.

Un ticket absent ou inaccessible produit le même 404, sur le détail, l'édition, la suppression et les commentaires. Le contrôle CSRF global précède les vues : pour un acteur authentifié, un jeton absent/invalide produit 400 quel que soit l'objet visé. Un GET vers les routes de suppression/ajout de commentaire reçoit 405, sans mutation. Validation incorrecte ou champs inattendus/dupliqués : 400. Corps trop volumineux : 413. Backend SQL/Redis indisponible : 503 générique, jamais d'autorisation de secours. Réponses des routes tickets : `Cache-Control: no-store`.

La politique est centralisée dans `ticket_service.visible_tickets` et `authorized_ticket` : une même sélection SQL paramétrée filtre listes, comptages et opérations. L'accès aux commentaires exige le parent autorisé. Les écritures verrouillent le ticket dans leur transaction. L'administration ne permet jamais de transférer un ticket ; un commentaire admin reste attribué à l'admin connecté.

Les convertisseurs de route acceptent les entiers signés : les fixtures négatives M5 sont utilisables. Les identifiants hors plage PostgreSQL INTEGER produisent 404 avant interrogation SQL.

## Validation et interface

Titre : 1–200 caractères ; description : 1–10000 ; commentaire : 1–5000. Texte Unicode conservé, sans HTML interprété ; caractère NUL refusé avant écriture. Statuts limités à `open`, `in_progress`, `closed`. Création : seuls titre/description acceptés ; édition : titre/description/statut ; commentaire : contenu ; suppression : aucun champ métier. Les champs CSRF/submit de formulaire sont admis, sans doublons. Aucun id, propriétaire, auteur, ticket parent, rôle ou date client ne peut être affecté.

La limite de corps est de 128 KiB sur les routes tickets pour permettre le maximum Unicode après encodage de formulaire, sans relever la limite d'authentification M6. Chaque page contient au plus 20 tickets ou 20 commentaires. Paramètres `page` et `comments_page` : un entier ASCII unique de 1 à 1000 ; valeur invalide ou dupliquée : 400. Une page valide hors résultats est vide. Ordre tickets : created_at décroissant puis id décroissant ; commentaires : created_at puis id croissants. Ces ordres sont stables pour des données inchangées ; la pagination offset n'est pas un instantané entre requêtes concurrentes.

Les templates Jinja conservent l'échappement automatique, y compris dans les champs de formulaires. Aucun `safe`, CDN ou script externe. La suppression est présentée dans un panneau de confirmation avec formulaire POST mentionnant la suppression des commentaires. Aucun changement par GET. Aucune édition/suppression individuelle de commentaire, recherche, pièce jointe ou éditeur riche.

## Sessions, transactions et preuves

Le contrôle M6 est étendu à tout le blueprint tickets : Redis disponible, échéance absolue vérifiée, état actif et rôle relus depuis SQL sur chaque requête authentifiée. Les cookies et TTL M6 restent inchangés ; `/healthz` et les ressources statiques demeurent indépendants des backends. Les transactions M5 assurent commit/rollback et fermeture des sessions, sans paramètres privés dans les logs SQL. La suppression utilise la cascade existante sans charger tous les commentaires.

Tests unitaires : pagination bornée, identifiants signés et refus sans backend. Tests fonctionnels d'intégration : services PostgreSQL/Redis réels exclusivement sur le volume CI jetable, acteurs Alice/Bob/admin fictifs, accès et comptages filtrés, propriété/auteur, champs sensibles/dupliqués, limites Unicode/statuts, CSRF, session expirée/rejouée/désactivée, panne injectée et rollback après flush. Ces tests de référence sont distincts des futures démonstrations de vulnérabilité/remédiation.

`scripts/ci/verify_auth_https.py` conserve le parcours M6 et ajoute création, consultation, modification, commentaire, suppression et refus croisés entre deux comptes, à travers Nginx avec certificat et nom vérifiés. Les deux connexions réussies consomment deux des cinq essais autorisés ; trois essais invalides suivent, puis le sixième doit recevoir 429 malgré des en-têtes forgés. Aucun quota ni protection désactivé. Les valeurs privées restent en mémoire.

Les contrôles M4–M6.1 sont conservés. La [première CI M7 sur d998105](https://github.com/Iyed523/VulnLab/actions/runs/36989912286) passe sur les trois jobs : 75 tests Python Windows/Linux et 141 tests PostgreSQL/Redis (84 précédents + 57 M7), puis parcours HTTPS deux utilisateurs, assertions d'infrastructure et témoin réseau avec nettoyage réussi. Le complément de livraison ajoute la vérification d'un rôle admin modifié en SQL entre deux requêtes et l'absence de mutation lors des refus de session/backend : la suite compte 142 tests d'intégration. L'état et le lien de la CI de livraison sont consignés dans la [PR M7 #5](https://github.com/Iyed523/VulnLab/pull/5), avec vérification de sa tête avant remise. Localement : 75 tests, Ruff/format, dépendances compatibles, wheel avec les trois templates tickets, Compose, actionlint, 91 liens locaux et `git diff --check` réussissent.

Une erreur d'import de tests a été corrigée avant publication en déclarant le package d'intégration et ses imports relatifs, compatibles avec le mode importlib existant. Aucun échec serveur ou assertion masqué, aucune protection désactivée.

Aucun test destructif local sur les volumes conservés : piles M6.1 et securevault restent arrêtées et intactes. Les preuves réelles M7 sont Linux CI ; le rapport Windows M6.1 reste une preuve distincte du socle précédent. Les erreurs de backend sont injectées dans des clients utilisant les services réels, sans coupure physique des conteneurs. Le témoin réseau ne garantit pas une interdiction globale des sorties ; le proxy peut sortir et l'isolation du navigateur n'est pas démontrée. Aucun audit exhaustif ni déploiement.

Commandes depuis la racine (exécutables sous `.tools` ou la venv, cache uv dans `.tools/uv-cache`) :

```text
vulnerable-app/.venv/Scripts/python.exe -m pytest vulnerable-app/tests tests/ci
vulnerable-app/.venv/Scripts/ruff.exe check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
vulnerable-app/.venv/Scripts/ruff.exe format --check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
uv pip check --python vulnerable-app/.venv/Scripts/python.exe
uv build vulnerable-app --python vulnerable-app/.venv/Scripts/python.exe --wheel --no-build-isolation --offline
docker compose --env-file .env.example -f compose.vulnerable.yaml -f compose.ci.yaml --profile ci --profile tools config --quiet
actionlint -shellcheck= -pyflakes= .github/workflows/ci.yml
git diff --check
```

La suite intégration et le parcours HTTPS sont lancés par le workflow CI sur ses propres ressources, avec nettoyage ciblé. Arrêt à M7 pour revue du Team Lead et validation du Product Owner ; aucune fusion ou mission suivante.
