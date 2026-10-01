# VulnLab — Web Application Security Laboratory

VulnLab est un portfolio pédagogique de sécurité applicative fondé sur une application fictive de gestion de tickets privés. Il permettra de comparer une faiblesse volontaire, sa démonstration locale et sa correction vérifiée.

**M1 et M2 validées ; M3 soumise à revue.** La fabrique Flask technique expose uniquement `GET /healthz`. Les tests Python passent et la pile Docker est préparée ; son exécution reste non vérifiée car le moteur Docker est inaccessible. Aucune fonctionnalité métier ni vulnérabilité volontaire n’est implémentée. L’isolation effective reste à vérifier.

## Deux versions prévues

- [vulnerable-app](vulnerable-app/README.md) : laboratoire volontairement vulnérable, exclusivement local, jamais destiné à la production.
- [secure-app](secure-app/README.md) : version corrigée, accompagnée à terme de tests de remédiation.

Les deux applications seront indépendantes, avec les mêmes contrats métier et schémas de données. Seuls des comptes et des données fictifs seront utilisés. Aucun service tiers ne sera une cible.

## Stack validée, à mettre en place

Flask, Jinja, HTML et CSS locaux dans un monolithe modulaire, sans frontend séparé ; PostgreSQL, SQLAlchemy, psycopg et Alembic ; Flask-Login, Flask-Session, Flask-WTF et Argon2id ; Redis propre à chaque version pour les sessions et les compteurs Flask-Limiter ; Gunicorn derrière Nginx ; Docker Compose avec environnements indépendants.

Les vérifications prévues reposent sur Pytest, des tests HTTP, Playwright et Ruff. GitHub Actions servira aux vérifications, sans déploiement. OWASP Top 10:2025 est l’édition de référence retenue. M2 utilise Python 3.13.15 avec GIL, uv 0.12.19, Flask 3.1.3, Pytest 9.1.1, Ruff 0.16.9 et Hatchling 1.32.4. M3 ajoute Gunicorn 26.2.0 pour Linux et verrouille les dépendances de construction. Les autres composants applicatifs seront introduits lorsqu’ils seront nécessaires. Le workflow est préparé pour Windows et Linux, sans exécution GitHub à ce stade.

## Structure actuelle

```text
VulnLab/
├── README.md
├── AGENTS.md
├── .gitignore
├── compose.vulnerable.yaml
├── .env.example
├── .dockerignore
├── docker/vulnerable/ (Dockerfile, nginx.conf et initdb/01-role.sh)
├── .github/workflows/ci.yml
├── vulnerable-app/
│   ├── README.md
│   ├── .python-version
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/vulnlab_vulnerable/__init__.py
│   └── tests/ (test_packaging.py et test_health.py)
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
        └── 0003-local-docker.md
```

## Documents de référence

- [Fonctionnement GitHub et revue par PR](docs/git-workflow.md)
- [Pile Docker, commandes et limites M3](docs/docker.md)
- [Installation, commandes et résultats M2](docs/development.md)
- [Décision sur l’outillage Python](docs/decisions/0002-python-tooling.md)
- [Architecture et modèle métier](docs/architecture.md)
- [Matrice des autorisations](docs/authorization-matrix.md)
- [Modèle de menace préliminaire](docs/threat-model.md)
- [Sécurité et isolation du laboratoire](docs/lab-safety.md)
- [Décision d’architecture](docs/decisions/0001-architecture.md)
- [Roadmap et choix des scénarios](docs/roadmap.md)
- [Règles des prochaines missions](AGENTS.md)

La progression se fait par missions, avec revue du Team Lead et validation du Product Owner avant la suivante. M1 et M2 sont validées selon le cadrage reçu. M3 est livrée pour revue, avec les contrôles Docker d’exécution bloqués ; M4 n’est pas commencée. Les outils locaux, environnements et wheels sont exclus de Git.

Le socle minimal est publié sur [GitHub](https://github.com/Iyed523/VulnLab). La branche `chore/bootstrap-lab` prépare la revue du travail complet et les contrôles Python Windows/Linux et Docker Linux. Les résultats CI seront consignés après exécution réelle.
