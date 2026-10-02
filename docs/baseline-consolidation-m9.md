# M9 — Consolidation et préparation de l'intégration

M1 à M8 et leurs corrections sont validées par le Product Owner. M9 part du dépôt propre, branche M8 à `b9f5a771cfc39e677601f69949268862ca262a56`. Consolidation sur `codex/m9-baseline-consolidation`, sans modification métier, version, migration, topologie de référence ou privilège. Aucune fusion, suppression de branche ou création de tag autorisée ici.

## Revue de la chaîne publiée

Les six PR sont ouvertes en brouillon ; les checks Python Linux, Python Windows et Docker Linux sont tous SUCCESS, pour push et PR aux têtes ci-dessous. Chaque tête contient sa base publiée ; deltas propres examinés par `git diff BASE HEAD`, et chemins versionnés inventoriés. Pas de clés/certificats privés, `.tools`, environnements locaux ou `secrets` versionnés. `.env.example` et mots de passe de fixtures restent fictifs et explicitement pédagogiques.

| PR | Base publiée | Tête validée | Périmètre du delta et revue |
| --- | --- | --- | --- |
| [#1](https://github.com/Iyed523/VulnLab/pull/1) | main `4b7f0c4` | `15284a827e2511195ef4f58c1f0858177ec6c56f` | M1–M3, outillage/CI/Docker et documentation ; 30 fichiers |
| [#2](https://github.com/Iyed523/VulnLab/pull/2) | chore/bootstrap-lab | `aabc745d0c103513e3d556bd3965fd36131b9dee` | HTTPS et témoin réseau strict M4/M4.1 ; 14 fichiers |
| [#3](https://github.com/Iyed523/VulnLab/pull/3) | codex/m4-local-https | `b6700c2905948c266af9d02de2d15ceb71f34468` | PostgreSQL, rôles séparés, migration 0001, fixtures/tests ; 29 fichiers |
| [#4](https://github.com/Iyed523/VulnLab/pull/4) | codex/m5-data-foundation | `4f1e2440212aedf88334dca20eb478e7edbc38db` | Auth/session/CSRF, HTTPS et validation Windows M6.1 ; 34 fichiers |
| [#5](https://github.com/Iyed523/VulnLab/pull/5) | codex/m6-auth-sessions | `b12bc1a6ed4ca7046032ffd0112638767f564e84` | Tickets privés/commentaires, autorisations et tests ; 24 fichiers |
| [#6](https://github.com/Iyed523/VulnLab/pull/6) | codex/m7-tickets-comments | `b9f5a771cfc39e677601f69949268862ca262a56` | Profil/admin minimal, révocation durable, migration 0002 ; 30 fichiers |

Les migrations 0001/0002 sont cumulatives, avec upgrade/check, conservation des données 0002 et tests PostgreSQL/Redis. Les corrections et tests précédents restent dans les arbres descendants. Aucun scénario VULN, implémentation secure-app ou déploiement. Les documents anciens sont des preuves historiques ; les contrats courants se trouvent dans [M8](profile-admin.md).

Protections main relues via API : PR obligatoire, trois checks GitHub Actions stricts (branche à jour), historique linéaire, conversations résolues, application aux administrateurs, force push et suppression interdits. Zéro approbation GitHub obligatoire pour le dépôt individuel ne remplace pas la validation du Product Owner. Squash seul autorisé ; auto-merge désactivé. **`delete_branch_on_merge=true` est actuellement activé** : le plan exige sa désactivation, avec autorisation explicite, avant la première fusion ; sinon GitHub pourrait supprimer automatiquement une branche parente encore utilisée. Aucun réglage distant modifié en M9.

## Validation Windows et ressources

L'inventaire initial du moteur Linux Docker Desktop réussit : sept conteneurs arrêtés code 0, quatre `vulnlab-m61-validation-*` et trois `securevault-*`, volumes `vulnlab-m61-validation_pgdata` et `securevault_postgres_data`, réseaux propres. Une preuve locale ignorée conserve identifiants, images, états/timestamps sans environnements ou logs sensibles.

La préparation vérifie l'absence du projet/volume M9 et le port 8443 avant toute construction. [Overlay M9](../compose.validation-m9.yaml) : image distincte `vulnlab-m9-validation-app:m8`, projet explicite `vulnlab-m9-validation`, volume propre. Certificats et clé existants à préserver sans remplacement ni affichage. Ne jamais réutiliser les volumes précédents ou exécuter les tests destructifs sur eux.

Incident observé : après l'inventaire réussi, Docker renvoie HTTP 500 sur `/version` et `/containers/json`, avec API négociée 1.48 comme avec API 1.45 limitée au processus de diagnostic. La première préparation s'arrête avant création, build ou démarrage M9. Le parcours HTTPS Windows et l'infrastructure M8 n'ont donc pas été exécutés en M9 ; ce critère reste à confirmer après rétablissement du moteur. Aucun redémarrage global ou opération sur les autres piles. Aucune ressource M9 créée à conserver/arrêter. L'état final des sept conteneurs précédents ne peut pas être relu pendant cet incident ; seule l'absence d'opération de notre part et leur inventaire initial sont établis, sans prétendre vérifier un état externe devenu inaccessible.

Procédure préparée depuis la racine (Python local, environnement limité au processus) :

```powershell
$dockerArgs = @('--config', '.tools/docker-config', '-H', 'npipe:////./pipe/dockerDesktopLinuxEngine')
$composeArgs = $dockerArgs + @('compose', '--project-name', 'vulnlab-m9-validation', '--env-file', '.env.example', '-f', 'compose.vulnerable.yaml', '-f', 'compose.validation-m9.yaml')
docker @composeArgs config --quiet
docker @composeArgs build app
docker @composeArgs up -d --wait --wait-timeout 120
docker @composeArgs --profile tools run --rm data-tools upgrade
docker @composeArgs --profile tools run --rm data-tools check
docker @composeArgs --profile tools run --rm data-tools seed
# Variables DOCKER_HOST, DOCKER_CONFIG et VULNLAB_COMPOSE_PROJECT
# transmises seulement aux processus de validation de cette pile.
python scripts/ci/verify_auth_https.py
python scripts/ci/verify_docker.py
docker @composeArgs stop --timeout 20
```

Les scripts valident TLS avec la CA locale explicite, nom d'hôte et loopback, sans navigateur personnel, modification hosts ou magasin de confiance. Les secrets, SID et jetons restent en mémoire. Migration attendue : `0002_session_version`. Arrêt uniquement M9 ; volume/conteneurs/réseaux/image conservés pour revue, témoins temporaires supprimés par leur contrôle. Après l'arrêt, comparer les identifiants/images/états/timestamps des sept conteneurs initiaux et présence de leurs volumes/réseaux. Aucun `down --volumes`, prune ou nettoyage global local.

## Plan de fusion après autorisation explicite

Ordre strict **#1 → #2 → #3 → #4 → #5 → #6**, squash pour chaque PR. Conserver toutes les branches parentes jusqu'à réparation de tous leurs descendants. Le squash conserve l'arbre, pas l'ascendance : un simple reciblage vers main conserve les anciens commits dans la comparaison à la base commune. Ne pas prendre ce diff cumulatif pour le seul changement de la mission.

1. Obtenir l'autorisation Product Owner pour les fusions et la désactivation de la suppression automatique ; vérifier main, settings, SHA des six têtes et trois checks de #1. Sortir #1 du brouillon, relire son diff, squash sans suppression de branche. Actualiser `origin/main` et relever le vrai SHA de squash S1. Vérifier que l'arbre main est celui de #1 validée.
2. Pour #2, préparer une branche temporaire locale depuis le nouveau main. Appliquer **uniquement** `git diff --binary 15284a8 aabc745` dans un index temporaire ; contrôler le patch et l'arbre. Si main contient d'autres changements, les préserver et revoir tout conflit ; ne pas imposer aveuglément l'ancien arbre.
3. Préparer un commit de réconciliation à deux parents : tête publiée actuelle de #2 et nouveau main, avec l'arbre obtenu à l'étape précédente. `git commit-tree TREE -p HEAD_PR -p NEW_MAIN` puis créer une référence temporaire locale. Vérifier que HEAD_PR est ancêtre du commit et que `git diff NEW_MAIN REPAIR` contient exactement le delta propre attendu. Cela permet un **push normal en avance rapide** vers la branche publiée, sans reset/rebase forcé. Réexaminer le commit et les deux parents avant publication autorisée ; ne pas utiliser aveuglément `merge -s ours`.
4. Seulement pendant l'exécution autorisée : `git push origin TEMP:BRANCHE_PR` sans `--force`, puis reciblage de la PR existante vers main. Relire diff/fichiers/commits et checks sur cette nouvelle tête. Les anciens commits restent dans l'historique de la branche mais la base de comparaison contient désormais le vrai main. Attendre trois checks verts et résolution des conversations avant squash. Vérifier l'arbre main après fusion ; relever S2.
5. Répéter pour #3 avec delta `aabc745..b6700c2`, #4 `b6700c2..4f1e244`, #5 `4f1e244..b12bc1a`, #6 `b12bc1a..b9f5a77`, chaque fois avec le **vrai main courant** et les têtes publiées fraîchement relues. Reconstituer les réconciliations après chaque squash ; les SHA de simulation ne sont pas ceux des futures fusions.
6. Vérifier l'arbre main final contre M8 et expliquer toute différence autorisée. Les fichiers de consolidation M9 appartiennent à une PR dépendante séparée ; ils ne sont pas injectés dans les six PR validées. Si cette PR doit ensuite intégrer main, appliquer le même traitement à sa dépendance M8. CI finale verte sur main. Suppression éventuelle des branches uniquement après décision séparée, tous descendants traités et travail intégré vérifié.

Ce plan est préparé, aucune étape distante de fusion/reciblage/réparation n'est réalisée en M9. Les trois checks actuels ne remplacent pas ceux des futures têtes réconciliées ou de main.

## Simulation locale

[scripts/simulate_pr_chain.py](../scripts/simulate_pr_chain.py) part du main réellement publié après fetch, exige la tête M8 validée, un dépôt propre et l'absence des références temporaires attendues. Il applique chaque delta propre dans un index temporaire, compare l'arbre à la tête de mission, crée six commits de squash locaux et cinq réconciliations locales à deux parents, vérifie l'avance rapide et le delta. Le checkout, l'index réel et les branches publiées restent inchangés ; aucune opération distante/tag. Les références temporaires sont conservées pour revue, jamais écrasées si elles existent.

```powershell
git fetch origin
python scripts/simulate_pr_chain.py
git diff --exit-code codex/m9-integration-preview origin/codex/m8-profile-admin
git rev-parse codex/m9-integration-preview^{tree}
git rev-parse origin/codex/m8-profile-admin^{tree}
```

Simulation réellement exécutée depuis `origin/main` `4b7f0c4d0ead81dd5bd682703e832bd3917efb4b` : chaque patch s'applique sans conflit, chaque arbre intermédiaire égale sa tête validée. Six squashes locaux : `f8c141c`, `bdea9a1`, `54875a4`, `cbaa0d0`, `359c8ac`, `41b4633`. Les cinq réconciliations préservent leur tête publiée comme parent ; l'avance rapide et le delta propre comparé au main simulé sont vérifiés.

Tête `codex/m9-integration-preview` : `41b463366c0a632afe98c43d8b8c567219483cac`. Arbre final et arbre M8 : **`a91d4664b8ea74467a60860c53c8b9830cbff747`**, identiques ; `git diff --exit-code` retourne 0. Aucune différence à expliquer avec M8. Les fichiers de consolidation M9 sont volontairement hors de cette simulation des six PR ; leur PR dépendante séparée sera traitée après M8 si autorisée. Les branches `codex/m9-integration-preview` et `codex/m9-pr2-reconciled` à `codex/m9-pr6-reconciled` restent locales. Cette preuve ne constitue aucune fusion ou réussite des futures checks reciblés.

## Référence proposée

Ne créer `baseline-functional-v1` qu'après autorisation des fusions, chaîne intégrée sans perte, CI finale verte sur le vrai main, validation Product Owner et arbre identifié. Le tag **annoté** devra indiquer que ce socle fonctionnel précède toute faiblesse volontaire et consigner le SHA main/proofs pertinents. Sa création et son push attendent une autorisation explicite distincte ; aucun tag créé en M9.

## Contrôles et limites

82 tests Python locaux réussis sans régression. La CI de consolidation doit réellement exécuter les 236 tests PostgreSQL/Redis sur ses seules ressources dédiées, HTTPS et infrastructure. Ruff/formatage incluent le script de simulation. Dépendances, wheel, Compose, actionlint, liens documentaires et diff check sont vérifiés avant livraison ; résultats CI/tête finale dans la PR M9 dépendante de #6.

Sorties possibles du proxy et isolation du navigateur restent des limites. Le témoin local ne prouve pas un filtrage global. Pas d'audit exhaustif des secrets/historique ou byte à byte des volumes externes ; les chemins versionnés et deltas examinés ne contiennent aucun secret réel identifié. Arrêt M9 pour revue ; aucune mission suivante.
