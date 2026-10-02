# ADR 0006 — Authentification de référence et sessions Redis

Date : 2026-10-02. Statut : M6 validée par le Product Owner ; complément M6.1 soumis à revue.

M6.1 vérifie le socle sous Docker Desktop Windows. Les sondes acceptent un projet VulnLab distinct pour préserver les ressources existantes. Sur Windows, le contrôle des clés combine ACL NTFS sans lecteurs génériques et refus réel d'ouverture en écriture ; il ne déduit pas la confidentialité NTFS du mode apparent 777 des bind mounts. Linux CI conserve le mode 0640 et le contrôle POSIX. Voir [le rapport local](../local-validation-m61.md).

M5 fournit les comptes fictifs et Argon2id. M6 adopte Flask-Login, Flask-Session, Flask-WTF et Flask-Limiter avec versions verrouillées, sans changer le schéma. Les sessions et compteurs restent dans Redis ; aucune solution de secours ne permet de poursuivre une authentification lors d'une panne. Les cookies opaques sont renouvelés à la connexion et supprimés à la déconnexion. La durée authentifiée est absolue et le compte actif est vérifié à chaque requête concernée.

Une seule frontière de confiance Nginx est configurée pour l'adresse IP et HTTPS. Les formulaires restent locaux, protégés par CSRF ; inscription sans attribution de privilèges et compte en lecture seule. Les tests utilisent les vrais services puis un parcours HTTPS avec confiance explicite du certificat. Les contrôles précédents restent exigés.

Conséquences : Redis devient nécessaire aux routes d'authentification, avec 503 contrôlé en cas d'indisponibilité. Aucun reset, administration, tickets, faiblesse volontaire ou session de `secure-app` n'est ajouté. La clé locale est générée séparément et ne doit jamais être versionnée. Détails, procédures et limites dans [le guide M6](../auth-sessions.md). Validation finale réservée au Team Lead et au Product Owner.
