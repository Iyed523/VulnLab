# ADR 0002 — Environnement Python et contrôles M2

- Date : 2026-09-30.
- Statut : proposé pour revue du Team Lead et validation du Product Owner ; M1 validée.

CPython 3.13.15 standard avec GIL respecte la série imposée par M2. La disponibilité de cette version de maintenance a été vérifiée sur python.org. La compatibilité du projet est limitée à `>=3.13,<3.14` ; `.python-version` fixe la version corrective utilisée.

uv 0.12.19 gère le Python dédié, l’environnement `.venv` et le verrou généré. Sa version exacte est imposée dans `pyproject.toml` et la CI. L’installation locale reste dans `.tools`, sans modification du PATH global ni du Python système. Chaque application aura son propre projet, environnement et verrou ; aucun workspace uv global n’est créé.

La structure `src/vulnlab_vulnerable` évite que le répertoire courant suffise à rendre le package importable. Hatchling 1.32.4 construit la distribution `vulnlab-vulnerable`. Le test d’amorçage relie l’import aux métadonnées de l’installation. Une installation non éditable de la wheel hors du checkout complète ce contrôle.

Seuls Flask 3.1.3, Pytest 9.1.1 et Ruff 0.16.9 sont ajoutés, avec leurs dépendances transitives dans `uv.lock`. Les extensions et services futurs restent hors périmètre. Ruff et Pytest sont configurés dans le même `pyproject.toml`.

La CI utilise le même verrou sur les runners hébergés Windows et Linux, avec des actions épinglées par SHA vérifié, des permissions en lecture et sans déploiement. `uv sync --locked` et `uv run --locked` refusent un verrou périmé. `uv build` ne propose pas `--locked` dans cette version : il est exécuté derrière `uv run --locked`. Hatchling est fixé, mais ses dépendances de construction isolées ne sont pas couvertes par le verrou applicatif ; aucune reproductibilité binaire intégrale n’est revendiquée.

Les sources de versions, les résultats réels et les limites de sécurité figurent dans le [guide de développement](../development.md). Ces contrôles valident l’installation et l’outillage, pas les fonctionnalités métier ou la sécurité de l’application.
