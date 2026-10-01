# Développement — M2 validée, outillage actualisé en M3

M1 et M2 sont validées. M3 ajoute uniquement la fabrique et le contrat HTTP technique `/healthz`, Gunicorn sur Linux et le groupe build verrouillé. Les fichiers Docker et les contrôles bloqués sont décrits dans [docker.md](docker.md). Aucun modèle métier ni scénario vulnérable n’est créé. `secure-app` reste documentaire.

## Versions et sources

Versions sélectionnées et métadonnées consultées le 28 septembre 2026 ; vérifications locales finales le 30 septembre 2026.

| Composant | Version | Source officielle |
| --- | --- | --- |
| CPython standard avec GIL | 3.13.15 | [Publication Python](https://www.python.org/downloads/release/python-31315/) |
| uv | 0.12.19 | [Publication Astral](https://github.com/astral-sh/uv/releases/tag/0.12.19) |
| Flask | 3.1.3 | [Métadonnées PyPI](https://pypi.org/pypi/Flask/3.1.3/json) |
| Pytest | 9.1.1 | [Métadonnées PyPI](https://pypi.org/pypi/pytest/9.1.1/json) |
| Ruff | 0.16.9 | [Métadonnées PyPI](https://pypi.org/pypi/ruff/0.16.9/json) |
| Hatchling | 1.32.4 | [Métadonnées PyPI](https://pypi.org/pypi/hatchling/1.32.4/json) |

Les versions retenues sont stables, non retirées sur PyPI et leurs contraintes Python acceptent 3.13. Les 14 distributions externes de `uv.lock`, ainsi que Hatchling et uv, ont été contrôlées via l’API PyPI versionnée : aucun avis associé à ces versions n’était retourné. Les versions transitives sont celles de `uv.lock`, généré par uv, jamais édité à la main.

Les avis publics des dépôts [Flask](https://github.com/pallets/flask/security/advisories), [Pytest](https://github.com/pytest-dev/pytest/security/advisories), [Ruff](https://github.com/astral-sh/ruff/security/advisories), [Hatch](https://github.com/pypa/hatch/security/advisories) et [uv](https://github.com/astral-sh/uv/security/advisories) ont également été consultés. Flask 3.1.3 corrige notamment [GHSA-68rp-wp8r-4726](https://github.com/pallets/flask/security/advisories/GHSA-68rp-wp8r-4726) ; uv 0.12.19 est postérieur au correctif 0.12.18 de [GHSA-2cv4-cqwr-gwf7](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7). Ce contrôle ponctuel des informations publiées n’est ni un audit complet ni une garantie d’absence de vulnérabilités, et ne couvre pas exhaustivement les dépendances de construction ou les bibliothèques embarquées.

## Prérequis et installation Windows

PowerShell, Git et un accès HTTPS à GitHub, PyPI et aux distributions Python gérées par uv sont nécessaires. Aucun privilège administrateur ni activation manuelle de venv n’est requis. Les outils ne proviennent pas d’un autre projet.

Depuis la racine `C:\Users\iyedl\Bureau\VulnLab`, pour une première installation uniquement :

```powershell
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force .tools | Out-Null
Invoke-WebRequest 'https://github.com/astral-sh/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip' -OutFile .tools/uv.zip
if ((Get-FileHash .tools/uv.zip -Algorithm SHA256).Hash.ToLower() -ne '6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0') {
    throw 'Archive uv non conforme'
}
Expand-Archive .tools/uv.zip .tools/uv -Force
```

L’empreinte a été comparée au champ `digest` de l’API de la publication officielle. Le téléchargement et cette vérification ont été exécutés. Python est fourni par le mécanisme officiel [uv python install](https://docs.astral.sh/uv/guides/install-python/), qui distribue les builds CPython gérés par Astral.

À chaque nouvelle session, depuis la racine du dépôt :

```powershell
$uv = (Resolve-Path .tools/uv/uv.exe).Path
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.tools/python'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.tools/uv-cache'
& $uv --version
& $uv python install 3.13.15 --no-bin
if ($LASTEXITCODE) { throw 'Installation Python échouée' }
Set-Location vulnerable-app
& $uv sync --locked --group build --python 3.13.15
if ($LASTEXITCODE) { throw 'Synchronisation échouée' }
```

Cette synchronisation installe le projet en mode éditable dans `vulnerable-app/.venv`, avec Flask et le groupe `dev`. Ne pas utiliser un `UV_PROJECT_ENVIRONMENT` pointant vers un autre environnement. Les variables ci-dessus ne modifient que la session courante ; aucun PATH global n’a été modifié.

## Contrôles Windows

Depuis `vulnerable-app`, dans la session préparée ci-dessus, exécuter chaque commande et arrêter en cas d’échec :

```powershell
& $uv run --locked python -c "import sys; print(sys.version); assert sys._is_gil_enabled(); print('GIL actif')"
if ($LASTEXITCODE) { throw 'Python incorrect' }
& $uv pip check
if ($LASTEXITCODE) { throw 'Dépendances incohérentes' }
& $uv run --locked ruff check .
if ($LASTEXITCODE) { throw 'Analyse Ruff échouée' }
& $uv run --locked ruff format --check .
if ($LASTEXITCODE) { throw 'Formatage incorrect' }
& $uv run --locked pytest
if ($LASTEXITCODE) { throw 'Tests échoués' }
& $uv run --locked --group build -- $uv build --wheel --no-build-isolation
if ($LASTEXITCODE) { throw 'Construction échouée' }
$before = (Get-FileHash uv.lock -Algorithm SHA256).Hash
& $uv sync --locked
if ($LASTEXITCODE) { throw 'Seconde synchronisation échouée' }
if ($before -ne (Get-FileHash uv.lock -Algorithm SHA256).Hash) { throw 'Verrou modifié' }
```

`uv pip check` examine l’environnement déjà synchronisé ; il ne résout ni ne modifie le verrou. `uv build` n’accepte pas `--locked` : l’enveloppe `uv run --locked` vérifie le verrou avant la construction. Depuis M3, le groupe build contient Hatchling et ses transitives dans le verrou. La commande de construction synchronise ce groupe puis utilise --no-build-isolation pour éviter une nouvelle résolution.

Pytest conserve **un test d’installation** et ajoute en M3 trois tests de contrat HTTP technique, qui relie la distribution installée au package importé. Les marqueurs `functional`, `vulnerable_behavior` et `security` sont réservés aux missions futures ; aucun test de ces catégories n’existe. Aucun `PYTHONPATH` ni ajout de `src` à `sys.path` n’est utilisé.

## Vérification de la wheel hors des sources

Depuis `vulnerable-app`, après construction, avec `$uv` et les variables précédentes :

```powershell
$project = (Get-Location).Path
$tempCheck = Join-Path ([IO.Path]::GetTempPath()) ('vulnlab-m2-' + [guid]::NewGuid())
New-Item -ItemType Directory $tempCheck | Out-Null
& $uv venv --python 3.13.15 "$tempCheck/.venv"
if ($LASTEXITCODE) { throw 'Création venv échouée' }
& $uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file "$tempCheck/runtime.txt"
if ($LASTEXITCODE) { throw 'Export échoué' }
& $uv pip sync --python "$tempCheck/.venv/Scripts/python.exe" --require-hashes "$tempCheck/runtime.txt" --offline
if ($LASTEXITCODE) { throw 'Installation des dépendances échouée' }
& $uv pip install --python "$tempCheck/.venv/Scripts/python.exe" --no-deps "$project/dist/vulnlab_vulnerable-0.1.0-py3-none-any.whl"
if ($LASTEXITCODE) { throw 'Installation wheel échouée' }
& $uv pip check --python "$tempCheck/.venv/Scripts/python.exe"
if ($LASTEXITCODE) { throw 'Dépendances wheel incohérentes' }
Push-Location $tempCheck
try {
    & "$tempCheck/.venv/Scripts/python.exe" -I -c "import json, pathlib, sys; from importlib.metadata import distribution; import vulnlab_vulnerable; d = distribution('vulnlab-vulnerable'); p = pathlib.Path(vulnlab_vulnerable.__file__).resolve(); assert p.is_relative_to(pathlib.Path(sys.prefix).resolve()); assert p in {pathlib.Path(d.locate_file(f)).resolve() for f in d.files}; assert not json.loads(d.read_text('direct_url.json')).get('dir_info', {}).get('editable', False); print(d.metadata['Name'], d.version, p)"
    if ($LASTEXITCODE) { throw 'Import wheel échoué' }
} finally {
    Pop-Location
}
```

L’export est un fichier temporaire généré depuis le verrou, pas une deuxième liste maintenue. Le mode hors ligne utilise le cache rempli par la synchronisation précédente. `-I` empêche l’import de dépendre du répertoire courant ou de variables Python externes. Le dossier temporaire peut être supprimé après inspection de son chemin exact.

## Équivalents Linux — préparés, non exécutés localement

Préinstaller uv **0.12.19** par une [méthode officielle](https://docs.astral.sh/uv/getting-started/installation/) adaptée à l’architecture. Depuis la racine du dépôt, avec ce binaire accessible comme `uv` :

```bash
set -eu
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python"
export UV_CACHE_DIR="$PWD/.tools/uv-cache"
uv --version
uv python install 3.13.15 --no-bin
cd vulnerable-app
uv sync --locked --group build --python 3.13.15
uv pip check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked --group build -- uv build --wheel --no-build-isolation
```

Pour répéter le contrôle non éditable sous Linux, utiliser `mktemp -d`, `uv venv --python 3.13.15 "$tempCheck/.venv"`, puis les mêmes commandes d’export et d’installation en remplaçant `Scripts/python.exe` par `bin/python`. Exécuter l’import avec `-I` depuis ce dossier temporaire. Cette procédure Linux est fournie comme équivalent et n’a pas été exécutée en M2.

## Mise à jour explicite du verrou

Depuis `vulnerable-app`, après autorisation de la mission de mise à jour : vérifier versions, compatibilité et avis publics ; modifier les versions directes dans `pyproject.toml` si nécessaire. Exécuter `& $uv lock --upgrade-package NOM` (Linux : `uv lock --upgrade-package NOM`), puis `sync --locked` et tous les contrôles ci-dessus. Pour une évolution volontaire de l’ensemble des transitives, employer `lock --upgrade`. Examiner les changements de `uv.lock` ; ne jamais le modifier à la main. Si Python ou uv évolue, aligner `.python-version`, `required-version`, la CI et ce guide.

Le verrou initial a été généré avec `uv lock --project vulnerable-app` depuis la racine. Les commandes ordinaires et la CI utilisent `--locked` afin d’échouer au lieu de régénérer implicitement un verrou incohérent.

## Workflow et bilan réel

Le [workflow](../.github/workflows/ci.yml) cible `push` et `pull_request`, les runners hébergés `ubuntu-latest` et `windows-latest`, une limite de 15 minutes et uniquement `contents: read`. Aucun déploiement, publication, secret de déploiement ou neutralisation d’échec n’est prévu.

Les tags ont été résolus par `git ls-remote` sur leurs dépôts officiels et les définitions `action.yml` ont été consultées au SHA exact :

- [actions/checkout v7.0.1](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1).
- [astral-sh/setup-uv v10.2.0](https://github.com/astral-sh/setup-uv/tree/c18668ad3cf93ea998bef934396af7bb5c839dc7).

Validation statique exécutée depuis la racine : `.tools/actionlint/actionlint.exe -shellcheck= -pyflakes= .github/workflows/ci.yml`, avec [actionlint 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), sans diagnostic. L’archive officielle a été vérifiée par SHA256. ShellCheck et Pyflakes n’étaient pas utilisés ; les commandes Python ont été exécutées séparément sous Windows. Cette validation ne simule pas un runner GitHub.

Résultats locaux : Python standard avec GIL, uv 0.12.19, synchronisation verrouillée, 15 distributions compatibles, analyse et formatage Ruff réussis, **4 tests collectés et réussis en M3**, wheel construite et importée sans installation éditable depuis un dossier temporaire, 8 distributions compatibles dans cet environnement de wheel. La seconde synchronisation n’a pas modifié le verrou.

Les interruptions dues aux limites d’utilisation ont retardé les consultations et la validation du workflow ; aucune réussite n’a été simulée. Les téléchargements ont ensuite été repris avec autorisation. L’aide de uv a permis de corriger la commande de construction initialement prévue avec un `--locked` non disponible sur `uv build`.

**Le workflow est préparé et vérifié localement, pas exécuté sur GitHub.** Aucun remote n’est configuré, aucun commit ni push n’est créé. Linux n’a pas été testé localement. Aucun test métier, audit applicatif ou test d’isolation réseau n’est revendiqué. M2 est validée ; M3 est soumise à revue avec les limites détaillées dans docker.md. M4 n’est pas commencée.
