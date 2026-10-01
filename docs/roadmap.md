# Roadmap

Chaque étape nécessite une revue du Team Lead et une validation du Product Owner avant de passer à la suivante. M1 a été revue et validée par le Product Owner selon le cadrage M2. M2 est également validée. M3 est soumise à revue, avec les contrôles Docker d’exécution bloqués ; M4 n’est pas commencée.

| Étape | Contenu | État à la livraison M3 |
| --- | --- | --- |
| 1 | Conception | Validée par le Product Owner selon le cadrage fourni |
| 2 — M1 | Dépôt et documentation de référence | Validés |
| 3 — M2 | Environnement Python, sélection des versions, dépendances et CI minimale | Validée ; workflow GitHub non exécuté |
| 4 — M3 puis M4 | Premier socle Docker ; puis HTTPS et vérifications complémentaires d’isolation | M3 préparée et soumise à revue, moteur inaccessible ; M4 à venir |
| 5 | Données fictives et socle fonctionnel | À venir |
| 6 | Tests communs et référence Git traçable du socle | À venir |
| 7 | Introduction des vulnérabilités une par une | À venir |
| 8 | Audit initial avec preuves réelles | À venir |
| 9 | Copie traçable vers `secure-app` | À venir |
| 10 | Remédiations une par une et tests associés | À venir |
| 11 | Validation transversale et portfolio | À venir |

Les deux répertoires sont documentés dès M1. La présence de `secure-app/README.md` ne signifie pas qu’une copie applicative ou une remédiation a déjà eu lieu. La future référence Git sera créée dans une mission autorisée ; M1, M2 et M3 n’avaient créé aucun commit. M3-Git publie un commit d’amorçage réel sur main, puis le travail complet sur chore/bootstrap-lab, sans reconstituer de faux historique antérieur.

## Sélection des scénarios

- Retenus : VULN-001, VULN-002, VULN-003, VULN-004, VULN-005, VULN-007, VULN-008 et VULN-009.
- Conditionnel : VULN-006, uniquement si une fonctionnalité de diagnostic utile justifie sa présence.
- Reporté : VULN-010.

Ces identifiants expriment une sélection, sans attribuer de mécanisme non fourni par le cadrage. La matrice détaillée, les intitulés, correspondances OWASP Top 10:2025, fiches d’audit et preuves seront produits lors de missions ultérieures. Aucun scénario n’est implémenté ou démontré en M3.

## Décisions restant ouvertes

Les versions Python, uv, Flask, Pytest, Ruff et Hatchling ainsi que le verrou et la CI minimale sont consignés dans le [guide de développement](development.md) et l’[ADR 0002](decisions/0002-python-tooling.md). M2 est validée. Gunicorn et les fichiers Docker de M3 sont décrits dans [docker.md](docker.md) et l’[ADR 0003](decisions/0003-local-docker.md). Les versions des autres composants seront choisies dans leurs missions respectives. Les noms d’hôtes, ports HTTPS, certificats, règles de sorties réseau et leur validation sous Docker Desktop relèvent de l’infrastructure. La liste explicite des champs de profil autorisés et les détails des contrats HTTP seront fixés avant leur implémentation. VULN-006 reste conditionnelle ; VULN-010 ne rejoint pas le périmètre courant.

Références : [ADR initial](decisions/0001-architecture.md), [architecture](architecture.md), [autorisations](authorization-matrix.md), [sécurité locale](lab-safety.md).

M3-Git : le socle minimal est publié sur [Iyed523/VulnLab](https://github.com/Iyed523/VulnLab). La CI prévoit les contrôles Python Windows/Linux et Docker Linux ; leurs résultats et la PR restent à confirmer. Voir [git-workflow.md](git-workflow.md). M3 demeure soumise à revue.
