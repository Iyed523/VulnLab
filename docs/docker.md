# Docker et HTTPS local — M4 soumise à revue

M1, M2, M3 et M3-Git sont validées selon le cadrage reçu. M4 part de `chore/bootstrap-lab` au commit `15284a8`, pas du main minimal. La PR #1 demeure ouverte en brouillon ; aucune fusion n’est effectuée. `secure-app` reste documentaire.

## État et images

Docker CLI 28.0.4 et Compose v2.34.0-desktop.1 sont présents sur le poste. Le moteur `docker_engine` demeure inaccessible et aucune ressource locale ne peut être inventoriée ou démarrée. Aucun écouteur 8443 n’a été observé. Les contrôles Docker réels sont confiés au runner Linux ; ils ne valident pas Docker Desktop.

Les images et digests du socle M3 sont conservés :

| Image | SHA256 de l’index |
| --- | --- |
| python:3.13.15-slim-bookworm | 2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 |
| nginx:1.30.5-alpine | 0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94 |
| postgres:16.15-bookworm | efedf3595f1d6f415c08568ba171029bf54052e754cc9f030e3f2412b21f3d67 |
| redis:8.10.2-trixie | 6f81e8915c60b065a524e6967e0ad1c639ba6efa84d669f823683ea04d9150ee |
| ghcr.io/astral-sh/uv:0.12.19 (build seul) | 04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 |

Les sources, vérifications ponctuelles de sécurité et limites de ces images sont consignées dans l’[ADR M3](decisions/0003-local-docker.md) et les versions dans le [guide Python](development.md). Le Dockerfile construit la wheel après synchronisation verrouillée du groupe build, sans nouvelle isolation/résolution du backend, puis installe uniquement les dépendances d’exécution et la wheel non éditable. Les outils de développement ne sont pas copiés dans l’environnement final.

## Certificat et hôtes

Le seul hôte servi est `vulnerable.vulnlab.test`, sur `127.0.0.1:8443`. `secure.vulnlab.test` est réservé et rejeté par cette pile. Aucun port IPv6 ni toutes interfaces n’est publié. Le port hôte 8080 est retiré.

Le [script de génération](../scripts/generate_local_certificate.py) utilise OpenSSL pour créer un certificat autosigné RSA 3072/SHA256, SAN DNS `vulnerable.vulnlab.test`, usage serveur, CA:FALSE, valable sept jours. La procédure est reproductible ; les clés sont aléatoires et ne doivent jamais être déterministes. Le script refuse d’écraser un certificat existant. Les fichiers restent dans `certs/local/vulnerable`, ignorés par Git et exclus du contexte Docker.

Choix : confiance explicite dans ce certificat dédié plutôt qu’installation d’une autorité système. Aucun fichier hosts, magasin de confiance ou pare-feu global n’est modifié. Les tests utilisent `--cacert` et `--resolve`, jamais `-k` ou une désactivation de validation TLS. Le nom est vérifié en plus de la signature.

Sous Linux, la clé a le mode 0640 et appartient au groupe de l’opérateur ; le proxy reçoit uniquement ce groupe supplémentaire via `TLS_KEY_GID`. Le certificat est 0644, le répertoire 0755, le montage complet est en lecture seule. La CI vérifie les droits de la clé et son accès par Nginx. Sous Windows, chmod n’offre pas les mêmes garanties que les ACL NTFS : conserver le dossier privé et vérifier manuellement les ACL avant usage ; les droits du montage Docker Desktop restent non vérifiés.

Nginx accepte TLS 1.2/1.3 et rejette les SNI inconnus avec `ssl_reject_handshake`. Après une négociation valide, un Host HTTP inconnu est rejeté avec 421. Un accès HTTP en clair au port TLS reçoit 400, sans atteindre l’application. Aucune redirection vers une destination variable, aucun HSTS persistant ni header de remédiation pédagogique n’est ajouté.

Le healthcheck du proxy utilise seulement `127.0.0.1:8081/healthz` dans son propre conteneur, transmis à Flask. Cette sonde HTTP interne est inaccessible sur les réseaux du conteneur et n’est pas publiée. Elle vérifie le processus/proxy, tandis que le contrôle CI séparé vérifie TLS et le nom depuis le runner. Les communications proxy→app restent HTTP sur frontend interne ; elles ne constituent pas un accès utilisateur non chiffré publié.

## Commandes Windows depuis la racine

Préparer les variables de session Python selon [development.md](development.md). OpenSSL fourni par Git for Windows 3.2.3 a été trouvé et utilisé sur ce poste ; aucun nouvel OpenSSL n’a été installé.

```powershell
& .tools/python/cpython-3.13.15-windows-x86_64-none/python.exe scripts/generate_local_certificate.py --openssl 'C:/Program Files/Git/usr/bin/openssl.exe'
& 'C:/Program Files/Git/usr/bin/openssl.exe' verify -CAfile certs/local/vulnerable/server.crt -verify_hostname vulnerable.vulnlab.test certs/local/vulnerable/server.crt
$env:TLS_KEY_GID = '1000'
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml config --quiet
```

Ces commandes ont réussi hors exécution Docker. Le fichier de démonstration contient uniquement des identifiants fictifs ; une éventuelle `.env` locale reste exclue. Ne pas afficher de dumps d’environnement avec des secrets.

Après vérification d’un moteur Linux accessible, du port 8443 libre et des ressources existantes, les commandes suivantes sont préparées pour Docker Desktop mais non exécutées localement :

```powershell
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml build app
if ($LASTEXITCODE) { throw 'Construction échouée' }
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml up -d --wait --wait-timeout 120
if ($LASTEXITCODE) { throw 'Démarrage échoué' }
curl.exe --noproxy '*' --cacert certs/local/vulnerable/server.crt --resolve vulnerable.vulnlab.test:8443:127.0.0.1 --max-time 5 https://vulnerable.vulnlab.test:8443/healthz
docker --config .tools/docker-config compose --env-file .env.example -f compose.vulnerable.yaml down --timeout 20
```

Si le curl Windows utilise un backend TLS incapable de charger ce certificat via `--cacert`, utiliser le curl fourni par Git for Windows et consigner sa version. Ne pas contourner l’erreur avec `-k`. Pour un navigateur, une résolution et une confiance explicites nécessiteraient une décision de l’opérateur ; le laboratoire ne les installe pas automatiquement.

## Linux et CI

Depuis la racine, avec Python et OpenSSL disponibles :

```bash
set -eu
python3 scripts/generate_local_certificate.py
export TLS_KEY_GID="$(id -g)"
openssl verify -CAfile certs/local/vulnerable/server.crt -verify_hostname vulnerable.vulnlab.test certs/local/vulnerable/server.crt
docker compose --env-file .env.example -f compose.vulnerable.yaml config --quiet
docker compose --env-file .env.example -f compose.vulnerable.yaml build app
docker compose --env-file .env.example -f compose.vulnerable.yaml up -d --wait --wait-timeout 120
python3 scripts/ci/verify_docker.py
docker compose --env-file .env.example -f compose.vulnerable.yaml down --timeout 20
```

Le script de vérification utilise le contexte Docker actif du runner et un nom de témoin dédié ; il refuse implicitement un conflit de nom au lieu de supprimer une ressource existante. Les utilisateurs locaux doivent conserver leur contexte et inventorier la pile avant exécution. La CI génère ses certificats éphémères, conserve les diagnostics d’échec et supprime uniquement ses ressources et son volume jetable avec `always()`. Le poste local utilise `down` sans `--volumes`, afin de conserver les données.

Pour renouveler un certificat expiré : arrêter la pile, retirer explicitement les deux fichiers de cette version après vérification de leur chemin, puis relancer la génération. Aucun script ne détruit automatiquement une clé existante. Une remise à zéro SQL est destructive : `docker compose --env-file .env.example -f compose.vulnerable.yaml down --volumes --timeout 20` supprime les données fictives de cette pile ; ne jamais l’employer automatiquement sur un volume local existant.

## Réseaux et portée des preuves

- Ingress bridge non interne : proxy seulement, pour permettre la publication loopback, conformément au correctif M3.
- Frontend interne : proxy et app. Backend interne : app, db et redis. Aucun service interne ne publie de port ; aucun accès direct de ces services à ingress.
- Les flux nécessaires Nginx→app et app→ports PostgreSQL/Redis sont vérifiés. La route `/healthz` ne réalise elle-même aucune connexion SQL/Redis.
- Le script conserve le temoin HTTP local sur ingress, sans port publie, et son controle positif depuis le proxy ; la presence de wget est verifiee. Pour app/db/redis, une sonde ephemere utilise l'image Python deja epinglee et partage seulement l'espace reseau du service (`--network container:<identifiant>`), sans montage, port, capacite ou privilege supplementaire. Aucun interpreteur n'est installe dans les images applicatives. Temoin et sondes sont retires par leurs seuls identifiants crees, dans finally.
- Chaque sonde confirme le chargement de socket avant la connexion TCP au temoin. Seuls ECONNREFUSED, ENETUNREACH, EHOSTUNREACH et TimeoutError de connexion (delai socket de deux secondes) produisent un JSON exact et le code dedie 10. Une connexion reussie fait echouer le controle de blocage. Outil absent, erreur de syntaxe, stderr, code/resultat incoherent ou autre exception font echouer le controle ; les codes 1 et 124 seuls ne prouvent rien. Le timeout global du processus Docker (quinze secondes) est une erreur distincte, jamais une preuve reseau.
- La preuve concerne exclusivement l'acces TCP au temoin depuis ces espaces reseau, au moment du test, via une sonde non root. Elle ne teste pas les binaires metier ou une politique dependant de leur UID, ni une interdiction globale des sorties. Les 21 tests du protocole/classement sont distincts des quatre tests applicatifs ; Ruff et le formatage CI couvrent aussi scripts et tests d'infrastructure.
- Ce témoin montre aussi que le proxy peut sortir sur ingress. Il ne prouve pas une interdiction générale de sorties réseau du proxy, ni celle des autres services vers toutes les destinations possibles.

Restriction recherchée : rendre ingress interne supprimait le fonctionnement loopback sur le runner M3 ; ce changement n’est donc pas réintroduit. Désactiver le masquerading ne suffirait pas à bloquer les destinations directement routables. Sans filtrage réseau par service, aucune garantie globale du proxy n’est revendiquée. Proposition à examiner par le Product Owner : une politique de sortie sur un hôte Linux dédié limitant le proxy au frontend et aux connexions entrantes établies, vérifiée par plusieurs témoins. Elle nécessiterait une décision d’environnement et des règles de pare-feu ; M4 ne les applique pas au système global et n’ajoute ni privilège NET_ADMIN ni orchestrateur.

## Droits et données

App et proxy sont non root, sans capacités ; Redis utilise redis. PostgreSQL passe de l’initialisation aux processus postgres, avec les capacités d’initialisation M3 conservées uniquement dans la déclaration. La CI inspecte les UID et capacités effectives du processus principal, no-new-privileges, rootfs en lecture seule, montages et écritures temporaires ciblées. /tmp est writable pour app/proxy/db et /data pour Redis ; les racines doivent refuser un fichier de sonde.

PostgreSQL conserve son volume dédié et l’authentification SCRAM. `vulnlab_init` initialise ; `vulnlab_app` n’est ni superutilisateur, créateur de bases/rôles, réplicateur ni bypass RLS. Les tests vérifient ces attributs et la connexion du compte applicatif. Aucun schéma métier n’est ajouté. Redis reste authentifié et volatil.

Deux noms d’hôtes ne prouvent ni la séparation des cookies futurs, ni celle du navigateur. Aucun compte personnel ne doit être ouvert dans le profil de laboratoire ; les preuves XSS futures resteront locales, sans collecte ni transmission de données.

## Résultats M4

Local Windows : certificat généré et nom/signature vérifiés, configuration Compose et actionlint validés ; moteur Docker inaccessible. Aucun conteneur, volume ou réseau local n’a été créé ou supprimé. Contrôles locaux réussis : synchronisation verrouillée et cohérence des 19 distributions, Ruff, formatage, quatre tests Pytest, wheel construite hors ligne, Compose, actionlint, 61 liens locaux et diff --check. Le certificat est explicitement vérifié et un nom incorrect est refusé. Les fichiers sensibles sont ignorés, hors contexte de build ; secure-app reste documentaire. M4 reste soumise à revue.

Options vérifiées dans les sources officielles : [Nginx SSL et ssl_reject_handshake](https://nginx.org/en/docs/http/ngx_http_ssl_module.html), [OpenSSL req et addext](https://docs.openssl.org/3.5/man1/openssl-req/), [réseau bridge Docker et masquerading](https://docs.docker.com/engine/network/drivers/bridge/). Aucune nouvelle option n’est supposée disponible sans source ou exécution CI.

La [CI M4 sur b3190fd](https://github.com/Iyed523/VulnLab/actions/runs/36919627007) a réussi pour Python Windows, Python Linux et Docker Linux. Le job Docker a construit/démarré les quatre services, vérifié HTTPS avec confiance et nom, JSON 200, route absente 404, Host inconnu 421, SNI inconnus rejetés, HTTP en clair 400 sur le port TLS, seul port loopback 8443, réseaux, montages, clé 0640 lisible sans écriture, UID non root et capacités effectives nulles, rootfs et temporaires, rôle SQL et accès TCP internes. Le témoin a été accessible du proxy, refusé depuis app/db/redis, puis retiré. Le nettoyage de la pile et du volume éphémère CI a réussi. Ces résultats sont Linux CI, pas Docker Desktop local.

La [PR M4 #2](https://github.com/Iyed523/VulnLab/pull/2) reste ouverte en brouillon vers chore/bootstrap-lab, dépendante de la PR #1. Après fusion autorisée du socle, elle devra être reciblée vers main. Le commit documentaire de bilan ne modifie pas la configuration testée ; la CI de sa tête finale est également suivie avant remise du compte rendu.
