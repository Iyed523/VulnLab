# VULN-003 — IDOR de consultation d’un ticket privé

Faiblesse pédagogique intentionnelle introduite en M11, exclusivement dans `vulnerable-app`. Une démonstration réussie constate une divulgation ; elle ne valide pas la sécurité. La remédiation n’est pas appliquée et `secure-app` reste documentaire.

## Référence et périmètre

Le tag annoté `baseline-functional-v1` conserve le socle correct `bd029b523d1835e737faae51b6c9d5c47d5a6efb`. Son objet tag publié est `455d21178ecebb70845306604bea2d5a10816705`, inchangé. Au baseline, `ticket_detail` impose la propriété ou le rôle admin, et `test_inaccessible_and_missing_ticket_identical_404[GET détail]` exige 404 pour le ticket d’autrui.

Attaquant : utilisateur fictif actif connecté (Bob). Victime : autre utilisateur fictif (Alice). Seul **GET `/tickets/<id>`** utilise `vulnerable_ticket_detail` : recherche SQLAlchemy paramétrée par identifiant, sans filtre propriétaire/rôle. Authentification, état actif, expiration et version de session restent contrôlés avant la vue. Identifiant absent ou hors entier SQL signé : 404. Les fixtures négatives restent compatibles. Le HEAD implicite conserve l’autorisation du baseline, sans divulgation de corps. Aucun mode caché ou option de bypass générique.

`ticket_detail` reste autorisée pour édition, suppression et ajout de commentaire. Liste et comptage gardent le filtre de propriété/rôle ; droits d’écriture, auteur serveur, propriétaire immuable, CSRF, quotas, échappement, profil/admin, TLS et topologie restent inchangés. Les formulaires et boutons rendus à Bob ne lui accordent aucun droit : refus serveur 404 avec CSRF valide, 400 sans CSRF valide.

## Informations réellement rendues

La page expose titre, description et statut du ticket ; contenu des commentaires, nom affiché de leur auteur et date de création ; nombre total de commentaires et identifiant du ticket dans les liens/formulaires. **Les commentaires ne sont pas protégés contre cette lecture** : pagination par 20, pages 1–1000, soit jusqu’à 20 000 lignes parcourables, avec total affiché. L’existence d’un ticket est distinguable de son absence.

Le template ne rend pas le propriétaire SQL, son username, les mots de passe/hashes, les SID, ni les dates de création/mise à jour du ticket. Le CSRF du formulaire est celui de l’acteur courant, pas un jeton de la victime. Le contenu reste échappé HTML ; cette mission n’introduit pas de XSS ni d’écriture inter-utilisateur.

## Correspondances et sévérité

[OWASP Top 10:2025 A01 — Broken Access Control](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/) décrit l’accès à des objets d’autrui par modification de leur identifiant. [CWE-639 — Authorization Bypass Through User-Controlled Key](https://cwe.mitre.org/data/definitions/639.html) correspond précisément à la lecture d’un enregistrement d’un autre utilisateur via une clé contrôlée par le client. Sources officielles vérifiées le 3 octobre 2026 ; correspondance retenue pour ce mécanisme, sans prétendre qu’elle décrit toutes les faiblesses du laboratoire.

Sévérité pédagogique **élevée pour la confidentialité métier** : tout utilisateur actif peut lire les tickets et commentaires privés d’autrui dès qu’un identifiant valide est connu ou deviné. Aucune écriture supplémentaire ni atteinte directe à la disponibilité démontrée ; authentification requise. Pas de score CVSS inventé et données du laboratoire exclusivement fictives.

## Reproduction locale contrôlée

Sur une pile neuve dédiée, avec PostgreSQL/Redis et HTTPS validé, le parcours `scripts/ci/verify_auth_https.py` inscrit Alice (`m11httpsalice`) et Bob (`m7httpsbob`), fictifs. Alice crée un ticket et un commentaire portant un marqueur `VULN-003-<UUID>` ; le chemin est extrait de Location, sans identifiant fixe. Bob se connecte séparément : liste vide et marqueur absent ; GET direct retourne 200 et divulgue ticket/commentaire/auteur/date. HEAD et édition GET restent 404 ; POST édition/suppression/commentaire avec CSRF valide restent 404 ; sans CSRF, 400. La vue d’Alice confirme les données inchangées. Visiteur et SID invalide : 303 vers login.

Un second SID de Bob vérifie le refus sur détail pendant sa désactivation. Son SID original ne fait aucune requête pendant l’inactivité ; après réactivation, il reste révoqué, préservant la preuve M8. Quatre logins réussis et un échec consomment exactement cinq essais ; le sixième reste 429 malgré les en-têtes forgés. La politique de quota n’est pas modifiée.

Commandes CI : `python3 scripts/ci/verify_docker.py`, puis seed explicite et `python3 scripts/ci/verify_auth_https.py`. Les tests destructifs PostgreSQL utilisent exclusivement le volume éphémère du runner, avec `VULNLAB_EPHEMERAL_DB=ci-only`. Ne pas exécuter ces suites sur securevault, M6.1, M9 ou un volume conservé. Aucune validation Docker Desktop M11 n’est revendiquée ; les preuves HTTPS visent le loopback du runner CI.

## Classification et traçabilité des tests

- Python Windows/Linux : 20 tests fonctionnels, 62 tests `preserved_protection`, aucun test de divulgation sans base réelle.
- PostgreSQL/Redis : 100 tests fonctionnels, 143 `preserved_protection`, 3 `vulnerable_behavior` (deux sens de lecture, pagination/échappement des commentaires divulgués), collectés séparément. Les exécutions réelles sont consignées dans l’audit après CI.
- Les 82 tests Python du baseline sont conservés. Des marqueurs classent les protections ; aucune assertion n’est supprimée à cette fin.
- Des 236 cas PostgreSQL/Redis du baseline, seule la variante GET détail du test 404 inter-utilisateur est remplacée par les démonstrations ; les variantes édition/suppression/commentaire restent intactes. Le contrôle du ticket absent/hors borne est ajouté séparément.
- Le test de rechargement du rôle admin rétrogradé vérifie désormais 404 sur GET édition, liste vide et commentaire refusé ; sa précédente attente 404 sur GET détail est incompatible avec VULN-003. Le rechargement du rôle lui-même reste intact.
- Les deux attentes HTTPS de refus de lecture inter-utilisateur deviennent 200 avec assertions de données fictives ; les écritures restent refusées. Aucun skip, xfail, assertion permissive ou remédiation simulée.

Les catégories sont disjointes et explicitement exécutées par la CI. `security` demeure réservé aux futures remédiations ; `preserved_protection` ne prétend pas valider une sécurité exhaustive.

## Observation, limites et remédiation prévue

[CI réelle sur cd92bc1](https://github.com/Iyed523/VulnLab/actions/runs/37132827269) réussie : 20 tests Python fonctionnels et 62 protections par plateforme ; 100 tests PostgreSQL fonctionnels, 143 protections PostgreSQL/Redis et 3 démonstrations volontaires réussis. HTTPS validé sur le loopback du runner : Bob reçoit 200 pour le détail d’Alice et ses commentaires, malgré une liste vide ; édition/suppression/commentaire restent 404. Visiteur/SID invalide et désactivation/révocation sont réellement contrôlés. Voir [preuve JSON nettoyée](../proofs/VULN-003-https-ci.json) et [audit](../security-audit.md). La preuve identifie le SHA applicatif observé ; les modifications ultérieures de livraison concernent ces documents et la preuve, avec nouvelle CI finale attendue.

Prévu pour la future correction : appliquer côté serveur la propriété ou le rôle admin avant toute lecture, réutiliser le chemin autorisé du baseline, et rétablir le refus inter-utilisateur sur détail tout en gardant les tests fonctionnels et d’écriture. Aucune remédiation dans cette mission.

Limites conservées : proxy susceptible de sorties, pas de preuve de filtrage global ou d’isolation du navigateur ; pas d’audit exhaustif. Aucun tiers ciblé, exfiltration, secret dans la preuve, déploiement ou publication d’image. M11 s’arrête pour revue, sans fusion.
