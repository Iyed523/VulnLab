# M12.2 — navigateur dédié et HTTPS local

Livraison depuis M12.1 validée `43241ffb4db1c8aec5038a818f8087531ebd2cdb`,
branche `m12-2-browser-lab-tls`, état initial propre. PR brouillon vers
`m12-1-browser-sandbox`, dépendante de #17, #16 et #15, sans fusion.
VULN-003 demeure la seule faiblesse introduite. Les arbres applicatifs,
modèles, migrations, dépendances et `baseline-functional-v1` sont inchangés.
**Aucun XSS : `xss_allowed=false` demeure obligatoire.**

## Topologie dédiée

`compose.browser-lab.yaml` est un overlay de `compose.vulnerable.yaml`.
Projet `vulnlab-m12-2-browser-lab`, volume PostgreSQL neuf, aucune réutilisation
de réseau ou volume securevault/M6.1/M9. Tous les ports proxy sont retirés de
cette pile ; aucun port navigateur/témoin/app/db/redis publié.

| Service | Réseaux de ce projet | Flux utiles |
| --- | --- | --- |
| browser-lab | browser-test interne uniquement | HTTPS proxy 8443 ; témoins locaux dédiés |
| proxy | browser-test, frontend interne, ingress | Proxy HTTP vers app:8000 |
| app | frontend et backend internes | PostgreSQL 5432, Redis 6379 |
| db/redis/data-tools | backend interne | Stockage et provisionnement explicite |
| tls-witness | browser-test interne uniquement | TLS 8443/8444/8445 ; statistiques HTTP 8446 |

Alias Docker local `vulnerable.vulnlab.test` uniquement sur le proxy du réseau
browser-test. Les réseaux effectifs et montages du conteneur navigateur sont
inspectés avant d'attendre son résultat. Les sondes TCP utilisent les IP
numériques inspectées de l'application/frontend, de PostgreSQL et Redis/backend,
jamais une adresse tierce. Un contrôle positif depuis l'app exige que les trois
ports soient réellement joignables, puis le navigateur doit recevoir un refus
de connexion/routage ou un timeout **de connexion**. DNS, permission, outil
absent, syntaxe et timeout global ne valent pas preuve de restriction Docker.
Les adresses internes dynamiques sont retirées de la preuve versionnée.

Le proxy conserve ingress, réseau non interne : des sorties restent possibles
pour son processus. Nginx transmet vers une destination app fixe ; il ne devient
pas un proxy CONNECT générique. Ces tests ne prouvent aucune interdiction globale
des sorties du proxy ni de tous les protocoles natifs du navigateur. Le navigateur
peut joindre les témoins de son propre réseau sans filtre ; les refus du filtre
Playwright sont distincts des refus Docker vers les réseaux internes.

## Deux chemins de confiance TLS distincts

Certificats générés pour deux jours par OpenSSL dans `certs/local/m122`, ignoré
par Git. Le générateur refuse un répertoire préexistant. Une autorité de
laboratoire signe le proxy et les témoins valides ; une seconde autorité signe
le témoin non approuvé. Clés privées réservées au proxy/témoin/générateur,
clé de session réservée à l'app ; **seul public/** est monté dans browser-lab.
Le répertoire public contient seulement des certificats, jamais des clés.
Aucun changement de la confiance Windows, aucun certificat privé versionné.

Chromium : base NSS vide dans `$HOME/.local/share/pki/nssdb`, sous le tmpfs `/tmp`.
`certutil -N --empty-password` puis import de la seule autorité approuvée avec
`-t C,,`. Cette méthode correspond à la [documentation Linux Chromium](https://chromium.googlesource.com/chromium/src.git/+/refs/heads/main/docs/linux/cert_management.md)
(depuis M146, nouveau chemin NSS). `libnss3-tools=2:3.98-1ubuntu0.2` est ajouté
uniquement à l'image de test, même version que NSS de l'image épinglée.
Image, Playwright 1.63.0 et dépendances Python M12.1 restent épinglés.

Médiateur `route.fetch` : pilote Node lancé avec
`NODE_EXTRA_CA_CERTS=/run/trust/trusted.crt`, défini **avant** sa création.
[Node documente la lecture au lancement](https://nodejs.org/api/cli.html#node_extra_ca_certsfile).
Il ajoute cette autorité aux autorités préexistantes ; ce n'est pas une liste
exclusive de confiance, d'où la nécessité de la politique d'origine exacte.
[Playwright route.fetch](https://playwright.dev/python/docs/api/class-route#route-fetch)
utilise la requête API du contexte ; il n'a pas de paramètre Python
`ignore_https_errors`. Les [réglages du contexte](https://playwright.dev/python/docs/api/class-browser#browser-new-context)
fixent `ignore_https_errors=False`, service workers bloqués et téléchargements
non acceptés. Aucun argument navigateur de contournement des certificats.
Les deux chemins sont testés indépendamment, et non supposés équivalents.

| Témoin TLS | Chromium direct | route.fetch puis fulfill |
| --- | --- | --- |
| Autorité approuvée, nom good.vulnlab.test correct | 200 et marqueur neutre | 200 et marqueur neutre |
| Autorité inconnue, nom untrusted.vulnlab.test correct | ERR_CERT_AUTHORITY_INVALID | Erreur explicite de chaîne |
| Autorité approuvée, nom wrong.vulnlab.test incorrect | ERR_CERT_COMMON_NAME_INVALID | Erreur explicite d'altnames |
| Même serveur/certificat incorrect, alias correct.vulnlab.test | Succès | Succès |
| Même serveur d'autorité inconnue, contexte neuf approuvant sa CA | Succès | Succès |

Les témoins ne rejettent ni Host ni SNI. Leur résolution et joignabilité sont
prouvées par les contrôles positifs correspondants. Le dernier contrôle utilise
un **autre processus**, autre HOME/NSS temporaire et nouveau pilote Node avec
bundle des deux CA, seulement après les refus. Il ne transforme pas le contexte
principal en contexte permissif. Aucun `ignore_https_errors=True`.
Les erreurs sont classées par moteur et cause ; une réponse TLS non vérifiée
ne doit jamais être affichée comme le document du témoin.

## Médiation et parcours sans XSS

Le contexte métier autorise uniquement `(https, vulnerable.vulnlab.test, 8443)`.
Les contextes de témoins sont neufs et distincts. Navigation brute contrôlée
avant normalisation Chromium : HTTP, userinfo, autre hôte/port sont refusés.
Chaque hop de redirection est vérifié avant la requête suivante, avec
`max_redirects=0` et borne de dix sauts. Les exceptions fetch restent en mémoire,
la requête est annulée avec `failed` ; les appelants font échouer toute erreur
inattendue. Aucun message d'erreur contenant headers/body d'auth n'est imprimé.

Après 301/302 POST ou 303 hors GET/HEAD, la requête suivante devient GET avec
corps explicitement vide (`b""`) et sans en-têtes d'entité hérités. `None`
reprendrait le corps original selon le [client Playwright 1.63.0](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/src/client/fetch.ts).
L'en-tête Cookie original est retiré pour laisser le cookie jar partagé gérer
rotation et suppression : un en-tête explicite empêcherait cette mise à jour,
comme le montre le [moteur API Playwright épinglé](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/src/server/fetch.ts).
307/308 conservent méthode et corps ; HEAD reste HEAD après 303. Ces contrats
sont testés, puis le parcours réel vérifie connexion et déconnexion.

Le médiateur fournit le document final à l'URL de navigation d'origine : il
n'émule pas un changement automatique de l'URL visible après redirection.
Le parcours ne suppose donc pas cette équivalence ; il navigue explicitement
vers `/account` après vérification du résultat de connexion. Cette limite sera
à considérer avant tout scénario DOM futur, sans modification applicative ici.

Témoins réseau connecté : HTTPS interdit et handshake WSS joignables sans filtre,
puis origine autorisée/redirection relative acceptées. Accès direct interdit,
redirection et chaîne vers le témoin interdits ; compteurs du témoin inchangés.
HTTP clair et userinfo refusés. WSS fermé sans nouveau handshake serveur.
Un téléchargement natif est réellement déclenché : son événement et le motif
exact `accept_downloads=False` sont vérifiés, pas seulement ERR_FAILED. Le
médiateur refuse aussi Content-Disposition attachment avant fulfill, sans
événement download ni erreur fetch. Aucune acceptation ni persistance.
Une tentative d'enregistrement service worker doit produire le
message de blocage Playwright et aucun worker. Les témoins loopback M12.1 sont
aussi rejoués dans ce conteneur connecté.

Parcours : `/healthz`, formulaires `/login` et `/register`, CSS local, connexion
Alice fictive, consultation de son propre compte, déconnexion puis nouvel accès
au compte montrant le formulaire de connexion. Cookies et CSRF uniquement dans
les contextes en mémoire, sans trace, HAR, capture de formulaire, profil exporté
ou log contenant leurs valeurs. Aucun usage de l'IDOR, commentaire ou charge XSS.

Sandbox contrôlée avant et après les accès : Layer 1 Namespace, namespaces PID
et réseau, seccomp-BPF et TSYNC ; processus navigateur/renderers non-root,
CapEff/CapPrm nuls, NoNewPrivs=1, Seccomp=2 et filtre renderer additionnel.
Le profil seccomp M12.1 reste inchangé. Racine read-only, cap_drop ALL,
no-new-privileges, tmpfs, limites CPU/mémoire/PID et profil vierge conservés.

## Exécution et portée des preuves

```text
# Construire M12.1 avant le générateur/différentiel conservés.
docker compose -f compose.browser.yaml build
python scripts/ci/verify_browser_lab.py --proof .tools/m122-local-proof.json
# En Windows, fournir --docker avec le chemin Docker et DOCKER_HOST/DOCKER_CONFIG.
```

Le script vérifie absence des ressources de son projet et des certificats,
génère des secrets fictifs neufs, contrôle Compose, construit les images,
attend la santé, migre/seed explicitement, exécute les témoins puis nettoie dans
finally. `down --volumes` cible uniquement le projet qu'il a créé ; suppression
du répertoire de certificats vérifiée sous certs/local. La CI garde aussi un
nettoyage de secours sur son runner neuf. Aucune ressource des piles conservées
n'est arrêtée, recréée ou supprimée.

Les suites M11 et portes M12.1 restent exécutées dans la CI. La porte M12.2
retourne nonzero si un prérequis manque ; même un diagnostic reconnu n'est pas
une validation. Preuve nettoyée et résultats de CI sur la tête finale sont
examinés avant remise ; aucune preuve n'est produite sur une porte en échec.

Essais corrigés : format initial de clé de session incompatible, décodage de
sortie Docker Windows cp1252, paramètre route.fetch non pris en charge,
refus de routage non encore classé, libellé d'erreur de navigation lors du
téléchargement. Aucun de ces essais n'a été présenté comme une porte réussie.
Le témoin HTTPS faisait initialement les handshakes dans la boucle accept :
une préconnexion Chrome inactive bloquait le client suivant et produisait
un vrai timeout fetch, qui a maintenu la porte en échec. Une page dédiée
est utilisée pour le téléchargement refusé, comme pour les autres navigations
négatives, pour éviter une navigation concurrente vers chrome-error. Les handshakes sont
désormais dans des threads distincts avec timeout de trois secondes.
La wheel utilise explicitement l'interpréteur venv contenant Hatchling ; le
premier essai avec l'interpréteur de base n'avait pas ce backend.

Le parcours authentifié initial échouait également : la médiation reprenait
corps et cookies du POST après 303. La correction ci-dessus a été vérifiée par
la connexion, lecture du compte Alice et révocation effective à la déconnexion.

## Résultats locaux du 4 octobre 2026

Docker Desktop 4.93.0 (240920), moteur Linux 29.8.1, API 1.56,
noyau WSL2 6.18.40.1, Chromium 153.0.8010.12. Docker Desktop a été relancé après
constat d'un moteur arrêté ; aucun réglage système ou magasin de confiance
n'a été modifié. Les 11 conteneurs, leurs états/dates/images, 3 volumes et 7
réseaux des piles conservées sont inchangés. Les 10 noms de réseaux persistent ;
seul l'identifiant du réseau intégré bridge a changé au redémarrage Docker.
Aucune vérification octet par octet des données des volumes n'est revendiquée.

| Contrôle réellement exécuté | Résultat / portée |
| --- | --- |
| Pytest fonctionnel, sélection sans vulnerable_behavior/preserved_protection | 20 réussis |
| Pytest preserved_protection | 157 réussis, dont 95 unitaires navigateur ; 131 tests antérieurs conservés |
| Ruff check et format, app/scripts/tests/ci/docker/browser | Réussis ; 53 fichiers au format |
| Wheel uv build --wheel --no-build-isolation --python .venv/Scripts/python.exe | Réussie ; code applicatif inchangé |
| Compose M12.1 et overlay M12.2 config --quiet, actionlint | Réussis |
| Porte M12.1 + verify_browser_namespace.py | Réussis ; contrôle navigateur officiel exit 2 attendu, pas un succès sandbox |
| verify_browser_lab.py --proof .tools/m122-local-proof.json | Exit 0 ; sandbox avant/après, deux moteurs TLS, réseau, parcours propre et nettoyage vérifiés |
| Liens locaux, sources LF de la preuve, arbres app/secure/seccomp, git diff --check | Vérifiés avant commit |

[Preuve nettoyée](proofs/M12-2-browser-lab-tls.json) : résultats structurés du
dernier lancement réussi, environnement et empreintes SHA-256 des sources LF.
Ni adresse IP dynamique, cookie, jeton, identifiant de connexion, clé privée,
profil, capture ou trace de formulaire. La CI exécute séparément les suites
PostgreSQL/Redis M11 : leurs résultats ne sont pas déduits du parcours local.
Les liens de CI sur le SHA final figurent dans la PR et le compte rendu de remise.

Écart de préparation à signaler : la seule consultation initiale du catalogue
APT a utilisé un conteneur jetable root avec CHOWN/DAC_OVERRIDE/FOWNER/SETUID/SETGID
explicités. Cette commande était inutilement privilégiée et ne respecte pas
la contrainte « aucune capacité supplémentaire ». Ce conteneur --rm a terminé ;
il n'a pas exécuté Chromium ni monté de secret ou de pile conservée. Aucune
capacité de ce type n'est ajoutée au navigateur, témoins ou générateur livré.
Cet écart ne doit pas être effacé des observations de mission.

Aucun filtrage hôte, capacité supplémentaire dans la solution, mode privilégié,
unconfined, no-sandbox, socket Docker, réseau hôte, tag, fusion ou déploiement.
Arrêt pour revue Team Lead et validation Product Owner. VULN-002 reste ultérieure.
