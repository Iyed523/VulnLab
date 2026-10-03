# Modèle de menace préliminaire

Ce document décrit les risques à examiner, sans constat d’audit ni vulnérabilité démontrée. L’application et ses protections ne sont pas encore implémentées. OWASP Top 10:2025 est l’édition de référence ; les correspondances détaillées et fiches d’audit seront produites ultérieurement.

## Actifs

- Confidentialité des tickets privés, commentaires et profils fictifs.
- Intégrité des propriétaires, auteurs, rôles, statuts et relations métier.
- Hachages de mots de passe fictifs, identifiants de session, secrets de configuration et clés HTTPS locales.
- Disponibilité des piles locales, intégrité des données de test et fiabilité des preuves et tests.
- Poste hôte et navigateur de la personne réalisant le laboratoire.

## Acteurs et hypothèses

Les acteurs sont le visiteur non connecté, l’utilisateur `user`, l’administrateur fictif `admin` et l’opérateur local du laboratoire. Un visiteur ou un utilisateur peut agir de manière hostile dans les scénarios autorisés, par exemple en modifiant des identifiants ou des champs envoyés. L’opérateur contrôle les environnements et leur remise à zéro ; un rôle métier `admin` ne doit pas fournir des privilèges système ou SQL.

Seuls des comptes et données fictifs sont autorisés. Le poste de l’opérateur est supposé maîtrisé pour l’exercice ; cela ne constitue pas une garantie contre une compromission de l’hôte. Aucun service tiers n’est une cible. Les mécanismes d’isolation restent des exigences à vérifier sous Docker Desktop.

## Frontières de confiance et risques à tester

| Frontière | Risques envisagés et contrôles futurs |
| --- | --- |
| Navigateur → Nginx local | Entrées hostiles, confusion d’hôte, transport ; HTTPS local et hôtes distincts |
| Nginx → Flask/Gunicorn | Confiance excessive dans les en-têtes de proxy ; configuration et validation explicites |
| Requête/session → règles métier | Usurpation, accès au ticket d’autrui, élévation de rôle ; contrôles serveur selon la matrice |
| Flask → PostgreSQL | Altération des requêtes et données ; accès structurés, contraintes et compte SQL non administrateur |
| Flask → Redis | Vol ou mélange de sessions, contournement des compteurs ; stockage et secrets séparés |
| Conteneurs → hôte/réseau extérieur | Exposition involontaire ou sorties réseau ; privilèges minimaux et isolation vérifiée |
| Pile vulnérable → pile corrigée | Contamination par données, volumes, secrets ou sessions partagés ; séparation indépendante |
| Contenu stocké → navigateur | Exécution XSS et interaction avec d’autres contextes du navigateur ; preuves strictement locales |
| Dépôt/preuves → lecteurs et CI | Fuite de secrets, preuves trompeuses ; exclusions ciblées, nettoyage et résultats vérifiables |

La matrice d’[autorisations](authorization-matrix.md) fixe les comportements attendus. Les risques ci-dessus ne préjugent ni des scénarios finalement détaillés ni de résultats d’audit. L’[isolation du serveur ne garantit pas celle du navigateur](lab-safety.md).
