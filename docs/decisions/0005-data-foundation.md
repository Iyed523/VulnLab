# ADR 0005 — Modèles et migrations PostgreSQL

- Date : 2026-10-01.
- Statut : M5 soumise à revue du Team Lead et validation du Product Owner.
- Base : `aabc745`, M4/M4.1 validées ; PR #1/#2 non fusionnées.

SQLAlchemy direct est retenu, sans Flask-SQLAlchemy ni Flask-Migrate : la petite fabrique et les transactions explicites suffisent. Migrations Alembic indépendantes des modèles courants pour garder la première révision reproductible. PostgreSQL réel est indispensable pour contraintes regex, FK, identité, TIMESTAMPTZ, droits et migrations ; SQLite ne valide pas ces propriétés.

Versions directes épinglées et transitives verrouillées avec hashes dans uv.lock : SQLAlchemy 2.1.1 (série stable courante), psycopg[binary] 3.3.6, Alembic 1.20.0, argon2-cffi 25.1.0. Installation effective sur CPython 3.13.15 Windows ; compatibilité Linux vérifiée par construction/CI. L'extra binary psycopg fournit libpq sans installer un compilateur ou une bibliothèque système dans le runtime ; les bibliothèques embarquées nécessitent de suivre les mises à jour de ses wheels.

Sources consultées le 1 octobre 2026 : [SQLAlchemy versions](https://www.sqlalchemy.org/download.html), [psycopg notes](https://www.psycopg.org/psycopg3/docs/news.html), [installation psycopg binary](https://www.psycopg.org/psycopg3/docs/basic/install.html), [Alembic changelog](https://alembic.sqlalchemy.org/en/latest/changelog.html), [argon2-cffi changelog](https://github.com/hynek/argon2-cffi/blob/main/CHANGELOG.md), [profil/API Argon2](https://argon2-cffi.readthedocs.io/en/stable/api.html).

Avis pertinents examinés : [CVE-2019-7548](https://github.com/advisories/GHSA-38fc-9xqv-7f7q) concerne l'ancienne série SQLAlchemy, pas la version retenue. Les pages sécurité officielles de [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy/security), [Alembic](https://github.com/sqlalchemy/alembic/security), [psycopg](https://github.com/psycopg/psycopg/security) et [argon2-cffi](https://github.com/hynek/argon2-cffi/security) ont été consultées. Cette vérification ponctuelle n'est ni un scan exhaustif des transitives/libpq ni une preuve d'absence de vulnérabilité.

Les rôles SQL séparent migration et runtime ; les identifiants de maintenance ne sont pas fournis à app. Une commande ponctuelle sur backend exécute les migrations/fixtures, jamais les workers. Les privileges par défaut du migrateur couvrent les futurs objets métier ; les objets de maintenance doivent retirer les grants hérités. initdb et son invocation explicite pour un volume ancien sont transactionnels ; aucun volume ou credential existant n'est remplacé automatiquement.

Les fixtures utilisent des identifiants négatifs réservés, des mots de passe publics fictifs Argon2id et un verrou transactionnel. Elles refusent les collisions au lieu d'écraser les données. Normalisation des comptes ASCII via NFKC/strip/casefold, longueurs bornées, suppressions CASCADE/RESTRICT et convention UTC sont détaillées dans le [guide de données](../data-foundation.md). Les relations SQL ne constituent pas des autorisations ; aucun champ de profil futur ni route métier n'est défini.

HTTPS et l'isolation M4.1 sont conservés ; Docker Desktop local non vérifié et accès sortant possible du proxy restent des limites. M5 ne déploie rien, ne fusionne aucune PR et n'introduit aucune faiblesse volontaire.
