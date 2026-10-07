from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import check as check_api
from app.core.botdetect import detector
from app.core.botdetect.prompt import REPORT_TOOL, SYSTEM_PROMPT
from app.core.usage.limits import Limiter
from app.main import app

client = TestClient(app)

GOOD = {
    "level": "scam",
    "verdict": "This is a scam. Do not click.",
    "kind": "Bank impersonation.",
    "bot": "Almost certainly a machine.",
    "reasons": ["It never names the bank.", "It wants a click.", "It hurries you."],
    "steps": ["Do not click.", "Call the number on your card.", "Delete the text."],
}


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = [] if self.payload is None else [SimpleNamespace(type="tool_use", input=self.payload)]
        return SimpleNamespace(content=content, usage=SimpleNamespace(input_tokens=1500, output_tokens=250))


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.setattr(check_api, "limiter", Limiter(per_minute=5, per_day=25, global_per_day=1000))
    check_api._selftest_cache.update(at=0.0, body=None)


def test_prompt_carries_the_governing_rule():
    assert "An unanticipated message is presumed a scam" in SYSTEM_PROMPT
    assert "\u2014" not in SYSTEM_PROMPT and "\u2013" not in SYSTEM_PROMPT
    assert REPORT_TOOL["input_schema"]["properties"]["reasons"]["maxItems"] == 3


def test_assess_sends_message_as_data_and_forces_the_report_tool():
    fake = FakeClient(GOOD)
    result = detector.assess("Click here now", client=fake)
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "report"}
    assert call["messages"][0]["content"] == "<message>\nClick here now\n</message>"
    assert result.level == "scam" and result.verdict == GOOD["verdict"]
    assert result.cost_usd == pytest.approx(0.00275)


def test_house_style_is_enforced_on_the_way_out():
    messy = dict(GOOD, verdict="This is a scam \u2014 do not click.", reasons=["a", "b", "c", "d"], level="made_up")
    result = detector.build_assessment(messy)
    assert "\u2014" not in result.verdict and result.verdict == "This is a scam, do not click."
    assert len(result.reasons) == 3
    assert result.level == "presumed_scam"


def test_model_failure_becomes_detector_unavailable():
    with pytest.raises(detector.DetectorUnavailable):
        detector.assess("x", client=FakeClient(error=RuntimeError("boom")))
    with pytest.raises(detector.DetectorUnavailable):
        detector.assess("x", client=FakeClient(payload=None))
    with pytest.raises(detector.DetectorUnavailable):
        detector.assess("x", client=FakeClient(payload=dict(GOOD, steps=[])))


def test_check_endpoint_returns_assessment(monkeypatch):
    monkeypatch.setattr(detector, "assess", lambda message: detector.build_assessment(GOOD))
    r = client.post("/api/check", json={"message": "Click here now"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "result": GOOD}


def test_check_endpoint_rejects_empty_and_too_long():
    assert client.post("/api/check", json={"message": "   "}).status_code == 400
    assert client.post("/api/check", json={"message": "x" * 6001}).status_code == 413


def test_check_endpoint_falls_back_when_model_is_down(monkeypatch):
    def down(message):
        raise detector.DetectorUnavailable("down")

    monkeypatch.setattr(detector, "assess", down)
    r = client.post("/api/check", json={"message": "hello"})
    assert r.status_code == 503 and r.json() == {"ok": False, "reason": "unavailable"}


def test_no_key_means_fallback_not_a_crash(monkeypatch):
    monkeypatch.setattr(detector.get_settings(), "anthropic_api_key", "")
    r = client.post("/api/check", json={"message": "hello"})
    assert r.status_code == 503


def test_per_visitor_minute_limit(monkeypatch):
    monkeypatch.setattr(detector, "assess", lambda message: detector.build_assessment(GOOD))
    codes = [client.post("/api/check", json={"message": "hi"}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_limiter_daily_and_global_ceilings():
    now = [1_000_000.0]
    lim = Limiter(per_minute=100, per_day=3, global_per_day=5, clock=lambda: now[0])
    assert [lim.allow("a")[0] for _ in range(4)] == [True, True, True, False]
    assert lim.allow("a")[1] == "daily"
    assert lim.allow("b")[0] and lim.allow("c")[0]
    assert lim.allow("d") == (False, "busy")
    now[0] += 86400
    assert lim.allow("a")[0]


def test_selftest_reports_cost_and_is_cached(monkeypatch):
    calls = []

    def fake(message):
        calls.append(message)
        return detector.build_assessment(GOOD, input_tokens=1500, output_tokens=250)

    monkeypatch.setattr(detector, "assess", fake)
    first = client.get("/api/selftest").json()
    assert first["passed"] == first["total"] == len(check_api.SELFTEST_MESSAGES)
    assert first["cost_usd_per_check"] == pytest.approx(0.00275)
    second = client.get("/api/selftest").json()
    assert second["cached"] is True and len(calls) == len(check_api.SELFTEST_MESSAGES)


def test_request_matches_the_installed_sdk():
    """The first live deploy failed because the SDK no longer accepts every older argument."""
    import inspect

    from anthropic.resources.messages import Messages

    fake = FakeClient(GOOD)
    detector.assess("hello", client=fake)
    inspect.signature(Messages.create).bind(None, **fake.calls[0])


def test_keycheck_reports_shape_and_never_the_key(monkeypatch):
    secret = "sk-ant-api03-" + "Z" * 40
    monkeypatch.setattr(check_api._settings, "anthropic_api_key", " " + secret + "\n")
    r = client.get("/api/keycheck")
    body = r.json()
    assert body["starts_with_sk_ant"] is True and body["length"] == len(secret) and body["had_outer_spaces"] is True
    assert secret not in r.text and "ZZZZ" not in r.text
    monkeypatch.setattr(check_api._settings, "anthropic_api_key", "sk-proj-abc")
    assert client.get("/api/keycheck").json()["looks_like"] == "an OpenAI-style key"
