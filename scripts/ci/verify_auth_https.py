"""One real local HTTPS flow; no cookie, token, password or response dump."""

import http.client
import json
import re
import socket
import ssl
from http.cookies import SimpleCookie
from urllib.parse import urlencode
from uuid import uuid4

HOST = "vulnerable.vulnlab.test"
BASE = f"https://{HOST}:8443"
COOKIE = "__Host-vulnlab-session"


class LocalHTTPS(http.client.HTTPSConnection):
    def connect(self):
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        self.sock = self._context.wrap_socket(connection, server_hostname=self.host)


class Client:
    def __init__(self):
        self.cookie = None
        self.context = ssl.create_default_context(
            cafile="certs/local/vulnerable/server.crt"
        )

    def request(self, method, path, data=None, forwarded=None):
        connection = LocalHTTPS(HOST, 8443, context=self.context, timeout=5)
        headers = {"Referer": BASE + path.split("?")[0]}
        if self.cookie:
            headers["Cookie"] = f"{COOKIE}={self.cookie}"
        if forwarded:
            headers.update(forwarded)
        body = None
        if data is not None:
            body = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            text = response.read().decode("utf-8")
            response_headers = dict(response.getheaders())
            raw_cookie = response.getheader("Set-Cookie")
            if raw_cookie:
                parsed = SimpleCookie(raw_cookie)
                if COOKIE in parsed:
                    self.cookie = parsed[COOKIE].value or None
            return status, text, response_headers
        finally:
            connection.close()


def token(body):
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    assert match, "CSRF field missing; contents withheld"
    return match.group(1)


def verify_tickets(client):
    marker = "VULN-003-" + uuid4().hex
    status, body, _ = client.request("GET", "/tickets/new")
    assert status == 200
    status, _, headers = client.request(
        "POST",
        "/tickets/new",
        {
            "title": f"<b>{marker}</b>",
            "description": f"<script>{marker} description</script>",
            "csrf_token": token(body),
        },
    )
    assert status == 303
    path = headers["Location"]
    status, body, _ = client.request("GET", path)
    assert status == 200 and f"&lt;b&gt;{marker}&lt;/b&gt;" in body
    assert f"&lt;script&gt;{marker} description&lt;/script&gt;" in body
    assert (
        client.request(
            "POST",
            path + "/comments",
            {"content": f"<b>{marker} comment</b>", "csrf_token": token(body)},
        )[0]
        == 303
    )
    assert Client().request("GET", path)[0] == 303
    invalid = Client()
    invalid.cookie = "invalid-fictitious-session"
    assert invalid.request("GET", path)[0] == 303
    other = Client()
    status, body, _ = other.request("GET", "/register")
    assert status == 200
    assert (
        other.request(
            "POST",
            "/register",
            {
                "username": "m7httpsbob",
                "display_name": "HTTPS Bob fictitious",
                "password": "demo-HTTPS-Bob-only!",
                "csrf_token": token(body),
            },
        )[0]
        == 303
    )
    status, body, _ = other.request("GET", "/login")
    assert status == 200
    assert (
        other.request(
            "POST",
            "/login",
            {
                "username": "m7httpsbob",
                "password": "demo-HTTPS-Bob-only!",
                "csrf_token": token(body),
            },
        )[0]
        == 303
    )
    disabled_probe = Client()
    status, probe_body, _ = disabled_probe.request("GET", "/login")
    assert status == 200
    assert (
        disabled_probe.request(
            "POST",
            "/login",
            {
                "username": "m7httpsbob",
                "password": "demo-HTTPS-Bob-only!",
                "csrf_token": token(probe_body),
            },
        )[0]
        == 303
    )
    status, body, _ = other.request("GET", "/tickets/new")
    assert status == 200
    other_token = token(body)
    detail_status, disclosed, _ = other.request("GET", path)
    assert (
        detail_status == 200
    )  # VULN-003: expected disclosure, not security validation.
    assert f"&lt;b&gt;{marker}&lt;/b&gt;" in disclosed
    assert f"&lt;script&gt;{marker} description&lt;/script&gt;" in disclosed
    assert f"&lt;b&gt;{marker} comment&lt;/b&gt;" in disclosed
    assert "&lt;b&gt;HTTPS Alice fictitious&lt;/b&gt;" in disclosed
    assert "Comments (1)" in disclosed and "Status: open" in disclosed
    assert re.search(r"— \d{4}-\d{2}-\d{2}", disclosed)
    other_token = token(
        disclosed
    )  # Visible form token still grants no write permission.
    assert other.request("HEAD", path)[0] == 404
    assert other.request("POST", path + "/delete", {})[0] == 400
    refused = {}
    assert other.request("GET", path + "/edit")[0] == 404
    for suffix, data in [
        ("edit", {"title": "Denied", "description": "Local", "status": "closed"}),
        ("comments", {"content": "Denied"}),
        ("delete", {}),
    ]:
        refused[suffix] = other.request(
            "POST", path + "/" + suffix, data | {"csrf_token": other_token}
        )[0]
        assert refused[suffix] == 404
    listing_status, listing, _ = other.request("GET", "/tickets")
    assert listing_status == 200 and marker not in listing
    assert "Total visible: 0" in listing
    status, unchanged, _ = client.request("GET", path)
    assert status == 200 and marker in unchanged and "Status: open" in unchanged
    assert "Comments (1)" in unchanged and "Denied" not in unchanged
    print(
        "VULN-003_PROOF "
        + json.dumps(
            {
                "classification": "intentional_weakness_observed",
                "ticket_path": path,
                "marker": marker,
                "bob_list_status": listing_status,
                "bob_list_contains_marker": False,
                "bob_detail_status": detail_status,
                "exposed": [
                    "title",
                    "description",
                    "status",
                    "comment_content",
                    "author_display_name",
                    "comment_created_at",
                    "comment_count",
                    "ticket_id_in_links",
                ],
                "bob_post_refusals": refused,
                "bob_edit_get": 404,
                "bob_head": 404,
                "visitor": 303,
                "invalid_session": 303,
                "csrf_missing": 400,
                "victim_data_unchanged": True,
            },
            sort_keys=True,
        )
    )
    status, _, other_headers = other.request(
        "POST",
        "/tickets/new",
        {
            "title": "Bob private marker",
            "description": "Local",
            "csrf_token": other_token,
        },
    )
    assert status == 303
    assert client.request("GET", other_headers["Location"])[0] == 200
    assert client.request("GET", other_headers["Location"] + "/edit")[0] == 404
    other.ticket_path = other_headers["Location"]
    status, body, _ = client.request("GET", path + "/edit")
    assert status == 200
    assert (
        client.request(
            "POST",
            path + "/edit",
            {
                "title": "Edited HTTPS ticket",
                "description": "Local",
                "status": "closed",
                "csrf_token": token(body),
            },
        )[0]
        == 303
    )
    status, body, _ = client.request("GET", path)
    assert status == 200 and "Edited HTTPS ticket" in body and "Status: closed" in body
    assert (
        client.request(
            "POST",
            path + "/comments",
            {"content": "<b>HTTPS comment</b>", "csrf_token": token(body)},
        )[0]
        == 303
    )
    status, body, _ = client.request("GET", path)
    assert status == 200 and "&lt;b&gt;HTTPS comment&lt;/b&gt;" in body
    assert client.request("GET", path + "/delete")[0] == 405
    assert client.request("POST", path + "/delete", {})[0] == 400
    assert (
        client.request("POST", path + "/delete", {"csrf_token": token(body)})[0] == 303
    )
    assert client.request("GET", path)[0] == 404
    assert other.request("GET", other_headers["Location"])[0] == 200
    status, create_body, _ = client.request("GET", "/tickets/new")
    assert status == 200
    status, _, retained = client.request(
        "POST",
        "/tickets/new",
        {
            "title": marker + " retained victim",
            "description": "Fictitious lifecycle guard",
            "csrf_token": token(create_body),
        },
    )
    assert status == 303
    other.victim_path = retained["Location"]
    assert other.request("GET", other.victim_path)[0] == 200
    print(
        "HTTPS VULN-003: cross-user GET disclosure observed; functional lifecycle, escaping and write refusals verified; sensitive values withheld."
    )
    return other, disabled_probe


def verify_accounts(client, other, disabled_probe):
    assert client.request("GET", "/admin/users")[0] == 403
    status, body, _ = client.request("GET", "/account/edit")
    assert status == 200
    assert (
        client.request("POST", "/account/edit", {"display_name": "Changed"})[0] == 400
    )
    assert (
        client.request(
            "POST",
            "/account/edit",
            {"display_name": "Changed", "role": "admin", "csrf_token": token(body)},
        )[0]
        == 400
    )
    status, _, headers = client.request(
        "POST",
        "/account/edit",
        {"display_name": "<b>M8 profile</b>", "csrf_token": token(body)},
    )
    assert status == 303 and headers["Location"] == "/account"
    assert "&lt;b&gt;M8 profile&lt;/b&gt;" in client.request("GET", "/account")[1]
    admin = Client()
    status, body, _ = admin.request("GET", "/login")
    assert status == 200
    assert (
        admin.request(
            "POST",
            "/login",
            {
                "username": "admin",
                "password": "demo-Admin-only!",
                "csrf_token": token(body),
            },
        )[0]
        == 303
    )
    status, body, _ = admin.request("GET", "/admin/users")
    assert status == 200
    for private in ("password_hash", "$argon2", "session_version", "_auth_version"):
        assert private not in body
    match = re.search(r'data-user-id="(-?\d+)" data-username="m7httpsbob"', body)
    assert match, "Fictitious test user not listed"
    target = match.group(1)
    csrf = token(body)
    old = other.cookie
    for action in ("deactivate", "activate"):
        path = f"/admin/users/{target}/{action}"
        assert admin.request("GET", path)[0] == 405
        assert admin.request("POST", path, {})[0] == 400
        status, _, headers = admin.request("POST", path, {"csrf_token": csrf})
        assert status == 303 and headers["Location"] == "/admin/users"
        if action == "deactivate":
            assert disabled_probe.request("GET", other.victim_path)[0] == 303
            # The original other SID receives no request during inactivity.
    # Re-enable before this session's next request: SQL version must still revoke it.
    assert other.request("GET", "/account/edit")[0] == 303 and other.cookie is None
    other.cookie = old
    assert other.request("GET", "/tickets")[0] == 303
    other.cookie = old
    assert other.request("GET", other.victim_path)[0] == 303
    assert (
        admin.request("POST", "/admin/users/-1003/deactivate", {"csrf_token": csrf})[0]
        == 403
    )
    print(
        "HTTPS M8: own profile, admin rights, status changes and durable SID revocation verified; private values withheld."
    )


def main():
    client = Client()
    assert client.request("GET", "/account")[0] == 303
    status, body, _ = client.request("GET", "/register")
    assert status == 200
    assert (
        client.request(
            "POST",
            "/register",
            {
                "username": "m11httpsalice",
                "display_name": "<b>HTTPS Alice fictitious</b>",
                "password": "demo-HTTPS-flow-only!",
                "csrf_token": token(body),
            },
        )[0]
        == 303
    )
    assert client.request("GET", "/account")[0] == 303
    status, body, _ = client.request("GET", "/login")
    assert status == 200
    old = client.cookie
    status, _, headers = client.request(
        "POST",
        "/login",
        {
            "username": "M11HTTPSALICE",
            "password": "demo-HTTPS-flow-only!",
            "csrf_token": token(body),
        },
    )
    assert status == 303 and headers["Location"] == "/account"
    assert client.cookie and client.cookie != old, "SID rotation failed"
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", client.cookie), "Opaque SID expected"
    cookie_header = headers["Set-Cookie"]
    assert all(
        item in cookie_header
        for item in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/")
    )
    assert "Domain=" not in cookie_header and "remember" not in cookie_header
    replay = Client()
    replay.cookie = old
    assert replay.request("GET", "/account")[0] == 303
    other, disabled_probe = verify_tickets(client)
    assert client.request("GET", "/logout")[0] == 405
    status, body, _ = client.request("GET", "/account")
    assert status == 200 and "&lt;b&gt;HTTPS Alice fictitious&lt;/b&gt;" in body
    assert "password_hash" not in body and "$argon2" not in body
    verify_accounts(client, other, disabled_probe)
    assert client.request("POST", "/logout", {})[0] == 400
    assert client.request("GET", "/account")[0] == 200
    authenticated = client.cookie
    assert client.request("POST", "/logout", {"csrf_token": token(body)})[0] == 303
    assert client.cookie is None
    replay.cookie = authenticated
    assert replay.request("GET", "/account")[0] == 303
    assert client.request("GET", "/login?next=https://example.invalid")[0] == 400
    status, body, _ = client.request("GET", "/login")
    assert status == 200
    csrf = token(body)
    # Four successful logins consumed four of five attempts. Forged proxy chains
    # must not create new IP buckets; nginx replaces them with the actual peer.
    for index in range(1):
        assert (
            client.request(
                "POST",
                "/login",
                {
                    "username": "unknown",
                    "password": "demo-wrong-password!",
                    "csrf_token": csrf,
                },
                {
                    "X-Forwarded-For": f"192.0.2.{index + 1}",
                    "X-Forwarded-Proto": "http",
                    "X-Forwarded-Host": "example.invalid",
                },
            )[0]
            == 401
        )
    assert (
        client.request(
            "POST",
            "/login",
            {
                "username": "unknown",
                "password": "demo-wrong-password!",
                "csrf_token": csrf,
            },
            {"X-Forwarded-For": "192.0.2.99"},
        )[0]
        == 429
    )
    print(
        "HTTPS auth: registration/login/account/logout, SID replays, CSRF, cookie and forged-header limiting verified; sensitive values withheld."
    )


if __name__ == "__main__":
    main()
