# M6.1 — Validation locale Docker Desktop Windows

Date : 2026-10-02. M6 validée par le Product Owner sur `4aa5cb0`. M6.1 reste soumise à revue et validation finale. Aucun changement métier, migration, version épinglée ou fusion.

## État initial et préparation

Branche `codex/m6-auth-sessions`, dépôt propre, PR #4 en brouillon. Le moteur Linux Docker Desktop 28.0.4 répond sur `npipe:////./pipe/dockerDesktopLinuxEngine`. L'accès au pipe nécessite une exécution autorisée hors sandbox ; aucun contexte global ou fichier Docker personnel n'a été modifié. Les commandes utilisent `.tools/docker-config` et l'endpoint explicite.

Inventaire préalable sans environnement ni configuration sensible : trois conteneurs securevault arrêtés (`securevault-api-1`, `securevault-postgres-1`, `securevault-redis-1`), volume `securevault_postgres_data`, réseau `securevault_default`. Identifiants, statut/code de sortie/timestamps et images des conteneurs ont été conservés dans une preuve locale ignorée, puis comparés après les tests. Le port loopback 8443 était libre ; le volume de validation était absent.

Les fichiers existants `certs/local/vulnerable/server.crt`, `server.key` et `secrets/local/session-key` ont été conservés, sans remplacement ni affichage des clés. OpenSSL vérifie le certificat et `vulnerable.vulnlab.test`. Aucun hosts, magasin de confiance, pare-feu ou logiciel global n'a été modifié.

## Ressources dédiées et commandes

Le projet `vulnlab-m61-validation` crée quatre conteneurs, trois réseaux (`_ingress`, `_frontend`, `_backend`) et le volume neuf `vulnlab-m61-validation_pgdata`, créé à `2026-10-02T08:57:13Z`. Compose les étiquette avec son nom de projet. L'overlay [compose.validation.yaml](../compose.validation.yaml) utilise l'image distincte `vulnlab-m61-validation-app:m6.1` pour app/data-tools. Les témoins et sondes temporaires portent aussi une étiquette de projet et sont supprimés par leur identifiant exact.

Commandes PowerShell depuis la racine, avec un Python local sous `.tools/python/cpython-3.13.15-windows-x86_64-none/python.exe` :

```powershell
$dockerArgs = @('--config', '.tools/docker-config', '-H', 'npipe:////./pipe/dockerDesktopLinuxEngine')
$composeArgs = $dockerArgs + @('compose', '--project-name', 'vulnlab-m61-validation', '--env-file', '.env.example', '-f', 'compose.vulnerable.yaml', '-f', 'compose.validation.yaml')
docker @composeArgs config --quiet
docker @composeArgs build app
docker @composeArgs up -d --wait --wait-timeout 120
docker @composeArgs --profile tools run --rm data-tools upgrade
docker @composeArgs --profile tools run --rm data-tools check
docker @composeArgs --profile tools run --rm data-tools seed
```

**Avant toute nouvelle validation**, vérifier que le nom de projet choisi et son volume sont absents, et que 8443 est libre. Ne pas arrêter son occupant. Les ressources conservées de cette livraison ne sont pas une base vierge à réutiliser pour une suite destructive. Générer certificat et clé uniquement lorsque leurs fichiers sont absents ; les scripts refusent de les écraser.

Les scripts reçoivent des variables limitées à leur processus :

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
$env:DOCKER_CONFIG = (Resolve-Path '.tools/docker-config').Path
$env:VULNLAB_COMPOSE_PROJECT = 'vulnlab-m61-validation'
python scripts/ci/verify_auth_https.py
python scripts/ci/verify_docker.py
```

Dans l'exécution réalisée, ces variables ont été transmises aux processus enfants Python, sans persistance ni changement de contexte. Les exemples sont à exécuter dans une session dédiée. Le parcours d'inscription HTTPS est destiné à une pile fraîche : il crée un compte fictif et consomme des quotas.

## Observations Windows réelles

- Image construite, dépendances verrouillées cohérentes, quatre services healthy. Migrations `upgrade`, `check` et `seed` exécutées explicitement ; aucune migration depuis Gunicorn.
- Client Python HTTPS depuis Windows : CA locale explicite, nom TLS vérifié, accès loopback sans modification hosts. Inscription, login, account échappé, logout POST, refus GET logout, CSRF, attributs du cookie, rotation et rejeux refusés, redirection externe refusée et quotas malgré des en-têtes forgés réussissent. Cookies, jetons et réponses sensibles restent en mémoire.
- Contrôles HTTPS d'infrastructure : healthz 200, route absente 404 sans traceback, Host inconnu 421, SNI inconnus rejetés, HTTP en clair 400 sur le port TLS. Le client curl Windows avec `--cacert` et `--resolve` réussit sans désactiver TLS.
- Seul port publié : `127.0.0.1:8443`. Réseaux frontend/backend internes ; UID principaux non root, capacités effectives nulles, no-new-privileges et racines en lecture seule. Écritures temporaires ciblées permises et écriture à la racine refusée. Compte SQL applicatif sans privilèges globaux, connexion effective et accès TCP internes vérifiés. Aucun identifiant de migration dans l'app.
- Contrôle positif du témoin depuis proxy réussi ; sondes app/db/redis : socket disponible puis `network-unreachable`. Les erreurs d'outil, de syntaxe et le timeout global restent distincts d'un refus de connexion. Les témoins/sondes sont retirés après chaque contrôle.

### Permissions des clés

Docker Desktop présente les bind mounts Windows avec un mode apparent `777`. Ce résultat **ne prouve pas des ACL NTFS privées**. De plus, `test -w` donne un résultat trompeur pour le fichier proxy malgré le montage `RW=false`.

Le contrôle vérifie désormais la lecture par le processus non root et le refus réel d'une ouverture append, **sans écrire de contenu ni tronquer le fichier**. Ce refus réussit pour les deux clés. Les ACL NTFS sont examinées comme métadonnées : aucune ACE autorisant la lecture à Everyone, Authenticated Users, Anonymous, Users ou Guests n'est observée. Les ACE spécifiques au compte local, aux identités de sandbox, à SYSTEM et aux administrateurs restent présentes ; leur appartenance complète n'est pas auditée. Cette observation limitée n'est pas une équivalence au mode POSIX 0640.

Sur Linux CI, les assertions 0640 et absence de droits pour les autres restent exigées, en plus du refus réel d'ouverture en écriture. Aucun chmod Windows, changement d'ACL ou privilège supplémentaire n'est introduit.

## Tests et état final

Localement : 64 tests Pytest passent, dont les 54 existants et 10 ciblés sur les noms de projet et les ACE de lecture trop larges/manquantes. Ruff et formatage incluent scripts/tests ; Compose et actionlint réussissent, ainsi que `git diff --check`. Les 84 tests d'intégration ne sont **pas** lancés localement : ils restent exécutés sur la base jetable Linux CI, séparément des preuves Windows ci-dessus. La CI de la tête finale est vérifiée avant remise dans la [PR #4](https://github.com/Iyed523/VulnLab/pull/4).

Arrêt ciblé exécuté :

```powershell
docker @composeArgs stop --timeout 20
```

Les quatre conteneurs de validation sont arrêtés avec code 0 ; conteneurs, réseaux, image et volume PostgreSQL sont conservés pour revue. Aucun témoin temporaire ne subsiste. Les trois conteneurs securevault ont exactement les mêmes identifiants, images et états/timestamps qu'avant les tests ; leurs volumes et réseau restent présents. Ils n'ont été ni démarrés ni montés par les contrôles. Aucun volume supprimé, aucun prune ou nettoyage global.

Limites : les sorties du proxy restent possibles ; le témoin prouve seulement le refus d'accès au témoin local au moment du test. L'isolation du navigateur n'est pas démontrée et aucun navigateur personnel authentifié n'est utilisé. Aucun audit byte à byte des volumes indépendants ou des appartenances ACL, aucun tiers ciblé, déploiement ou publication d'image. Arrêt à M6.1 pour revue du Team Lead et validation du Product Owner.
