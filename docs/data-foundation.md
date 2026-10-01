# Données PostgreSQL — M5

M4 et M4.1 sont validées par le Product Owner sur `aabc745`. M5 part de ce socle, sur `codex/m5-data-foundation`. Les PR #1 et #2 ne sont pas fusionnées. M5 reste soumise à revue ; aucune mission suivante n'est commencée. `secure-app` reste documentaire, aucun scénario volontairement vulnérable ni route métier n'est ajouté.

## Modèles et contrats

Tous les champs ci-dessous sont NOT NULL. Les identifiants sont des entiers PostgreSQL avec identité BY DEFAULT et clé primaire. L'identité produit des valeurs positives ; les fixtures réservent des valeurs négatives. Aucune autorisation n'est fournie par les relations ORM ou les contraintes SQL.

| Table | Champs et contraintes |
| --- | --- |
| users | username VARCHAR(32), unique ; password_hash VARCHAR(255), 1–255 caractères ; display_name VARCHAR(100), 1–100 ; role VARCHAR(5), user/admin, défaut user ; active booléen, défaut true ; created_at et updated_at TIMESTAMPTZ |
| tickets | owner_id FK users, RESTRICT ; title VARCHAR(200), 1–200 ; description TEXT, 1–10000 ; status VARCHAR(11), open/in_progress/closed, défaut open ; created_at et updated_at TIMESTAMPTZ |
| comments | ticket_id FK tickets, CASCADE ; author_id FK users, RESTRICT ; content TEXT, 1–5000 ; created_at TIMESTAMPTZ |

Le nom de compte est normalisé par NFKC, strip puis casefold, et doit respecter `[a-z0-9][a-z0-9_.-]{2,31}`. La contrainte SQL impose la même forme ASCII canonique aux écritures contournant l'ORM ; l'unicité est donc celle de cette forme. Les noms affichés et textes restent Unicode, sans transformation HTML ; leurs futurs rendus et validations fonctionnelles devront être traités dans la mission correspondante. Les textes vides sont refusés, les textes contenant seulement des espaces ne sont pas normalisés ici.

Les index uniques et primaires couvrent les recherches de compte/identifiant. Les FK owner_id, ticket_id et author_id ont leurs index. Aucun index de recherche spéculatif n'est ajouté. Supprimer un ticket supprime ses commentaires, avec ou sans chargement ORM ; supprimer un utilisateur propriétaire ou auteur référencé est refusé. La désactivation des comptes reste la convention future.

Les connexions demandent UTC ; les dates sont fournies par PostgreSQL avec fuseau. updated_at est actualisé pour les mises à jour ORM via `onupdate=now()` ; le SQL direct doit le gérer explicitement. Il n'y a pas de trigger caché. Le propriétaire du ticket reste un invariant des futurs cas d'usage et ne devra pas devenir éditable ; M5 n'expose aucun cas d'usage HTTP, et une FK seule ne l'impose pas. Les champs éditables du profil ne sont pas décidés ici. Voir la [matrice d'autorisations](authorization-matrix.md).

## Configuration et transactions

Chaque fabrique Flask accepte une configuration explicite et possède son propre objet Database dans `app.extensions`. DB_HOST, DB_NAME, DB_USER et DB_PASSWORD sont requis si une configuration SQL est demandée ; DB_PORT vaut 5432 par défaut. Une URL SQLAlchemy structurée protège les caractères réservés du mot de passe. L'objet de configuration masque celui-ci dans repr, echo est désactivé et hide_parameters est actif. Les commandes évitent les traces contenant les identifiants/paramètres. Ne jamais afficher l'environnement applicatif ni une URL contenant le mot de passe.

Créer/importer l'application n'ouvre pas de connexion. `/healthz` reste la santé HTTP et ne vérifie ni SQL ni Redis. Une transaction explicite ouvre une session, commit à la réussite, rollback à l'échec et ferme toujours la session. Aucun commit de requête implicite, aucune migration ou fixture au démarrage Gunicorn. Les futurs services devront utiliser cette frontière et effectuer leurs autorisations serveur.

## Privilèges

`vulnlab_init` reste le compte d'initialisation PostgreSQL du socle ; il n'est pas livré aux workers. `vulnlab_migrate` est LOGIN, sans superuser/createdb/createrole/replication/bypassrls ni appartenance à un rôle ; il a CONNECT et USAGE/CREATE sur public et possède les tables qu'il crée. Il n'est pas le compte runtime. `vulnlab_app` a CONNECT et USAGE public, CRUD sur les seules tables métier, USAGE/SELECT sur les séquences ; ni CREATE de schéma/table/temporaire, ni ALTER/DROP/TRUNCATE, ni accès à alembic_version. Les privileges PUBLIC du schéma et de la base sont retirés.

L'initialisation attribue les privilèges par défaut des objets futurs créés par `vulnlab_migrate` dans public. Les migrations doivent continuer de tourner avec ce rôle ; la première accorde explicitement les droits métier et retire ceux de la table de suivi Alembic. Un futur objet de maintenance devra lui aussi retirer les droits applicatifs hérités. Les tests vérifient également les grants d'une table/séquence future.

L'environnement permanent app ne contient que la configuration de `vulnlab_app`. Le mot de passe de migration est présent dans db pour le provisioning et dans l'outil ponctuel `data-tools`, jamais dans app. L'outil réutilise l'image applicative non root, sur backend seulement, sans port publié, capacités ou socket Docker. Il monte les migrations/configuration en lecture seule. Ce profil `tools` n'est pas démarré par `up` normal.

## Base neuve et commandes explicites

Après les vérifications de moteur, ressources et certificats décrites dans [docker.md](docker.md), depuis la racine :

```bash
docker compose --env-file .env.example -f compose.vulnerable.yaml config --quiet
docker compose --env-file .env.example -f compose.vulnerable.yaml build app
docker compose --env-file .env.example -f compose.vulnerable.yaml up -d --wait --wait-timeout 120
docker compose --env-file .env.example -f compose.vulnerable.yaml --profile tools run --rm data-tools upgrade
docker compose --env-file .env.example -f compose.vulnerable.yaml --profile tools run --rm data-tools check
docker compose --env-file .env.example -f compose.vulnerable.yaml --profile tools run --rm -e DB_USER=vulnlab_app -e DB_PASSWORD=demo-app-vulnlab-only data-tools seed
```

Ces commandes utilisent les seules valeurs fictives versionnées. Pour une configuration locale distincte, fournir le mot de passe applicatif sans l'inscrire dans une commande/historique et sans l'afficher ; ne pas réutiliser d'identifiant réel. Sous Windows, conserver `docker --config .tools/docker-config` selon le guide existant. Alembic utilise `vulnerable-app/alembic.ini`, aucune URL secrète dans ce fichier. L'upgrade est répétable, et `check` vérifie l'absence de différences entre modèles et schéma. Le schéma n'est jamais créé via create_all.

## Volume déjà initialisé

initdb ne se relance pas sur un volume existant. **Ne pas supprimer le volume pour forcer son exécution.** Arrêter app/proxy avant maintenance, conserver les données et leur sauvegarde locale protégée, inventorier rôles, droits et schéma sans afficher les mots de passe. Ajouter MIGRATION_DB_PASSWORD fictif dans la configuration de cette pile puis recréer uniquement db avec le même volume pour actualiser son environnement :

```bash
docker compose --env-file .env.example -f compose.vulnerable.yaml stop proxy app
docker compose --env-file .env.example -f compose.vulnerable.yaml up -d --no-deps --wait db
docker compose --env-file .env.example -f compose.vulnerable.yaml exec -T db sh /docker-entrypoint-initdb.d/01-role.sh
docker compose --env-file .env.example -f compose.vulnerable.yaml --profile tools run --rm data-tools upgrade
docker compose --env-file .env.example -f compose.vulnerable.yaml --profile tools run --rm data-tools check
docker compose --env-file .env.example -f compose.vulnerable.yaml up -d --wait --wait-timeout 120
```

Le provisioning est transactionnel et répétable, crée les rôles manquants et ne remplace pas les mots de passe des rôles existants. Des attributs administratifs ou appartenances inattendus provoquent un refus explicite. Les credentials configurés doivent donc correspondre aux rôles existants. Un volume M4 sans tables métier peut suivre cette procédure. Un schéma métier déjà présent ou un propriétaire/grant inattendu exige une revue de l'opérateur ; ne pas stamp, drop, transférer la propriété ou changer les mots de passe automatiquement. La procédure ne garantit pas la compatibilité de bases modifiées hors missions. Les workers ne migrent pas silencieusement.

## Fixtures fictives

Alice (-1001, user), Bob (-1002, user) et Admin fictif (-1003, admin) utilisent respectivement `demo-Alice-only!`, `demo-Bob-only!`, `demo-Admin-only!`. Ce sont des mots de passe publics de démonstration, jamais des secrets ou comptes réels. Argon2id emploie le profil RFC 9106 LOW_MEMORY : 64 MiB, trois passes, parallélisme quatre, sel aléatoire. Les valeurs hachées ne sont pas déterministes et ne sont jamais affichées.

Les tickets -2001/-2002 appartiennent à Alice/Bob ; les commentaires -3001/-3002 concernent Alice (Alice et administrateur) et -3003 Bob. Ces objets permettront de tester la propriété plus tard, sans présumer un contrôle d'accès actuel. La commande seed prend un verrou transactionnel PostgreSQL, conserve les hachages existants valides et ne crée aucun doublon. Une collision de nom, identifiant, mot de passe ou champ de fixture incompatible refuse toute l'opération, avec rollback. Aucune suppression, réinitialisation ou modification des autres données. Les objets de démonstration modifiés ne sont pas réécrits automatiquement.

## Tests, limites et résultats

Les tests unitaires et les 25 contrôles existants tournent sous Windows/Linux. Les tests d'intégration dans `vulnerable-app/integration` tournent seulement sur PostgreSQL réel via `compose.ci.yaml`, dans la base/volume jetables du runner. Ils exigent le marqueur explicite `VULNLAB_EPHEMERAL_DB=ci-only`, ne passent pas silencieusement et n'utilisent pas SQLite. **Ne jamais utiliser ce profil CI sur un volume local existant.** Downgrade, effacement des fixtures de test et ré-upgrade sont destructifs et limités à cette base CI. Aucune commande downgrade n'est ajoutée au CLI opérateur.

La CI conserve Python Windows, Python Linux et Docker Linux, construit les images sans les publier, vérifie migration et cohérence, puis contraintes, relations, cascades, UTC, rollback, seed, CRUD/DDL et grants futurs. Les contrôles HTTPS/réseau M4.1 restent exécutés. L'image de test contient Pytest ; l'image runtime conserve uniquement les dépendances d'exécution. Aucun port de stockage supplémentaire. Docker Desktop local reste inaccessible et les sorties possibles du proxy demeurent une limite. Les résultats réels de livraison seront consignés après exécution de la CI.

Voir l'[ADR M5](decisions/0005-data-foundation.md) pour les versions, sources et décisions.
