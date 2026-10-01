# Sécurité et isolation du laboratoire

**État M3 : configurations Docker préparées et validées statiquement ; moteur inaccessible, aucun conteneur ni contrôle d’isolation effectif vérifié.** Voir [le bilan Docker](docker.md). HTTPS et les contrôles complémentaires des sorties réseau restent en M4. HTTP local est provisoire, avant toute session ou authentification. Le laboratoire doit rester exclusivement local ; le service vulnérable ne doit jamais être publié ou déployé.

## Exigences pour les missions futures

| Domaine | Exigence et vérification future attendue |
| --- | --- |
| Données et cibles | Comptes et données exclusivement fictifs ; aucun service tiers utilisé comme cible |
| Exposition | Seuls les ports Nginx nécessaires sont publiés, exclusivement sur `127.0.0.1` ; vérifier les liaisons effectives |
| Services internes | Aucun port publié pour Flask/Gunicorn, PostgreSQL ou Redis ; vérifier Compose et l’état effectif |
| Séparation | Réseaux, volumes, secrets, sessions et compteurs Redis propres à chaque version ; vérifier l’absence d’accès croisé |
| Sorties réseau | Restreindre les sorties et vérifier leur blocage effectif sous Docker Desktop ; une configuration déclarative seule ne prouve pas le résultat |
| Conteneurs | Aucun mode privilégié, montage du socket Docker ou réseau hôte ; limiter capacités et privilèges au nécessaire |
| Base de données | Utilisateur SQL applicatif non administrateur, droits minimaux ; séparer les besoins éventuels de migration |
| Transport et navigateur | HTTPS local, hôtes distincts pour les deux versions, cookies et sessions distincts ; noms et ports à définir |
| Secrets | Secrets, clés privées et certificats locaux exclus de Git ; modèles de configuration sans secret réel |
| Remise à zéro | Procédure ciblée par version ; vérifier qu’elle ne modifie ni les volumes ni les données de l’autre version |
| Automatisation | GitHub Actions limité aux vérifications, aucun déploiement ni publication automatique du service vulnérable |

Les preuves d’isolation devront préciser l’environnement Docker Desktop, les commandes, les résultats observés et les limites. Les flux nécessaires entre Nginx, Flask et les stockages devront rester possibles tout en interdisant les accès non nécessaires. La méthode exacte sera choisie et validée dans la mission infrastructure.

## Limite du navigateur et preuves XSS

L’isolation du serveur ne garantit pas celle du navigateur. Celui-ci s’exécute sur le poste hôte et peut avoir accès à d’autres sites ou ressources que les conteneurs. Des hôtes distincts ne suffisent pas à garantir toute l’isolation du navigateur.

Les démonstrations XSS resteront locales, sans collecte ni transmission de données. Prévoir un profil de navigateur dédié sans comptes réels ni sessions personnelles, des données fictives et des preuves visuelles inoffensives. Aucun mécanisme d’exfiltration ni destination tierce ne fait partie des preuves autorisées.

## Preuves et dépôt

Les preuves sélectionnées et captures nettoyées pourront être versionnées : elles ne sont pas ignorées globalement. Avant ajout, vérifier qu’elles ne contiennent aucun secret, jeton ou donnée personnelle. Le `.gitignore` réduit les ajouts accidentels mais ne garantit pas à lui seul l’absence de secrets.

Voir le [modèle de menace](threat-model.md) et l’[architecture](architecture.md).
