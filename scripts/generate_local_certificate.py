"""Créer un certificat local éphémère sans modifier la confiance système."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    args = parser.parse_args()
    if not args.openssl:
        parser.error("Fournir --openssl avec le chemin d'un OpenSSL disponible")
    directory = Path("certs/local/vulnerable")
    directory.mkdir(parents=True, exist_ok=True)
    key = directory / "server.key"
    cert = directory / "server.crt"
    if key.exists() or cert.exists():
        parser.error(
            "Certificat existant : conserver ou retirer explicitement avant renouvellement"
        )
    previous = os.umask(0o077)
    try:
        subprocess.run(
            [
                args.openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-sha256",
                "-days",
                "7",
                "-subj",
                "/CN=vulnerable.vulnlab.test",
                "-addext",
                "subjectAltName=DNS:vulnerable.vulnlab.test",
                "-addext",
                "basicConstraints=critical,CA:FALSE",
                "-addext",
                "keyUsage=critical,digitalSignature,keyEncipherment",
                "-addext",
                "extendedKeyUsage=serverAuth",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        key.chmod(0o640)
        cert.chmod(0o644)
        directory.chmod(0o755)
    finally:
        os.umask(previous)
    gid = os.getgid() if hasattr(os, "getgid") else 1000
    print(
        f"Certificat local créé (7 jours). TLS_KEY_GID={gid}; aucune confiance système modifiée."
    )


if __name__ == "__main__":
    main()
