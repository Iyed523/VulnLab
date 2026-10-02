"""One real local HTTPS flow; no cookie, token, password or response dump."""

import http.client
import re
import socket
import ssl
from http.cookies import SimpleCookie
from urllib.parse import urlencode

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
    status, body, _ = client.request("GET", "/tickets/new")
    assert status == 200
    status, _, headers = client.request(
        "POST",
        "/tickets/new",
        {
            "title": "<b>HTTPS private ticket</b>",
            "description": "<script>local fictitious text</script>",
            "csrf_token": token(body),
        },
    )
    assert status == 303
    path = headers["Location"]
    status, body, _ = client.request("GET", path)
    assert status == 200 and "&lt;b&gt;HTTPS private ticket&lt;/b&gt;" in body
    assert "&lt;script&gt;local fictitious text&lt;/script&gt;" in body
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
    status, body, _ = other.request("GET", "/tickets/new")
    assert status == 200
    other_token = token(body)
    assert other.request("GET", path)[0] == 404
    assert other.request("GET", path + "/edit")[0] == 404
    for suffix, data in [
        ("edit", {"title": "Denied", "description": "Local", "status": "closed"}),
        ("comments", {"content": "Denied"}),
        ("delete", {}),
    ]:
        assert (
            other.request(
                "POST", path + "/" + suffix, data | {"csrf_token": other_token}
            )[0]
            == 404
        )
    assert "HTTPS private ticket" not in other.request("GET", "/tickets")[1]
    status, _, other_headers = other.request(
        "POST",
        "/tickets/new",
        {
            "title": "Bob private marker",
            "description": "Local",
            "csrf_token": other_token,
        },
    )
    assert status == 303 and client.request("GET", other_headers["Location"])[0] == 404
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
    print(
        "HTTPS tickets: create/read/edit/comment/delete, escaping and two-user access denial verified; private values withheld."
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
                "username": "m6https",
                "display_name": "<b>HTTPS fictitious</b>",
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
            "username": "M6HTTPS",
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
    verify_tickets(client)
    assert client.request("GET", "/logout")[0] == 405
    status, body, _ = client.request("GET", "/account")
    assert status == 200 and "&lt;b&gt;HTTPS fictitious&lt;/b&gt;" in body
    assert "password_hash" not in body and "$argon2" not in body
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
    # Two successful logins consumed two of five attempts. Forged proxy chains
    # must not create new IP buckets; nginx replaces them with the actual peer.
    for index in range(3):
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
