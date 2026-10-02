# VulnLab — Web Application Security Laboratory

VulnLab est un portfolio pédagogique de sécurité applicative fondé sur une application fictive de gestion de tickets privés. Il permettra de comparer une faiblesse volontaire, sa démonstration locale et sa correction vérifiée.

**M1 à M5 validées ; M6 soumise à revue après vérification.** Le socle ajoute inscription, connexion, compte en lecture seule et déconnexion, avec sessions Redis, CSRF et quotas. Aucune faiblesse volontaire n'est introduite. `/healthz` reste indépendant des services. Voir le [guide M6](docs/auth-sessions.md) et le [guide des données M5](docs/data-foundation.md). Docker Desktop local reste non vérifié et les sorties possibles du proxy restent une limite.

## Deux versions prévues

- [vulnerable-app](vulnerable-app/README.md) : laboratoire volontairement vulnérable, exclusivement local, jamais destiné à la production.
- [secure-app](secure-app/README.md) : version corrigée, accompagnée à terme de tests de remédiation.

Les deux applications seront indépendantes, avec les mêmes contrats métier et schémas de données. Seuls des comptes et des données fictifs seront utilisés. Aucun service tiers ne sera une cible.

## Stack validée, à mettre en place

Flask, Jinja, HTML et CSS locaux dans un monolithe modulaire, sans frontend séparé ; PostgreSQL, SQLAlchemy, psycopg et Alembic ; Flask-Login, Flask-Session, Flask-WTF et Argon2id ; Redis propre à chaque version pour les sessions et les compteurs Flask-Limiter ; Gunicorn derrière Nginx ; Docker Compose avec environnements indépendants.

Les vérifications prévues reposent sur Pytest, des tests HTTP, Playwright et Ruff. GitHub Actions servira aux vérifications, sans déploiement. OWASP Top 10:2025 est l’édition de référence retenue. M2 utilise Python 3.13.15 avec GIL, uv 0.12.19, Flask 3.1.3, Pytest 9.1.1, Ruff 0.16.9 et Hatchling 1.32.4. M3 ajoute Gunicorn 26.2.0 pour Linux et verrouille les dépendances de construction. Les autres composants applicatifs seront introduits lorsqu’ils seront nécessaires. Les trois jobs GitHub Actions ont réussi : Python Windows, Python Linux et Docker Linux.

## Structure actuelle

```text
VulnLab/
├── README.md
├── AGENTS.md
├── .gitignore
├── compose.vulnerable.yaml
├── compose.ci.yaml (tests PostgreSQL sur base jetable CI seulement)
├── .env.example
├── .dockerignore
├── docker/vulnerable/ (Dockerfile, nginx.conf et initdb/01-role.sh)
├── scripts/ (génération des certificats et contrôles CI)
├── .github/workflows/ci.yml
├── vulnerable-app/
│   ├── README.md
│   ├── .python-version
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/vulnlab_vulnerable/ (fabrique, database, models, passwords, seed, CLI)
│   ├── alembic.ini et migrations/
│   ├── integration/ (tests PostgreSQL réels)
│   └── tests/ (packaging, health et unités de données)
├── secure-app/README.md
└── docs/
    ├── architecture.md
    ├── threat-model.md
    ├── authorization-matrix.md
    ├── lab-safety.md
    ├── roadmap.md
    ├── docker.md
    ├── development.md
    └── decisions/
        ├── 0001-architecture.md
        ├── 0002-python-tooling.md
        ├── 0003-local-docker.md
        ├── 0004-local-https.md
        └── 0005-data-foundation.md
```

## Documents de référence

- [Modèles, migrations et fixtures M5](docs/data-foundation.md)
- [Décision sur le socle persistant](docs/decisions/0005-data-foundation.md)

- [Fonctionnement GitHub et revue par PR](docs/git-workflow.md)
- [HTTPS local, Docker et limites M4](docs/docker.md)
- [Installation, commandes et résultats M2](docs/development.md)
- [Décision sur l’outillage Python](docs/decisions/0002-python-tooling.md)
- [Architecture et modèle métier](docs/architecture.md)
- [Matrice des autorisations](docs/authorization-matrix.md)
- [Modèle de menace préliminaire](docs/threat-model.md)
- [Sécurité et isolation du laboratoire](docs/lab-safety.md)
- [Décision d’architecture](docs/decisions/0001-architecture.md)
- [Roadmap et choix des scénarios](docs/roadmap.md)
- [Règles des prochaines missions](AGENTS.md)

La progression se fait par missions avec revue du Team Lead et validation du Product Owner. M4 et M4.1 sont validées sur `aabc745`. `codex/m5-data-foundation` part de ce socle et dépend de `codex/m4-local-https`, elle-même dépendante de `chore/bootstrap-lab`. Aucune PR n'est fusionnée. M6 attend la revue finale ; aucune mission suivante n'est commencée.

L’accès utilisateur préparé est `https://vulnerable.vulnlab.test:8443`, publié seulement sur `127.0.0.1`, avec certificat dédié et confiance explicite. `secure.vulnlab.test` est réservé. Le [guide Docker](docs/docker.md) décrit la génération Windows/Linux, les commandes sans modification hosts, les contrôles et les limites des sorties du proxy. Docker Desktop local demeure inaccessible. Les clés, outils, caches et environnements ne sont pas versionnés.

La [PR M4 #2](https://github.com/Iyed523/VulnLab/pull/2) est ouverte en brouillon vers le socle. La [CI M4 vérifiée](https://github.com/Iyed523/VulnLab/actions/runs/36919627007) passe sur les trois jobs ; les limites Docker Desktop et de sorties du proxy restent explicites.
