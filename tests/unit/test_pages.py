from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_page_renders():
    r = client.get("/")
    assert r.status_code == 200
    assert "Ask once. Eight AI models answer." in r.text
    assert 'href="/h-bot"' in r.text


def test_hbot_page_renders():
    r = client.get("/h-bot")
    assert r.status_code == 200
    assert "Who's on the other end?" in r.text
    assert "/static/hbot.js" in r.text


def test_static_files_served():
    for path in ("/static/home.css", "/static/hbot.css", "/static/hbot.js", "/static/logo.png", "/static/brian.jpg"):
        assert client.get(path).status_code == 200, path


def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}
