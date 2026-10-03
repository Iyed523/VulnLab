# Audit pédagogique initial — M11

Périmètre : application fictive sur les ressources exclusivement locales du runner CI. Aucun audit exhaustif, test tiers ou garantie générale de sécurité. Baseline fonctionnel préservé par le tag annoté `baseline-functional-v1` sur bd029b5.

## VULN-003

Le code préparé pour GET détail omet intentionnellement la propriété du ticket. Le rendu peut donc divulguer titre, description, statut, commentaires, noms affichés des auteurs, dates, total et identifiant dans les liens. Voir [fiche précise et remédiation prévue](vulnerabilities/VULN-003.md).

Avant publication : 20 tests Python fonctionnels et 62 de protections conservées passent localement ; 100 cas PostgreSQL fonctionnels, 143 protections et 3 démonstrations sont collectés, mais ne sont pas présentés comme exécutés localement. La preuve HTTPS/PostgreSQL sera consignée après CI réelle. Aucune capture écran réalisée ou inventée.

Un résultat vert `vulnerable_behavior` signifie que la divulgation attendue est observée. Il ne signifie pas que le contrôle d’accès est sûr. Les tests de remédiation sont futurs ; aucun code corrigé n’est copié dans secure-app.
