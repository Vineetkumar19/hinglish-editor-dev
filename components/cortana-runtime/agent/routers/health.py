from fastapi import APIRouter

from core.config import settings, ROOT_DIR
import httpx

router = APIRouter(tags=["health"])
_brain_warmup = 'starting'


async def warm_brain():
    global _brain_warmup
    # Load on demand. Startup must not contend with StoryLens or hidden GPU jobs.
    _brain_warmup = 'on_demand'


@router.get("/api/health")
def health():
    return {"status": "ok", "app": "cortana", "phase": settings.phase}


@router.get("/api/ready")
def ready():
    return {"status": "ready", "app": "cortana", "local_only": True}


@router.get("/api/status")
async def status():
    from core import stt
    from core.app_config import approved_apps, approved_search_roots
    brain = {"model": settings.ollama_model, "available": False, "loaded": False,
             "warmup": _brain_warmup}
    vision = {"model": settings.ollama_vision_model, "available": False, "loaded": False}
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            tags = (await client.get(settings.ollama_host + "/api/tags")).json()
            running = (await client.get(settings.ollama_host + "/api/ps")).json()
            if any(m.get('name') == settings.ollama_vision_model for m in tags.get('models', [])):
                detail = await client.post(settings.ollama_host + '/api/show', json={'model':settings.ollama_vision_model})
                detail.raise_for_status()
                vision['available'] = 'vision' in detail.json().get('capabilities', [])
        brain["available"] = any(m.get("name") == settings.ollama_model for m in tags.get("models", []))
        brain["loaded"] = any(m.get("name") == settings.ollama_model for m in running.get("models", []))
        vision["loaded"] = any(m.get("name") == settings.ollama_vision_model for m in running.get("models", []))
    except (httpx.HTTPError, ValueError):
        brain["error"] = "Ollama is unavailable. Open Ollama to enable local reasoning."
    return {
        "status": "ready" if brain["available"] else "degraded",
        "model_work_paused": (ROOT_DIR / 'memory/pause_model_work').exists(),
        "local_only": True, "cloud_enabled": False, "brain": brain,
        "model": brain["model"], "model_available": brain["available"],
        "model_loaded": brain["loaded"],
        "vision": vision,
        "apps": sorted(approved_apps()), "file_roots": approved_search_roots(),
        "languages": ["English", "Hindi", "Hinglish"],
        "speech": stt.runtime_status(),
        "screen": {"capture": "on request", "monitor": "primary", "storage": "memory"},
    }
