# Socle Docker local — M3 soumise à revue

M1 et M2 sont validées selon le cadrage reçu. M3 prépare uniquement `/healthz` et une pile locale Nginx → Gunicorn/Flask avec PostgreSQL et Redis pour les futurs accès. Aucun métier, session, table ou scénario vulnérable n’est ajouté. `secure-app` reste documentaire.

## État réellement observé le 1 octobre 2026

Docker CLI 28.0.4 et Compose v2.34.0-desktop.1 sont installés. Le contexte observé est `default`. Le moteur est inaccessible : le canal Windows `docker_engine` est absent, y compris lors de la vérification autorisée hors sandbox. Aucun processus Docker Desktop ou backend n’a été observé. Aucun écouteur sur 8080 n’a été retourné par l’inspection locale.

La configuration Docker personnelle n’a pas été lue : après un avertissement d’accès refusé émis par le client, les commandes utilisent `--config .tools/docker-config`, un emplacement dédié, sans changer le contexte global. Aucune installation système ni démarrage de Docker Desktop n’a été effectué.

La configuration Compose est validée statiquement. L’image applicative et les conteneurs n’ont pas été construits/démarrés. Le type Linux du moteur, les ressources préexistantes VulnLab et toutes les protections à l’exécution restent non vérifiés. **M3 ne peut pas être considérée entièrement validée tant que ces contrôles ne sont pas réalisés.**

## Images fixées et sources

Les manifestes ont été consultés dans les registres officiels Docker Hub et GHCR. Les digests ci-dessous sont ceux des index multiarchitectures ; Linux/amd64 est disponible pour les cinq images. La disponibilité ne prouve pas leur bon fonctionnement dans cette configuration.

| Image | Digest SHA256 de l’index |
| --- | --- |
| `python:3.13.15-slim-bookworm` | `2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26` |
| `nginx:1.30.5-alpine` | `0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94` |
| `postgres:16.15-bookworm` | `efedf3595f1d6f415c08568ba171029bf54052e754cc9f030e3f2412b21f3d67` |
| `redis:8.10.2-trixie` | `6f81e8915c60b065a524e6967e0ad1c639ba6efa84d669f823683ea04d9150ee` |
| `ghcr.io/astral-sh/uv:0.12.19` (construction seule) | `04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424` |

Sources de distribution : [Python](https://hub.docker.com/_/python), [Nginx](https://hub.docker.com/_/nginx), [PostgreSQL](https://hub.docker.com/_/postgres), [Redis](https://hub.docker.com/_/redis), [uv Docker](https://docs.astral.sh/uv/guides/integration/docker/). Python reste 3.13.15 standard ; son GIL est vérifié localement, pas encore dans l’image.

Consultations de sécurité : [avis Nginx](https://nginx.org/en/security_advisories.html), [avis PostgreSQL](https://www.postgresql.org/support/security/), [avis Redis](https://redis.io/blog/security-advisory-cve-2026-81934/), [publication Gunicorn 26.2.0](https://github.com/benoitc/gunicorn/releases/tag/26.2.0), [métadonnées Gunicorn](https://pypi.org/pypi/gunicorn/26.2.0/json). Nginx 1.30.5 inclut les seuils de correction indiqués sur la page consultée ; Redis 8.10.2 est postérieur au correctif 8.10.1 de CVE-2026-81934. PostgreSQL 16 est une série maintenue et 16.15 est une version corrective disponible. Gunicorn 26.2.0 est stable, non retirée et compatible Python >=3.10 ; l’API PyPI ne renvoie aucun avis associé. L’API GitHub des avis Gunicorn a retourné 404, ce qui ne prouve pas l’absence d’avis.

Ces vérifications sont ponctuelles : aucun scan exhaustif des couches d’images ou des bibliothèques du système n’a été exécuté. Épingler un digest rend la sélection explicite, mais impose une mise à jour volontaire pour recevoir de futurs correctifs.

## Construction et dépendances

Le contexte est la racine du dépôt. `.dockerignore` utilise une liste d’admission limitée aux sources Python, métadonnées du projet et Dockerfile. `.git`, `.tools`, `.venv`, `.env`, certificats, tests, caches et preuves sont exclus.

Gunicorn est déclaré uniquement pour `sys_platform == 'linux'`. Il figure dans le verrou universel et n’est pas installé dans l’environnement Windows. Le groupe `build` contient Hatchling 1.32.4, version identique au backend, et ses transitives sont résolues dans `uv.lock`.

Le Dockerfile synchronise `--locked --no-dev --group build`, puis construit avec `--no-build-isolation` dans cet environnement déjà verrouillé. Il exporte temporairement les seules dépendances d’exécution depuis le verrou avec leurs hashes, installe la wheel sans mode éditable dans `/opt/runtime`, puis copie cet environnement dans l’étape finale. Le code source du checkout, uv, Hatchling, Ruff et Pytest ne sont pas copiés dans l’environnement d’exécution. Aucun téléchargement ou installation n’a lieu au démarrage.

Gunicorn est le processus principal via CMD exec, reçoit SIGTERM et écrit ses journaux sur stdout/stderr. Son arrêt gracieux est borné à 15 secondes, avec 20 secondes accordées par Compose.

## Réseaux, santé et comptes fictifs

- Projet dédié : `vulnlab-vulnerable`, fichier explicite [compose.vulnerable.yaml](../compose.vulnerable.yaml), sans Compose par défaut.
- `frontend` interne : proxy et app ; `backend` interne : app, db et redis. Aucun réseau externe ou défaut partagé.
- Seul le proxy publie `127.0.0.1:8080:8080`. App, PostgreSQL et Redis ne publient aucun port hôte.
- App : `GET /healthz` retourne exactement `{"status":"ok"}` avec 200. Il teste seulement le processus HTTP, sans connexion ni diagnostic PostgreSQL/Redis. Flask ajoute les méthodes HTTP HEAD/OPTIONS habituelles ; POST est refusé.
- Le proxy vérifie la réponse de cette route à travers Nginx. L’application attend les healthchecks des stockages ; cela ne signifie pas qu’elle utilise ces stockages.
- PostgreSQL utilise la base `vulnlab`, le compte d’initialisation `vulnlab_init` et le rôle `vulnlab_app` sans superutilisateur, création de base/rôle, réplication ou contournement RLS. Seuls CONNECT et USAGE sur le schéma sont accordés ; aucune table n’existe.
- Authentification PostgreSQL locale et réseau SCRAM-SHA-256, jamais `trust`. L’initialisation ne s’exécute que sur un volume vide ; modifier les variables ne change pas les mots de passe d’un volume existant.
- Redis : mot de passe obligatoire, protected-mode actif, sans RDB ni AOF ; aucune donnée métier. Les ACL métier seront définies lorsqu’un usage sera introduit.

Toutes les valeurs de [.env.example](../.env.example) sont fictives et publiques. Aucun secret personnel n’est nécessaire. Les commandes de validation utilisent ce fichier de démonstration ; une copie `.env` locale éventuelle reste ignorée. Ne jamais afficher un dump Compose complet avec des secrets locaux.

## Privilèges et écritures déclarés

Tous les services demandent `no-new-privileges`, des limites CPU/mémoire/PID, un système de fichiers en lecture seule et aucune capacité Linux par défaut. App : UID/GID 10001, tmpfs `/tmp` pour Gunicorn. Proxy : utilisateur `nginx`, tmpfs `/tmp` pour PID et fichiers temporaires, configuration montée en lecture seule ; son entrypoint est remplacé par Nginx pour éviter la modification des fichiers de configuration au démarrage.

Redis utilise directement l’utilisateur `redis` et un tmpfs `/data`, sans volume persistant. PostgreSQL utilise l’entrypoint officiel : root uniquement pour préparer les droits du volume et du socket, puis passage à `postgres`. Les capacités CHOWN, DAC_OVERRIDE, FOWNER, SETGID et SETUID sont conservées pour cette initialisation ; aucune capacité réseau privilégiée n’est nécessaire. Le volume `vulnlab-vulnerable_pgdata` contient PGDATA ; `/var/run/postgresql` et `/tmp` sont des tmpfs ciblés.

Ces utilisateurs et permissions sont des déclarations à vérifier dans les processus réels, notamment après l’initialisation SQL. Aucun conteneur privilégié, socket Docker, réseau hôte ou montage général du poste n’est prévu.

## Commandes PowerShell depuis la racine

Prérequis : Docker Desktop démarré par l’opérateur avec un moteur Linux accessible, port 8080 libre. Vérifier les ressources existantes avant lancement ; ne pas changer le contexte global ni arrêter un processus qui occupe le port.

```powershell
docker --config .tools/docker-config version
docker --config .tools/docker-config info --format '{{.OSType}}'
docker --config .tools/docker-config context show
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
docker --config .tools/docker-config ps -a --filter label=com.docker.compose.project=vulnlab-vulnerable
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml config --quiet
```

La validation `config --quiet` a été exécutée avec succès. Les commandes suivantes sont préparées, non exécutées faute de moteur :

```powershell
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml build app
if ($LASTEXITCODE) { throw 'Construction Docker échouée' }
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml up -d --wait --wait-timeout 120
if ($LASTEXITCODE) { throw 'Démarrage Docker échoué' }
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml ps
Invoke-RestMethod -Uri http://127.0.0.1:8080/healthz -TimeoutSec 5
curl.exe --max-time 5 -i http://127.0.0.1:8080/missing
```

Contrôles ciblés à réaliser avant validation, sans dump d’environnement :

```powershell
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml exec -T app id
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml exec -T proxy id
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml exec -T app python -c "import socket; [socket.create_connection((h,p),timeout=3).close() for h,p in [('db',5432),('redis',6379)]]; print('TCP internes accessibles')"
$roleQuery = "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = 'vulnlab_app';"
$roleQuery | docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli ping'
```

Compléter par les inspections ciblées `docker inspect --format` des ports (`NetworkSettings.Ports`), réseaux (`NetworkSettings.Networks`), options de sécurité/capacités, montages et processus (`docker top`). Vérifier que les quatre conteneurs sont sains, que le serveur SQL s’exécute comme `postgres`, Redis comme `redis`, et que seules les écritures prévues sont possibles. Les sondes TCP confirment uniquement la connectivité, pas des accès métier ni une sécurité de protocole complète.

Arrêt propre avec conservation du volume :

```powershell
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml down --timeout 20
```

Remise à zéro **destructive**, uniquement après décision explicite et vérification du projet : la commande suivante supprime aussi le volume PostgreSQL et **toutes ses données fictives**. Elle n’a pas été exécutée.

```powershell
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml down --volumes --timeout 20
```

## Contrôles exécutés et limites

Synchronisation verrouillée du groupe build, contrôle des 19 distributions installées sous Windows, Ruff et formatage réussis, **4 tests collectés et réussis** (3 HTTP techniques, 1 packaging), wheel construite sans isolation de build supplémentaire, configuration Compose valide. Le workflow Python inclut le groupe build et est vérifié avec actionlint. Un défaut initial de formatage du nouveau test a été corrigé par Ruff.

Une seconde synchronisation conserve le hash du verrou. La construction a également réussi avec `uv build vulnerable-app --wheel --no-build-isolation --offline`, enveloppé par `uv run --locked --group build --project vulnerable-app` depuis la racine, confirmant que le backend local fonctionne sans nouvelle résolution réseau. La validation ciblée du JSON Compose confirme les quatre services, la seule liaison déclarée `127.0.0.1:8080`, les deux réseaux internes et les systèmes de fichiers en lecture seule. Ces résultats restent statiques.

Contrôles du dépôt : 28 fichiers versionnables non suivis examinés, 52 liens Markdown locaux valides, 8 exclusions/inclusions Git conformes, `git diff --check` sans erreur complété par l’examen des nouveaux fichiers (espaces finaux, marqueurs de conflit et motifs ciblés de secrets). Aucun motif recherché n’a été trouvé ; ce contrôle n’est pas un détecteur exhaustif. `secure-app` contient toujours uniquement son README. Le script d’initialisation est en LF pour Linux. Git reste sur `main`, sans commit ni remote.

Le moteur inaccessible empêche : construction Docker, installation non éditable dans l’image finale, démarrage, HTTP traversant Nginx, healthchecks réels, ports/réseaux effectifs, utilisateurs et écritures, attributs SQL réels, communications internes et arrêt de pile. Aucune ressource Docker n’a été créée par la mission, aucun volume n’a été supprimé ; les ressources préexistantes n’ont pas pu être inventoriées.

Les réseaux `internal` restreignent déclarativement les communications ; aucune absence de sortie réseau n’est affirmée. Les contrôles complémentaires sous Docker Desktop, HTTPS local et hôtes distincts relèvent de M4. HTTP local n’est qu’une étape technique avant toute authentification ou session. L’isolation des conteneurs ne garantit pas celle du navigateur.
