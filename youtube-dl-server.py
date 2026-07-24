import json
import os
from http.cookiejar import Cookie
from pathlib import Path

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from yt_dlp import YoutubeDL
from yt_dlp import version as yt_dlp_version
from yt_dlp.cookies import YoutubeDLCookieJar

COOKIES_PATH = "/root/web/cookies.txt"
OUTPUT_DIR = "/root/music"
OUTPUT_TEMPLATE = f"{OUTPUT_DIR}/%(title).200s [%(id)s].%(ext)s"
DENO_PATH = "/root/.deno/bin/deno"
ENV_FILE = "/root/web/.env"


def _load_cookie_sync_token() -> str:
    """Read YDL_COOKIE_SYNC_TOKEN from /root/web/.env. Idempotent at runtime."""
    try:
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("YDL_COOKIE_SYNC_TOKEN="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return ""


def build_ydl_options() -> dict:
    options: dict = {
        "format": "bestaudio/best",
        "outtmpl": OUTPUT_TEMPLATE,
        "noplaylist": True,
        "updatetime": False,
        "js_runtimes": {"deno": {"path": DENO_PATH}},
        "remote_components": {"ejs:github"},
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if os.path.isfile(COOKIES_PATH):
        options["cookiefile"] = COOKIES_PATH
    return options


def download(url: str) -> None:
    options = build_ydl_options()
    print(f"[download] starting url={url} options={options}")
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    with YoutubeDL(options) as ydl:
        ydl.download([url])
    print(f"[download] done url={url}")


def _build_cookie(c: dict) -> Cookie | None:
    """Convert a browser.cookies API cookie dict to http.cookiejar.Cookie."""
    name = c.get("name")
    value = c.get("value", "")
    domain = c.get("domain", "")
    path = c.get("path", "/")
    if not name or not domain:
        return None

    expires = c.get("expirationDate")
    if expires is not None:
        expires = int(expires)

    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=bool(path),
        secure=bool(c.get("secure", False)),
        expires=expires,
        discard=False,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": ""} if c.get("httpOnly") else {},
        rfc2109=False,
    )


async def save_cookies(request: Request) -> JSONResponse:
    expected = _load_cookie_sync_token()
    auth = request.headers.get("Authorization", "")
    if not expected or not auth.startswith("Bearer ") or auth[7:] != expected:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = json.loads(await request.body())
    except (ValueError, json.JSONDecodeError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    raw_cookies = body.get("cookies", [])
    if not isinstance(raw_cookies, list):
        return JSONResponse({"error": "cookies must be a list"}, status_code=400)

    jar = YoutubeDLCookieJar()
    for c in raw_cookies:
        if not isinstance(c, dict):
            continue
        cookie = _build_cookie(c)
        if cookie is not None:
            jar.set_cookie(cookie)

    Path(COOKIES_PATH).parent.mkdir(parents=True, exist_ok=True)
    jar.save(COOKIES_PATH, ignore_discard=True, ignore_expires=True)

    return JSONResponse({"success": True, "count": len(list(jar))})


async def index(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "service": "youtube-dl-server",
            "yt_dlp_version": yt_dlp_version.__version__,
        }
    )


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


async def q_put(request: Request) -> JSONResponse:
    url = request.query_params.get("url", "").strip()
    if not url:
        return JSONResponse(
            {"success": False, "error": "missing url"},
            status_code=400,
        )
    print(f"[q] enqueued url={url}")
    task = BackgroundTask(download, url)
    return JSONResponse({"success": True, "url": url}, background=task)


routes = [
    Route("/", endpoint=index),
    Route("/healthz", endpoint=healthz),
    Route("/youtube-dl/q", endpoint=q_put, methods=["GET"]),
    Route("/youtube-dl/cookies", endpoint=save_cookies, methods=["POST"]),
    Route("/q", endpoint=q_put, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes)
