# Audit pédagogique — M11 et préparation M12

Périmètre : application fictive sur les ressources exclusivement locales du runner CI. Aucun audit exhaustif, test tiers ou garantie générale de sécurité. Baseline fonctionnel préservé par le tag annoté `baseline-functional-v1` sur bd029b5.

## VULN-003

Le code préparé pour GET détail omet intentionnellement la propriété du ticket. Le rendu peut donc divulguer titre, description, statut, commentaires, noms affichés des auteurs, dates, total et identifiant dans les liens. Voir [fiche précise et remédiation prévue](vulnerabilities/VULN-003.md).

Observation réelle le 3 octobre 2026 sur [CI cd92bc1](https://github.com/Iyed523/VulnLab/actions/runs/37132827269), trois jobs verts. Python Windows/Linux : 20 fonctionnels et 62 protections chacun ; PostgreSQL/Redis : 100 fonctionnels, 143 protections et 3 démonstrations réussis. Les démonstrations couvrent les deux sens de consultation inter-utilisateur et les commentaires paginés/échappés. Les assertions hors périmètre conservent les refus serveur.

[Preuve nettoyée](proofs/VULN-003-https-ci.json), extraite du parcours réel avec CA et nom TLS vérifiés : compte Alice fictif, ticket et commentaire avec marqueur UUID ; compte Bob distinct, liste 200 sans marqueur et comptage nul, détail direct 200 avec données ; édition GET et POST édition/suppression/commentaire 404, HEAD 404, CSRF absent 400, données de la victime inchangées. Visiteur et SID invalide restent 303. Un autre ticket d’Alice créé avec identifiant retourné vérifie que Bob désactivé puis son ancien SID après réactivation ne peuvent plus lire un ticket victime.

Les contrôles d’infrastructure et témoin réseau réussissent : proxy joignable, app/db/redis refusés. Les migrations sur volume éphémère, sessions, profil/admin, quotas et parcours fonctionnels continuent réellement à passer. Les cinq tentatives de login restent vérifiées (quatre réussies, une refusée, sixième 429) ; le SID original de Bob reste sans requête pendant l’inactivité, distinct de la sonde du compte désactivé.

Aucune validation Docker Desktop M11 ou capture écran revendiquée. Les preuves sont celles du loopback local au runner Linux ; seules les vérifications Python sont également exécutées sur le poste Windows. Aucun cookie, jeton, mot de passe, certificat privé ou chemin personnel présent dans la preuve versionnée. SHA/source CI associés à la preuve, pas une capture inventée. La CI de la tête documentaire finale est vérifiée avant remise dans la [PR brouillon #15](https://github.com/Iyed523/VulnLab/pull/15).

Un résultat vert `vulnerable_behavior` signifie que la divulgation attendue est observée. Il ne signifie pas que le contrôle d’accès est sûr. Les tests de remédiation sont futurs ; aucun code corrigé n’est copié dans secure-app.

## M12 — prérequis navigateur bloqué, aucune XSS introduite

Le [rapport M12](m12-browser-preparation.md) distingue configuration, essais et
conditions non vérifiées. Sur Docker Desktop 4.93.0, moteur Linux 29.8.1/API 1.56,
Chromium Playwright 1.63.0 non-root sans capacités échoue avant navigation :
`No usable sandbox!` avec seccomp standard, puis échec `sys_chroot` du zygote avec
le profil officiel. Mode porte Compose : exit 2 ; mode diagnostic : exit 0 avec
`sandbox_verified=false`, `xss_allowed=false`. [Preuve nettoyée](proofs/M12-browser-preflight.json).
Le succès du diagnostic n'est pas un succès du prérequis. Erreurs d'outil,
syntaxe, timeout et résultats inattendus continuent à faire échouer le contrôle.

36 nouveaux tests unitaires `preserved_protection` vérifient les origines,
chaînes de redirections, erreurs et classement du diagnostic ; ils ne prouvent
pas le filtrage d'un navigateur réel. Les témoins HTTP locaux préparés ne sont
pas exécutés, le TLS navigateur et tout effet XSS ne sont pas vérifiés.
Tous les fichiers de `vulnerable-app` et `secure-app` restent identiques à M11 :
aucune attente d'échappement adaptée. Aucune nouvelle démonstration de faiblesse,
capture DOM ou sévérité observée. VULN-003 et sa preuve antérieure restent valides.

La CI conserve les trois jobs et les suites M11, ajoute Ruff sur l'outillage
navigateur et un diagnostic de compatibilité explicitement nommé préparation.
Elle n'autorise pas l'introduction du XSS. Sur [CI réelle 702fb22](https://github.com/Iyed523/VulnLab/actions/runs/37136872044),
les trois jobs sont verts : Python Windows/Linux, 20 fonctionnels et 98 protections
chacun ; PostgreSQL/Redis, 100 fonctionnels, 143 protections et 3 démonstrations
VULN-003. Parcours HTTPS réel inchangé réussi : divulgation attendue, refus
d'écriture, CSRF, sessions, administration et quotas conservés. Le diagnostic
navigateur CI confirme `zygote-chroot-denied`, sandbox et TLS navigateur non
vérifiés, `xss_allowed=false` ; aucun témoin navigateur exécuté.

La [PR M12 #16](https://github.com/Iyed523/VulnLab/pull/16) reste en brouillon vers
`m11-vuln-003-idor`, dépendant de #15 non fusionnée. Les documents/proofs qui
consignent ces résultats sont livrés après l'exécution observée ; la CI de la
tête documentaire finale est vérifiée séparément avant remise. Arrêt pour
décision Product Owner, sans fusion, déploiement, nouveau tag ou modification
des piles conservées.

Vérifications locales Windows réellement réussies : 20 fonctionnels + 98
protections, wheel, 42 paquets compatibles, Ruff/formatage incluant les scripts
et l'outillage navigateur, Compose, actionlint, liens locaux et diff propres.
Inventaires Docker avant/après identiques : 11 conteneurs préservés avec leurs
états et dates, 3 volumes, 10 réseaux. Aucun audit octet par octet des volumes.
