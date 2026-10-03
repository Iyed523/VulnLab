# M12.1 — sandbox et témoins locaux vérifiés, sans connexion au laboratoire

Branche `m12-1-browser-sandbox`, créée depuis M12 validée
`3f39c5b40bf90f48169aa8bed8e6b50577d140e1`, état initial propre.
La livraison dépend de `m12-vuln-002-stored-xss`, sans fusion.
**Aucun changement applicatif ou XSS.** Les arbres `vulnerable-app` et
`secure-app`, main et le tag baseline sont préservés. Les essais antérieurs M12
restent une [preuve historique de blocage](proofs/M12-browser-preflight.json).

## Cause distinguée par des contrôles différentiels

Le seul message Chromium `sys_chroot` ne permettait pas de conclure. La sonde
`namespace_probe.py` appelle `chroot("/proc/self/fdinfo/")` dans un processus
jetable, puis dans un user namespace neuf avec uniquement son UID/GID mappé.
Les deux conteneurs ont les mêmes options non-root, `cap_drop: ALL`, bounding set
nul au départ, no-new-privileges, seccomp, racine en lecture seule et réseau none.
Seule la condition seccomp de `chroot` diffère. Aucun paramètre hôte modifié.

| Contexte observé | Profil officiel | Profil adapté | Interprétation |
| --- | --- | --- | --- |
| Processus Docker non-root, CapEff/CapBnd nuls | EPERM | EPERM | Le syscall autorisé par seccomp reste soumis au droit noyau |
| User namespace neuf, mapping de son seul UID/GID, droit chroot local présent | EPERM | Succès | Le filtre seccomp officiel est le refus déterminant dans cet essai |
| Chromium complet avec sandbox exigée | Porte exit 2, zygote-chroot-denied | Porte exit 0 après tous les témoins | Diagnostic reconnu distinct de sandbox vérifiée |

La création du namespace réussit avec les deux profils. CapEff et CapBnd y sont
temporairement non nuls **relativement à ce namespace enfant**, comportement du
noyau ; ce n'est pas un `cap_add` Docker ni une capacité dans le namespace parent.
Le conteneur initial et les processus navigateur/rendu après initialisation
ont des capacités effectives nulles. Les mappings ne donnent pas accès aux UID
root de l'hôte. Voir [user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)
et [chroot(2)](https://man7.org/linux/man-pages/man2/chroot.2.html).
Ces contrôles isolent la cause pour l'environnement testé, sans exclure un
refus supplémentaire AppArmor, de kernel ou de namespace sur un autre système.

## Adaptation retenue et limites

Le profil officiel Playwright 1.63.0 est conservé inchangé dans `seccomp.json`,
avec sa licence Apache 2.0. `seccomp-chroot.json` en dérive : la règle
`names=["chroot"], action=SCMP_ACT_ALLOW` n'a plus la condition
`includes.caps=["CAP_SYS_CHROOT"]`. Un commentaire explique cette modification.
Un test compare les deux JSON et exige que **rien d'autre ne change**.

Effet : le filtre ne bloque plus ce syscall dans le namespace enfant où Chromium
effectue son confinement. Le noyau continue à exiger le droit chroot dans le
namespace appelant ; son refus reste vérifié dans le processus parent.
Seccomp ne peut pas comparer le chemin pointé par un argument ni réserver cette
règle uniquement à un namespace enfant : le syscall est permis par le filtre
pour tous les processus du conteneur, sous réserve des contrôles noyau.
Le profil n'est donc pas une permission limitée au seul chemin fdinfo.
L'autorisation n'est pas une preuve globale d'absence d'évasion.

[Chromium 153 — credentials.cc](https://github.com/chromium/chromium/blob/153.0.8010.12/sandbox/linux/services/credentials.cc)
décrit le chroot de confinement dans fdinfo, suivi de chdir, et
[namespace_sandbox.cc](https://github.com/chromium/chromium/blob/153.0.8010.12/sandbox/linux/services/namespace_sandbox.cc)
le confinement par namespaces. Le [profil Playwright épinglé](https://github.com/microsoft/playwright/blob/v1.63.0/utils/docker/seccomp_profile.json)
contient la condition retirée. [Docker seccomp](https://docs.docker.com/engine/security/seccomp/)
et [capacités Docker](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities)
expliquent les deux couches distinctes. Sources officielles vérifiées le
3 octobre 2026 ; pas d'attribution de toute restriction au seul log Chromium.

## Navigateur vierge et résultats réels

Docker Desktop 4.93.0 (240920), moteur Linux 29.8.1, API 1.56, WSL2
6.18.40.1 ; même image officielle et digest que M12, Playwright 1.63.0 et
Chromium **153.0.8010.12** réellement observé. Aucun changement de versions.
Le projet dédié est `vulnlab-m12-1-browser-preflight`, réseau `none`, non-root
`pwuser`, sans volume, montage personnel, socket Docker ou port publié.
Racine read-only, tmpfs, limites CPU/mémoire/PID, capacités retirées,
no-new-privileges et seccomp conservés. Aucun SYS_ADMIN/SYS_CHROOT ajouté,
mode privilégié, unconfined, option no-sandbox ou changement système.

`channel="chromium"` utilise Chromium complet de cette image : headless-shell
avait renvoyé ERR_INVALID_URL sur chrome://sandbox. Les libellés sont ceux de
[l'interface Chromium 153](https://github.com/chromium/chromium/blob/153.0.8010.12/chrome/browser/resources/sandbox_internals/sandbox_internals.ts),
pas l'ancien libellé M12 « Namespace Sandbox ».
La sonde exige exactement : Layer 1 Sandbox = Namespace, PID namespaces = Yes,
Network namespaces = Yes, Seccomp-BPF = Yes et TSYNC = Yes.
Les `/proc/.../status` des processus navigateur et rendu confirment UID non-root,
CapEff/CapPrm nuls, NoNewPrivs=1, Seccomp=2 ; les renderers possèdent un filtre
supplémentaire par rapport au processus navigateur. Voir la
[preuve nettoyée réelle](proofs/M12-1-browser-sandbox.json).

Deux témoins HTTP sur loopback et ports dynamiques restent **dans ce conteneur** :

- contexte vierge positif sans filtre : HTTP et handshake WebSocket réussissent ;
- contexte filtré : HTTP autorisé et redirection relative autorisée réussissent ;
- accès direct interdit, redirection interdite et chaîne de deux redirections refusés ;
- WebSocket interdit fermé sans handshake supplémentaire reçu par le témoin ;
- compteurs du témoin interdit inchangés après application de la politique.

Chaque refus HTTP utilise une page dédiée pour éviter une navigation concurrente
vers le document d'erreur Chromium. L'essai a aussi révélé un blocage du callback
WebSocket en API synchrone ; traceback localisé sur `WebSocketRoute.close`.
L'outillage utilise désormais l'API **asynchrone** officielle Playwright, sans
changer les assertions ou les dépendances. L'échéance globale des témoins échoue
explicitement en cas de suspension. Les serveurs ont des timeouts et sont fermés
après les contextes. Aucun tiers n'est une cible, aucune charge XSS exécutée.

## Porte obligatoire, tests et commandes

La CI appelle la porte sans mode diagnostic permissif. Un lancement bloqué
retourne 2, même si son motif est reconnu ; outil absent, timeout, état incomplet
ou résultat inattendu échouent. Un contrôle négatif réel exige exit 2 avec le
profil officiel. Un succès de porte ne concerne que les exigences **M12.1**.
`lab_tls_verified=false` et `xss_allowed=false` restent explicites.

```text
docker compose -f compose.browser.yaml config --quiet
docker compose -f compose.browser.yaml build
docker compose -f compose.browser.yaml run --rm browser-preflight
python scripts/ci/verify_browser_namespace.py
docker compose -f compose.browser.yaml down --timeout 20
```

Le script différentiel crée seulement des conteneurs `--rm`, réseau none,
non-root sans capacité ni volume. Il exige les résultats attendus pour chaque
profil et la porte négative ; aucune erreur d'exécution n'est absorbée.
Pas de profils, cookies, HAR, vidéos, certificats ou secrets téléversés.

Tests locaux réellement réussis : **20 fonctionnels + 111 protections**,
dont 49 tests unitaires navigateur (36 M12 conservés, 13 nouveaux).
Les doubles de test ont été adaptés aux coroutines, sans attente supprimée.
Les états sandbox manquants/refusés, erreurs d'outil et unique delta seccomp sont
testés. Ruff/formatage sur 47 fichiers, Compose navigateur et applicatif/CI,
actionlint et diff check réussis. Un avertissement de cache Pytest Windows lors
d'un essai élevé ne concernait pas les tests ; la suite finale utilise
`-p no:cacheprovider`, sans modifier les permissions ou les assertions.

Les trois jobs CI conservent les suites M11 PostgreSQL/Redis/HTTPS et le build
wheel, et exécutent maintenant la porte obligatoire et le différentiel.
Leur résultat sur la tête publiée est contrôlé avant remise dans la PR de livraison.

## Portée et arrêt

Les témoins prouvent les refus du médiateur HTTP/redirections et WebSocket face
à des endpoints locaux joignables. Ils ne prouvent pas le filtrage global de
tous les flux natifs/protocoles du navigateur. Le réseau none n'est pas une
preuve de la politique à appliquer après connexion au proxy.
Le profil seccomp amont conservé n'est pas présenté comme un audit du profil
Docker actuel ni une garantie complète d'isolation du kernel.

Aucune connexion au laboratoire, confiance TLS navigateur, charge XSS,
démonstration DOM ou remédiation secure-app. Ces étapes restent ultérieures,
après revue et autorisation. Aucun changement de main/tag, fusion ou déploiement.
Piles et volumes securevault, M6.1 et M9 préservés ; inventaire des métadonnées
comparé avant/après essais : les 11 conteneurs, 3 volumes et réseaux des piles
sont inchangés. Le réseau Docker intégré `bridge` a un identifiant différent
du relevé initial ; la cause n’a pas été établie et aucune mutation de ce réseau
n’a été demandée par ces essais. Aucun audit octet par octet des volumes.
