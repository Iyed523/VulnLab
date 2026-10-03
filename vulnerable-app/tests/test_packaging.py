"""Contrôle d'installation uniquement, sans validation métier ou de sécurité."""

import json
from importlib import metadata
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import vulnlab_vulnerable


def test_installed_distribution_owns_imported_package():
    """Relier l'import aux métadonnées de l'installation éditable ou de la wheel."""
    distribution = metadata.distribution("vulnlab-vulnerable")
    assert distribution.metadata["Name"] == "vulnlab-vulnerable"
    imported = Path(vulnlab_vulnerable.__file__).resolve()
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")

    if direct_url.get("dir_info", {}).get("editable"):
        source = Path(url2pathname(urlsplit(direct_url["url"]).path))
        expected = source / "src" / "vulnlab_vulnerable" / "__init__.py"
        assert imported == expected.resolve()
    else:
        owned_files = {
            Path(distribution.locate_file(file)).resolve()
            for file in distribution.files or ()
        }
        assert imported in owned_files
