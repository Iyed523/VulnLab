"""Generate fresh local-only M12.2 identities; never reuse existing secrets."""

import argparse
import os
import secrets
import subprocess
from pathlib import Path


def generate(directory, openssl):
    directory.mkdir(parents=True, exist_ok=False)
    for name in ("public", "proxy", "witness", "issuer"):
        (directory / name).mkdir()

    def run(*args):
        subprocess.run(
            [openssl, *map(str, args)], capture_output=True, check=True, timeout=60
        )

    for name in ("trusted", "untrusted"):
        run(
            "req",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-sha256",
            "-days",
            "2",
            "-subj",
            f"/CN=M12.2 fictitious {name} authority",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-keyout",
            directory / "issuer" / f"{name}.key",
            "-out",
            directory / "public" / f"{name}.crt",
        )
    for name, authority, sans, target in (
        ("server", "trusted", "DNS:vulnerable.vulnlab.test", "proxy"),
        (
            "good",
            "trusted",
            "DNS:good.vulnlab.test,DNS:forbidden.vulnlab.test",
            "witness",
        ),
        ("untrusted", "untrusted", "DNS:untrusted.vulnlab.test", "witness"),
        ("wrong", "trusted", "DNS:correct.vulnlab.test", "witness"),
    ):
        key, cert = (
            directory / target / f"{name}.key",
            directory / target / f"{name}.crt",
        )
        csr = directory / "issuer" / f"{name}.csr"
        ext = directory / "issuer" / f"{name}.ext"
        ext.write_text(
            f"subjectAltName={sans}\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
        )
        run(
            "req",
            "-new",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-subj",
            f"/CN={name}.vulnlab.test",
            "-keyout",
            key,
            "-out",
            csr,
        )
        run(
            "x509",
            "-req",
            "-in",
            csr,
            "-CA",
            directory / "public" / f"{authority}.crt",
            "-CAkey",
            directory / "issuer" / f"{authority}.key",
            "-set_serial",
            "0x" + secrets.token_hex(16),
            "-days",
            "2",
            "-sha256",
            "-extfile",
            ext,
            "-out",
            cert,
        )
        key.chmod(0o640)
    # Match the unchanged application's exact 32-byte hexadecimal key contract.
    (directory / "session-key").write_text(
        secrets.token_hex(32) + "\n", encoding="ascii"
    )
    (directory / "session-key").chmod(0o640)
    (directory / "public" / "both.crt").write_bytes(
        (directory / "public" / "trusted.crt").read_bytes()
        + (directory / "public" / "untrusted.crt").read_bytes()
    )
    assert all(path.suffix == ".crt" for path in (directory / "public").iterdir())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("certs/local/m122"))
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    previous = os.umask(0o022)
    try:
        generate(args.directory, args.openssl)
    finally:
        os.umask(previous)
    print(
        "Fresh M12.2 certificates/session generated; public trust directory contains no keys"
    )


if __name__ == "__main__":
    main()
