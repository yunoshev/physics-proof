"""A scripted fake Meta API server (stdlib http.server in a thread)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeMetaHandler(BaseHTTPRequestHandler):
    """Serves queued (status, headers, body) tuples; records requests."""

    script: list[tuple[int, dict[str, str], bytes]] = []
    requests: list[dict] = []

    def log_message(self, *args: object) -> None:
        pass

    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length else b""
        try:
            parsed = json.loads(raw_body) if raw_body else None
        except ValueError:
            parsed = None
        FakeMetaHandler.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers),
                "body": raw_body,
                "json": parsed,
            }
        )
        index = min(len(FakeMetaHandler.requests) - 1, len(FakeMetaHandler.script) - 1)
        status, headers, body = FakeMetaHandler.script[index]
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self._serve()

    def do_DELETE(self) -> None:
        self._serve()

    def do_GET(self) -> None:
        self._serve()


def start_fake_server(
    script: list[tuple[int, dict[str, str], bytes]],
) -> tuple[ThreadingHTTPServer, str]:
    """Start the fake server; returns (server, base_url). Caller must shut down."""
    FakeMetaHandler.script = list(script)
    FakeMetaHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMetaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"
