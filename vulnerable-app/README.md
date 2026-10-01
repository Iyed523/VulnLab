# VulnLab — version vulnérable

> **AVERTISSEMENT : laboratoire volontairement vulnérable, exclusivement local, non destiné à la production. Ne jamais publier ni déployer ce service.**

État M4 : package installable et fabrique Flask technique avec `GET /healthz` retournant `{"status":"ok"}`. Cette santé concerne seulement le processus HTTP. Aucun métier, session ou scénario vulnérable n’est implémenté.

Le [guide Docker](../docs/docker.md) décrit la pile Nginx/Gunicorn/PostgreSQL/Redis, ses commandes et les vérifications bloquées par le moteur Docker inaccessible. Le socle M3 a été vérifié sur Linux CI. M4 prépare HTTPS sur vulnerable.vulnlab.test:8443, avec confiance TLS explicite ; Docker Desktop local reste non vérifié et les limites de sorties du proxy sont documentées.

Le [guide de développement](../docs/development.md) fournit les commandes Python. Quatre tests passent sous Windows : un de packaging et trois de contrat HTTP technique, sans valeur d’audit de sécurité. M1 à M3-Git sont validées ; M4 reste soumise à revue et M5 n’est pas commencée.

Cette version accueillera une application fictive de tickets privés, puis des faiblesses introduites une par une, identifiées, justifiées et testées. Les démonstrations utiliseront uniquement des comptes et données fictifs, sans cibler de tiers. Les preuves XSS resteront locales, sans collecte ni transmission de données.

Consulter l’[architecture](../docs/architecture.md), les [autorisations de référence](../docs/authorization-matrix.md), les [exigences d’isolation](../docs/lab-safety.md) et la [roadmap](../docs/roadmap.md). Les écarts volontaires aux règles de référence devront être explicitement documentés dans les missions futures.
