"""Dedicated local HTTPS witnesses, no auth or sensitive request logging."""

import base64
import hashlib
import json
import ssl
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

hits = Counter()
lock = threading.Lock()


class TLSServer(ThreadingHTTPServer):
    """Handshake per client thread: idle preconnections cannot stall accept."""

    def finish_request(self, request, client_address):
        request.settimeout(3)
        try:
            with self.tls_context.wrap_socket(request, server_side=True) as tls:
                self.RequestHandlerClass(tls, client_address, self)
        except (ssl.SSLError, TimeoutError):
            # Certificate rejection and abandoned preconnections are expected
            # server-side events. They never classify a client test as success.
            request.close()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def do_GET(self):
        host = self.headers.get("Host", "").split(":")[0]
        if self.path == "/stats":
            with lock:
                body = json.dumps(dict(hits)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        with lock:
            hits[host] += 1
        if self.headers.get("Upgrade", "").lower() == "websocket":
            with lock:
                hits[host + ":ws"] += 1
            accept = base64.b64encode(
                hashlib.sha1(
                    (
                        self.headers["Sec-WebSocket-Key"]
                        + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                    ).encode(),
                    usedforsecurity=False,
                ).digest()
            ).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            try:
                self.connection.recv(1024)
            except TimeoutError:
                pass
            return
        redirects = {
            "/relative": "/positive",
            "/chain": "/redirect",
            "/redirect": "https://forbidden.vulnlab.test:8443/denied",
        }
        self.send_response(302 if self.path in redirects else 200)
        if self.path in redirects:
            self.send_header("Location", redirects[self.path])
        self.send_header("Content-Type", "text/html")
        if self.path in {"/download", "/download-mediated"}:
            self.send_header(
                "Content-Disposition", 'attachment; filename="local-test.txt"'
            )
        self.end_headers()
        self.wfile.write(b"<h1>Local M12.2 witness</h1>")

    def log_message(self, *_args):
        pass


def main():
    servers = []
    for port, name in (
        (8443, "good"),
        (8444, "untrusted"),
        (8445, "wrong"),
        (8446, None),
    ):
        server_type = TLSServer if name else ThreadingHTTPServer
        server = server_type(("0.0.0.0", port), Handler)
        server.daemon_threads = True
        if name:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(f"/run/witness/{name}.crt", f"/run/witness/{name}.key")
            server.tls_context = ctx
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print("Local TLS witnesses ready; no SNI or HTTP Host rejection", flush=True)
    try:
        threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
