# Fonctionnement Git et GitHub

Le dépôt cible est [Iyed523/VulnLab](https://github.com/Iyed523/VulnLab). M3-Git autorise la publication du code, des commits, une PR brouillon et les protections disponibles. Elle n’autorise aucune fusion ou publication du service.

Pour chaque mission : partir de `main` synchronisée, créer une branche dédiée, effectuer des commits décrivant le travail réel, puis pousser cette branche et ouvrir une PR. Ne jamais reconstruire artificiellement un historique de missions antérieures.

Depuis la racine, pour une future mission autorisée :

```powershell
git switch main
git pull --ff-only origin main
git switch -c NOM-DE-BRANCHE
# Ajouter explicitement les fichiers de la mission après examen.
git diff --cached --check
git diff --cached
git commit -m "Description du changement réel"
git push -u origin NOM-DE-BRANCHE
```

Le premier commit d’amorçage doit contenir uniquement un README autonome et `.gitignore`. Le travail M1–M3 complet est conservé sur `chore/bootstrap-lab` pour revue. Les contrôles attendus sont `Python Windows`, `Python Linux` et `Docker Linux` ; le dernier utilise uniquement les conteneurs locaux du runner, avec les identifiants fictifs du laboratoire.

Les diagnostics Docker sont affichés dans les logs en cas d’échec, puis le job nettoie uniquement sa pile et son volume avec `always()`. Le nettoyage ne neutralise pas un échec des étapes précédentes. Aucun nettoyage global, secret GitHub, registre ou déploiement n’est utilisé.

La revue du Team Lead et la validation explicite du Product Owner précèdent toute autorisation de fusion. Le squash merge est la méthode prévue ; aucune approbation par un second compte n’est exigée pour un dépôt géré seul. La PR initiale doit rester ouverte en brouillon, sans merge automatique.

Après une fusion autorisée et réalisée, synchroniser localement `main` avec `git pull --ff-only origin main`. Ne supprimer une branche locale qu’après avoir vérifié que son travail est intégré ; préserver toute modification locale et ne jamais forcer un push.

## État de M3-Git

Au démarrage : dépôt local sans commit ni remote, dépôt GitHub public et vide, identité Git existante, GitHub CLI sans session authentifiée. L’authentification GitHub est nécessaire pour la PR et les réglages. Le commit minimal 4b7f0c4 a été publié sur main avec l’authentification Git existante. La configuration safe.directory nécessaire au processus hors sandbox a été passée par commande, sans changer la configuration globale. La connexion GitHub CLI a ensuite permis le diagnostic, la PR et les protections.

M1 et M2 sont validées ; M3 reste soumise à revue. Un résultat Docker Linux en CI ne validera pas automatiquement Docker Desktop sur le poste local. M4 n’est pas commencée.

## Première publication et exécution

- `4b7f0c4` : commit minimal réel sur `main`, README d’amorçage et `.gitignore`, créé avec un index temporaire ; fichiers de travail conservés.
- `6437535` : socles M1–M3 et contrôles CI publiés sur `chore/bootstrap-lab`.
- [Exécution initiale](https://github.com/Iyed523/VulnLab/actions/runs/36854637686) : Python Linux réussi ; Docker Linux a construit l’image mais échoué au démarrage. Les diagnostics et le nettoyage ciblé ont réussi. Python Windows et Python Linux ont tous deux réussi.

Le refus initial de lecture des logs sans authentification est résolu. Aucun jeton n’a été lu ou affiché.

## Résultat après authentification

La [PR #1](https://github.com/Iyed523/VulnLab/pull/1) est ouverte en brouillon. La [CI sur 4a82ae2](https://github.com/Iyed523/VulnLab/actions/runs/36857188426) a réussi pour Python Windows, Python Linux et Docker Linux après correction des tmpfs YAML, du réseau d’entrée du proxy et du socket de contrôle Gunicorn.

Réglages appliqués et relus via API : squash seul autorisé, auto-merge désactivé ; main exige les trois jobs GitHub Actions, une branche à jour, la résolution des conversations et un historique linéaire, avec application aux administrateurs. Push forcé et suppression de main interdits. Une PR est requise, avec zéro approbation obligatoire pour ce dépôt individuel. Aucun merge effectué.
