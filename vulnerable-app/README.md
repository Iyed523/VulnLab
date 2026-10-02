# VulnLab — version vulnérable

> **AVERTISSEMENT : laboratoire volontairement vulnérable, exclusivement local, non destiné à la production. Ne jamais publier ni déployer ce service.**

État M6 : modèles PostgreSQL M5 conservés, inscription, connexion, compte actif en lecture seule et déconnexion POST. Sessions Redis, CSRF et quotas protègent ce socle de référence sans faiblesse volontaire. `GET /healthz` retourne `{"status":"ok"}` et concerne seulement le processus HTTP. Voir le [guide M6](../docs/auth-sessions.md) pour les contrats, la clé locale et les limites, ainsi que le [guide M5](../docs/data-foundation.md).

Le [guide Docker](../docs/docker.md) décrit la pile Nginx/Gunicorn/PostgreSQL/Redis, ses commandes et les vérifications bloquées par le moteur Docker inaccessible. Le socle M3 a été vérifié sur Linux CI. M4 prépare HTTPS sur vulnerable.vulnlab.test:8443, avec confiance TLS explicite ; Docker Desktop local reste non vérifié et les limites de sorties du proxy sont documentées.

Le [guide de développement](../docs/development.md) fournit les commandes Python. Les 25 tests du socle M4.1 sont conservés, complétés par les tests unitaires de données et les tests PostgreSQL réels en CI. Ces contrôles ne sont pas un audit de sécurité. M4/M4.1 sont validées ; M5 est validée ; M6 reste soumise à revue.

Cette version accueillera une application fictive de tickets privés, puis des faiblesses introduites une par une, identifiées, justifiées et testées. Les démonstrations utiliseront uniquement des comptes et données fictifs, sans cibler de tiers. Les preuves XSS resteront locales, sans collecte ni transmission de données.

Consulter l’[architecture](../docs/architecture.md), les [autorisations de référence](../docs/authorization-matrix.md), les [exigences d’isolation](../docs/lab-safety.md) et la [roadmap](../docs/roadmap.md). Les écarts volontaires aux règles de référence devront être explicitement documentés dans les missions futures.
