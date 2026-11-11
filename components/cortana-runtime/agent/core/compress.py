"""Optional prompt compression for conversation history, via headroom-ai.

Scope, stated precisely because it matters: this compresses only the
*older conversation history* pulled from SQLite before it's prepended to
a request. It never touches the tool results generated during the current
turn.

That boundary is not arbitrary — it's a correctness fix for a real bug I
found while wiring this up. Headroom's default pipeline replaces long
content with a CCR reference token (e.g. `<<ccr:2038b42d43ee,string,10.5KB>>`)
instead of the real text, on the assumption the calling agent can retrieve
the original via a `headroom_retrieve` tool. Cortana's local 3B model has
no such tool and no extra round-trip budget for one. If a fresh `read_pdf`
result got compressed this way, "summarize this PDF" would get back a
reference token instead of the actual text and either hallucinate or
fail — the exact bug class this project has already been bitten by once.
Old history, by contrast, is safe to compress: the model isn't reading it
verbatim to produce this turn's answer, it's just prior context.

Fails silently to "no compression" if headroom-ai isn't installed, or if
compression raises for any reason — this is a latency optimization, never
allowed to be why a chat request fails.
"""

import logging

logger = logging.getLogger(__name__)

_compress_fn = None
_load_attempted = False


def _get_compress_fn():
    global _compress_fn, _load_attempted
    if not _load_attempted:
        _load_attempted = True
        try:
            from headroom import compress as _hc

            _compress_fn = _hc
            logger.info("headroom-ai available — conversation history compression enabled")
        except ImportError:
            logger.info(
                "headroom-ai not installed — history compression disabled. "
                "Install with: pip install headroom-ai"
            )
    return _compress_fn


def compress_history(history: list[dict], *, model: str = "gpt-4o-mini") -> list[dict]:
    """Compresses older conversation turns. Returns `history` unchanged if
    headroom isn't installed, disabled, or too small to bother with."""
    from core.config import settings

    if not settings.headroom_enabled or not history:
        return history

    fn = _get_compress_fn()
    if fn is None:
        return history

    try:
        # protect_recent keeps the last few turns verbatim — the ones most
        # likely to matter for an immediate follow-up ("open it", "the
        # second one") — and only compresses further back than that.
        from headroom import CompressConfig

        result = fn(
            history,
            model=model,
            optimize=True,
            config=CompressConfig(protect_recent=4, min_tokens_to_compress=200),
        )
        if result.tokens_saved > 0:
            logger.info(
                "history compressed: %d -> %d tokens (saved %d)",
                result.tokens_before, result.tokens_after, result.tokens_saved,
            )
        return result.messages
    except Exception as e:  # noqa: BLE001 — never let compression break a chat turn
        logger.warning("history compression failed, sending uncompressed: %s", e)
        return history
