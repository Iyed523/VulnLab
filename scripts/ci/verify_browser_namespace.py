"""Differential syscall controls: isolated containers, no capability or network."""

import json
import subprocess
from pathlib import Path


def main():
    for profile, expectation in (
        ("seccomp.json", "denied"),
        ("seccomp-chroot.json", "allowed"),
    ):
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--init",
                "--network",
                "none",
                "--user",
                "pwuser",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--security-opt",
                f"seccomp={Path('docker/browser', profile).resolve()}",
                "--memory",
                "256m",
                "--cpus",
                "1",
                "--pids-limit",
                "64",
                "--tmpfs",
                "/tmp:rw,nosuid,size=16m,mode=1777",
                "--entrypoint",
                "python",
                "vulnlab-m12-1-browser:1.63.0",
                "/opt/browser/namespace_probe.py",
                "--expect-chroot",
                expectation,
            ],
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        print(profile, result.stdout.strip())
    # Negative browser control: a recognized failure MUST still fail the gate.
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--init",
            "--network",
            "none",
            "--user",
            "pwuser",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--security-opt",
            f"seccomp={Path('docker/browser/seccomp.json').resolve()}",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "--tmpfs",
            "/tmp:rw,nosuid,size=256m,mode=1777",
            "--shm-size",
            "256m",
            "vulnlab-m12-1-browser:1.63.0",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 2, "Negative browser gate did not fail as expected"
    report = json.loads(result.stdout)
    assert report["reason"] == "zygote-chroot-denied"
    assert report["sandbox_verified"] is False
    assert report["network_restrictions_verified"] is False
    assert report["xss_allowed"] is False
    print("negative_browser_gate", result.returncode, result.stdout.strip())


if __name__ == "__main__":
    main()
