"""Preparation-only checks: no browser execution and no XSS payload."""

import asyncio
import errno
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.preserved_protection

spec = importlib.util.spec_from_file_location(
    "browser_policy", Path(__file__).parents[2] / "docker/browser/network_policy.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
ALLOWED = {("https", "vulnerable.vulnlab.test", 8443)}


@pytest.mark.parametrize(
    "path", ["/tickets", "/login?next=%2Ftickets", "/static/a.css"]
)
def test_lab_origin_allowed(path):
    assert policy.permitted("https://vulnerable.vulnlab.test:8443" + path, ALLOWED)


@pytest.mark.parametrize(
    "url",
    [
        "http://vulnerable.vulnlab.test:8443/tickets",
        "https://vulnerable.vulnlab.test/tickets",
        "https://forbidden.vulnlab.test:8443/",
        "https://vulnerable.vulnlab.test.forbidden.test:8443/",
        "https://vulnerable.vulnlab.test:8443@forbidden.test/",
        "https://user@vulnerable.vulnlab.test:8443/",
        "https://vulnerable.vulnlab.test:invalid/",
        "https://vulnerable.vulnlab.test:8443\\@forbidden.test/",
        "https://vulnerable.vulnlab.test:8443/\n",
        "file:///tmp/private",
        "data:text/plain,local",
        "ws://vulnerable.vulnlab.test:8443/",
        "https://[invalid/",
    ],
)
def test_other_destinations_and_malformed_urls_denied(url):
    assert not policy.permitted(url, ALLOWED)


def test_relative_redirect_preserves_authorized_origin():
    assert (
        policy.redirect_target(
            "https://vulnerable.vulnlab.test:8443/login", "/tickets", ALLOWED
        )
        == "https://vulnerable.vulnlab.test:8443/tickets"
    )


@pytest.mark.parametrize(
    "location",
    [
        "//forbidden.vulnlab.test:8443/",
        "https://forbidden.vulnlab.test/",
        "file:///tmp/a",
    ],
)
def test_redirect_is_rejected_before_following(location):
    with pytest.raises(ValueError, match="not authorized"):
        policy.redirect_target(
            "https://vulnerable.vulnlab.test:8443/a", location, ALLOWED
        )


class Context:
    async def route(self, pattern, callback):
        self.callback = callback

    async def route_web_socket(self, pattern, callback):
        self.websocket_callback = callback


class Response:
    def __init__(self, status, location=None):
        self.status = status
        self.headers = {} if location is None else {"location": location}
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class Route:
    def __init__(self, url, responses, method="GET", body=None):
        async def all_headers(_request):
            return {
                "cookie": "fictitious-old-session",
                "content-type": "application/x-www-form-urlencoded",
                "content-length": str(len(body or b"")),
            }

        self.request = type(
            "Request",
            (),
            {
                "url": url,
                "method": method,
                "post_data_buffer": body,
                "all_headers": all_headers,
            },
        )()
        self.responses = iter(responses)
        self.calls = []
        self.aborted = False
        self.fulfilled = False

    async def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)

    async def abort(self, reason):
        assert reason == "blockedbyclient"
        self.aborted = True

    async def fulfill(self, response):
        assert response.status == 200
        self.fulfilled = True


def run_route(route):
    async def run():
        context = Context()
        await policy.install_policy(context, ALLOWED)
        await context.callback(route)

    asyncio.run(run())


def test_forbidden_request_never_fetches():
    route = Route("https://forbidden.vulnlab.test/", [])
    run_route(route)
    assert route.aborted and not route.fulfilled and not route.calls


def test_redirect_chain_checked_at_every_hop_before_fetch():
    responses = [
        Response(302, "/second"),
        Response(307, "https://forbidden.vulnlab.test/"),
    ]
    route = Route("https://vulnerable.vulnlab.test:8443/first", responses)
    run_route(route)
    assert route.aborted and not route.fulfilled
    assert [call["url"] for call in route.calls] == [
        "https://vulnerable.vulnlab.test:8443/first",
        "https://vulnerable.vulnlab.test:8443/second",
    ]
    assert all(call["max_redirects"] == 0 for call in route.calls)
    assert all(response.disposed for response in responses)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_authorized_redirect_method_and_body_semantics(status):
    route = Route(
        "https://vulnerable.vulnlab.test:8443/first",
        [Response(status, "/second"), Response(200)],
        "POST",
        b"fictitious=local",
    )
    run_route(route)
    assert route.fulfilled and not route.aborted
    expected = ("POST", b"fictitious=local") if status in {307, 308} else ("GET", b"")
    assert (route.calls[1]["method"], route.calls[1]["post_data"]) == expected
    assert all("cookie" not in call["headers"] for call in route.calls)
    if status not in {307, 308}:
        assert "content-length" not in route.calls[1]["headers"]
        assert "content-type" not in route.calls[1]["headers"]


def test_redirect_loop_fails_closed():
    route = Route(
        "https://vulnerable.vulnlab.test:8443/a",
        [Response(302, "/a") for _ in range(10)],
    )
    run_route(route)
    assert route.aborted and not route.fulfilled and len(route.calls) == 10


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_303_preserves_get_or_head_and_explicitly_empty_body(method):
    route = Route(
        "https://vulnerable.vulnlab.test:8443/first",
        [Response(303, "/second"), Response(200)],
        method,
    )
    run_route(route)
    assert route.calls[1]["method"] == method
    assert route.calls[1]["post_data"] == b""
    assert "cookie" not in route.calls[1]["headers"]


def test_redirect_without_location_fails_closed():
    route = Route("https://vulnerable.vulnlab.test:8443/a", [Response(302)])
    run_route(route)
    assert route.aborted and not route.fulfilled


def test_unknown_fetch_error_is_not_success_or_network_blockage():
    class BrokenRoute(Route):
        async def fetch(self, **kwargs):
            raise RuntimeError("tool failure")

    route = BrokenRoute("https://vulnerable.vulnlab.test:8443/a", [])
    with pytest.raises(RuntimeError, match="tool failure"):
        run_route(route)
    assert not route.aborted and not route.fulfilled


result_spec = importlib.util.spec_from_file_location(
    "sandbox_result", Path(__file__).parents[2] / "docker/browser/sandbox_result.py"
)
result = importlib.util.module_from_spec(result_spec)
result_spec.loader.exec_module(result)


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("FATAL: No usable sandbox!", "no-usable-sandbox"),
        ('Check failed: sys_chroot("/proc/self/fdinfo/") == 0', "zygote-chroot-denied"),
    ],
)
def test_explicit_sandbox_incompatibility_classified(message, reason):
    assert result.classify_launch_error(message) == reason


@pytest.mark.parametrize(
    "message",
    ["executable missing", "SyntaxError", "timeout", "unexpected launch exit"],
)
def test_tool_execution_errors_are_never_sandbox_validation(message):
    with pytest.raises(RuntimeError, match="Unexpected browser execution error"):
        result.classify_launch_error(message)


SANDBOX_ROWS = [
    ["Layer 1 Sandbox", "Namespace"],
    ["PID namespaces", "Yes"],
    ["Network namespaces", "Yes"],
    ["Seccomp-BPF sandbox", "Yes"],
    ["Seccomp-BPF sandbox supports TSYNC", "Yes"],
]


def test_exact_verified_sandbox_layers_accepted():
    assert result.verify_sandbox_rows(SANDBOX_ROWS) == dict(SANDBOX_ROWS)


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("missing", [False, True])
def test_unverified_sandbox_layer_never_accepted(index, missing):
    rows = [row.copy() for row in SANDBOX_ROWS]
    if missing:
        del rows[index]
    else:
        rows[index][1] = "No"
    with pytest.raises(RuntimeError, match="Unverified Chromium sandbox prerequisite"):
        result.verify_sandbox_rows(rows)


def test_seccomp_adaptation_changes_only_chroot_condition_and_comment():
    directory = Path(__file__).parents[2] / "docker/browser"
    original = json.loads((directory / "seccomp.json").read_text())
    adapted = json.loads((directory / "seccomp-chroot.json").read_text())
    expected = json.loads(json.dumps(original))
    rules = [rule for rule in expected["syscalls"] if rule["names"] == ["chroot"]]
    assert len(rules) == 1
    assert rules[0]["includes"] == {"caps": ["CAP_SYS_CHROOT"]}
    assert rules[0]["action"] == "SCMP_ACT_ALLOW"
    rules[0]["includes"] = {}
    rules[0]["comment"] = (
        "M12.1: allow chroot syscall; kernel capability checks remain in the calling "
        "user namespace. No container capability is added."
    )
    assert adapted == expected


def test_websocket_policy_closes_without_connecting_to_server():
    context = Context()
    asyncio.run(policy.install_policy(context, ALLOWED))

    class Socket:
        closed = False

        async def close(self):
            self.closed = True

        async def connect_to_server(self):
            raise AssertionError("Forbidden WebSocket connected")

    socket = Socket()
    asyncio.run(context.websocket_callback(socket))
    assert socket.closed


tls_spec = importlib.util.spec_from_file_location(
    "tls_result", Path(__file__).parents[2] / "docker/browser/tls_result.py"
)
tls = importlib.util.module_from_spec(tls_spec)
tls_spec.loader.exec_module(tls)


@pytest.mark.parametrize(
    ("engine", "message", "expected"),
    [
        ("chromium", "net::ERR_CERT_AUTHORITY_INVALID", "authority"),
        ("chromium", "net::ERR_CERT_COMMON_NAME_INVALID", "name"),
        ("mediator", "self-signed certificate in certificate chain", "authority"),
        ("mediator", "unable to verify the first certificate", "authority"),
        ("mediator", "unable to get local issuer certificate", "authority"),
        ("mediator", "Hostname/IP does not match certificate's altnames", "name"),
    ],
)
def test_tls_failure_requires_explicit_engine_and_cause(engine, message, expected):
    assert tls.tls_failure(message, engine) == expected


@pytest.mark.parametrize("engine", ["chromium", "mediator"])
@pytest.mark.parametrize(
    "message",
    [
        "ENOTFOUND",
        "net::ERR_NAME_NOT_RESOLVED",
        "timeout",
        "SyntaxError",
        "tool missing",
        "HTTP 421",
        "TLS handshake closed",
    ],
)
def test_dns_timeout_execution_http_and_sni_are_not_certificate_evidence(
    engine, message
):
    with pytest.raises(RuntimeError, match="prerequisite unverified"):
        tls.tls_failure(message, engine)


def test_tls_ambiguity_fails_closed():
    with pytest.raises(RuntimeError, match="prerequisite unverified"):
        tls.tls_failure(
            "net::ERR_CERT_AUTHORITY_INVALID net::ERR_CERT_COMMON_NAME_INVALID",
            "chromium",
        )


def test_mediator_does_not_override_context_tls_settings():
    route = Route("https://vulnerable.vulnlab.test:8443/a", [Response(200)])
    run_route(route)
    assert "ignore_https_errors" not in route.calls[0]


def test_mediator_failure_is_retained_and_never_fulfilled():
    class BrokenRoute(Route):
        async def fetch(self, **kwargs):
            raise RuntimeError("unable to verify the first certificate")

        async def abort(self, reason):
            assert reason == "failed"
            self.aborted = True

    ctx = Context()
    errors = []
    asyncio.run(policy.install_policy(ctx, ALLOWED, errors))
    route = BrokenRoute("https://vulnerable.vulnlab.test:8443/a", [])
    asyncio.run(ctx.callback(route))
    assert (
        len(errors) == 1 and tls.tls_failure(str(errors[0]), "mediator") == "authority"
    )
    assert route.aborted and not route.fulfilled


network_spec = importlib.util.spec_from_file_location(
    "network_result", Path(__file__).parents[2] / "docker/browser/network_result.py"
)
network = importlib.util.module_from_spec(network_spec)
network_spec.loader.exec_module(network)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TimeoutError(), "connection-timeout"),
        (ConnectionRefusedError(errno.ECONNREFUSED, "refused"), "connection-refused"),
        (OSError(errno.ENETUNREACH, "unreachable"), "network-unreachable"),
        (OSError(errno.EHOSTUNREACH, "unreachable"), "host-unreachable"),
    ],
)
def test_only_explicit_socket_refusals_are_network_evidence(error, reason):
    assert network.connection_refusal(error) == reason


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(),
        PermissionError(),
        OSError(errno.EINVAL, "invalid"),
        RuntimeError("tool failed"),
    ],
)
def test_unexpected_socket_tool_error_is_never_isolation(error):
    with pytest.raises(RuntimeError, match="isolation unverified"):
        network.connection_refusal(error)


@pytest.mark.parametrize(
    "url",
    [
        "http://vulnerable.vulnlab.test:8443/",
        "https://user@vulnerable.vulnlab.test:8443/",
        "https://forbidden.vulnlab.test:8443/",
    ],
)
def test_raw_navigation_refused_before_browser_normalization(url):
    class Page:
        async def goto(self, *_args, **_kwargs):
            raise AssertionError("Forbidden navigation reached the browser")

    with pytest.raises(ValueError, match="not authorized"):
        asyncio.run(policy.navigate(Page(), url, ALLOWED))


@pytest.mark.parametrize(
    "navigation", ["Download is starting", "net::ERR_ABORTED", "net::ERR_FAILED"]
)
def test_download_requires_real_event_and_exact_accept_downloads_failure(navigation):
    assert (
        network.download_refusal(
            navigation,
            "Pass 'accept_downloads=True' when you are creating your browser context.",
        )
        == "accept-downloads-disabled"
    )


@pytest.mark.parametrize(
    ("navigation", "failure"),
    [
        ("net::ERR_FAILED", None),
        ("net::ERR_FAILED", "tool failed"),
        ("net::ERR_ABORTED", "canceled"),
        (
            "timeout",
            "Pass 'accept_downloads=True' when you are creating your browser context.",
        ),
    ],
)
def test_generic_errors_and_cancellation_never_prove_download_block(
    navigation, failure
):
    with pytest.raises(RuntimeError, match="prerequisite unverified"):
        network.download_refusal(navigation, failure)


@pytest.mark.parametrize(
    "header",
    [
        "attachment; filename=local.txt",
        "ATTACHMENT",
        " attachment ; filename=local.txt",
    ],
)
def test_attachment_is_not_fulfilled_by_mediator(header):
    response = Response(200)
    response.headers["content-disposition"] = header
    route = Route("https://vulnerable.vulnlab.test:8443/file", [response])
    context = Context()
    decisions = []
    asyncio.run(policy.install_policy(context, ALLOWED, decisions=decisions))
    asyncio.run(context.callback(route))
    assert decisions == ["attachment-refused-before-fulfill"]
    assert route.aborted and not route.fulfilled and response.disposed
