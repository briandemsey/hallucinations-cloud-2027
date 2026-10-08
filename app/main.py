import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import check, health

BASE_DIR = Path(__file__).parent

log = logging.getLogger("uvicorn.error")


def _report_key_at_startup() -> None:
    """Write one line to the service log saying whether the provider accepts the stored key.

    Only the key's shape and the provider's answer are logged, never the key.
    """
    try:
        info = {**check._key_shape(), **check._key_probe()}
        log.info(
            "KEYCHECK accepted=%s key_type=%s length=%s provider_says=%s",
            info.get("accepted"), info.get("key_type"), info.get("length"), info.get("provider_says"),
        )
    except Exception as exc:  # never block startup on this
        log.info("KEYCHECK could not run: %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_report_key_at_startup, daemon=True).start()
    yield


app = FastAPI(title="H-BOTdetector", lifespan=lifespan)
app.include_router(health.router)
app.include_router(check.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/h-bot")
def hbot_redirect():
    return RedirectResponse("/", status_code=308)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /\n"
