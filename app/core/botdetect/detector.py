"""Reads one pasted message with the AI model and returns the assessment.

The message text is never logged or stored here.
"""

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


def _clean_list(items, limit: int = 3) -> list[str]:
    out = [_clean(i) for i in (items or []) if str(i).strip()]
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


def _client():
    import anthropic

    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        raise DetectorUnavailable("no API key configured")
    return anthropic.Anthropic(api_key=key, timeout=25.0, max_retries=1)


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
