# ADR 0008 — Profil limité et révocation durable des sessions

Date : 2026-10-02. Statut : proposé pour revue M8.

Le profil ne modifie que le nom affiché de l'acteur connecté. Les opérations administratives se limitent à la liste de cinq champs publics métier et au statut actif des utilisateurs ordinaires. Les administrateurs ne peuvent pas changer leur statut ou celui d'un autre administrateur ; aucun changement de rôle ou suppression.

Un simple drapeau `active` ne révoque pas une session gardée pendant une désactivation/réactivation. La migration 0002 ajoute une version SQL non négative, copiée dans la session lors du login et incrémentée atomiquement à la désactivation. La réactivation conserve cette version. SQL constitue l'autorité durable ; les anciens SID restent inutilisables, même avant suppression physique Redis. Les anciens SID sans version exigent une reconnexion.

Les vues privées portent le marqueur `protected`, réutilisé par le contrôle global de backend/expiration/identité. Les services M8 revérifient les droits et la version sous verrou dans leurs transactions, indépendamment des boutons. Les cibles sont limitées par session/route et les champs par liste explicite.

Conséquences : une migration conservant les données et une reconnexion lors de l'adoption. Aucune nouvelle dépendance ou topologie. Pas de purge Redis globale, d'annulation de requête en cours ou de gestion HTTP des administrateurs. Maintenance SQL directe : incrément obligatoire de version à la désactivation pour conserver la garantie après réactivation. Retour à M7 : invalidation explicite préalable des sessions du seul projet. [Contrats, procédures et preuves](../profile-admin.md).
