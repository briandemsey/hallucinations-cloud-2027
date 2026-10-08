from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_detector_is_the_home_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "Who's on the other end?" in r.text
    assert "/static/hbot.js" in r.text


def test_step_one_shows_only_the_detector():
    text = client.get("/").text
    for banned in ("Hallucinations.cloud", "H-LLM", "Multi-Model", "eight"):
        assert banned not in text, banned


def test_substack_and_book_tabs_present():
    text = client.get("/").text
    assert "https://brianrdemsey.substack.com" in text
    assert "The Book" in text


def test_old_address_redirects():
    r = client.get("/h-bot", follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"] == "/"


def test_static_files_served():
    for path in ("/static/site.css", "/static/hbot.js", "/static/logo.png", "/static/brian.jpg"):
        assert client.get(path).status_code == 200, path


def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_robots_allows_everything():
    r = client.get("/robots.txt")
    assert r.status_code == 200 and "Allow: /" in r.text
