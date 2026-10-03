# ADR 0007 — Tickets privés et commentaires de référence

Date : 2026-10-02. Statut : proposé pour revue M7.

La matrice validée est appliquée par une sélection SQL centralisée : propriétaire courant ou administrateur actif. Le même périmètre sert aux listes, comptages et recherches d'objet avant lecture/écriture. Aucun bouton ou identifiant client ne confère un droit. Le propriétaire reste immuable et l'auteur d'un commentaire est toujours l'acteur connecté.

Les routes réutilisent sessions Redis, CSRF et transactions M5/M6 ; le contrôle d'échéance et d'état actif est étendu à chaque route tickets. Les écritures verrouillent leur parent autorisé ; suppression par cascade SQL existante. Entiers signés pour fixtures négatives, pagination fixe 20 et borne 1000, texte Unicode échappé sans rendu HTML utilisateur.

Conséquences : formulaires simples, destinations POST locales fixes et erreurs 404 identiques pour absence/inaccessibilité. La pagination offset n'est pas un instantané concurrent. Aucun schéma, version ou privilège modifié ; aucune administration, pièce jointe, recherche ou faiblesse volontaire. Tests fonctionnels PostgreSQL/Redis et HTTPS sur ressources CI jetables, sans toucher les piles locales conservées. [Contrats et limites M7](../tickets-comments.md).
