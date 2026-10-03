"""Contrôles du laboratoire local du runner, sans sonde extérieure."""

import json
import subprocess
import time
from pathlib import Path

PROBE_IMAGE = "python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26"

# Only socket failures explicitly handled here can produce a denial result.
NETWORK_PROBE = r"""
import errno
import json
import socket
import sys

print("socket-ready", flush=True)
try:
    with socket.create_connection((sys.argv[1], 8088), timeout=2):
        result = "connected"
except TimeoutError:
    result = "connection-timeout"
except OSError as error:
    expected = {
        errno.ECONNREFUSED: "connection-refused",
        errno.ENETUNREACH: "network-unreachable",
        errno.EHOSTUNREACH: "host-unreachable",
    }
    if error.errno not in expected:
        raise
    result = expected[error.errno]
print(json.dumps({"result": result}))
sys.exit(0 if result == "connected" else 10)
"""


COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    ".env.example",
    "-f",
    "compose.vulnerable.yaml",
]


def run(args, *, stdin=None):
    return subprocess.run(
        args, input=stdin, text=True, capture_output=True, check=True, timeout=30
    ).stdout.strip()


def execute_probe(command, service):
    try:
        return subprocess.run(command, text=True, capture_output=True, timeout=15)
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            f"{service}: global process timeout; no network denial proven"
        ) from error
    except OSError as error:
        raise AssertionError(f"{service}: probe tool execution failed") from error


def classify_witness_result(result, service):
    """Reject execution errors even when their exit code resembles a denial."""
    lines = result.stdout.splitlines()
    if result.stderr or len(lines) != 2 or lines[0] != "socket-ready":
        raise AssertionError(f"{service}: probe/tool error or invalid output")
    try:
        payload = json.loads(lines[1])
    except ValueError as error:
        raise AssertionError(f"{service}: invalid probe result") from error
    if payload == {"result": "connected"} and result.returncode == 0:
        raise AssertionError(f"{service}: local witness reachable; blocking failed")
    expected = (
        "connection-refused",
        "connection-timeout",
        "network-unreachable",
        "host-unreachable",
    )
    for outcome in expected:
        if payload == {"result": outcome} and result.returncode == 10:
            return outcome
    raise AssertionError(f"{service}: unexpected probe result/code; no denial proven")


def verify_network_witness():
    """Témoin dédié joignable du proxy ; aucun tiers ne sert de cible."""
    image = PROBE_IMAGE
    container_id = run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "vulnlab-vulnerable-m4-witness",
            "--label",
            "vulnlab.m4.witness=true",
            "--network",
            "vulnlab-vulnerable_ingress",
            "--user",
            "65534:65534",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            "64m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "32",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=1m",
            image,
            "python",
            "-m",
            "http.server",
            "8088",
            "--directory",
            "/tmp",
        ]
    )
    try:
        info = json.loads(run(["docker", "inspect", container_id]))[0]
        address = info["NetworkSettings"]["Networks"]["vulnlab-vulnerable_ingress"][
            "IPAddress"
        ]
        run([*COMPOSE, "exec", "-T", "proxy", "sh", "-c", "command -v wget"])
        for _attempt in range(10):
            result = subprocess.run(
                [
                    *COMPOSE,
                    "exec",
                    "-T",
                    "proxy",
                    "wget",
                    "-q",
                    "-T",
                    "2",
                    "-O",
                    "-",
                    f"http://{address}:8088/",
                ],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("Positive control cannot reach local witness")
        for service in ("app", "db", "redis"):
            target = run([*COMPOSE, "ps", "-q", service])
            assert target, f"Missing container: {service}"
            # Reuse the pinned witness image, without modifying service images.
            probe = run(
                [
                    "docker",
                    "create",
                    "--network",
                    f"container:{target}",
                    "--user",
                    "65534:65534",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--memory",
                    "64m",
                    "--cpus",
                    "0.5",
                    "--pids-limit",
                    "32",
                    PROBE_IMAGE,
                    "python",
                    "-c",
                    NETWORK_PROBE,
                    address,
                ]
            )
            try:
                result = execute_probe(["docker", "start", "-a", probe], service)
                outcome = classify_witness_result(result, service)
                print(f"Witness {service}: socket available; {outcome}")
            finally:
                run(["docker", "rm", "-f", probe])
        print(
            "Witness: positive proxy access; app/db/redis denied. Proxy egress remains possible."
        )
    finally:
        run(["docker", "rm", "-f", container_id])


def main():
    expected = {
        "proxy": {"vulnlab-vulnerable_ingress", "vulnlab-vulnerable_frontend"},
        "app": {"vulnlab-vulnerable_frontend", "vulnlab-vulnerable_backend"},
        "db": {"vulnlab-vulnerable_backend"},
        "redis": {"vulnlab-vulnerable_backend"},
    }
    for service, networks in expected.items():
        container_id = run([*COMPOSE, "ps", "-q", service])
        assert container_id, f"Missing container: {service}"
        info = json.loads(run(["docker", "inspect", container_id]))[0]
        assert info["State"]["Health"]["Status"] == "healthy", service
        assert info["State"]["Running"], service
        host = info["HostConfig"]
        if service == "app":
            environment = dict(value.split("=", 1) for value in info["Config"]["Env"])
            assert environment.get("DB_USER") == "vulnlab_app"
            assert not any(
                key in environment
                for key in (
                    "MIGRATION_DB_PASSWORD",
                    "POSTGRES_PASSWORD",
                    "APP_DB_PASSWORD",
                )
            ), "Maintenance credentials in application environment"
            assert "vulnlab_migrate" not in environment.values()
        assert not host["Privileged"], service
        assert host["ReadonlyRootfs"], service
        assert "no-new-privileges" in " ".join(host["SecurityOpt"]), service
        assert set(info["NetworkSettings"]["Networks"]) == networks, service
        ports = info["NetworkSettings"]["Ports"]
        published = {port: bindings for port, bindings in ports.items() if bindings}
        if service == "proxy":
            assert published == {
                "8443/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8443"}]
            }, published
        else:
            assert not published, service
        uid = run(
            [
                *COMPOSE,
                "exec",
                "-T",
                service,
                "sh",
                "-c",
                "awk '/^Uid:/{print $2}' /proc/1/status",
            ]
        )
        assert int(uid) > 0, f"Root main process: {service}"
        caps = run(
            [
                *COMPOSE,
                "exec",
                "-T",
                service,
                "sh",
                "-c",
                "awk '/^CapEff:/{print $2}' /proc/1/status",
            ]
        )
        assert int(caps, 16) == 0, f"Effective capabilities: {service}"
        temporary = "/data" if service == "redis" else "/tmp"
        run(
            [
                *COMPOSE,
                "exec",
                "-T",
                service,
                "sh",
                "-c",
                f"if touch /m4-write-probe 2>/dev/null; then rm /m4-write-probe; exit 1; fi; "
                f"touch {temporary}/m4-write-probe && rm {temporary}/m4-write-probe",
            ]
        )
        if service == "proxy":
            proxy_info = info
        print(
            f"{service}: healthy, non-root, no effective capabilities, writes limited"
        )

    for name in {network for values in expected.values() for network in values}:
        network = json.loads(run(["docker", "network", "inspect", name]))[0]
        assert network["Internal"] == (name != "vulnlab-vulnerable_ingress"), name
        assert network["Labels"]["com.docker.compose.project"] == "vulnlab-vulnerable"

    volume = json.loads(
        run(["docker", "volume", "inspect", "vulnlab-vulnerable_pgdata"])
    )[0]
    assert volume["Labels"]["com.docker.compose.project"] == "vulnlab-vulnerable"

    def https(path, host="vulnerable.vulnlab.test", headers=()):
        output = run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--noproxy",
                "*",
                "--max-time",
                "5",
                "--cacert",
                "certs/local/vulnerable/server.crt",
                "--resolve",
                f"{host}:8443:127.0.0.1",
                *headers,
                "--write-out",
                "\n%{http_code}",
                f"https://{host}:8443{path}",
            ]
        )
        body, status = output.rsplit("\n", 1)
        return body, int(status)

    body, status = https("/healthz")
    assert status == 200 and json.loads(body) == {"status": "ok"}
    body, status = https("/missing")
    assert status == 404
    assert not any(
        value in body for value in ("Traceback", "Debugger", "vulnlab_vulnerable")
    )
    _, status = https("/healthz", headers=("-H", "Host: unknown.vulnlab.test"))
    assert status == 421, "Unknown HTTP Host accepted"
    for hostname in ("unknown.vulnlab.test", "secure.vulnlab.test"):
        rejected = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--noproxy",
                "*",
                "--max-time",
                "5",
                "--cacert",
                "certs/local/vulnerable/server.crt",
                "--resolve",
                f"{hostname}:8443:127.0.0.1",
                f"https://{hostname}:8443/healthz",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert rejected.returncode == 35, f"Unexpected SNI result: {hostname}"
    plain = run(
        [
            "curl",
            "--silent",
            "--noproxy",
            "*",
            "--max-time",
            "5",
            "--write-out",
            "\n%{http_code}",
            "http://127.0.0.1:8443/healthz",
        ]
    )
    assert plain.rsplit("\n", 1)[1] == "400", "Plain HTTP served on TLS port"

    tls_mount = next(
        m for m in proxy_info["Mounts"] if m["Destination"] == "/etc/nginx/tls"
    )
    assert not tls_mount["RW"]
    mode = run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "proxy",
            "stat",
            "-c",
            "%a",
            "/etc/nginx/tls/server.key",
        ]
    )
    assert mode == "640", "Private key permissions too broad"
    run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "proxy",
            "sh",
            "-c",
            "test -r /etc/nginx/tls/server.key && test ! -w /etc/nginx/tls/server.key",
        ]
    )
    assert Path("certs/local/vulnerable/server.key").stat().st_mode & 0o007 == 0

    query = (
        "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname = 'vulnlab_app';"
    )
    result = run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h 127.0.0.1 -U "$POSTGRES_USER" '
            '-d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tA',
        ],
        stdin=query,
    )
    assert result == "vulnlab_app|f|f|f|f|f", "Unexpected SQL privileges"
    result = run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'PGPASSWORD="$APP_DB_PASSWORD" exec psql -h 127.0.0.1 -U vulnlab_app '
            '-d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tA',
        ],
        stdin="SELECT current_user;",
    )
    assert result == "vulnlab_app", "Application SQL login failed"
    run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "app",
            "python",
            "-c",
            "import socket; [socket.create_connection((h,p),timeout=3).close() "
            "for h,p in [('db',5432),('redis',6379)]]",
        ]
    )
    verify_network_witness()
    print("Verified HTTPS, expected hosts, infrastructure and local network witness")


if __name__ == "__main__":
    main()
