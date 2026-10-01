# ADR 0003 — Premier socle Docker local

- Date : 2026-10-01.
- Statut : M3 soumise à revue ; validation d’exécution bloquée par le moteur Docker inaccessible.
- M1 et M2 : validées selon le cadrage reçu.

La pile est définie dans un fichier Compose explicitement nommé, avec un projet dédié. Seul Nginx publie `127.0.0.1:8080`. Les réseaux internes frontend et backend séparent les flux, sans réseau externe partagé. PostgreSQL possède son volume dédié ; Redis reste volatil.

Une fabrique Flask expose seulement `/healthz`, qui décrit la disponibilité HTTP du processus. Aucun accès PostgreSQL/Redis ni comportement métier n’est ajouté. Gunicorn 26.2.0 est limité à Linux par un marqueur de dépendance pour préserver l’environnement Windows.

Pour résoudre la limite M2, Hatchling et ses transitives sont inclus dans un groupe build verrouillé. Le backend et le groupe fixent la même version 1.32.4. La wheel est construite avec `--no-build-isolation` après synchronisation verrouillée ; les outils de construction ne sont pas copiés dans l’environnement final, installé sans mode éditable.

Les images officielles ou Astral sont fixées par version et digest réel. Python conserve 3.13.15 standard. Leur disponibilité Linux/amd64 a été vérifiée dans les manifestes ; les avis publics ont été consultés sans prétendre à un scan exhaustif.

L’application et Nginx utilisent des utilisateurs non root, tous les services demandent des privilèges limités et des écritures ciblées. PostgreSQL conserve uniquement les capacités d’initialisation nécessaires au volume et au changement d’utilisateur. Le rôle applicatif distinct ne possède aucun privilège administratif. Les identifiants sont exclusivement fictifs.

HTTP local est une étape provisoire. HTTPS, hôtes distincts et vérification complémentaire des sorties réseau restent en M4. Les choix déclaratifs doivent être confrontés aux conteneurs réels avant validation : le moteur Docker n’était pas disponible pendant M3.

Les versions, digests, commandes, droits, résultats et vérifications bloquées sont détaillés dans [docker.md](../docker.md). Aucun service ou image n’est publié, aucun commit ni nettoyage Docker global n’est effectué.
