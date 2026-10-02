# Authentification et sessions M6

M7 étend la même vérification d'échéance, d'état actif et de disponibilité Redis à chaque route tickets, avec réponses privées sans cache partagé. Aucun changement de cookie, TTL ou quota : voir [contrats M7](tickets-comments.md). Le parcours HTTPS ajoute deux utilisateurs et les opérations tickets/commentaires.

M6 est validée par le Product Owner. Le [rapport M6.1](local-validation-m61.md) ajoute les preuves HTTPS réelles depuis Windows vers Docker Desktop, les différences de permissions et l'arrêt ciblé avec volume conservé. Les limites Docker Desktop mentionnées dans le bilan M6 ci-dessous sont historiques ; les sorties du proxy et l'isolation du navigateur restent des limites actuelles.

M5 est validée sur `b6700c2`. M6 ajoute un socle de référence sans faiblesse volontaire, sans route de tickets, sans modification des modèles ou migrations, et sans implémentation dans `secure-app`. La branche `codex/m6-auth-sessions` dépend de `codex/m5-data-foundation`. Sa PR reste en brouillon ; toute fusion et tout reciblage ultérieur exigent une autorisation.

## Contrats

- `GET /register` et `GET /login` affichent des formulaires locaux Jinja/CSS.
- `POST /register` normalise le nom conformément à M5, force `role=user` et `active=true`, refuse les champs sensibles et les doublons de champs. Succès : 303 vers login, sans connexion automatique. Collision : 409, y compris après une insertion concurrente, avec rollback.
- `POST /login` renvoie une erreur générique 401 pour identifiant inconnu, mot de passe incorrect ou compte inactif. Un hash Argon2id fictif est vérifié pour les identifiants inconnus ; cela ne constitue pas une garantie de temps constant. Un hash ancien est renouvelé après authentification réussie. Succès : 303 vers `/account`. `next` accepte seulement `/account` ; une autre destination reçoit 400.
- `GET /account` exige un compte actif et affiche uniquement son nom, son nom affiché et son rôle. Aucun hash ni donnée d'un autre compte. Les valeurs HTML sont échappées.
- `POST /logout` exige authentification et CSRF ; supprime la session Redis et le cookie. GET reçoit 405. Les visiteurs non authentifiés sont redirigés vers login.

Les mots de passe contiennent 12 à 128 caractères, sans troncature ni exigence artificielle de classes de caractères. Les limites sont vérifiées avant Argon2id. Nom brut limité à 128 caractères, nom affiché à 100 ; corps HTTP limité à 8192 octets. Les mots de passe ne sont jamais stockés dans les sessions ni réaffichés dans les formulaires.

## Sessions et indisponibilité

Flask-Login 0.6.3, Flask-Session 0.8.0, Flask-WTF 1.3.0, Flask-Limiter 4.1.1 et redis-py 7.4.1 sont épinglés dans le lock. Redis 7 est compatible avec la contrainte `<8` de `limits[redis]`. Les sessions sont exclusivement côté serveur, encodées en MessagePack sans repli pickle. Le cookie `__Host-vulnlab-session` porte un identifiant opaque aléatoire, `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, sans Domain ni remember-me.

La session authentifiée expire après 1800 secondes, avec échéance absolue côté serveur et TTL Redis. La connexion remplace l'identifiant et supprime l'ancien enregistrement. Le compte actif est relu en PostgreSQL sur chaque requête d'authentification : une désactivation invalide une session existante. Les réponses d'authentification portent `Cache-Control: no-store`.

Une configuration absente, une erreur SQL, Redis ou du stockage des compteurs produit une réponse générique 503, jamais une authentification accordée ni un stockage de secours. Une erreur de sauvegarde après traitement remplace également la réponse de succès. Si Redis est inaccessible, la suppression distante ne peut être garantie avant son retour ou l'expiration : le client reçoit 503 et son cookie est supprimé. `/healthz` reste indépendant des services et ne crée pas de session.

## CSRF, compteurs et proxy

CSRF reste actif sur les trois POST, avec durée de jeton de 15 minutes et vérification stricte du referrer HTTPS. Jeton absent/invalide : 400. Les compteurs Redis limitent login à 5 POST/minute et register à 3 POST/minute par adresse IP, sans verrouillage permanent de compte. Les tentatives à CSRF invalide peuvent consommer le quota ; un dépassement reçoit 429.

Le déploiement Compose autorise exactement un saut Nginx (`ProxyFix` pour adresse et protocole seulement). Nginx remplace les en-têtes transmis par le client et conserve le port HTTPS dans Host. Cette confiance suppose l'accès applicatif privé prévu par la topologie ; elle n'est pas une protection d'un serveur Flask directement exposé. Les logs HTTP ne contiennent que méthode et statut, sans requête complète, cookies ou paramètres.

## Clé locale et exécution

Avant le démarrage décrit dans [Docker](docker.md), exécuter :

```powershell
python scripts/generate_session_key.py
```

Le script crée exclusivement `secrets/local/session-key`, aléatoire, ignoré par Git et exclu du contexte Docker. Il refuse de remplacer un fichier existant et n'affiche pas sa valeur. Sous Linux, mode 0640 et groupe du propriétaire ; le conteneur applicatif reçoit ce groupe via `TLS_KEY_GID` et un montage en lecture seule. Sous Windows, conserver les ACL locales privées. La CI génère une clé éphémère par checkout, sans artefact contenant la clé. L'application ne reçoit pas les identifiants de migration.

## Vérifications et limites

Les tests unitaires couvrent configuration absente, redirections et génération sans écrasement. Les tests d'intégration utilisent PostgreSQL et Redis réels sur les ressources CI jetables : concurrence, Argon2, expiration, rotation/rejeu, logout, compte inactif, CSRF, quotas et erreurs de backend. Le script `scripts/ci/verify_auth_https.py` utilise le certificat local comme CA explicite, vérifie le nom TLS et traverse réellement Nginx sur loopback, sans désactiver la validation TLS. Il conserve les valeurs sensibles uniquement en mémoire.

La [CI sur b9d27e7](https://github.com/Iyed523/VulnLab/actions/runs/36985502105) passe sur les trois jobs. Docker Linux exécute 84 tests d'intégration (55 M5 et 29 M6), puis les assertions M4 et le parcours HTTPS réel : inscription, login, account, logout, rejeux de SID, CSRF, attributs du cookie et quotas malgré des en-têtes forgés. Le contrôle positif du proxy et les refus du témoin local par app/db/redis réussissent. Le nettoyage de la pile et du volume CI réussit. Les erreurs de backend sont injectées dans des clients utilisant les services réels ; ce ne sont pas des tests de coupure physique des conteneurs.

La première CI avait signalé le type incompatible de durée CSRF avec Flask-WTF 1.3 ; la valeur est désormais 900 secondes, sans désactivation de CSRF. Un test unitaire exerce directement génération et validation avec cette version épinglée. Local Windows : 54 tests réussis (41 M4/M5 et 13 M6), Ruff et formatage sur tous les modules/scripts, dépendances cohérentes, wheel construite hors ligne avec templates/CSS présents, Compose, actionlint, 79 liens documentaires locaux et `git diff --check`. La tête de livraison est également vérifiée en CI avant remise via la [PR brouillon M6 #4](https://github.com/Iyed523/VulnLab/pull/4).

Commandes depuis la racine, après synchronisation verrouillée documentée en M5 :

```text
uv run --locked --project vulnerable-app pytest vulnerable-app/tests tests/ci
uv run --locked --project vulnerable-app ruff check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
uv run --locked --project vulnerable-app ruff format --check --config vulnerable-app/pyproject.toml vulnerable-app scripts tests/ci
uv pip check --python vulnerable-app/.venv/Scripts/python.exe
uv build vulnerable-app --python vulnerable-app/.venv/Scripts/python.exe --wheel --no-build-isolation --offline
docker compose --env-file .env.example -f compose.vulnerable.yaml -f compose.ci.yaml --profile ci --profile tools config --quiet
actionlint -shellcheck= -pyflakes= .github/workflows/ci.yml
git diff --check
```

Les exécutables locaux sont sous `.tools` ou la venv ; le cache uv est dirigé vers `.tools/uv-cache` dans le sandbox. En CI seulement, `docker compose ... --profile ci run --rm integration-test`, `python3 scripts/ci/verify_docker.py` et `python3 scripts/ci/verify_auth_https.py` réalisent les contrôles destructifs sur les ressources propres au runner. Ne jamais appliquer la suite d'intégration à un volume local existant.

Ces tests fonctionnels ne constituent pas un audit global de sécurité. Docker Desktop local et l'isolation du navigateur ne sont pas démontrés ; les sorties possibles du proxy restent une limite M4. Le témoin réseau M4 démontre uniquement le refus d'accès à un témoin local depuis les services testés. Aucun tiers, déploiement ou publication d'image. Une clé configurée mais illisible/invalide fait échouer explicitement le démarrage, sans clé automatique ou stockage de secours.

La première CI verte signalait aussi l'option Redis dépréciée `retry_on_timeout` ; elle est remplacée par `Retry(NoBackoff(), 0)`, API vérifiée dans la version installée, pour ne pas répéter automatiquement les opérations échouées. Les timeouts de connexion et socket restent limités à une seconde.

Sources : [Flask-Login](https://flask-login.readthedocs.io/en/0.6.3/), [Flask-Session](https://flask-session.readthedocs.io/en/latest/security.html), [Flask-WTF CSRF](https://flask-wtf.readthedocs.io/en/latest/csrf/), [Flask-Limiter](https://flask-limiter.readthedocs.io/en/stable/configuration.html), [ProxyFix](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/), [Redis Retry](https://redis.readthedocs.io/en/stable/retry.html).
