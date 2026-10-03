# VULN-002 — XSS stocké dans les commentaires, prévu mais non introduit

**État M12.1 : navigateur vérifié sur loopback, sans connexion au laboratoire.**
Le blocage sandbox historique M12 est résolu ; aucun XSS
n'est présent dans cette livraison. Le contenu des commentaires reste échappé
comme à M11 et au tag `baseline-functional-v1`. Aucun effet DOM, persistance
d'exécution, sévérité constatée ou capture navigateur ne peut être revendiqué.
Voir le [rapport M12.1 et ses limites](../m12-1-browser-sandbox.md) et le
[diagnostic historique M12](../m12-browser-preparation.md). TLS navigateur et
introduction du XSS restent ultérieurs après revue.

## Périmètre pédagogique prévu, conditionnel

Après vérification réelle des prérequis seulement : rendre sans échappement
uniquement `comment.content` dans le détail de ticket. Garder autoescape Jinja,
titre, description, noms affichés et autres champs échappés ; stockage SQL
paramétré, droits d'écriture, auteur serveur, CSRF, limites, sessions, quotas,
administration et périmètre VULN-003 conservés. Aucun changement de schéma,
migration ou implémentation secure-app.

Scénario prévu indépendant de l'IDOR : un admin fictif autorisé ajoute un
commentaire au ticket d'Alice ; Alice consulte son propre ticket. Seul effet
autorisé : marqueur visuel DOM déterministe, sans requête réseau ni lecture
de cookies, stockage, formulaires ou jetons. Vérifier exécution réelle,
persistance après rechargement, absence avant consultation et échappement des
autres champs. Ces vérifications sont **non exécutées**, pas des succès attendus.

## Correspondances vérifiées et remédiation prévue

[CWE-79](https://cwe.mitre.org/data/definitions/79.html) décrit une entrée contrôlée
par l'utilisateur mal neutralisée dans une page web ; son variant stocké arrive
après stockage puis restitution. [OWASP A05:2025 — Injection](https://top10.owasp.org/2025/A05_2025-Injection/)
inclut CWE-79. Correspondances officielles vérifiées le 3 octobre 2026 pour le
mécanisme envisagé, pas constat d'une nouvelle faille du dépôt.

Impact futur possible : intégrité du contenu visible dans le contexte du site.
La démonstration limitée n'établirait pas une collecte ou compromission de compte.
Sévérité à justifier après observation réelle ; aucun score CVSS ni impact
observé inventé. Remédiation future : rétablir l'échappement contextuel à la sortie,
conformément à la [fiche OWASP de prévention XSS](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html),
avec tests de remédiation distincts. La sortie actuelle conserve cet échappement.

## Tests et preuve disponibles

Les 36 nouveaux tests de préparation sont `preserved_protection`, sans charge XSS.
Les démonstrations `vulnerable_behavior` restent exclusivement celles de VULN-003.
Aucune attente baseline/M11 adaptée, aucun skip/xfail, aucun contrôle assoupli.
La [preuve de prérequis bloqué](../proofs/M12-browser-preflight.json) n'est pas une
preuve XSS. Aucun navigateur personnel, tiers, collecte ou exfiltration utilisé.
M12.1 conserve les 36 tests unitaires et en ajoute 13 ; sandbox et témoins réseau
réels sont vérifiés séparément par la porte CI, sans charge pédagogique.
