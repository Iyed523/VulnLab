# ADR 0006 — Authentification de référence et sessions Redis

Date : 2026-10-02. Statut : proposé pour revue M6.

M5 fournit les comptes fictifs et Argon2id. M6 adopte Flask-Login, Flask-Session, Flask-WTF et Flask-Limiter avec versions verrouillées, sans changer le schéma. Les sessions et compteurs restent dans Redis ; aucune solution de secours ne permet de poursuivre une authentification lors d'une panne. Les cookies opaques sont renouvelés à la connexion et supprimés à la déconnexion. La durée authentifiée est absolue et le compte actif est vérifié à chaque requête concernée.

Une seule frontière de confiance Nginx est configurée pour l'adresse IP et HTTPS. Les formulaires restent locaux, protégés par CSRF ; inscription sans attribution de privilèges et compte en lecture seule. Les tests utilisent les vrais services puis un parcours HTTPS avec confiance explicite du certificat. Les contrôles précédents restent exigés.

Conséquences : Redis devient nécessaire aux routes d'authentification, avec 503 contrôlé en cas d'indisponibilité. Aucun reset, administration, tickets, faiblesse volontaire ou session de `secure-app` n'est ajouté. La clé locale est générée séparément et ne doit jamais être versionnée. Détails, procédures et limites dans [le guide M6](../auth-sessions.md). Validation finale réservée au Team Lead et au Product Owner.
