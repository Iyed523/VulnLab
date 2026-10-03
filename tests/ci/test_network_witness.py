"""Infrastructure probe classification; independent of application behavior."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.preserved_protection


spec = importlib.util.spec_from_file_location(
    "verify_docker", Path(__file__).parents[2] / "scripts/ci/verify_docker.py"
)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


@pytest.mark.parametrize(
    "name", ["securevault", "../vulnlab-test", "vulnlab-test;other"]
)
def test_project_rejects_unrelated_or_malformed_names(name):
    with pytest.raises(ValueError):
        verify.compose_project(name)


def test_dedicated_project_is_accepted():
    assert verify.compose_project("vulnlab-m61-validation") == "vulnlab-m61-validation"


@pytest.mark.parametrize(
    "sid", ["S-1-1-0", "S-1-5-11", "S-1-5-7", "S-1-5-32-545", "S-1-5-32-546"]
)
def test_private_acl_rejects_broad_readers(sid):
    with pytest.raises(AssertionError, match="Broad Windows reader"):
        verify.assert_private_acl([{"sid": sid, "allow": True, "rights": 1}])


def test_private_acl_requires_evidence_and_accepts_system_access():
    with pytest.raises(AssertionError, match="Missing Windows ACL"):
        verify.assert_private_acl([])
    verify.assert_private_acl([{"sid": "S-1-5-18", "allow": True, "rights": 1}])


def result(outcome, code=10, stderr=""):
    return subprocess.CompletedProcess(
        [], code, "socket-ready\n" + json.dumps({"result": outcome}) + "\n", stderr
    )


@pytest.mark.parametrize(
    "outcome",
    [
        "connection-refused",
        "connection-timeout",
        "network-unreachable",
        "host-unreachable",
    ],
)
def test_expected_connection_failure(outcome):
    assert verify.classify_witness_result(result(outcome), "db") == outcome


def test_success_fails_blocking_check():
    with pytest.raises(AssertionError, match="reachable; blocking failed"):
        verify.classify_witness_result(result("connected", 0), "app")


@pytest.mark.parametrize(
    "output",
    [
        subprocess.CompletedProcess([], 127, "", "python: not found"),
        subprocess.CompletedProcess([], 1, "", "SyntaxError"),
        subprocess.CompletedProcess([], 124, "socket-ready\n", ""),
        result("connection-refused", 1),
        result("connection-refused", 124),
        result("connection-refused", 10, "execution error"),
        result("unexpected"),
        subprocess.CompletedProcess([], 10, "socket-ready\ninvalid json", ""),
    ],
)
def test_execution_errors_never_prove_denial(output):
    with pytest.raises(AssertionError):
        verify.classify_witness_result(output, "redis")


@pytest.mark.parametrize(
    "error, message",
    [
        (subprocess.TimeoutExpired("docker", 15), "global process timeout"),
        (FileNotFoundError("docker"), "tool execution failed"),
    ],
)
def test_process_errors_are_explicit(monkeypatch, error, message):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(verify.subprocess, "run", fail)
    with pytest.raises(AssertionError, match=message):
        verify.execute_probe(["docker"], "app")


@pytest.mark.parametrize(
    "failure, expected",
    [
        ("None", "connected"),
        ("ConnectionRefusedError(errno.ECONNREFUSED, 'refused')", "connection-refused"),
        ("TimeoutError('connect deadline')", "connection-timeout"),
        ("OSError(errno.ENETUNREACH, 'unreachable')", "network-unreachable"),
        ("OSError(errno.EHOSTUNREACH, 'unreachable')", "host-unreachable"),
        ("OSError(errno.EACCES, 'execution error')", None),
    ],
)
def test_actual_probe_protocol(failure, expected):
    # Exercise the shipped probe with injected socket outcomes, without a third party.
    setup = f"""
import errno
import socket
from contextlib import nullcontext
def connect(*args, **kwargs):
    failure = {failure}
    if failure is not None:
        raise failure
    return nullcontext()
socket.create_connection = connect
"""
    output = subprocess.run(
        [sys.executable, "-c", setup + verify.NETWORK_PROBE, "127.0.0.1"],
        text=True,
        capture_output=True,
        timeout=5,
    )
    if expected is None or expected == "connected":
        with pytest.raises(AssertionError):
            verify.classify_witness_result(output, "app")
    else:
        assert verify.classify_witness_result(output, "app") == expected
