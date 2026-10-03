# Sécurité et isolation du laboratoire

M11 introduit exclusivement [VULN-003](vulnerabilities/VULN-003.md), divulgation du détail et de ses commentaires. Code publié pour revue, service jamais publié. Tests réels uniquement sur ressources CI éphémères ; pas de validation Docker Desktop M11 revendiquée. Les états historiques ci-dessous ne remplacent pas la preuve M11.

**État M4 : M3/M3-Git validées sur la base des trois jobs Linux/Windows du socle ; configuration HTTPS sur 127.0.0.1:8443 vérifiée dans la CI Linux M4.** Le moteur Docker Desktop reste inaccessible. Les preuves Linux CI M4 et leurs limites sont consignées dans [docker.md](docker.md), sans affirmation de validation Windows Docker. Le laboratoire reste exclusivement local, avec certificats privés exclus du dépôt et de la construction.

La restriction des sorties n’est pas une garantie globale : app/db/redis restent sur les réseaux internes, tandis que le proxy est sur ingress pour la publication loopback. Un témoin local, disponible lors d’un contrôle positif, sert à vérifier les refus des services internes et l’accès encore possible du proxy. Aucune destination tierce n’est sondée. Une politique de sortie exhaustive du proxy demanderait une décision de filtrage de l’environnement ; aucune modification système globale n’est effectuée.

## Exigences pour les missions futures

M6 ajoute le cookie `__Host-vulnlab-session`, les sessions Redis et une clé locale ignorée montée en lecture seule. Les preuves d'expiration, rotation, CSRF et quotas concernent les parcours testés ; elles ne prouvent ni une isolation du navigateur ni une interdiction globale des sorties. Voir [le guide M6](auth-sessions.md). Les clés, cookies, jetons et mots de passe ne doivent pas être capturés dans les preuves ; les logs HTTP sont limités à méthode et statut.

| Domaine | Exigence et vérification future attendue |
| --- | --- |
| Données et cibles | Comptes et données exclusivement fictifs ; aucun service tiers utilisé comme cible |
| Exposition | Seuls les ports Nginx nécessaires sont publiés, exclusivement sur `127.0.0.1` ; vérifier les liaisons effectives |
| Services internes | Aucun port publié pour Flask/Gunicorn, PostgreSQL ou Redis ; vérifier Compose et l’état effectif |
| Séparation | Réseaux, volumes, secrets, sessions et compteurs Redis propres à chaque version ; vérifier l’absence d’accès croisé |
| Sorties réseau | Restreindre les sorties et vérifier leur blocage effectif sous Docker Desktop ; une configuration déclarative seule ne prouve pas le résultat |
| Conteneurs | Aucun mode privilégié, montage du socket Docker ou réseau hôte ; limiter capacités et privilèges au nécessaire |
| Base de données | Utilisateur SQL applicatif non administrateur, droits minimaux ; séparer les besoins éventuels de migration |
| Transport et navigateur | HTTPS local, vulnerable.vulnlab.test sur loopback 8443 ; secure.vulnlab.test réservé ; confiance explicite, séparation future des cookies et sessions à vérifier |
| Secrets | Secrets, clés privées et certificats locaux exclus de Git ; modèles de configuration sans secret réel |
| Remise à zéro | Procédure ciblée par version ; vérifier qu’elle ne modifie ni les volumes ni les données de l’autre version |
| Automatisation | GitHub Actions limité aux vérifications, aucun déploiement ni publication automatique du service vulnérable |

Les preuves d’isolation devront préciser l’environnement Docker Desktop, les commandes, les résultats observés et les limites. Les flux nécessaires entre Nginx, Flask et les stockages devront rester possibles tout en interdisant les accès non nécessaires. Les décisions actuelles et la proposition de filtrage complémentaire figurent dans l’[ADR M4](decisions/0004-local-https.md).

## Limite du navigateur et preuves XSS

M12 livrait [un prérequis bloqué](m12-browser-preparation.md).
[M12.1](m12-1-browser-sandbox.md) vérifie désormais la sandbox Chromium et les
témoins HTTP/redirection/WebSocket locaux, dans un conteneur réseau none,
non-root sans capacités ajoutées. Une règle seccomp chroot est adaptée ; les
contrôles noyau restent actifs. La porte obligatoire échoue sur tout prérequis
M12.1 manquant. **Aucun XSS ni connexion au laboratoire** : le TLS navigateur
reste non vérifié et nécessite une étape ultérieure après revue. Un filtre de
requêtes n'est pas une preuve de filtrage global de tous les flux du navigateur.

L’isolation du serveur ne garantit pas celle du navigateur. Celui-ci s’exécute sur le poste hôte et peut avoir accès à d’autres sites ou ressources que les conteneurs. Des hôtes distincts ne suffisent pas à garantir toute l’isolation du navigateur.

Les démonstrations XSS resteront locales, sans collecte ni transmission de données. Prévoir un profil de navigateur dédié sans comptes réels ni sessions personnelles, des données fictives et des preuves visuelles inoffensives. Aucun mécanisme d’exfiltration ni destination tierce ne fait partie des preuves autorisées.

## Preuves et dépôt

Les preuves sélectionnées et captures nettoyées pourront être versionnées : elles ne sont pas ignorées globalement. Avant ajout, vérifier qu’elles ne contiennent aucun secret, jeton ou donnée personnelle. Le `.gitignore` réduit les ajouts accidentels mais ne garantit pas à lui seul l’absence de secrets.

Voir le [modèle de menace](threat-model.md) et l’[architecture](architecture.md).
