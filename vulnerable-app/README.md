# VulnLab — version vulnérable

> **AVERTISSEMENT : laboratoire volontairement vulnérable, exclusivement local, non destiné à la production. Ne jamais publier ni déployer ce service.**

État M7 : tickets privés et commentaires, avec politique propriétaire/administrateur appliquée côté serveur, pagination et transactions. Modèles M5, authentification, sessions Redis et CSRF conservés ; aucune faiblesse volontaire. `GET /healthz` retourne `{"status":"ok"}` et concerne seulement le processus HTTP. Voir les [contrats M7](../docs/tickets-comments.md), le [guide M6](../docs/auth-sessions.md) et le [guide M5](../docs/data-foundation.md).

Le [guide Docker](../docs/docker.md) décrit la pile Nginx/Gunicorn/PostgreSQL/Redis et ses commandes. Le [rapport M6.1](../docs/local-validation-m61.md) distingue les preuves Windows Docker Desktop de la CI Linux ; les sorties possibles du proxy restent une limite. M7 utilise seulement les ressources jetables CI et préserve les piles locales arrêtées.

Le [guide de développement](../docs/development.md) fournit les commandes Python. Les tests M4–M6.1 sont conservés, complétés par les tests M7 unitaires, fonctionnels PostgreSQL/Redis et HTTPS. Ces contrôles ne sont pas un audit de sécurité. M6/M6.1 sont validées ; M7 reste soumise à revue.

Le comportement de référence tickets/commentaires est implémenté. Les futures faiblesses seront introduites une par une, identifiées, justifiées et testées dans une mission autorisée. Les démonstrations utiliseront uniquement des comptes et données fictifs, sans cibler de tiers. Les preuves XSS resteront locales, sans collecte ni transmission de données.

Consulter l’[architecture](../docs/architecture.md), les [autorisations de référence](../docs/authorization-matrix.md), les [exigences d’isolation](../docs/lab-safety.md) et la [roadmap](../docs/roadmap.md). Les écarts volontaires aux règles de référence devront être explicitement documentés dans les missions futures.
