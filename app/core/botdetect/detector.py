"""Reads one pasted message with the AI model and returns the assessment.

The message text is never logged or stored here.
"""

import json
import re
from dataclasses import dataclass

from app.config import get_settings
from app.core.botdetect.prompt import REPORT_TOOL, SYSTEM_PROMPT

LEVELS = ("scam", "presumed_scam", "low_risk")

# Published price for Claude Haiku 4.5, US dollars per million tokens (checked 2026-10-07).
PRICE_IN_PER_MTOK = 1.00
PRICE_OUT_PER_MTOK = 5.00


class DetectorUnavailable(Exception):
    """The AI model could not be reached or returned something unusable."""


@dataclass
class Assessment:
    level: str
    verdict: str
    kind: str
    bot: str
    reasons: list[str]
    steps: list[str]
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * PRICE_IN_PER_MTOK + self.output_tokens * PRICE_OUT_PER_MTOK) / 1_000_000

    def public(self) -> dict:
        return {
            "level": self.level,
            "verdict": self.verdict,
            "kind": self.kind,
            "bot": self.bot,
            "reasons": self.reasons,
            "steps": self.steps,
        }


def _clean(text: str) -> str:
    """House style: no dashes used as punctuation, single spaces, no markdown marks."""
    text = str(text).replace("\u2014", ", ").replace("\u2013", ", ")
    text = re.sub(r"\s+,", ",", text)
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _as_list(items) -> list:
    """The model sometimes sends a list as one string: JSON text, or lines. Never split it into letters."""
    if items is None:
        return []
    if isinstance(items, str):
        text = items.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except ValueError:
                pass
        lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln) for ln in text.splitlines()]
        return [ln for ln in lines if ln.strip()]
    if isinstance(items, (list, tuple)):
        return list(items)
    return [items]


def _clean_list(items, limit: int = 3) -> list[str]:
    out = [_clean(i) for i in _as_list(items) if str(i).strip()]
    return out[:limit]


def build_assessment(data: dict, input_tokens: int = 0, output_tokens: int = 0) -> Assessment:
    level = data.get("level")
    if level not in LEVELS:
        level = "presumed_scam"
    result = Assessment(
        level=level,
        verdict=_clean(data.get("verdict", "")),
        kind=_clean(data.get("kind", "")),
        bot=_clean(data.get("bot", "")),
        reasons=_clean_list(data.get("reasons")),
        steps=_clean_list(data.get("steps")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    if not (result.verdict and result.bot and result.reasons and result.steps):
        raise DetectorUnavailable("incomplete assessment")
    return result


_AUTH_MODES = ("x-api-key", "bearer")
_auth_mode_cache: dict[str, str] = {}


def _make_client(key: str, mode: str, timeout: float = 25.0, max_retries: int = 1):
    """The provider accepts a key either in the x-api-key header or as a bearer token."""
    import anthropic

    if mode == "bearer":
        return anthropic.Anthropic(auth_token=key, api_key=None, timeout=timeout, max_retries=max_retries)
    return anthropic.Anthropic(api_key=key, timeout=timeout, max_retries=max_retries)


def probe_key(key: str) -> dict:
    """Ask the provider, both ways, whether it accepts the key. Listing models is free."""
    results = {}
    for mode in _AUTH_MODES:
        try:
            _make_client(key, mode, timeout=15.0, max_retries=0).models.list(limit=1)
            results[mode] = "accepted"
        except Exception as exc:
            said = str(getattr(exc, "message", "") or exc).replace(key, "[key]")
            results[mode] = f"{type(exc).__name__}: {said[:220]}"
    return results


def _auth_mode(key: str) -> str:
    if key not in _auth_mode_cache:
        results = probe_key(key)
        _auth_mode_cache[key] = next((m for m in _AUTH_MODES if results[m] == "accepted"), "x-api-key")
    return _auth_mode_cache[key]


def _client():
    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        raise DetectorUnavailable("no API key configured")
    return _make_client(key, _auth_mode(key))


def assess(message: str, client=None) -> Assessment:
    settings = get_settings()
    client = client or _client()
    try:
        response = client.messages.create(
            model=settings.primary_model_name,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            tools=[REPORT_TOOL],
            tool_choice={"type": "tool", "name": "report"},
            messages=[{"role": "user", "content": f"<message>\n{message}\n</message>"}],
        )
    except DetectorUnavailable:
        raise
    except Exception as exc:  # network, auth, rate limit, model errors
        raise DetectorUnavailable(type(exc).__name__) from None

    block = next((b for b in response.content if getattr(b, "type", "") == "tool_use"), None)
    if block is None or not isinstance(block.input, dict):
        raise DetectorUnavailable("no assessment returned")
    usage = getattr(response, "usage", None)
    return build_assessment(
        block.input,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )
