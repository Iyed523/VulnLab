"""Contrôles du laboratoire local du runner, sans sonde extérieure."""

import json
import subprocess
import urllib.error
import urllib.request

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


def main():
    expected = {
        "proxy": {"vulnlab-vulnerable_frontend"},
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
        assert not host["Privileged"], service
        assert host["ReadonlyRootfs"], service
        assert "no-new-privileges" in " ".join(host["SecurityOpt"]), service
        assert set(info["NetworkSettings"]["Networks"]) == networks, service
        ports = info["NetworkSettings"]["Ports"]
        published = {port: bindings for port, bindings in ports.items() if bindings}
        if service == "proxy":
            assert published == {
                "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]
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
        print(f"{service}: healthy, non-root, expected networks and ports")

    for name in {network for values in expected.values() for network in values}:
        network = json.loads(run(["docker", "network", "inspect", name]))[0]
        assert network["Internal"], name
        assert network["Labels"]["com.docker.compose.project"] == "vulnlab-vulnerable"

    volume = json.loads(
        run(["docker", "volume", "inspect", "vulnlab-vulnerable_pgdata"])
    )[0]
    assert volume["Labels"]["com.docker.compose.project"] == "vulnlab-vulnerable"
    with urllib.request.urlopen("http://127.0.0.1:8080/healthz", timeout=5) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok"}
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/missing", timeout=5)
    except urllib.error.HTTPError as response:
        assert response.code == 404
        body = response.read().decode()
        assert not any(
            value in body for value in ("Traceback", "Debugger", "vulnlab_vulnerable")
        )
    else:
        raise AssertionError("Unknown route must return 404")

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
    print("HTTP proxy, isolated resources, SQL role and internal TCP checks passed")


if __name__ == "__main__":
    main()
