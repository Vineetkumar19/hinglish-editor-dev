"""Authenticated, loopback Storylens access to the existing Agent Suite."""
from __future__ import annotations

import hmac
import json
from pathlib import Path

from core import config, http
from core.llm import LLMError
from core.workflow_brain import (RECENT_CHATGPT_VERIFICATION, RECENT_STORYLENS_FALLBACK,
                                 STORYLENS_LOCAL_MODEL, cloud_unavailable, codex_path)
from server import console


URLS = {
    "dashboard": "/",
    "approvals": "/approvals",
    "workflows": "/workflows",
    "saas_demand": "/workflows#saas-demand",
}


def _authorised(handler):
    if not handler.server.integrated:
        handler._json(404, {"error": "Storylens integration is disabled."})
        return False
    token = config.get("DASHBOARD_TOKEN", "")
    auth = handler.headers.get("Authorization", "")
    if token and auth[:7].lower() == "bearer " and hmac.compare_digest(
        auth[7:].encode(), token.encode()
    ):
        return True
    handler.close_connection = True
    handler._json(401, {"error": "Bearer authentication required."})
    return False


def _codex_installed():
    try:
        codex_path()
        return True
    except LLMError:
        return False


def _connection(configured, verification=None, **details):
    verified_at = RECENT_CHATGPT_VERIFICATION.get(verification) if configured and verification else None
    return {"configured": bool(configured), "verified": bool(verified_at),
            "status": "verified" if verified_at else "unverified" if configured else "not configured",
            "verified_at": verified_at, **details}


def _local_ready():
    try:
        response = http.get('http://127.0.0.1:11434/api/tags', timeout=2, retries=0).raise_for_status()
        return any(row.get('name') == STORYLENS_LOCAL_MODEL for row in response.json().get('models', []))
    except (http.HttpError, OSError, ValueError, TypeError):
        return False


def _connections(handler):
    credentials_file = config.get("GOOGLE_CLIENT_SECRETS_FILE")
    google_client = (
        bool(credentials_file and Path(credentials_file).is_file())
        or bool(config.get("GOOGLE_CLIENT_ID") and config.get("GOOGLE_CLIENT_SECRET"))
    )
    google_credentials = bool(
        google_client and handler.store.kv_get("oauth", "google:default")
    )
    mail_transport = config.get("MAIL_TRANSPORT", "smtp").lower()
    mail = google_credentials if mail_transport == "gmail" else bool(
        config.get("SMTP_HOST") and config.get("SMTP_USER") and config.get("SMTP_PASSWORD")
    )
    search_provider = config.get("SEARCH_PROVIDER", "seeds")
    search_env = {"brave": "BRAVE_API_KEY", "serper": "SERPER_API_KEY", "searxng": "SEARXNG_URL"}
    search = (
        Path(config.get("SEEDS_FILE", str(config.profiles_dir() / "targets.yaml"))).is_file()
        if search_provider == "seeds"
        else _codex_installed() if search_provider == "chatgpt_web"
        else bool(config.get(search_env.get(search_provider, "")))
    )
    return {
        "suite": {"configured": True, "verified": True, "status": "connected"},
        "chatgpt": _connection(
            _codex_installed(), verification="model_response",
            model=config.get("SUITE_CHATGPT_MODEL", "gpt-6.1-sol"),
            reasoning_effort=config.get("SUITE_CHATGPT_REASONING_EFFORT", "medium"),
            detail="A successful model response in this process verifies the connection.",
        ),
        "local_fallback": {"configured": True, "verified": bool(RECENT_STORYLENS_FALLBACK),
                           "status": 'ready' if _local_ready() else 'unavailable',
                           "model": STORYLENS_LOCAL_MODEL,
                           "last_use": dict(RECENT_STORYLENS_FALLBACK),
                           "current_outage": cloud_unavailable()},
        "email": _connection(mail, transport=mail_transport, dry_run=config.dry_run()),
        "google_calendar": _connection(google_credentials),
        "telegram": _connection(bool(config.get("TELEGRAM_BOT_TOKEN"))),
        "discovery": _connection(search, provider=search_provider,
                                 verification="web_search" if search_provider == "chatgpt_web" else None,
                                 mode="live public web" if search_provider != "seeds" else "curated seeds only"),
    }


def _product_status(store):
    from agents.saas_sales import product

    ready, reason = product.ready_to_sell()
    enabled = config.get_bool("SAAS_ENABLED")
    from agents.saas_sales.research import launch_settings

    settings = launch_settings(store)
    blockers = []
    if not settings["public_url"]:
        blockers.append("Storylens is localhost only. Add a public URL when it is hosted.")
    else:
        blockers.append("Public URL supplied. Hosting and promotion still require separate review.")
    if not enabled:
        blockers.append("SaaS outreach is disabled by SAAS_ENABLED.")
    if not ready and "no name" not in reason:
        blockers.append(reason)
    blockers.append("Product launch is parked in the native console.")
    return {"name": settings["name"], "stage": settings["stage"], "profile_ready": ready,
            "outreach_enabled": enabled, "blockers": blockers,
            "hosting": settings["hosting"], "public_url_supplied": bool(settings["public_url"]),
            "demand_research_url": URLS["saas_demand"]}


def status(handler):
    if not _authorised(handler):
        return
    counts = handler._counts()
    connections = _connections(handler)
    product = _product_status(handler.store)
    agents = []
    for meta in console.AGENTS:
        key = meta["key"]
        state = handler._agent_state(key).get("status", "idle")
        pending = counts.get(key, 0)
        blocker = ""
        if key == "saas_sales":
            blocker = " ".join(product["blockers"])
        elif console.demo_mode():
            blocker = "The Agent Suite is in read-only demo mode."
        elif not connections["chatgpt"]["configured"] and connections['local_fallback']['status'] != 'ready':
            blocker = "ChatGPT and the local Ollama model are both unavailable. Saved work is preserved."
        agents.append({
            "key": key, "name": meta["name"], "description": meta["does"],
            "status": "waiting for you" if pending else state,
            "pending": pending, "runnable": meta["runnable"] and not blocker,
            "url": f"/agent/{key}", "blocker": blocker,
        })
    handler._json(200, {"agents": agents, "connections": connections, "urls": URLS,
                        "saas": product})


def run(handler):
    if not _authorised(handler):
        return
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if not 0 < length <= 4096:
            raise ValueError("invalid body length")
        body = json.loads(handler.rfile.read(length))
        if not isinstance(body, dict) or set(body) != {"agent"} or not isinstance(body["agent"], str):
            raise ValueError("invalid run request")
    except (ValueError, UnicodeError):
        handler.close_connection = True
        return handler._json(400, {"error": "Expected a JSON object with a single agent key."})

    key = body["agent"]
    meta = console.agent_meta(key)
    if meta is None or key != meta["key"]:
        return handler._json(404, {"error": "No such agent."})
    if console.demo_mode():
        return handler._json(403, {"error": "The Agent Suite is in read-only demo mode."})
    if not meta["runnable"]:
        return handler._json(409, {"status": "parked", "url": f"/agent/{key}",
                                   "error": " ".join(_product_status(handler.store)["blockers"])})
    if not _codex_installed() and not _local_ready():
        return handler._json(503, {"error": "ChatGPT and the local Ollama model are both unavailable. Saved work is preserved."})
    code, payload = handler._start_agent(key, meta)
    handler._json(code, payload)
