"""M9 local-only squash preview; never checks out, pushes, merges or tags."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

REFS = [
    "origin/main",
    "origin/chore/bootstrap-lab",
    "origin/codex/m4-local-https",
    "origin/codex/m5-data-foundation",
    "origin/codex/m6-auth-sessions",
    "origin/codex/m7-tickets-comments",
    "origin/codex/m8-profile-admin",
]
EXPECTED = "b9f5a771cfc39e677601f69949268862ca262a56"
PREVIEW = "refs/heads/codex/m9-integration-preview"


def git(*args, data=None, env=None):
    return subprocess.run(
        ["git", *args], input=data, env=env, check=True, capture_output=True
    ).stdout


def main():
    if git("status", "--porcelain").strip():
        raise RuntimeError("Commit consolidation changes before simulation")
    commits = [git("rev-parse", ref).decode().strip() for ref in REFS]
    if commits[-1] != EXPECTED:
        raise RuntimeError("M8 head differs from the validated mission input")
    names = [PREVIEW] + [f"refs/heads/codex/m9-pr{i}-reconciled" for i in range(2, 7)]
    for name in names:
        exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", name], check=False
        )
        if exists.returncode != 1:
            raise RuntimeError(f"Existing or unreadable local ref: {name}")
    for base, head in zip(commits, commits[1:], strict=False):
        git("merge-base", "--is-ancestor", base, head)
    results = []
    current = commits[0]
    with tempfile.TemporaryDirectory(prefix="vulnlab-m9-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        for number, (base, head) in enumerate(
            zip(commits, commits[1:], strict=False), 1
        ):
            git("read-tree", current, env=env)
            patch = git("diff", "--binary", base, head)
            git("apply", "--cached", "--check", data=patch, env=env)
            git("apply", "--cached", data=patch, env=env)
            tree = git("write-tree", env=env).decode().strip()
            expected_tree = git("rev-parse", f"{head}^{{tree}}").decode().strip()
            if tree != expected_tree:
                raise RuntimeError(f"Unexpected tree at PR {number}")
            if number > 1:
                # Preserve the published head as a parent: future normal push can
                # fast-forward. New main becomes the merge base of the same PR.
                repair = (
                    git(
                        "commit-tree",
                        tree,
                        "-p",
                        head,
                        "-p",
                        current,
                        data=f"Local M9 reconciliation for PR {number}\n".encode(),
                    )
                    .decode()
                    .strip()
                )
                git("merge-base", "--is-ancestor", head, repair)
                if git("diff", "--binary", current, repair) != patch:
                    raise RuntimeError("Reconciliation altered the mission delta")
                name = f"refs/heads/codex/m9-pr{number}-reconciled"
                git("update-ref", name, repair, "0" * 40)
            current = (
                git(
                    "commit-tree",
                    tree,
                    "-p",
                    current,
                    data=f"Local M9 squash preview PR {number}\n".encode(),
                )
                .decode()
                .strip()
            )
            results.append(
                dict(pr=number, base=base, head=head, squash=current, tree=tree)
            )
    git("update-ref", PREVIEW, current, "0" * 40)
    if git("diff", "--exit-code", current, EXPECTED):
        raise RuntimeError("Final preview differs from M8")
    print(
        json.dumps(
            dict(
                main=commits[0],
                stages=results,
                preview=current,
                final_tree=results[-1]["tree"],
                identical_to_m8=True,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
