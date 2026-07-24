import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from yt_dlp import YoutubeDL
from yt_dlp import version as yt_dlp_version

COOKIES_PATH = "/root/web/cookies.txt"
OUTPUT_DIR = "/root/music"
OUTPUT_TEMPLATE = f"{OUTPUT_DIR}/%(title).200s [%(id)s].%(ext)s"


def build_ydl_options() -> dict:
    options: dict = {
        "format": "bestaudio/best",
        "outtmpl": OUTPUT_TEMPLATE,
        "noplaylist": True,
        "updatetime": False,
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
    Route("/q", endpoint=q_put, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes)
