# ADR 0001 — Architecture du laboratoire VulnLab

- Date de consignation : 2026-09-28.
- Statut : décisions d’architecture validées par le Product Owner selon le cadrage de M1 ; implémentation à venir.
- Portée : application fictive de gestion de tickets, laboratoire exclusivement local.

## Contexte

Le portfolio doit rendre compréhensible et reproductible la comparaison entre une faiblesse volontaire et sa remédiation. Le socle doit rester suffisamment simple pour concentrer le travail sur la sécurité applicative et permettre des preuves locales traçables.

## Décisions et raisons

| Décision validée | Raison |
| --- | --- |
| Flask, monolithe modulaire | Organiser les responsabilités sans multiplier les services applicatifs et les frontières inutiles au projet |
| Jinja, HTML et CSS locaux, rendu serveur sans frontend séparé | Garder un parcours requête–contrôle–rendu lisible et limiter la complexité de l’interface |
| Deux répertoires `vulnerable-app` et `secure-app` dans un dépôt | Comparer les versions et conserver leur traçabilité ensemble |
| Duplication pédagogique maîtrisée des implémentations sensibles | Permettre des correctifs indépendants sans corriger implicitement la version vulnérable via du code partagé |
| Contrats métier et schémas identiques, fixtures et outils de tests partageables | Comparer les comportements sur un socle cohérent et reproductible |
| Deux piles indépendantes Nginx → Gunicorn/Flask → PostgreSQL/Redis avec Docker Compose | Séparer exécution, données, sessions et secrets et permettre une remise à zéro ciblée |
| PostgreSQL, SQLAlchemy, psycopg, Alembic | Distinguer stockage relationnel, accès aux données et évolution traçable du schéma |
| Flask-Login, Flask-Session, Flask-WTF, Argon2id | Fournir les briques prévues pour identité, sessions, formulaires et hachage |
| Redis séparé par version pour sessions et compteurs Flask-Limiter | Éviter le mélange des états de session et de limitation entre les versions |
| Gunicorn derrière Nginx, HTTPS local et hôtes distincts | Définir une frontière HTTP explicite et le transport local prévu |
| Pytest, tests HTTP, Playwright et Ruff | Couvrir logique, échanges HTTP, parcours navigateur et qualité du code |
| GitHub Actions pour les vérifications, sans déploiement | Automatiser les contrôles sans exposer le laboratoire |
| Branche principale cible `main`, branches temporaires de travail | Garder une référence lisible et des changements revus par mission |
| OWASP Top 10:2025 comme référence | Employer une édition commune pour la documentation future des scénarios |

## Conséquences

La duplication exige de surveiller la cohérence des contrats et schémas tout en conservant les écarts de sécurité explicitement documentés. Le code sensible ne doit pas être mutualisé. Une référence Git puis une copie traçable vers la version corrigée sont prévues avant les remédiations.

L’indépendance des piles impose des réseaux, volumes, secrets et sessions distincts. Elle reste à vérifier, notamment pour les sorties réseau sous Docker Desktop, et ne garantit pas l’isolation du navigateur. Les exigences sont détaillées dans [lab-safety](../lab-safety.md).

Les versions exactes des outils ne sont pas sélectionnées. Cet ADR n’affirme aucune installation, protection effective ou réussite de test. M1 reste documentaire, sans commit ni développement applicatif.

Voir l’[architecture](../architecture.md), la [matrice d’autorisations](../authorization-matrix.md) et la [roadmap](../roadmap.md) pour les contrats, scénarios retenus et étapes de validation.
