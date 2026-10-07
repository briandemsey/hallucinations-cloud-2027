from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import health

BASE_DIR = Path(__file__).parent

app = FastAPI(title="H-BOTdetector")
app.include_router(health.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/h-bot")
def hbot_redirect():
    return RedirectResponse("/", status_code=308)
