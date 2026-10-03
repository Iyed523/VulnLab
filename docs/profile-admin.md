# M8 — Profil et administration minimale de référence

M8 et corrections validées par le Product Owner sur `b9f5a771cfc39e677601f69949268862ca262a56`. Les trois jobs finaux sont verts avec 82 tests Python et 236 tests PostgreSQL/Redis ; voir la [CI de livraison](https://github.com/Iyed523/VulnLab/actions/runs/37016447314). Les mentions de revue ci-dessous décrivent la livraison historique. M9 prépare une validation Windows distincte et l'intégration : [rapport M9](baseline-consolidation-m9.md).

M8 part de M7 validée `b12bc1a6ed4ca7046032ffd0112638767f564e84`, dépôt propre, sur `codex/m8-profile-admin`. Les PR précédentes restent en brouillon, sans fusion. Implémentation de référence uniquement dans `vulnerable-app`, sans faiblesse volontaire ni modification de `secure-app`.

## Contrats HTTP

| Route | Accès et résultat |
| --- | --- |
| GET `/account/edit` | Compte actif connecté, formulaire de son propre `display_name` |
| POST `/account/edit` | CSRF valide, uniquement `display_name`, 1–100 caractères sans NUL ; succès 303 `/account` |
| GET `/admin/users` | Administrateur actif ; 20 comptes/page, `page` unique ASCII 1–1000, ordre `id` croissant |
| POST `/admin/users/<id>/activate` | Administrateur actif, cible `role=user`, CSRF ; succès 303 `/admin/users` |
| POST `/admin/users/<id>/deactivate` | Même droit ; désactivation et incrément de version atomiques ; succès 303 `/admin/users` |

Identifiants PostgreSQL signés, fixtures négatives compatibles. Absence/hors plage : 404 après droit administratif. Utilisateur non administrateur : 403 pour une requête valide, indépendamment de l'existence de la cible. Toute cible administrateur, y compris soi-même : 403. GET sur les actions : 405, aucun changement. Visiteur ou session révoquée/expirée : 303 `/login?next=/account` avant contrôle CSRF. Backend indisponible : 503 contrôlé, aucune autorisation par défaut. Réponses privées `Cache-Control: no-store`.

Les seuls champs de formulaire supplémentaires admis sont `csrf_token` et `submit`, chacun unique. Champs inattendus, dupliqués ou invalides : 400 sans écriture partielle. Les actions statut n'acceptent aucun champ métier. Les assignments SQL sont explicites, jamais alimentés en masse depuis le formulaire. Profil ciblé par l'identité courante, statut ciblé par la route. La liste sélectionne uniquement `id`, `username`, `display_name`, `role`, `active` ; aucun hash ou état de session. Jinja échappe les noms, navigation selon rôle et confirmation de désactivation avec CSRF. CSS local, aucune ressource tierce.

## Autorisations et révocation

Le garde `protected` est attaché à toutes les vues privées M6/M7/M8 ; le contrôle global lit ce marqueur, sans liste de nouveaux endpoints à maintenir. Il vérifie disponibilité Redis, échéance absolue et identité SQL actuelle. Les opérations profil/admin relisent et verrouillent l'acteur dans leur transaction : actif, version identique, rôle admin si nécessaire. Les cibles de statut sont verrouillées dans la même transaction. Les tickets et commentaires sont préservés.

Une session contient `_auth_version`, égal à `users.session_version` lors de la connexion. Transition actif vers inactif : incrément sous verrou ; désactivation répétée : pas de nouvel incrément. Réactivation : version conservée. Une version différente invalide le SID et efface la session Redis à sa prochaine requête protégée ; toutes les anciennes sessions émises avant la désactivation M8 sont refusées, même si aucune requête n'a eu lieu pendant l'inactivité. Les sessions d'avant M8 sans version imposent une nouvelle connexion. Le nom affiché est relu à la requête suivante.

Portée : révocation logique vérifiée sur les requêtes protégées ; pas de purge immédiate de tous les SID Redis (ils disparaissent lors du rejeu ou à leur TTL). Une requête déjà engagée avant la désactivation peut finir ; pas d'annulation rétroactive. Les opérations M8 sérialisent leur vérification/écriture avec le verrou utilisateur. M7 conserve ses transactions existantes, sans nouvelle garantie d'annulation des opérations en cours. Une indisponibilité Redis peut empêcher la suppression physique, mais SQL refuse encore la version obsolète après rétablissement. Une modification directe SQL de `active` sans incrément de version ne possède pas la garantie de révocation après réactivation : la maintenance locale doit incrémenter la version dans la même transaction de désactivation. Gestion des administrateurs et rotation globale des sessions hors périmètre HTTP M8.

## Migration et procédure préparée

[ADR 0008](decisions/0008-profile-admin.md), [migration 0002](../vulnerable-app/migrations/versions/0002_session_version.py) : ajout `users.session_version INTEGER NOT NULL DEFAULT 0`, contrainte non négative. Révision 0001 conservée ; aucune réécriture des données métier, privilège ou version épinglée modifiée. Le rôle de migration existant applique le schéma, pas le worker HTTP.

Pour un environnement local que son propriétaire choisit de faire évoluer : sauvegarder ses données fictives, arrêter ses workers et reconstruire l'image M8 ; exécuter explicitement `data-tools upgrade`, puis `data-tools check` avec le projet Compose exact et sa configuration. Redémarrer seulement après réussite. Les connexions existantes doivent être renouvelées. Les instructions M5 de [maintenance et sauvegarde](data-foundation.md) restent applicables. Cette procédure n'est pas appliquée aux piles M6.1 ou securevault conservées.

Un retour à M7 supprimerait le mécanisme de version : arrêter les workers et invalider explicitement les sessions de ce seul projet avant tout retour de code/schéma. Le downgrade retire la colonne ; ne pas le lancer sur un volume existant sans décision de son propriétaire. Le test aller/retour de migration concerne exclusivement la base CI jetable.

## Vérifications et limites

Commandes locales depuis la racine :

```powershell
& vulnerable-app/.venv/Scripts/python.exe -m pytest vulnerable-app/tests tests/ci
& vulnerable-app/.venv/Scripts/python.exe -m pytest --collect-only -q vulnerable-app/integration
& vulnerable-app/.venv/Scripts/ruff.exe check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
& vulnerable-app/.venv/Scripts/ruff.exe format --check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
& .tools/uv/uv.exe pip check --python vulnerable-app/.venv/Scripts/python.exe
& .tools/uv/uv.exe build vulnerable-app --python vulnerable-app/.venv/Scripts/python.exe --wheel --no-build-isolation --offline
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml -f compose.ci.yaml --profile ci --profile tools config --quiet
& .tools/actionlint/actionlint.exe -shellcheck= -pyflakes= .github/workflows/ci.yml
git diff --check
```

82 tests locaux réussis, dont les 75 du socle ; le complément de livraison collecte 236 tests d'intégration (142 du socle + 94 M8). La [première CI M8 sur c3ee33e](https://github.com/Iyed523/VulnLab/actions/runs/37015821758) réussit les trois jobs : 82 tests Python Linux/Windows et 229 tests PostgreSQL/Redis réels, migration aller/retour avec conservation des données, rollback après flush, revalidation d'un acteur obsolète, bornes et projection de liste, CSRF et refus des champs sensibles, sessions anciennes après désactivation/réactivation. Le complément ajoute deux sessions simultanées révoquées, indisponibilité Redis à l'ouverture et contraintes SQL de version ; son résultat sur la tête de livraison sera vérifié et consigné dans la [PR M8 #6](https://github.com/Iyed523/VulnLab/pull/6).

Le parcours HTTPS M6/M7/M8 et l'infrastructure réussissent dans cette CI : profil, administrateur fictif seedé explicitement, statut et rejeu avant toute requête pendant l'inactivité. Trois connexions réelles et deux échecs consomment exactement les cinq essais autorisés ; la sixième reste 429. TLS, contrôle positif du témoin réseau et refus attendus sont réellement exécutés. Nettoyage des ressources appartenant au runner réussi. Ruff/format, 42 distributions compatibles, wheel avec nouveaux modules/templates, Compose, actionlint (sans ShellCheck/Pyflakes), liens locaux et `git diff --check` passent localement.

Docker Desktop local : pipe du moteur Linux absent lors de l'inspection M8 ; pas de validation Docker Windows actuelle revendiquée. Aucune opération de démarrage, migration ou nettoyage sur les piles M6.1/securevault ; aucun volume existant supprimé. Pagination offset bornée, sans instantané concurrent. Pas de preuve d'isolation du navigateur ou d'interdiction globale des sorties. Pas d'audit exhaustif ni déploiement. M8 reste soumise à revue Team Lead et validation Product Owner.

Fichiers M8 : services `accounts`, `account_service`, `web_controls` ; intégration `auth`, `auth_service`, factory, formulaires, modèles et routes tickets ; templates profil/liste et navigation, CSS ; migration 0002 ; tests HTTP, PostgreSQL/Redis et migration ; script HTTPS, workflow CI ; matrice, guides et ADR 0008. Versions verrouillées, première migration et infrastructure inchangées. État Git de livraison : branche M8 suivie sur origin, commits poussés ; la tête et l'état propre sont revérifiés avant remise dans la PR. Aucune PR fusionnée, aucun déploiement ni mission suivante.
