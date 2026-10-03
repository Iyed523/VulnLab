# Règles de travail VulnLab

- Avant toute modification, inspecter les fichiers, l’état Git et les instructions applicables, y compris les `AGENTS.md` parents et ceux du sous-répertoire concerné. Lire les documents de référence pertinents.
- Respecter le périmètre de la mission autorisée. S’arrêter pour revue du Team Lead et validation du Product Owner ; ne jamais commencer automatiquement la mission suivante.
- Préserver les fichiers, modifications utilisateur, branches, historique et remotes existants. Ne pas écraser un travail inconnu. Ne pas committer ou effectuer d’opération distante sans autorisation.
- Séparer strictement le code pédagogique de `vulnerable-app` et le code corrigé de `secure-app`. Ne pas partager les implémentations sensibles ; conserver les contrats métier et schémas communs.
- Associer chaque faiblesse volontaire à un identifiant `VULN-xxx`, une justification pédagogique et un test. Documenter son périmètre, sa preuve locale et sa remédiation lors de la mission correspondante.
- Distinguer tests fonctionnels, démonstrations de vulnérabilité et tests de remédiation. Une démonstration attendue ne doit pas être présentée comme une validation de sécurité.
- Ne jamais masquer un échec, désactiver arbitrairement un contrôle ou falsifier un résultat pour obtenir une CI verte.
- Exécuter les contrôles pertinents réellement disponibles. Rapporter leurs commandes, résultats, portée et limites, en incluant les fichiers non suivis. Ne jamais inventer de preuve, constat d’audit ou validation.
- Ne jamais publier ou déployer le service vulnérable. Respecter le périmètre exclusivement local, les données fictives et les exigences de [sécurité du laboratoire](docs/lab-safety.md). Aucun tiers ne doit être ciblé.
- Ne pas lire, copier ou afficher de secrets réels. Exclure de Git secrets et certificats privés. Examiner et nettoyer les preuves avant leur versionnement.
- Distinguer exigences prévues et protections effectivement vérifiées ; ne pas déduire l’isolation du navigateur de celle du serveur.
- Rendre compte de l’état initial, des fichiers créés ou modifiés, des commandes, des vérifications réelles, des difficultés, des limites et de l’état Git final. Signaler les décisions ouvertes et laisser la validation au Product Owner.
