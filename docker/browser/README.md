# Outillage M12.1/M12.2 — navigateur de test dédié, aucun XSS

Voir le [rapport M12.1](../../docs/m12-1-browser-sandbox.md) : adaptation chroot
seccomp minimale, sandbox et témoins loopback réellement vérifiés. La porte
retourne 2 pour un blocage connu ; toute autre erreur échoue explicitement.
Le mode diagnostic permissif M12 est retiré. M12.2 ajoute une pile HTTPS dédiée ;
voir [topologie, confiance TLS et preuves M12.2](../../docs/m12-2-browser-lab-tls.md).
Aucun XSS autorisé.

`seccomp.json` est une copie inchangée de :
https://github.com/microsoft/playwright/blob/v1.63.0/utils/docker/seccomp_profile.json

SHA-256 : `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
Licence amont Apache 2.0 conservée dans [LICENSE.seccomp](LICENSE.seccomp).
Le profil amont est dérivé du profil Docker ; il n'est pas présenté comme un
audit du profil seccomp actuel de Docker. `seccomp.json` reste inchangé.
`seccomp-chroot.json` est sa variante : seule la condition de capacité Docker
de la règle chroot est retirée, avec un commentaire ; test d'équivalence stricte.
La licence amont s'applique aux deux profils. Les contrôles noyau restent actifs.

Le build M12.1 copie les fichiers nommés ; le build M12.2 copie les modules
Python du même contexte `docker/browser`, sans certificat ou profil.
M12.1 conserve réseau none et aucun volume. M12.2 reste non-root sans capacités,
sur son réseau interne browser-test, avec le seul répertoire de CA publiques
monté en lecture seule ; aucun montage de clé privée ou session.
