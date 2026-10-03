# Audit pédagogique initial — M11

Périmètre : application fictive sur les ressources exclusivement locales du runner CI. Aucun audit exhaustif, test tiers ou garantie générale de sécurité. Baseline fonctionnel préservé par le tag annoté `baseline-functional-v1` sur bd029b5.

## VULN-003

Le code préparé pour GET détail omet intentionnellement la propriété du ticket. Le rendu peut donc divulguer titre, description, statut, commentaires, noms affichés des auteurs, dates, total et identifiant dans les liens. Voir [fiche précise et remédiation prévue](vulnerabilities/VULN-003.md).

Observation réelle le 3 octobre 2026 sur [CI cd92bc1](https://github.com/Iyed523/VulnLab/actions/runs/37132827269), trois jobs verts. Python Windows/Linux : 20 fonctionnels et 62 protections chacun ; PostgreSQL/Redis : 100 fonctionnels, 143 protections et 3 démonstrations réussis. Les démonstrations couvrent les deux sens de consultation inter-utilisateur et les commentaires paginés/échappés. Les assertions hors périmètre conservent les refus serveur.

[Preuve nettoyée](proofs/VULN-003-https-ci.json), extraite du parcours réel avec CA et nom TLS vérifiés : compte Alice fictif, ticket et commentaire avec marqueur UUID ; compte Bob distinct, liste 200 sans marqueur et comptage nul, détail direct 200 avec données ; édition GET et POST édition/suppression/commentaire 404, HEAD 404, CSRF absent 400, données de la victime inchangées. Visiteur et SID invalide restent 303. Un autre ticket d’Alice créé avec identifiant retourné vérifie que Bob désactivé puis son ancien SID après réactivation ne peuvent plus lire un ticket victime.

Les contrôles d’infrastructure et témoin réseau réussissent : proxy joignable, app/db/redis refusés. Les migrations sur volume éphémère, sessions, profil/admin, quotas et parcours fonctionnels continuent réellement à passer. Les cinq tentatives de login restent vérifiées (quatre réussies, une refusée, sixième 429) ; le SID original de Bob reste sans requête pendant l’inactivité, distinct de la sonde du compte désactivé.

Aucune validation Docker Desktop M11 ou capture écran revendiquée. Les preuves sont celles du loopback local au runner Linux ; seules les vérifications Python sont également exécutées sur le poste Windows. Aucun cookie, jeton, mot de passe, certificat privé ou chemin personnel présent dans la preuve versionnée. SHA/source CI associés à la preuve, pas une capture inventée. La CI de la tête documentaire finale est vérifiée avant remise dans la [PR brouillon #15](https://github.com/Iyed523/VulnLab/pull/15).

Un résultat vert `vulnerable_behavior` signifie que la divulgation attendue est observée. Il ne signifie pas que le contrôle d’accès est sûr. Les tests de remédiation sont futurs ; aucun code corrigé n’est copié dans secure-app.
