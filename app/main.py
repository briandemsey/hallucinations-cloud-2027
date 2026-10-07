from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import health

BASE_DIR = Path(__file__).parent

app = FastAPI(title="hallucinations.cloud")
app.include_router(health.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active": "home"})


@app.get("/h-bot", response_class=HTMLResponse)
def hbot(request: Request):
    return templates.TemplateResponse(request, "hbot.html", {"active": "hbot"})
