# VulnLab — Web Application Security Laboratory

VulnLab est un portfolio pédagogique de sécurité applicative fondé sur une application fictive de gestion de tickets privés. Il permettra de comparer une faiblesse volontaire, sa démonstration locale et sa correction vérifiée.

**M12 — préparation navigateur uniquement, sans XSS introduit.** La sandbox Chromium reste bloquée dans l'environnement dédié sans capacités ; les restrictions réseau et TLS navigateur ne sont donc pas vérifiées. Voir [diagnostic et décision ouverte](docs/m12-browser-preparation.md) et [VULN-002 prévue](docs/vulnerabilities/VULN-002.md).

M11 est validée par le Product Owner, sa PR reste en brouillon sans fusion. VULN-003 permet à un utilisateur actif connecté de consulter le détail d’un ticket d’autrui, commentaires inclus, en modifiant l’identifiant. Cette branche reste volontairement vulnérable : une démonstration verte constate une divulgation, sans validation de sécurité. Liste, comptage et écritures gardent leurs autorisations ; les commentaires restent échappés. Voir [fiche VULN-003](docs/vulnerabilities/VULN-003.md), [matrice](docs/vulnerability-matrix.md) et [audit](docs/security-audit.md).

Le socle M10 correct reste au tag annoté `baseline-functional-v1`, sur `bd029b523d1835e737faae51b6c9d5c47d5a6efb`. Aucun tag déplacé, remédiation secure-app, fusion M11 ou déploiement. HTTPS reste exclusivement sur le loopback ; les sorties du proxy et l’isolation du navigateur demeurent des limites.

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

La progression se fait par missions avec revue du Team Lead et validation du Product Owner. M10 a intégré le socle dans main sur `bd029b5`, conservé au tag annoté `baseline-functional-v1`. M11 introduit uniquement VULN-003 sur sa branche de revue, sans fusion ; les autres faiblesses et la remédiation restent hors périmètre. La validation Windows M9 antérieure a réussi avec Docker Desktop 4.93.0 et moteur Linux 29.8.1 ; ses ressources, M6.1 et securevault restent conservées. M11 utilise les ressources locales éphémères des runners pour ses preuves HTTPS, sans validation Docker Desktop M11.

L’accès utilisateur préparé est `https://vulnerable.vulnlab.test:8443`, publié seulement sur `127.0.0.1`, avec certificat dédié et confiance explicite. `secure.vulnlab.test` est réservé. Le [guide Docker](docs/docker.md) décrit la génération Windows/Linux, les commandes sans modification hosts, les contrôles et les limites des sorties du proxy. Docker Desktop local a fait l’objet de la validation M6.1, distincte de la CI M7. Les clés, outils, caches et environnements ne sont pas versionnés.

La [PR M4 #2](https://github.com/Iyed523/VulnLab/pull/2) est ouverte en brouillon vers le socle. La [CI M4 vérifiée](https://github.com/Iyed523/VulnLab/actions/runs/36919627007) passe sur les trois jobs ; les limites Docker Desktop et de sorties du proxy restent explicites.
