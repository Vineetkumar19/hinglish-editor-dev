"""LLM provider abstraction.

Providers are selected with LLM_PROVIDER:

  anthropic  - Claude via the Messages REST API      (ANTHROPIC_API_KEY)
  openai     - OpenAI-compatible /chat/completions   (OPENAI_API_KEY, OPENAI_BASE_URL)
  ollama     - a local Ollama server                 (OLLAMA_BASE_URL)
  offline    - deterministic, no network. Real code paths, templated content.

A local model is a first-class provider here, not a downgrade: a run costs
nothing, the brand's site text never leaves the machine, and the only price is
that small models need more help to stay on format. That help is `json_schema`,
threaded through `complete()` so a runtime that can constrain its own output
(Ollama's `format`, an OpenAI-compatible `response_format`) is handed the shape
instead of being asked for it in prose.

`structured()` is the workhorse: it asks for JSON matching a schema, validates
it, and on failure feeds the validation errors back for one repair attempt
before giving up. That is the "strict Pydantic schema" contract the blueprint
specifies, implemented without Pydantic.
"""
from __future__ import annotations

import json
import functools
import os
import re
import threading
import time
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config, http
from .log import get_logger
from .schema import ValidationError, describe, validate

log = get_logger("llm")

_LOCAL_INFERENCE_LOCK = threading.RLock()
_LOCAL_INFERENCE_STATE = threading.local()


def _serial_local(fn):
    """One local generation at a time, including tool turns and model loading."""
    @functools.wraps(fn)
    def guarded(*args, **kwargs):
        with _LOCAL_INFERENCE_LOCK:
            if getattr(_LOCAL_INFERENCE_STATE, "active", False):
                return fn(*args, **kwargs)
            lock_path = config.data_dir() / "local-inference.lock"
            with lock_path.open("a+b") as handle:
                if lock_path.stat().st_size == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    deadline = time.monotonic() + config.get_float("OLLAMA_QUEUE_TIMEOUT", 600)
                    while True:
                        try:
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise LLMError("Timed out waiting for the local model queue")
                            time.sleep(0.1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX)
                _LOCAL_INFERENCE_STATE.active = True
                try:
                    return fn(*args, **kwargs)
                finally:
                    _LOCAL_INFERENCE_STATE.active = False
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle, fcntl.LOCK_UN)
    return guarded


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, i: int, o: int) -> None:
        self.input_tokens += i
        self.output_tokens += o
        self.calls += 1


@dataclass
class Message:
    """One turn. Carries tool calls and tool results as well as plain text.

    `tool_calls` is what the model asked for; `name` is set on a tool RESULT
    message so the model can tell which answer belongs to which call. Both are
    left out of the wire format when empty, so a provider that knows nothing
    about tools sees exactly what it saw before.
    """
    role: str
    content: str
    tool_calls: list | None = None
    name: str = ""

    def to_api(self) -> dict:
        out = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = self.tool_calls
        if self.name:
            out["name"] = self.name
        return out


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# JSON extraction from a chatty model
# --------------------------------------------------------------------------
def extract_json(text: str) -> Any:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back to the outermost balanced {...} or [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise LLMError(f"model did not return parseable JSON: {text[:300]!r}")


def json_schema_for(schema: dict) -> dict:
    """Our compact schema shape rewritten as the JSON Schema a local runtime
    compiles into a grammar.

    Bounds (min_length, minimum, min_items) are deliberately dropped. Grammar
    compilers handle them inconsistently, and a rejected grammar costs the whole
    call - whereas `validate()` still enforces every bound on the way back, so
    nothing is actually relaxed.
    """
    t = schema.get("type", "string")
    out: dict = {"type": t}
    if t == "string" and schema.get("max_length"):
        out["maxLength"] = int(schema["max_length"])
    if "enum" in schema:
        out["enum"] = list(schema["enum"])
    if t == "object":
        props = {k: json_schema_for(v) for k, v in schema.get("properties", {}).items()}
        out["properties"] = props
        required = list(schema.get("required") or [])
        # A local model drops optional keys more often than it fills them. Asking
        # for all of them keeps the reply one predictable shape; the ones with
        # defaults are cheap for the model and save a repair round-trip.
        out["required"] = required or list(props)
    elif t == "array":
        out["items"] = json_schema_for(schema.get("items", {"type": "string"}))
    return out


# --------------------------------------------------------------------------
# providers
# --------------------------------------------------------------------------
class Provider:
    name = "base"

    def complete(self, system: str, messages: list[Message], *,
                 max_tokens: int, temperature: float,
                 json_schema: dict | None = None) -> tuple[str, tuple[int, int]]:
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self):
        self.key = config.require("ANTHROPIC_API_KEY")
        self.base = config.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        self.model = config.get("LLM_MODEL", "claude-sonnet-4-5")
        self.version = config.get("ANTHROPIC_VERSION", "2023-06-01")

    def complete(self, system, messages, *, max_tokens, temperature,
                 json_schema=None):
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            body["system"] = system
        resp = http.post(f"{self.base}/v1/messages", json_body=body, timeout=120,
                         headers={"x-api-key": self.key,
                                  "anthropic-version": self.version})
        if not resp.ok:
            raise LLMError(f"anthropic {resp.status}: {resp.text[:400]}")
        data = resp.json()
        parts = [b.get("text", "") for b in data.get("content", [])
                 if b.get("type") == "text"]
        u = data.get("usage", {})
        return "".join(parts), (u.get("input_tokens", 0), u.get("output_tokens", 0))


def _is_local(url: str) -> bool:
    return any(h in url for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))


class OpenAIProvider(Provider):
    """OpenAI's API, and every local server that imitates it.

    LM Studio, llama.cpp's server, vLLM and Jan all speak this dialect, so
    pointing OPENAI_BASE_URL at one of them is enough to run entirely on this
    machine. Those servers ignore the key, so a local base URL does not require
    one - demanding a key that means nothing is the commonest reason a local
    setup refuses to start.
    """
    name = "openai"

    def __init__(self):
        self.base = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.local = _is_local(self.base)
        self.key = (config.get("OPENAI_API_KEY", "") or "local"
                    if self.local else config.require("OPENAI_API_KEY"))
        self.model = config.get("LLM_MODEL", "gpt-4o-mini")

    def complete(self, system, messages, *, max_tokens, temperature,
                 json_schema=None):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": m.role, "content": m.content} for m in messages]
        body = {"model": self.model, "messages": msgs,
                "max_tokens": max_tokens, "temperature": temperature}
        if json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "reply", "strict": True,
                                "schema": {**json_schema,
                                           "additionalProperties": False}},
            }
        try:
            resp = http.post(f"{self.base}/chat/completions", timeout=
                             config.get_float("LLM_TIMEOUT", 300 if self.local else 120),
                             json_body=body, retries=0 if self.local else 3,
                             headers={"Authorization": f"Bearer {self.key}"})
        except http.HttpError as exc:
            if self.local:
                raise LLMError(
                    f"cannot reach a local model server at {self.base}. Start it "
                    f"(LM Studio: Developer tab, Start Server) and check the port. "
                    f"({exc})") from exc
            raise
        if json_schema and resp.status == 400 and "response_format" in resp.text:
            # Older local servers reject the strict-schema form. The prose
            # instruction in structured() still asks for the same JSON, so drop
            # the constraint rather than the call.
            body.pop("response_format", None)
            resp = http.post(f"{self.base}/chat/completions", timeout=300,
                             json_body=body, retries=0,
                             headers={"Authorization": f"Bearer {self.key}"})
        if not resp.ok:
            raise LLMError(f"openai {resp.status}: {resp.text[:400]}")
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage", {})
        return text, (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))


class OllamaProvider(Provider):
    """A model running on this machine, through Ollama.

    Three settings decide whether this works at all, and all three have bad
    defaults on the Ollama side for this job - see the comments in __init__.
    """
    name = "ollama"

    def __init__(self):
        self.base = config.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = config.get("LLM_MODEL", "llama3.1")
        # Ollama's own default context window is 2048 tokens. A pitch prompt
        # carries several thousand characters of the brand's own site text, and
        # at 2048 that text is silently cut off the front - the model then
        # writes a generic email and looks like it ignored the brand. This is
        # the single most important setting on this class.
        self.num_ctx = config.get_int("OLLAMA_NUM_CTX", 8192)
        # Without this the model is unloaded from memory between leads and every
        # lead pays the load cost again.
        self.keep_alive = config.get("OLLAMA_KEEP_ALIVE", "10m")
        self.timeout = config.get_float("LLM_TIMEOUT", 300)

    @_serial_local
    def complete(self, system, messages, *, max_tokens, temperature,
                 json_schema=None, tools=None):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [m.to_api() if hasattr(m, "to_api")
                else {"role": m.role, "content": m.content} for m in messages]
        body = {"model": self.model, "messages": msgs, "stream": False,
                "think": config.get_bool("OLLAMA_THINK", False),
                "keep_alive": self.keep_alive,
                "options": {"temperature": temperature,
                            "num_predict": max_tokens,
                            "num_ctx": self.num_ctx}}
        if config.get("OLLAMA_NUM_GPU") is not None:
            body["options"]["num_gpu"] = config.get_int("OLLAMA_NUM_GPU", 99)
        body["options"]["num_batch"] = config.get_int("OLLAMA_NUM_BATCH", 256)
        if json_schema and not tools:
            # Ollama compiles this into a grammar, so the model cannot emit
            # anything but conforming JSON. It is the difference between a 7B
            # model being usable here and not.
            #
            # Not sent alongside tools: a grammar that forces the reply into
            # the answer shape leaves no room for the model to emit a tool
            # call instead, so it would never use its hands.
            body["format"] = json_schema
        if tools:
            body["tools"] = [t.spec() for t in tools]
        try:
            # retries=0: a refused connection to localhost will not succeed on
            # the third try, and the default backoff makes the failure take
            # seven seconds to report something the user can read at once.
            resp = http.post(f"{self.base}/api/chat", timeout=self.timeout,
                             retries=0, json_body=body)
        except http.HttpError as exc:
            raise LLMError(
                f"cannot reach Ollama at {self.base}. Start it with "
                f"`ollama serve` (or open the Ollama app) and try again. ({exc})"
            ) from exc
        if resp.status == 404:
            raise LLMError(
                f"Ollama is running but has no model called {self.model!r}. "
                f"Pull it with `ollama pull {self.model}`, or set LLM_MODEL to "
                f"one that `ollama list` shows.")
        if not resp.ok:
            raise LLMError(f"ollama {resp.status}: {resp.text[:400]}")
        data = resp.json()
        self.last_message = data.get("message", {}) or {}
        if not self.last_message.get("content") and not self.last_message.get("tool_calls"):
            raise LLMError("Ollama returned no answer. Increase the output budget "
                           "or disable thinking with OLLAMA_THINK=false.")
        return self.last_message.get("content", ""), (
            data.get("prompt_eval_count", 0), data.get("eval_count", 0))

    # The tool loop needs the whole message, not just its text, because the
    # interesting part of a tool turn is `tool_calls` and the content is empty.
    supports_tools = True

    @_serial_local
    def chat(self, system, messages, *, max_tokens, temperature, tools=None):
        """One turn, returning the full assistant message."""
        self.last_message = {}
        self.complete(system, messages, max_tokens=max_tokens,
                      temperature=temperature, tools=tools)
        return dict(self.last_message)

    @_serial_local
    def warm(self) -> None:
        """Load the model into memory before it is needed.

        Ollama loads a model on first use, so that cost - tens of seconds for a
        7B - lands inside the first brand's wait and looks like the writing
        being slow. Sending an empty prompt loads it and generates nothing, so
        this costs no tokens and changes no output; it just moves the load out
        of the first card.
        """
        try:
            http.post(f"{self.base}/api/generate", timeout=self.timeout,
                      retries=0, json_body={"model": self.model,
                                            "keep_alive": self.keep_alive,
                                            "options": {"num_ctx": self.num_ctx,
                                                        "num_gpu": config.get_int("OLLAMA_NUM_GPU", 99)}})
        except http.HttpError as exc:
            log.debug(f"could not preload {self.model}: {exc}")

    @_serial_local
    def speed(self) -> tuple[float, str]:
        """Tokens per second on a tiny generation, for the doctor.

        This is the number that decides whether the setup is usable: the same
        model that answers in eight seconds on a GPU takes four minutes on a
        CPU, and from the outside the second one looks like a hang.
        """
        try:
            resp = http.post(f"{self.base}/api/generate", timeout=180, retries=0,
                             json_body={"model": self.model, "prompt": "Say hello.",
                                        "stream": False, "think": config.get_bool("OLLAMA_THINK", False),
                                        "keep_alive": self.keep_alive,
                                        "options": {"num_predict": 32,
                                                    "num_gpu": config.get_int("OLLAMA_NUM_GPU", 99),
                                                    "num_ctx": self.num_ctx}})
        except http.HttpError as exc:
            return 0.0, str(exc)[:120]
        if not resp.ok:
            return 0.0, f"{resp.status}: {resp.text[:120]}"
        data = resp.json()
        out, ns = data.get("eval_count", 0), data.get("eval_duration", 0)
        if not out or not ns:
            return 0.0, "the model answered but reported no timings"
        return out / (ns / 1e9), ""

    def models(self) -> list[str]:
        """What is installed, for the doctor. Empty list if unreachable."""
        try:
            resp = http.get(f"{self.base}/api/tags", timeout=10, retries=0)
        except http.HttpError:
            return []
        if not resp.ok:
            return []
        return [m.get("name", "") for m in (resp.json().get("models") or [])]


# -- offline -----------------------------------------------------------------
OFFLINE_HANDLERS: dict[str, Callable[[dict], Any]] = {}


def offline_handler(task: str):
    """Register a deterministic stand-in for one LLM task."""
    def deco(fn):
        OFFLINE_HANDLERS[task] = fn
        return fn
    return deco


def stub_from_schema(schema: dict, hint: str = "") -> Any:
    """Produce a schema-valid placeholder value."""
    t = schema.get("type", "string")
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if t == "object":
        out = {}
        props = schema.get("properties", {})
        for k, v in props.items():
            out[k] = stub_from_schema(v, hint=k)
        return out
    if t == "array":
        item = schema.get("items", {"type": "string"})
        n = max(1, int(schema.get("min_items", 1)))
        return [stub_from_schema(item, hint) for _ in range(n)]
    if t in ("number", "integer"):
        lo = schema.get("minimum", 0)
        hi = schema.get("maximum", lo + 1)
        mid = (lo + hi) / 2
        return int(mid) if t == "integer" else round(mid, 3)
    if t == "boolean":
        return True
    ml = schema.get("min_length", 0)
    text = f"[offline:{hint}]" if hint else "[offline]"
    return text.ljust(ml, ".")


class OfflineProvider(Provider):
    """Deterministic provider used for tests and dry runs.

    It never invents facts: text output is templated from the inputs it is
    given, so anything it produces is traceable to the prompt.
    """
    name = "offline"

    def complete(self, system, messages, *, max_tokens, temperature,
                 json_schema=None):
        last = messages[-1].content if messages else ""
        return (f"[offline provider] no model configured. "
                f"Prompt was {len(last)} chars."), (0, 0)


def _chatgpt_provider() -> Provider:
    from .workflow_brain import ChatGPTProvider, StorylensProvider
    return StorylensProvider() if config.get_bool('SUITE_STORYLENS_INTEGRATED') else ChatGPTProvider()


PROVIDERS = {
    "chatgpt": _chatgpt_provider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "offline": OfflineProvider,
    "none": OfflineProvider,
}


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------
class LLM:
    def __init__(self, provider: str | None = None, store=None):
        name = (provider or config.get("LLM_PROVIDER", "offline")).lower()
        if name not in PROVIDERS:
            raise LLMError(f"unknown LLM_PROVIDER {name!r}; "
                           f"choose from {sorted(PROVIDERS)}")
        self.provider_name = name
        self._cls = PROVIDERS[name]
        self._impl: Provider | None = None
        self.usage = Usage()
        self.store = store
        self.cache = name != "chatgpt" and config.get_bool("LLM_CACHE", True)

    @property
    def impl(self) -> Provider:
        if self._impl is None:
            self._impl = self._cls()
        return self._impl

    @property
    def is_offline(self) -> bool:
        return self.provider_name in ("offline", "none")

    # -- caching -------------------------------------------------------------
    def _cache_key(self, *parts) -> str:
        import hashlib
        raw = json.dumps(parts, default=str, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _cached(self, key: str):
        if self.cache and self.store is not None:
            return self.store.kv_get("llm_cache", key)
        return None

    def _store_cache(self, key: str, value) -> None:
        if self.cache and self.store is not None:
            self.store.kv_set("llm_cache", key, value)

    # -- text ----------------------------------------------------------------
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, history: list[Message] | None = None,
                 json_schema: dict | None = None) -> str:
        msgs = list(history or []) + [Message("user", prompt)]
        key = self._cache_key("complete", self.provider_name, system,
                              [(m.role, m.content) for m in msgs], max_tokens,
                              temperature, json_schema)
        hit = self._cached(key)
        if hit is not None:
            log.debug("llm cache hit")
            return hit
        text, (i, o) = self.impl.complete(system, msgs, max_tokens=max_tokens,
                                          temperature=temperature,
                                          json_schema=json_schema)
        self.usage.add(i, o)
        receipt = getattr(self.impl, 'last_receipt', {})
        log.debug("llm call", provider=receipt.get('provider', self.provider_name),
                  model=receipt.get('model', ''), fallback_reason=receipt.get('reason', ''), in_tok=i, out_tok=o)
        if temperature <= 0.35:
            self._store_cache(key, text)
        return text

    # -- hands ---------------------------------------------------------------
    def with_tools(self, prompt: str, tool_names: list[str], *,
                   system: str = "", max_tokens: int = 1200,
                   temperature: float = 0.3, max_calls: int | None = None,
                   call_log=None) -> tuple[str, Any]:
        """Let the model go and look things up before it answers.

        The loop: ask, and if the reply is a tool call rather than an answer,
        run the tool, hand the result back, and ask again. It ends when the
        model answers in words or when the call budget runs out.

        Returns (answer, call_log). Never raises for a tool failure - a tool
        that errors hands its error back as text, because a model that gets an
        error can try something else, whereas an exception ends the draft.

        Falls back to a single plain call when the provider cannot do tools or
        when nothing bindable was asked for, so a caller never has to check.
        """
        from core import tools as tools_mod
        budget = max_calls if max_calls is not None else tools_mod.MAX_CALLS
        log_to = call_log if call_log is not None else tools_mod.CallLog()
        bound = tools_mod.bind(tool_names or [])

        if self.is_offline or not bound or not getattr(
                self.impl, "supports_tools", False):
            return self.complete(prompt, system=system, max_tokens=max_tokens,
                                 temperature=temperature), log_to

        convo: list[Message] = [Message("user", prompt)]
        for _ in range(budget + 1):
            try:
                reply = self.impl.chat(system, convo, max_tokens=max_tokens,
                                       temperature=temperature, tools=bound)
            except (LLMError, Exception) as exc:  # noqa: BLE001
                log.warn(f"tool-calling turn failed, answering without it: {exc}")
                return self.complete(prompt, system=system,
                                     max_tokens=max_tokens,
                                     temperature=temperature), log_to

            calls = reply.get("tool_calls") or []
            content = reply.get("content") or ""
            if not calls:
                return content, log_to

            # Record what it asked for, then answer each call in order.
            convo.append(Message("assistant", content, tool_calls=calls))
            for call in calls[:budget]:
                fn = (call.get("function") or {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                result = tools_mod.execute(name, args, log_to=log_to)
                convo.append(Message("tool", result, name=name))
            budget -= len(calls)
            if budget <= 0:
                # Out of budget. Ask once more, without tools, so it finishes
                # the job with whatever it already has rather than stopping
                # mid-thought.
                convo.append(Message(
                    "user", "You have used all your lookups. Answer now with "
                            "what you have."))
                try:
                    final = self.impl.chat(system, convo, max_tokens=max_tokens,
                                           temperature=temperature, tools=None)
                    return (final.get("content") or ""), log_to
                except Exception as exc:  # noqa: BLE001
                    log.warn(f"final turn failed: {exc}")
                    return "", log_to
        return "", log_to

    def structured_with_tools(self, prompt: str, schema: dict,
                              tool_names: list[str], *, system: str = "",
                              task: str = "", context: dict | None = None,
                              max_tokens: int = 1200, temperature: float = 0.3,
                              call_log=None) -> tuple[Any, Any]:
        """Look things up first, then answer in the required shape.

        Two phases on purpose. A grammar that forces the reply into the answer
        shape leaves the model no way to emit a tool call, so the lookups have
        to finish before the schema is applied. The gathered facts are handed
        to the structured call as notes.
        """
        from core import tools as tools_mod
        log_to = call_log if call_log is not None else tools_mod.CallLog()
        if self.is_offline or not tool_names or self.provider_name == "chatgpt":
            return self.structured(prompt, schema, system=system, task=task,
                                   context=context, max_tokens=max_tokens,
                                   temperature=temperature), log_to

        notes, log_to = self.with_tools(
            prompt + "\n\nFirst, look up anything you need. When you have it, "
                     "reply in plain words with the facts you found and what "
                     "you intend to say. Do not write the final message yet.",
            tool_names, system=system, max_tokens=600,
            temperature=temperature, call_log=log_to)

        enriched = prompt
        if log_to.calls:
            enriched = (f"{prompt}\n\nWHAT YOU LOOKED UP\n"
                        f"{log_to.summary()}\n\nWhat you found:\n{notes[:2000]}")
        return self.structured(enriched, schema, system=system, task=task,
                               context=context, max_tokens=max_tokens,
                               temperature=temperature), log_to

    # -- structured ----------------------------------------------------------
    def structured(self, prompt: str, schema: dict, *, system: str = "",
                   task: str = "", context: dict | None = None,
                   max_tokens: int = 2048, temperature: float = 0.2,
                   repairs: int = 1) -> Any:
        """Return JSON matching `schema`, validated, with a repair round-trip."""
        if self.is_offline:
            return self._offline_result(task, schema, context)

        try:
            return self._structured(prompt, schema, system=system,
                                    max_tokens=max_tokens,
                                    temperature=temperature, repairs=repairs)
        except (LLMError, http.HttpError) as exc:
            # A model that is switched off, out of memory or talking nonsense
            # must not end the run. The deterministic handler produces the same
            # shape from the same inputs, so the work continues - visibly
            # degraded rather than silently lost.
            if self.provider_name == "chatgpt" or not config.get_bool("LLM_FALLBACK_OFFLINE", True):
                raise
            if task not in OFFLINE_HANDLERS:
                raise
            log.warn("local model unavailable, falling back to the written "
                     "template", task=task, error=str(exc)[:200])
            out = self._offline_result(task, schema, context)
            if isinstance(out, dict):
                out.setdefault("_fallback", str(exc)[:200])
            return out

    def _offline_result(self, task: str, schema: dict, context: dict | None):
        handler = OFFLINE_HANDLERS.get(task)
        raw = handler(context or {}) if handler else stub_from_schema(schema)
        return validate(raw, schema)

    def _structured(self, prompt: str, schema: dict, *, system: str,
                    max_tokens: int, temperature: float, repairs: int) -> Any:
        instruction = textwrap.dedent(f"""
            Respond with a single JSON object and nothing else. No prose, no
            code fence, no explanation. Keep every string concise and use valid
            JSON escaping. It must match this shape exactly:

            {describe(schema)}
        """).strip()
        full_system = (system + "\n\n" + instruction).strip() if system else instruction

        attempt = 0
        convo: list[Message] = []
        last_err = ""
        while True:
            text = self.complete(prompt if not convo else
                                 f"Your previous reply was invalid: {last_err}\n"
                                 f"Return corrected JSON only.",
                                 system=full_system, max_tokens=max_tokens,
                                 temperature=temperature, history=convo,
                                 json_schema=json_schema_for(schema))
            convo = convo + [Message("user", prompt), Message("assistant", text)]
            try:
                return validate(extract_json(text), schema)
            except (LLMError, ValidationError) as exc:
                last_err = str(exc)[:400]
                if attempt >= repairs:
                    raise LLMError(
                        f"model output failed validation after {attempt + 1} "
                        f"attempts: {last_err}") from exc
                log.warn("structured output invalid, asking for repair",
                         error=last_err[:160])
                attempt += 1

    # -- classification ------------------------------------------------------
    def classify(self, text: str, labels: list[str], *, system: str = "",
                 task: str = "", context: dict | None = None) -> dict:
        schema = {
            "type": "object",
            "required": ["label", "confidence"],
            "properties": {
                "label": {"type": "string", "enum": labels},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1,
                               "default": 0.5},
                "reason": {"type": "string", "default": ""},
            },
        }
        return self.structured(
            f"Classify the following. Choose exactly one label from "
            f"{labels}.\n\n---\n{text[:6000]}\n---",
            schema, system=system, task=task,
            context={**(context or {}), "text": text, "labels": labels},
            temperature=0.0)


_default: LLM | None = None


def get_llm(store=None) -> LLM:
    global _default
    if _default is None:
        from .store import get_store
        _default = LLM(store=store or get_store())
    return _default


def reset_llm() -> None:
    global _default
    _default = None
