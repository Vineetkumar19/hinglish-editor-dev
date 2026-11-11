"""Opt-in Twilio test gateway. The Storylens review server stays on loopback."""

import argparse
import asyncio
import base64
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import FastAPI, Request as WebRequest, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from websockets.exceptions import WebSocketException

from .call_qa import LANGUAGES, now, retention_days
from .call_qa_http import INBOUND, gateway_key
from .call_qa_stream import PhoneSession, open_realtime


ROUTE = "/telephony"
PHONE = re.compile(r"\+[1-9][0-9]{7,14}")
LANGUAGE_KEYS = {"1": "en", "2": "hi", "3": "hinglish"}
ENGLISH = ("en-IN", "Google.en-IN-Standard-E")
HINDI = ("hi-IN", "Google.hi-IN-Standard-E")
CONSENT = {
    "en": [(ENGLISH, "This is a Storylens AI assistant. With your permission, your test call will be recorded and processed by AI for review. When the notice ends, press one to agree. Hang up to decline.")],
    "hi": [(HINDI, "यह स्टोरीलेंस का ए आई सहायक है। आपकी अनुमति से यह परीक्षण कॉल रिकॉर्ड होगी और समीक्षा के लिए ए आई इसे प्रोसेस करेगा। सहमति देने के लिए सूचना के बाद एक दबाएँ। मना करने के लिए कॉल काट दें।")],
    "hinglish": [
        (HINDI, "यह स्टोरीलेंस का ए आई असिस्टेंट है। यह टेस्ट कॉल आपकी अनुमति से रिकॉर्ड होगी।"),
        (ENGLISH, "AI will process this recording for review. Press one after this notice to agree, or hang up to decline."),
    ],
}


def sid(value, prefix):
    return isinstance(value, str) and bool(re.fullmatch(prefix + r"[0-9a-fA-F]{32}", value))


@dataclass(frozen=True)
class Config:
    public_origin: str
    account_sid: str
    auth_token: str = field(repr=False)
    test_line: str = field(repr=False)
    callers: frozenset = field(repr=False)
    storylens: str
    key: bytes = field(repr=False)
    openai_key: str = field(repr=False)
    realtime_model: str
    expires_at: float
    max_duration: int
    spool: Path

    @classmethod
    def from_environment(cls):
        def env(key):
            return os.environ.get(key, "").strip()

        if env("STORYLENS_CALL_QA_TWILIO_TEST_ENABLED") != "1" or env("STORYLENS_CALL_QA_OPENAI_ENABLED") != "1":
            raise ValueError("Authorize the dedicated test line and OpenAI processing before enabling the gateway.")
        public = env("CALL_QA_TWILIO_PUBLIC_ORIGIN").rstrip("/")
        local = env("CALL_QA_STORYLENS_ORIGIN").rstrip("/") or "http://127.0.0.1:8765"
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+", public):
            raise ValueError("Supply an HTTPS public origin for the telephony routes.")
        if not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", local) or urlsplit(local).port > 65535:
            raise ValueError("Use a loopback Storylens origin.")
        account, auth_token = env("TWILIO_ACCOUNT_SID"), env("TWILIO_AUTH_TOKEN")
        model, openai_key = env("CALL_QA_REALTIME_MODEL"), env("OPENAI_API_KEY")
        key = gateway_key()
        if not (sid(account, "AC") and auth_token and key and model and openai_key):
            raise ValueError("Supply authorized Twilio and OpenAI test credentials, the model and the ingress key.")
        test_line = env("CALL_QA_TWILIO_TEST_LINE")
        callers = frozenset(part.strip() for part in env("CALL_QA_TWILIO_TEST_CALLERS").split(","))
        if not all(PHONE.fullmatch(number) for number in (test_line, *callers)) or test_line in callers:
            raise ValueError("Supply the dedicated test line and distinct allowlisted callers in E.164 format.")
        expiry = datetime.fromisoformat(env("CALL_QA_TEST_LINE_EXPIRES_UTC"))
        if expiry.utcoffset() != timezone.utc.utcoffset(expiry):
            raise ValueError("Supply a UTC expiration timestamp for the test line.")
        duration = int(env("CALL_QA_MAX_DURATION_SECONDS") or "300")
        if not 15 <= duration <= 600:
            raise ValueError("The call duration limit must be between 15 and 600 seconds.")
        spool = env("CALL_QA_GATEWAY_SPOOL")
        if not spool or not Path(spool).is_absolute():
            raise ValueError("Supply an absolute private gateway spool directory.")
        return cls(public, account, auth_token, test_line, callers, local, key, openai_key,
                   model, expiry.timestamp(), duration, Path(spool))


def say(parent, locale_and_voice, text):
    language, voice = locale_and_voice
    SubElement(parent, "Say", language=language, voice=voice).text = text


def unique_form(raw):
    values = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=100)
    if any(len(item) != 1 for item in values.values()):
        raise ValueError("Repeated webhook parameter")
    return {key: value[0] for key, value in values.items()}


class Gateway:
    def __init__(self, config, model=open_realtime):
        self.config = config
        self.model = model
        self.active = set()
        self.used = {}
        self.rings = {}
        self.spool_lock = asyncio.Lock()

    def url(self, action, **query):
        return self.config.public_origin + ROUTE + "/" + action + ("?" + urlencode(query) if query else "")

    def verify_twilio(self, target, fields, signature, *, media=False):
        suffix = "".join(key + fields[key] for key in sorted(fields))
        origin = self.config.public_origin
        origins = (origin, origin.replace("https:", "wss:")) if media else (origin,)
        # Twilio can canonicalize the trailing slash on WebSocket signatures.
        targets = (target, target + "/") if media else (target,)
        for candidate in origins:
            for path in targets:
                digest = hmac.digest(self.config.auth_token.encode(), (candidate + path + suffix).encode(), "sha1")
                if hmac.compare_digest(base64.b64encode(digest), signature.encode()):
                    return media or fields.get("AccountSid") == self.config.account_sid
        return False

    def ticket(self, call, language, expiry):
        return hmac.new(self.config.key, f"twilio-consent:{call}:{language}:{expiry}".encode(), hashlib.sha256).hexdigest()

    def gather(self, response, action):
        return SubElement(response, "Gather", input="dtmf", numDigits="1", timeout="7", method="POST", action=action)

    def voice(self, action, fields, query):
        response = Element("Response")
        call = fields.get("CallSid", "")
        caller = fields.get("From")
        current = time.time()
        if (fields.get("To") != self.config.test_line or caller not in self.config.callers
                or fields.get("Direction") != "inbound" or not sid(call, "CA")):
            SubElement(response, "Reject", reason="rejected")
        elif current >= self.config.expires_at:
            say(response, ENGLISH, "This Storylens test line has expired.")
            SubElement(response, "Hangup")
        elif action == "inbound" and not query:
            last_call, last_time = self.rings.get(caller, ("", 0))
            if self.active or (call != last_call and current - last_time < 12):
                say(response, ENGLISH, "The Storylens test line is busy. Try again shortly.")
            else:
                self.rings[caller] = (call, current)
                menu = self.gather(response, self.url("language"))
                say(menu, ENGLISH, "Storylens AI test line. For English, press one.")
                say(menu, HINDI, "हिंदी के लिए दो दबाएँ।")
                say(menu, ENGLISH, "For Hinglish, press three.")
            SubElement(response, "Hangup")
        elif action == "language" and not query and fields.get("Digits") in LANGUAGE_KEYS:
            language = LANGUAGE_KEYS[fields["Digits"]]
            for voice, prompt in CONSENT[language]:
                say(response, voice, prompt)
            self.gather(response, self.url("consent", lang=language))
            SubElement(response, "Hangup")
        elif action == "consent" and fields.get("Digits") == "1" and query.get("lang") in LANGUAGES:
            language = query["lang"]
            expiry = str(int(current) + 45)
            connect = SubElement(response, "Connect")
            stream = SubElement(connect, "Stream", url=self.url("media").replace("https:", "wss:"),
                                statusCallback=self.url("status"), statusCallbackMethod="POST")
            for name, value in {"lang": language, "exp": expiry, "ticket": self.ticket(call, language, expiry)}.items():
                SubElement(stream, "Parameter", name=name, value=value)
            fallback = HINDI if language == "hi" else ENGLISH
            say(response, fallback, "टेस्ट कॉल समाप्त हो गई है। धन्यवाद।" if language == "hi" else "The test call has ended. Thank you.")
            SubElement(response, "Hangup")
        else:
            SubElement(response, "Hangup")
        return tostring(response, encoding="utf-8", xml_declaration=True)

    def authorized_stream(self, event):
        if event.get("event") != "start":
            raise ValueError("Expected authenticated media start")
        start = event["start"]
        call, stream = start["callSid"], start["streamSid"]
        params = start["customParameters"]
        language, expiry = params.get("lang"), params.get("exp", "")
        fmt = start["mediaFormat"]
        if not (
            start["accountSid"] == self.config.account_sid and sid(call, "CA") and sid(stream, "MZ")
            and event["streamSid"] == stream and language in LANGUAGES and fmt == {
                "encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1,
            }
            and re.fullmatch(r"[0-9]{1,12}", expiry) and time.time() <= min(int(expiry), self.config.expires_at)
            and hmac.compare_digest(self.ticket(call, language, expiry), params.get("ticket", ""))
        ):
            raise ValueError("Invalid test call session or media format")
        return call, stream, language

    def deliver(self, path, event):
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        stamp = str(int(time.time()))
        signature = hmac.new(self.config.key, stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        request = Request(self.config.storylens + path, data=body, headers={
            "Content-Type": "application/json", "X-Call-QA-Timestamp": stamp, "X-Call-QA-Signature": signature,
        })
        with build_opener(ProxyHandler({})).open(request, timeout=5):
            pass

    async def status(self, state, detail):
        with suppress(OSError):
            await asyncio.to_thread(self.deliver, INBOUND + "-status", {
                "event_type": "gateway.status", "direction": "inbound", "state": state, "detail": detail,
            })

    def store_pending(self, path, event):
        self.config.spool.mkdir(mode=0o700, parents=True, exist_ok=True)
        pending = path.with_suffix(".tmp")
        with pending.open("w", encoding="utf-8") as stream:
            json.dump(event, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(path)

    async def commit(self, call, session, status, quality):
        artifact = await asyncio.to_thread(session.artifacts)
        if artifact is None:
            return
        wav, turns = artifact
        event = {
            "event_type": "recording.ready", "direction": "inbound", "event_id": "twilio:" + call,
            "provider": "twilio", "title": f"{LANGUAGES[session.language]} inbound test {call[-8:]}",
            "language": session.language, "test_call": True, "consent": True,
            "started_at": session.started_at, "ended_at": now(), "status": status,
            "quality": quality, "timing": session.metrics[:100],
            "transcript": turns, "recording": base64.b64encode(wav).decode(),
        }
        async with self.spool_lock:
            path = self.config.spool / (call + ".json")
            await asyncio.to_thread(self.store_pending, path, event)
            await self.deliver_pending(path, event)

    async def deliver_pending(self, path, event):
        try:
            await asyncio.to_thread(self.deliver, INBOUND, event)
        except HTTPError as error:
            if error.code != 409:
                await self.status("pending", "A test recording is waiting for Storylens to accept it.")
                return
        except OSError:
            return
        path.unlink(missing_ok=True)

    async def recover(self):
        while True:
            async with self.spool_lock:
                for path in self.config.spool.glob("CA*.json"):
                    try:
                        if time.time() - path.stat().st_mtime > retention_days() * 86400:
                            path.unlink()
                            continue
                        data = await asyncio.to_thread(path.read_text, encoding="utf-8")
                        await self.deliver_pending(path, json.loads(data))
                    except (ValueError, OSError):
                        continue
            await asyncio.sleep(15)

    async def stream(self, phone):
        if not self.verify_twilio(ROUTE + "/media", {}, phone.headers.get("X-Twilio-Signature", ""), media=True):
            await phone.close(code=1008)
            return
        await phone.accept()
        try:
            event = await asyncio.wait_for(phone.receive_json(), timeout=5)
            if event.get("event") == "connected":
                event = await asyncio.wait_for(phone.receive_json(), timeout=5)
            call, stream, language = self.authorized_stream(event)
        except (KeyError, ValueError, TypeError, TimeoutError, WebSocketDisconnect):
            await phone.close(code=1008)
            return
        self.used = {key: expiry for key, expiry in self.used.items() if expiry > time.time()}
        if self.active or call in self.used or len(list(self.config.spool.glob("CA*.json"))) >= 10:
            await phone.close(code=1013)
            return
        self.used[call] = time.time() + self.config.max_duration + 60
        self.active.add(call)
        session = PhoneSession(stream, language, self.config.max_duration)
        outcome, quality = "ended", ""
        try:
            async with self.model(self.config, language) as model:
                await session.run(phone, model, self.config.max_duration)
            if session.packet_gap:
                outcome, quality = "partial", "Missing provider audio packets were replaced with silence."
        except WebSocketDisconnect:
            outcome, quality = "partial", "Media disconnected before the provider stop event."
        except (RuntimeError, OSError, TimeoutError, ValueError, TypeError, KeyError, WebSocketException):
            outcome, quality = "partial", "Media or the OpenAI voice session stopped unexpectedly."
            await self.status("unavailable", quality)
        finally:
            with suppress(RuntimeError, OSError):
                await phone.close(code=1000)
            try:
                await self.commit(call, session, outcome, quality)
            except OSError:
                await self.status("unavailable", "The local gateway spool could not save the test recording.")
            finally:
                self.active.discard(call)


def app_for(gateway):
    @asynccontextmanager
    async def lifespan(_):
        recovery = asyncio.create_task(gateway.recover())
        try:
            yield
        finally:
            recovery.cancel()
            with suppress(asyncio.CancelledError):
                await recovery

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.post(ROUTE + "/{action}")
    async def webhook(action: str, request: WebRequest):
        if action not in {"inbound", "language", "consent", "status"}:
            return Response(status_code=404)
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return Response(status_code=415)
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 16384:
                    return Response(status_code=413)
                body.extend(chunk)
            fields = unique_form(body.decode("utf-8"))
            target = request.scope["raw_path"].decode("ascii")
            query = request.scope["query_string"].decode("ascii")
            if query:
                target += "?" + query
            if not gateway.verify_twilio(target, fields, request.headers.get("X-Twilio-Signature", "")):
                return Response(status_code=403)
            if action == "status":
                stream_event = fields.get("StreamEvent")
                if stream_event in ("stream-error", "stream-started", "stream-stopped") and sid(fields.get("CallSid"), "CA"):
                    state = {"stream-error": "unavailable", "stream-started": "connected", "stream-stopped": "ended"}[stream_event]
                    await gateway.status(state, "Twilio media stream " + stream_event.removeprefix("stream-") + ".")
                return Response(status_code=204)
            if action == "inbound" and time.time() >= gateway.config.expires_at:
                await gateway.status("expired", "The dedicated test line assignment expired.")
            return Response(gateway.voice(action, fields, unique_form(query)), media_type="text/xml")
        except (ValueError, WebSocketDisconnect):
            return Response(status_code=400)

    @app.websocket(ROUTE + "/media")
    async def media(phone: WebSocket):
        await gateway.stream(phone)

    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Storylens Call QA allowlisted Twilio test gateway")
    parser.add_argument("--port", type=int, default=8893)
    args = parser.parse_args()
    try:
        config = Config.from_environment()
    except ValueError as error:
        parser.error(str(error))
    uvicorn.run(app_for(Gateway(config)), host="127.0.0.1", port=args.port,
                access_log=False, proxy_headers=False, ws="websockets", ws_max_size=128 * 1024)


if __name__ == "__main__":
    main()
