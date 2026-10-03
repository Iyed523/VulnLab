"""Local-only request witnesses; never authenticate or execute an XSS payload."""

import base64
import faulthandler
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.async_api import Error


async def verify_restrictions(browser, install_policy):
    faulthandler.dump_traceback_later(30, exit=True)
    hits = []
    websocket_hits = []

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def do_GET(self):
            if self.headers.get("Upgrade", "").lower() == "websocket":
                websocket_hits.append(self.server.server_port)
                key = self.headers["Sec-WebSocket-Key"]
                accept = base64.b64encode(
                    hashlib.sha1(
                        (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode(),
                        usedforsecurity=False,
                    ).digest()
                ).decode()
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                self.wfile.flush()
                self.connection.settimeout(2)
                try:
                    self.connection.recv(1024)
                except TimeoutError:
                    pass
                return
            hits.append((self.server.server_port, self.path))
            if self.path in {"/relative", "/chain", "/redirect"}:
                self.send_response(302)
                locations = {
                    "/relative": "/positive",
                    "/chain": "/redirect",
                    "/redirect": forbidden + "/redirect-target",
                }
                self.send_header("Location", locations[self.path])
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
        async with await browser.new_context(
            ignore_https_errors=False, service_workers="block", accept_downloads=False
        ) as positive:
            print("Witness: positive HTTP/WebSocket", flush=True)
            page = await positive.new_page()
            assert (await page.goto(forbidden + "/positive")).status == 200
            result = await page.evaluate(
                """url => new Promise((resolve, reject) => {
                    const socket = new WebSocket(url);
                    socket.onopen = () => { socket.close(); resolve('opened'); };
                    socket.onerror = () => reject(new Error('Positive WebSocket failed'));
                    setTimeout(() => reject(new Error('WebSocket deadline')), 5000);
                })""",
                forbidden.replace("http:", "ws:") + "/ws-positive",
            )
            assert result == "opened"
        forbidden_hits = sum(port == servers[1].server_port for port, _ in hits)
        assert (servers[1].server_port, "/positive") in hits
        assert websocket_hits == [servers[1].server_port]
        async with await browser.new_context(
            ignore_https_errors=False, service_workers="block", accept_downloads=False
        ) as context:
            print("Witness: allowed HTTP/relative redirect", flush=True)
            await install_policy(
                context, {("http", "127.0.0.1", servers[0].server_port)}
            )
            page = await context.new_page()
            assert (await page.goto(allowed + "/positive")).status == 200
            assert (await page.goto(allowed + "/relative")).status == 200
            for url in (
                forbidden + "/direct",
                allowed + "/redirect",
                allowed + "/chain",
            ):
                print("Witness: negative HTTP", flush=True)
                negative = await context.new_page()
                try:
                    await negative.goto(url)
                except Error as error:
                    assert "net::ERR_BLOCKED_BY_CLIENT" in str(error), str(error)
                else:
                    raise AssertionError("Forbidden destination unexpectedly reached")
                finally:
                    # The pending Chromium error-document navigation must not race
                    # another assertion. Each denied navigation owns its empty page.
                    await negative.close()
            # Navigate to an allowed page before the local WebSocket test.
            result = await page.evaluate(
                """url => new Promise((resolve, reject) => {
                    const socket = new WebSocket(url);
                    socket.onclose = () => resolve('closed');
                    socket.onerror = () => resolve('error');
                    setTimeout(() => reject(new Error('WebSocket deadline')), 5000);
                })""",
                forbidden.replace("http:", "ws:") + "/ws-forbidden",
            )
            print("Witness: WebSocket closed", flush=True)
            assert result in {"closed", "error"}
            assert websocket_hits == [servers[1].server_port]
            assert (
                sum(port == servers[1].server_port for port, _ in hits)
                == forbidden_hits
            )
            return {
                "positive_http": True,
                "positive_websocket": True,
                "allowed_http_and_relative_redirect": True,
                "direct_denied": True,
                "redirect_denied": True,
                "redirect_chain_denied": True,
                "websocket_denied": True,
                "forbidden_http_requests_after_filter": 0,
                "forbidden_websocket_handshakes_after_filter": 0,
            }
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        faulthandler.cancel_dump_traceback_later()
