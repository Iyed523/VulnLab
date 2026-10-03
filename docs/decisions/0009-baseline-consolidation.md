# ADR 0009 — Intégrer les missions validées sans réécriture publiée

Date : 2026-10-02. Statut : proposé pour revue M9.

Conserver six PR dépendantes et leurs changements propres. Après autorisation, squasher dans l'ordre, puis réconcilier chaque branche avec le vrai nouveau main avant reciblage. Un squash conserve l'arbre mais pas l'ascendance ; reciblage seul insuffisant pour obtenir le delta de mission.

Le commit de réconciliation préparé localement possède la tête publiée et main comme parents ; son arbre est reconstruit par application du seul delta métier/documentaire validé sur main. Vérifier cet arbre et la filiation avant un push normal ; aucun force push. Main conserve un historique linéaire par les futurs squashes. Les SHA locaux de simulation ne remplacent pas ceux des fusions réelles.

La suppression automatique de branche actuellement activée doit être désactivée avec autorisation avant fusion. Aucune branche parente supprimée avant intégration et traitement de tous descendants. Les trois checks doivent repasser sur chaque nouvelle tête et sur main.

Validation Windows dans un nouveau projet/image/volume M9, indépendant de M6.1 et securevault. Volume conservé pour revue, clés existantes préservées. Aucun redémarrage Docker global pour contourner un incident moteur. Le tag annoté baseline-functional-v1 attend fusions autorisées, CI main verte et validation explicite ; aucune création en M9. [Preuves, procédure et limites](../baseline-consolidation-m9.md).
