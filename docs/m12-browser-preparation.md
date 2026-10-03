# M12 — préparation uniquement, prérequis navigateur bloqué

Rapport historique de M12 à `3f39c5b`. La résolution ultérieure, sans connexion
au laboratoire ni XSS, est décrite dans [M12.1](m12-1-browser-sandbox.md).

La branche `m12-vuln-002-stored-xss` part de M11 validée,
`a61fd1ae25d6783ea7a5aa9cbf2b323b817f3a74`. La [PR M11 #15](https://github.com/Iyed523/VulnLab/pull/15)
reste en brouillon vers main, sans fusion. Le tag annoté `baseline-functional-v1`
reste sur bd029b5, objet tag 455d21178ecebb70845306604bea2d5a10816705.
L'état initial était propre ; aucune modification utilisateur à déplacer.

**Aucun XSS introduit.** Le template, les suites M11, leurs attentes d'échappement,
les parcours HTTPS, les modèles, migrations et dépendances applicatives restent
identiques à M11. `secure-app` reste documentaire. Le cas de repli du point 4 de
la mission M12 s'applique : livrer les essais et la configuration, puis attendre
la décision du Product Owner. Aucune démonstration `vulnerable_behavior` VULN-002
ni capture de marqueur DOM n'est revendiquée.

## Configuration examinée et préparée

`compose.browser.yaml` est un projet distinct `vulnlab-m12-browser-preflight`.
Le conteneur `--rm` utilise `pwuser`, une racine en lecture seule, toutes les
capacités supprimées, `no-new-privileges`, seccomp actif, un réseau `none`,
des limites CPU/mémoire/PID et un `/tmp` éphémère. Aucun port publié, volume,
socket Docker, montage de répertoire personnel, profil, compte ou extension
personnels. Pas d'IPC partagé avec l'hôte, `SYS_ADMIN`, mode privilégié,
`seccomp=unconfined`, modification système ou option `--no-sandbox`.
Le profil Chromium temporaire est créé par Playwright dans le tmpfs puis détruit.

Image officielle : `mcr.microsoft.com/playwright/python:v1.63.0-noble`,
digest `sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0`.
Outils séparés de l'application : Playwright 1.63.0, pyee 13.0.0,
greenlet 3.2.4, typing-extensions 4.15.0 ; `pip check` réellement réussi.
Le premier build avait signalé typing-extensions absent : dépendance transitive
ajoutée explicitement, sans changement applicatif.

La [documentation Docker Playwright](https://playwright.dev/python/docs/docker)
explique l'association utilisateur non-root/profil seccomp et l'alignement des
versions image et paquet. La [référence de lancement](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch)
indique que la sandbox est désactivée par défaut : la sonde impose
`chromium_sandbox=True`. Le [profil officiel v1.63.0](https://github.com/microsoft/playwright/blob/v1.63.0/utils/docker/seccomp_profile.json)
est conservé sans modification dans `docker/browser/seccomp.json`, SHA-256
`cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
Ces sources officielles ont été vérifiées le 3 octobre 2026.

## Essais réellement exécutés et diagnostic

Poste : Docker Desktop 4.93.0 (240920), moteur Linux 29.8.1, API 1.56,
WSL2 Linux 6.18.40.1, amd64. Avant création : port 8443 sans listener,
11 conteneurs existants arrêtés, 3 volumes et 10 réseaux inventoriés.
Les sondes n'ont démarré aucune pile applicative du poste.
Après les essais, les inventaires avant/après sont identiques : mêmes IDs,
images, états, codes de sortie et dates de démarrage/arrêt des 11 conteneurs,
mêmes 3 volumes et 10 réseaux. Les piles securevault, M6.1 et M9 sont préservées.
Cette comparaison n'est pas un audit octet par octet des volumes. Seules les
images/cache de construction du navigateur ont été ajoutées localement.

| Essai Chromium vierge, sandbox exigée | Résultat réel | Conséquence |
| --- | --- | --- |
| Seccomp Docker standard, aucune capacité | Exit 2, `No usable sandbox!`, SIGTRAP | Sandbox non vérifiée |
| Profil officiel Playwright, aucune capacité | Exit 2, `sys_chroot("/proc/self/fdinfo/") == 0` échoue ; zygote interrompu | Sandbox non vérifiée |
| Configuration Compose finale, mode porte | Exit 2, `zygote-chroot-denied` | Interdiction de poursuivre vers le XSS |
| Même configuration, `--diagnostic` | Exit 0, même blocage explicite et `xss_allowed=false` | Diagnostic reconnu, jamais validation des prérequis |

La sonde confirme d'abord UID non-root, CapEff nul, `NoNewPrivs=1` et `Seccomp=2`.
Le profil officiel ne permet `chroot` que si la capacité `CAP_SYS_CHROOT` est
incluse, alors que toutes sont retirées ici : cette règle est cohérente avec
l'échec observé. Sans trace syscall, ce constat n'exclut pas une restriction
additionnelle du runtime. Il ne démontre pas une incompatibilité de tous les
environnements Playwright. Aucune capacité ni règle seccomp supplémentaire n'a
été ajoutée pour contourner cet échec.

La [preuve JSON nettoyée](proofs/M12-browser-preflight.json) contient les résultats
réels, pas des données de navigation. Aucun cookie, jeton, profil, clé, compte
réel ou capture inventée. Les diagnostics bruts du navigateur vierge restent
dans `.tools`, ignoré ; pas d'upload de traces, HAR, vidéos ou profils en CI.

## Restrictions préparées, portée et exigences encore non vérifiées

`network_policy.py` filtre des origines HTTP(S) exactes : schéma, hôte et port,
sans userinfo, URL malformée ou schéma local. La médiation emploie
`route.fetch(max_redirects=0)`, vérifie chaque Location et ne restitue que la
réponse finale, avec une limite de dix sauts. Elle refuse WebSocket.
Un simple `route.continue_()` ne suffit pas à maîtriser une chaîne de redirections.
Voir la [référence Route](https://playwright.dev/python/docs/api/class-route#route-fetch).
Les tests unitaires vérifient aussi 301/302/303/307/308, les boucles, Location
absente et la propagation des erreurs d'outil.

`witnesses.py` prépare deux serveurs HTTP sur loopback du conteneur, ports
dynamiques, sans tiers : une sonde positive atteint le témoin interdit dans un
contexte vierge distinct ; le contexte filtré doit ensuite atteindre le témoin
autorisé, refuser l'accès direct et la redirection vers le témoin interdit, sans
nouvelle requête reçue par celui-ci. Service workers bloqués, téléchargements
refusés, `ignore_https_errors=False`, contextes non persistants fermés explicitement.
**Ces contrôles navigateur ne se sont pas exécutés : le lancement est bloqué.**
Les 36 nouveaux tests unitaires ne remplacent pas ces témoins réels.

Le réseau `none` borne l'essai aux témoins internes au conteneur. Aucun accès au
laboratoire n'est configuré à ce stade. Une future connexion au proxy nécessitera
un réseau dédié, une seule origine TLS autorisée, la confiance explicite dans le
certificat public local et un contrôle négatif de certificat/nom invalide.
La vérification TLS M11 par le client HTTP est conservée ; elle ne prouve pas le
TLS du navigateur. **TLS navigateur non préparé complètement et non vérifié.**
Un filtre Playwright ne démontre pas une isolation globale du navigateur, des
flux natifs, du système de fichiers ou de tous les protocoles.

## Commandes et classification CI

Depuis la racine, après inventaire des ressources :

```text
docker compose -f compose.browser.yaml config --quiet
docker compose -f compose.browser.yaml build
docker compose -f compose.browser.yaml run --rm browser-preflight
docker compose -f compose.browser.yaml run --rm browser-preflight --diagnostic
docker compose -f compose.browser.yaml down --timeout 20
```

Le mode porte reste nonzero pour un blocage connu. Seul le mode diagnostic
classe explicitement les deux erreurs connues ; un outil absent, une erreur de
syntaxe, un timeout ou un autre échec d'exécution demeure un échec explicite.
La CI utilise ce diagnostic de compatibilité nommé **préparation uniquement**.
Une CI verte signifie que M11 reste vérifiée et le diagnostic est valide ;
elle n'autorise pas le XSS et ne signifie pas que la sandbox fonctionne.
Les autres assertions CI restent inchangées. Nettoyage limité au projet M12
sans volume et à la pile éphémère du runner déjà utilisée pour M11.

Contrôles de livraison : Ruff et formatage incluent `docker/browser`, scripts et
tests ; tests Python fonctionnels/protections séparés ; wheel ; Compose ;
actionlint ; liens documentaires locaux ; `git diff --check`. La CI réexécute
PostgreSQL/Redis réels (100 fonctionnels, 143 protections, 3 démonstrations
VULN-003) et le parcours HTTPS M11. Les résultats finaux sont consignés dans
l'[audit](security-audit.md).

[CI observée sur 702fb22](https://github.com/Iyed523/VulnLab/actions/runs/37136872044) :
trois jobs verts, 20 fonctionnels + 98 protections Python par plateforme ;
100 fonctionnels + 143 protections PostgreSQL/Redis + 3 démonstrations VULN-003.
HTTPS et infrastructure M11 réellement réussis. Le diagnostic navigateur du
runner confirme le même `zygote-chroot-denied`, sans exécution des témoins.
Ces résultats concernent le commit d'outillage ; la tête documentaire finale
est également contrôlée avant remise. [PR brouillon M12 #16](https://github.com/Iyed523/VulnLab/pull/16)
vers `m11-vuln-003-idor`, dépendance M11 préservée.

Exécutés sur Windows : 20 tests fonctionnels et 98 protections réussis, dont les
36 nouveaux tests de préparation. `uv pip check` : 42 paquets compatibles.
Wheel construite avec `uv run --locked --group build --offline -- uv build
--wheel --no-build-isolation --offline`. Ruff/formatage : 45 fichiers Python,
Compose applicatif/CI et navigateur, actionlint, liens locaux et diff propres.

## Décision ouverte et arrêt M12

Faire examiner la compatibilité d'une sandbox sans capacités ajoutées, notamment
le traitement de `chroot` dans le namespace enfant, ou un autre environnement
d'exécution dédié. Toute solution doit conserver les restrictions de la mission
et être réellement vérifiée avant le changement de rendu. Ne pas modifier le
système hôte, accorder des privilèges supplémentaires ou désactiver la sandbox
dans cette livraison. Si le prérequis est résolu ultérieurement, exécuter ensuite
les témoins et TLS avant tout ajout de VULN-002. Arrêt pour revue Team Lead et
décision Product Owner, sans fusion ni passage à une autre mission.
