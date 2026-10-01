# ADR 0004 — HTTPS local et preuves d’isolation

- Date : 2026-10-01.
- Statut : M4 soumise à revue du Team Lead et validation du Product Owner.
- Dépendance : socle M3 validé `15284a8` sur chore/bootstrap-lab, PR #1 non fusionnée.

Décisions : HTTPS sur `127.0.0.1:8443`, hôte unique vulnerable.vulnlab.test, nom secure.vulnlab.test réservé, certificat autosigné dédié avec SAN et confiance explicitement fournie aux tests. Aucune autorité système ou modification hosts n’est installée. Le script refuse de remplacer des fichiers existants, les clés restent ignorées et hors contexte de build.

Nginx rejette les SNI et Host inconnus, supprime le port HTTP publié et conserve une sonde de processus seulement sur le loopback de son conteneur. La vérification HTTPS du runner est distincte de cette sonde. Les montages restent en lecture seule ; le groupe supplémentaire du proxy donne accès à la clé 0640 sans capacités ou privilèges root.

Ingress est conservé pour la publication loopback ; frontend et backend restent internes. Un témoin local vérifie un contrôle positif depuis le proxy avant les refus attendus des services internes. Les sorties possibles du proxy constituent une limite explicite. Une interdiction globale demanderait une politique de filtrage de l’environnement à décider, pas une affirmation fondée sur internal seul.

Les tests Python métier ne sont pas étendus. Les contrôles d’infrastructure existants sont conservés et complétés pour TLS, permissions, capabilities et écritures. Docker Desktop demeure inaccessible ; les preuves Linux CI ne se substituent pas à une validation Windows Docker.

Voir [docker.md](../docker.md) pour procédures, sources, proposition de restriction et résultats réels. Aucun métier, session, service public, changement d’image ou fusion n’est introduit.

Résultats : [CI b3190fd](https://github.com/Iyed523/VulnLab/actions/runs/36919627007) verte sur les trois jobs, avec tests TLS et témoins exécutés. Le proxy accède au témoin ingress, les services internes sont refusés ; le filtrage global du proxy demeure une limite. Localement, Python et certificat sont vérifiés, le moteur Docker reste inaccessible. [PR #2](https://github.com/Iyed523/VulnLab/pull/2) en brouillon et dépendante du socle. La validation Product Owner n’est pas anticipée.

Correction M4.1 autoris�e : le refus du t�moin exige d�sormais un protocole explicite issu des seules exceptions socket attendues. Une sonde �ph�m�re partage l�espace r�seau de chaque service, avec l�image Python existante �pingl�e, sans modifier les images, r�seaux ni privil�ges. Le timeout de connexion est distingu� du d�lai global Docker ; les erreurs d�outil/ex�cution ne sont jamais accept�es comme refus. Cette preuve limit�e au t�moin local ne vaut pas interdiction globale des sorties. Les tests de classement sont distincts du m�tier et scripts/tests sont inclus dans Ruff CI.
