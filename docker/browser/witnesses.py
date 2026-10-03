"""Local-only request witnesses; never authenticate or execute an XSS payload."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import Error


def verify_restrictions(browser, install_policy):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.server.server_port, self.path))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", forbidden + "/redirect-target")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Local M12 witness</h1>")

        def log_message(self, *_args):
            pass

    servers = [ThreadingHTTPServer(("127.0.0.1", 0), Handler) for _ in range(2)]
    allowed, forbidden = [
        f"http://127.0.0.1:{server.server_port}" for server in servers
    ]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # Positive local reachability, using a separate empty context.
        with browser.new_context(
            ignore_https_errors=False, service_workers="block", accept_downloads=False
        ) as positive:
            assert positive.new_page().goto(forbidden + "/positive").status == 200
        forbidden_hits = sum(port == servers[1].server_port for port, _ in hits)
        assert forbidden_hits == 1
        with browser.new_context(
            ignore_https_errors=False, service_workers="block", accept_downloads=False
        ) as context:
            install_policy(context, {("http", "127.0.0.1", servers[0].server_port)})
            page = context.new_page()
            assert page.goto(allowed + "/positive").status == 200
            for url in (forbidden + "/direct", allowed + "/redirect"):
                try:
                    page.goto(url)
                except Error as error:
                    assert "net::ERR_BLOCKED_BY_CLIENT" in str(error), str(error)
                else:
                    raise AssertionError("Forbidden destination unexpectedly reached")
            assert sum(port == servers[1].server_port for port, _ in hits) == 1
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
