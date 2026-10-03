# Outillage M12.1 — sandbox et témoins locaux, sans laboratoire ni XSS

Voir le [rapport M12.1](../../docs/m12-1-browser-sandbox.md) : adaptation chroot
seccomp minimale, sandbox et témoins loopback réellement vérifiés. La porte
retourne 2 pour un blocage connu ; toute autre erreur échoue explicitement.
Le mode diagnostic permissif M12 est retiré. Aucun accès lab/TLS ou XSS autorisé.

`seccomp.json` est une copie inchangée de :
https://github.com/microsoft/playwright/blob/v1.63.0/utils/docker/seccomp_profile.json

SHA-256 : `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
Licence amont Apache 2.0 conservée dans [LICENSE.seccomp](LICENSE.seccomp).
Le profil amont est dérivé du profil Docker ; il n'est pas présenté comme un
audit du profil seccomp actuel de Docker. `seccomp.json` reste inchangé.
`seccomp-chroot.json` est sa variante : seule la condition de capacité Docker
de la règle chroot est retirée, avec un commentaire ; test d'équivalence stricte.
La licence amont s'applique aux deux profils. Les contrôles noyau restent actifs.

Le build copie exclusivement les fichiers explicitement nommés du contexte
`docker/browser`, sans certificat, configuration personnelle ou profil.
Le conteneur d'essai est non-root, sans réseau ni capacités et sans volume.
