"""Generate only a new laboratory key, never replace or display an existing one."""

import argparse
import os
import secrets
from pathlib import Path


def generate(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(descriptor, "w", encoding="ascii") as output:
        output.write(secrets.token_hex(32) + "\n")
    path.chmod(0o640)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="secrets/local/session-key")
    args = parser.parse_args()
    try:
        generate(args.path)
    except FileExistsError:
        parser.exit(
            1, "Existing key preserved; replacement requires explicit maintenance.\n"
        )
    print("New local session key generated (contents withheld).")


if __name__ == "__main__":
    main()
