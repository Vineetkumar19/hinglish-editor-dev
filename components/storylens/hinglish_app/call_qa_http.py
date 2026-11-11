"""Storylens bridge routes. The telephony gateway only writes completed test calls."""

import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlencode

from .call_qa import CallQA, Conflict, ID, LANGUAGES, MAX_BODY_BYTES, retention_days
from .call_qa_report import FACTS, OUTCOMES, RUBRIC, anonymized, manual_report, review


PREFIX = "/api/call-qa/"
INBOUND = PREFIX + "inbound"
_review_workers = set()
_review_lock = threading.Lock()


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def gateway_key():
    value = os.environ.get("STORYLENS_CALL_QA_INGRESS_KEY", "").encode()
    return value if len(value) >= 32 else None


def read_body(handler, limit):
    if handler.headers.get("Transfer-Encoding") or len(handler.headers.get_all("Content-Length", [])) != 1:
        raise RequestError(400, "Send a single content length.")
    if handler.headers.get_content_type() != "application/json":
        raise RequestError(415, "Send application/json.")
    length = handler.headers.get("Content-Length")
    if not re.fullmatch(r"[0-9]{1,9}", length):
        raise RequestError(400, "Send a valid content length.")
    length = int(length)
    if not 0 < length <= limit:
        raise RequestError(413, "The call package is too large or empty.")
    prior_timeout = handler.connection.gettimeout()
    handler.connection.settimeout(15)
    try:
        body = handler.rfile.read(length)
    except TimeoutError as error:
        handler.close_connection = True
        raise RequestError(408, "The upload timed out. Retry with the same event ID.") from error
    finally:
        handler.connection.settimeout(prior_timeout)
    if len(body) != length:
        raise RequestError(400, "The call package upload was incomplete.")
    return body


def payload(body):
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise RequestError(400, "Send a valid UTF-8 JSON object.") from error
    if not isinstance(value, dict):
        raise RequestError(400, "Send a JSON object.")
    return value


def authenticated_inbound(handler, limit):
    key = gateway_key()
    if not key:
        raise RequestError(503, "Inbound test-call gateway is disabled.")
    body = read_body(handler, limit)
    timestamp = handler.headers.get("X-Call-QA-Timestamp", "")
    signature = handler.headers.get("X-Call-QA-Signature", "")
    if (not re.fullmatch(r"[0-9]{1,12}", timestamp)
            or abs(time.time() - int(timestamp)) > 300
            or not re.fullmatch(r"[0-9a-f]{64}", signature)):
        raise RequestError(403, "Invalid or expired inbound signature.")
    digest = hmac.new(key, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, signature):
        raise RequestError(403, "Invalid or expired inbound signature.")
    return payload(body)


def failure(handler, error):
    if isinstance(error, RequestError):
        status, message = error.status, str(error)
    elif isinstance(error, Conflict):
        status, message = 409, str(error)
    elif isinstance(error, KeyError):
        status, message = 404, "This call is unavailable."
    elif isinstance(error, ValueError):
        status, message = 400, str(error)
    else:
        status, message = 503, "Call QA storage is unavailable. Retry after checking local storage."
    return handler._json(status, {"error": message})


def schedule_review(store):
    def drain():
        try:
            while job := store.claim_report():
                call_id, claim = job
                try:
                    call = store.get(call_id)
                except KeyError:
                    continue
                try:
                    report = review(call)
                except Exception:
                    report = manual_report(call, "Automated review failed.")
                store.finish_report(call_id, claim, report)
        except sqlite3.Error:
            # The durable lease can recover when the workspace is available again.
            pass
        finally:
            with _review_lock:
                _review_workers.discard(store.path)

    with _review_lock:
        if store.path not in _review_workers:
            _review_workers.add(store.path)
            threading.Thread(target=drain, name="storylens-call-qa-review", daemon=True).start()


def audio_signature(state, call_id, expiry, scope="play"):
    value = f"call-qa-{scope}:{call_id}:{expiry}".encode()
    return hmac.new(state.token.encode(), value, hashlib.sha256).hexdigest()


def valid_audio_grant(state, call_id, query, scope="play"):
    expiry = query.get("expires", [""])[0]
    signature = query.get("signature", [""])[0]
    return (bool(re.fullmatch(r"[0-9]{1,12}", expiry) and re.fullmatch(r"[0-9a-f]{64}", signature))
            and time.time() <= int(expiry)
            and hmac.compare_digest(audio_signature(state, call_id, expiry, scope), signature))


def report_bytes(call):
    return (json.dumps(anonymized(call), indent=2) + "\n").encode("utf-8")


def save_local_report(root, call):
    folder = (root / "output" / "call-qa").resolve()
    if not folder.is_relative_to(root.resolve()):
        raise RequestError(503, "The Call QA output folder is outside the workspace.")
    folder.mkdir(parents=True, exist_ok=True)
    content = report_bytes(call)
    digest = hashlib.sha256(content).hexdigest()
    target = folder / f"call-qa-anonymized-{digest[:16]}.json"
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as output:
        pending = folder / os.path.basename(output.name)
        try:
            output.write(content)
        except OSError:
            output.close()
            pending.unlink(missing_ok=True)
            raise
    try:
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return {"path": str(target), "sha256": digest}


def get(handler, state, parsed):
    route = parsed.path.removeprefix(PREFIX)
    query = parse_qs(parsed.query)
    audio_route = re.fullmatch(r"calls/([^/]+)/audio", route)
    download_route = re.fullmatch(r"calls/([^/]+)/download-report", route)
    granted = (audio_route and valid_audio_grant(state, audio_route[1], query)) or (
        download_route and valid_audio_grant(state, download_route[1], query, "export"))
    if not handler._authorized() and not granted:
        return handler._json(403, {"error": "Open Call QA from Storylens to access the test workspace."})
    store = CallQA(state.root)
    try:
        if route == "settings":
            schedule_review(store)
            return handler._json(200, {"languages": LANGUAGES, "rubric": RUBRIC, "outcomes": OUTCOMES,
                                       "fact_kinds": FACTS, "retention_days": retention_days(),
                                       "gateway_enabled": gateway_key() is not None,
                                       "gateway_state": store.gateway_state()})
        if route == "calls":
            return handler._json(200, store.list(query.get("language", [""])[0], query.get("before", [""])[0]))
        if audio_route:
            audio = store.get(audio_route[1], audio=True)
            handler.send_response(200)
            handler.send_header("Content-Type", "audio/wav")
            handler.send_header("Content-Length", str(len(audio)))
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.end_headers()
            return handler.wfile.write(audio)
        if download_route:
            content = report_bytes(store.get(download_route[1]))
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Disposition", 'attachment; filename="storylens-call-qa-anonymized.json"')
            handler.send_header("Content-Length", str(len(content)))
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.end_headers()
            return handler.wfile.write(content)
        match = re.fullmatch(r"calls/([^/]+)(/playback|/export|/export-link)?", route)
        if match:
            call = store.get(match[1])
            if match[2] == "/playback":
                expiry = int(time.time()) + 120
                params = urlencode({"expires": expiry, "signature": audio_signature(state, call["id"], expiry)})
                return handler._json(200, {"url": PREFIX + "calls/" + call["id"] + "/audio?" + params})
            if match[2] == "/export":
                return handler._json(200, anonymized(call))
            if match[2] == "/export-link":
                expiry = int(time.time()) + 120
                params = urlencode({"expires": expiry, "signature": audio_signature(state, call["id"], expiry, "export")})
                return handler._json(200, {"url": PREFIX + "calls/" + call["id"] + "/download-report?" + params})
            if call["report"] is None:
                schedule_review(store)
            return handler._json(200, call)
        raise RequestError(404, "Call QA route unavailable.")
    except (KeyError, ValueError, sqlite3.Error) as error:
        return failure(handler, error)


def post(handler, state, parsed):
    store = CallQA(state.root)
    try:
        if parsed.path == INBOUND:
            event = authenticated_inbound(handler, MAX_BODY_BYTES)
            if event.get("event_type") != "recording.ready" or event.get("direction") != "inbound":
                raise RequestError(400, "Send an inbound recording.ready event.")
            result = store.ingest(event, "gateway")
        elif parsed.path == INBOUND + "-status":
            event = authenticated_inbound(handler, 2048)
            if event.get("event_type") != "gateway.status" or event.get("direction") != "inbound":
                raise RequestError(400, "Send a signed gateway status event.")
            store.set_gateway_state(event)
            return handler._json(200, {"ok": True})
        else:
            if not handler._authorized():
                raise RequestError(403, "Open Call QA from Storylens to edit the test workspace.")
            if parsed.path == PREFIX + "calls":
                result = store.ingest(payload(read_body(handler, MAX_BODY_BYTES)), "import")
            else:
                match = re.fullmatch(PREFIX + r"calls/([^/]+)/(review|delete|save-export)", parsed.path)
                if not match:
                    raise RequestError(404, "Call QA route unavailable.")
                data = payload(read_body(handler, 32768))
                if match[2] == "save-export":
                    return handler._json(200, save_local_report(state.root, store.get(match[1])))
                if match[2] == "delete":
                    if data.get("confirmed") is not True or not ID.fullmatch(match[1]):
                        raise RequestError(400, "Confirm removal of this test recording and its review.")
                    return handler._json(200, store.delete(match[1]))
                return handler._json(200, store.save(match[1], data))
        schedule_review(store)
        return handler._json(200 if result["duplicate"] else 201, result)
    except (KeyError, ValueError, OSError, sqlite3.Error) as error:
        return failure(handler, error)
