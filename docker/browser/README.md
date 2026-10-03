# Outillage M12 — préparation uniquement

Voir le [rapport M12](../../docs/m12-browser-preparation.md) : sandbox bloquée,
aucune introduction de XSS. Le mode normal de `sandbox_probe.py` est une porte
qui retourne 2 pour un blocage connu. `--diagnostic` classe ce blocage sans
prétendre valider les prérequis ; toute autre erreur échoue explicitement.

`seccomp.json` est une copie inchangée de :
https://github.com/microsoft/playwright/blob/v1.63.0/utils/docker/seccomp_profile.json

SHA-256 : `cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
Licence amont Apache 2.0 conservée dans [LICENSE.seccomp](LICENSE.seccomp).
Le profil amont est dérivé du profil Docker ; il n'est pas présenté comme un
audit du profil seccomp actuel de Docker. Aucune adaptation locale de ce profil.

Le build copie exclusivement les fichiers explicitement nommés du contexte
`docker/browser`, sans certificat, configuration personnelle ou profil.
Le conteneur d'essai est non-root, sans réseau ni capacités et sans volume.
