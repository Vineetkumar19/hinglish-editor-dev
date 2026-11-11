"""The desktop main process owns the session token; the renderer never sees it.

This protects the local HTTP service from unrelated web pages and other local
applications that do not possess the token. It is not a sandbox against malware
already running as this Windows user.
"""

import hmac
import os
from urllib.parse import urlsplit

from starlette.responses import JSONResponse


class LocalSessionAuth:
    def __init__(self, app):
        self.app = app
        self.token = os.environ.get("CORTANA_API_TOKEN", "")

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        headers = {}
        duplicate_security_header = False
        for key, value in scope.get("headers", []):
            if key in {b"authorization", b"host", b"origin"} and key in headers:
                duplicate_security_header = True
            headers[key] = value.decode("latin-1")

        error, status = None, 403
        try:
            hostname = urlsplit("//" + headers.get(b"host", "")).hostname
        except ValueError:
            hostname = None
        peer = (scope.get("client") or ("", 0))[0]
        if duplicate_security_header:
            error = "Duplicate security headers are not accepted."
        elif hostname not in {"127.0.0.1", "localhost", "::1"}:
            error = "Only a loopback host is accepted."
        elif peer not in {"127.0.0.1", "::1"}:
            error = "Only loopback clients are accepted."
        elif b"origin" in headers:
            # Browser access uses the narrow Electron IPC bridge instead.
            # Even Origin: null and localhost dev pages are not an exception.
            error = "Direct browser requests are not accepted. Use the desktop app."
        elif scope["type"] == "websocket":
            error = "WebSocket access is not enabled."
        elif scope["path"] == "/api/health" and scope["method"] == "GET":
            pass  # Minimal liveness only; no configuration or secrets.
        elif len(self.token) < 32:
            error, status = "Local authentication is not configured. Start Cortana from its desktop launcher.", 503
        elif not hmac.compare_digest(
            headers.get(b"authorization", "").encode("utf-8"), ("Bearer " + self.token).encode("utf-8")
        ):
            error, status = "Authentication required.", 401

        if error:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4403})
            else:
                response = JSONResponse(
                    {"detail": error},
                    status_code=status,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                )
                await response(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        await self.app(scope, receive, secure_send)
