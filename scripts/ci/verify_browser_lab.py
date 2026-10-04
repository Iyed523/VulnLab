"""Own, inspect and clean only the disposable M12.2 Compose project."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

PROJECT = "vulnlab-m12-2-browser-lab"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    directory = root / "certs/local/m122"
    env = dict(os.environ, M122_DIR=directory.as_posix())

    def docker(*arguments, timeout=180, check=True):
        return subprocess.run(
            [args.docker, *arguments],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=check,
        )

    for kind, label in (("ps", "--all"), ("volume", "ls"), ("network", "ls")):
        arguments = [
            kind,
            label,
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--quiet",
        ]
        assert not docker(*arguments).stdout.strip(), (
            "Existing M12.2 resources: preserve and stop"
        )
    assert not directory.exists(), "Existing certificate directory: preserve and stop"
    compose = [
        "compose",
        "--env-file",
        ".env.example",
        "-f",
        "compose.vulnerable.yaml",
        "-f",
        "compose.browser-lab.yaml",
    ]
    owned = False
    stage = "certificate-generation"
    try:
        # Already-built M12.1 tooling, never a browser session. No capability added.
        directory.parent.mkdir(parents=True, exist_ok=True)
        owned = True
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "pwuser",
            "--entrypoint",
            "python",
            "--volume",
            f"{root.as_posix()}:/workspace",
            "--workdir",
            "/workspace",
            "vulnlab-m12-1-browser:1.63.0",
            "scripts/generate_browser_lab_certificates.py",
            timeout=90,
        )
        gid = docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--entrypoint",
            "python",
            "--volume",
            f"{directory.as_posix()}:/certs:ro",
            "vulnlab-m12-1-browser:1.63.0",
            "-c",
            "import os; print(os.stat('/certs/proxy/server.key').st_gid)",
        ).stdout.strip()
        assert gid.isdigit()
        env["TLS_KEY_GID"] = gid
        stage = "compose-config"
        config = json.loads(docker(*compose, "config", "--format", "json").stdout)
        assert config["name"] == PROJECT
        browser = config["services"]["browser-lab"]
        assert set(browser["networks"]) == {"browser-test"}
        assert config["networks"]["browser-test"]["internal"] is True
        assert not browser.get("ports") and not config["services"]["proxy"].get("ports")
        assert browser["cap_drop"] == ["ALL"] and not browser.get("cap_add")
        assert len(browser["volumes"]) == 1 and browser["volumes"][0]["source"] == str(
            directory / "public"
        ).replace("\\", "/")
        stage = "build"
        print("M12.2: configuration checked; build dedicated images", flush=True)
        docker(*compose, "build", "app", "browser-lab", timeout=600)
        stage = "stack-health"
        docker(
            *compose,
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "120",
            "db",
            "redis",
            "app",
            "proxy",
            "tls-witness",
            timeout=160,
        )
        stage = "migrate-seed"
        print(
            "M12.2: dedicated services healthy; provision fictitious data", flush=True
        )
        docker(*compose, "--profile", "tools", "run", "--rm", "data-tools", "upgrade")
        docker(*compose, "--profile", "tools", "run", "--rm", "data-tools", "seed")
        targets = {}
        for service, network in (
            ("app", "frontend"),
            ("db", "backend"),
            ("redis", "backend"),
        ):
            identifier = docker(*compose, "ps", "-q", service).stdout.strip()
            info = json.loads(
                docker(
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Networks}}",
                    identifier,
                ).stdout
            )
            targets[service] = info[f"{PROJECT}_{network}"]["IPAddress"]
        stage = "positive-internal-tcp"
        code = (
            "import socket; targets="
            + repr(
                [
                    (targets["app"], 8000),
                    (targets["db"], 5432),
                    (targets["redis"], 6379),
                ]
            )
            + "; [socket.create_connection(t,timeout=3).close() for t in targets]; print('Three internal TCP positive controls passed')"
        )
        docker(*compose, "exec", "-T", "app", "python", "-c", code)
        env.update(
            APP_PROBE_IP=targets["app"],
            DB_PROBE_IP=targets["db"],
            REDIS_PROBE_IP=targets["redis"],
        )
        stage = "browser-gate"
        print(
            "M12.2: internal TCP positives passed; mandatory browser gate", flush=True
        )
        docker(*compose, "up", "-d", "browser-lab")
        identifier = docker(*compose, "ps", "--all", "-q", "browser-lab").stdout.strip()
        actual_networks = json.loads(
            docker(
                "inspect", "--format", "{{json .NetworkSettings.Networks}}", identifier
            ).stdout
        )
        assert set(actual_networks) == {f"{PROJECT}_browser-test"}
        runtime = json.loads(
            docker("inspect", "--format", "{{json .HostConfig}}", identifier).stdout
        )
        assert runtime["CapDrop"] == ["ALL"] and not runtime["CapAdd"]
        assert runtime["ReadonlyRootfs"] and not runtime["Privileged"]
        assert not runtime["PortBindings"]
        assert "no-new-privileges:true" in runtime["SecurityOpt"]
        assert len(runtime["Binds"]) == 1 and "/run/trust:ro" in runtime["Binds"][0]
        exit_code = int(docker("wait", identifier, timeout=180).stdout.strip())
        result = docker("logs", identifier)
        # Only the structured result is printed; never leak Playwright auth logs.
        records = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.startswith("{")
        ]
        assert records, "No browser gate result"
        report = records[-1]
        if exit_code != 0:
            for record in records[:-1]:
                if "attachment_decisions" in record:
                    print(json.dumps(record), flush=True)
        print(json.dumps(report), flush=True)
        assert exit_code == 0, "Mandatory browser prerequisites failed"
        assert (
            report["sandbox_verified"]
            and report["lab_tls_verified"]
            and report["xss_allowed"] is False
        )
        report["topology"] = {
            "project": PROJECT,
            "browser_networks": ["browser-test"],
            "internal": True,
            "published_ports": [],
            "browser_mounts": ["public-certificates-only"],
            "internal_tcp_positive_controls": True,
            "proxy_networks": ["ingress", "frontend", "browser-test"],
        }
    except Exception as error:
        print(
            json.dumps(
                {
                    "stage": stage,
                    "exception_type": type(error).__name__,
                    "verified": False,
                    "xss_allowed": False,
                }
            ),
            flush=True,
        )
        raise RuntimeError(
            "M12.2 prerequisites failed; sensitive diagnostics withheld"
        ) from None
    finally:
        if owned:
            # Project checked absent before creation; never target other volumes.
            docker(*compose, "down", "--volumes", "--timeout", "20", timeout=90)
            assert directory.resolve().parent == (root / "certs/local").resolve()
            if directory.exists():
                shutil.rmtree(directory)
            for kind, label in (("ps", "--all"), ("volume", "ls"), ("network", "ls")):
                assert not docker(
                    kind,
                    label,
                    "--filter",
                    f"label=com.docker.compose.project={PROJECT}",
                    "--quiet",
                ).stdout.strip(), "Disposable M12.2 resource remains after cleanup"
    report["cleanup"] = {
        "owned_resources_removed": True,
        "ephemeral_keys_removed": True,
    }
    if args.proof:
        args.proof.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("M12.2: all prerequisites verified; disposable resources cleaned", flush=True)


if __name__ == "__main__":
    main()
