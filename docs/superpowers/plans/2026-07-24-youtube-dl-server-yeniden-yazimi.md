# youtube-dl-server Yeniden Yazımı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mevcut `youtube-dl-server.py`'yi güncel Starlette + yt-dlp ile sıfırdan yazmak; `GET /q?url=...` mp3 indirip `/root/music/`'a kaydetsin, varsa `/root/web/cookies.txt` kullansın.

**Architecture:** Tek dosyalık Starlette uygulaması. `/q` endpoint'i hemen 200 döner, indirmeyi BackgroundTask'e bırakır. yt-dlp options sabit: bestaudio → mp3 postprocess, `/root/music/`, `noplaylist: True`. `cookies.txt` dosya varsa `cookiefile` eklenir, yoksa yt-dlp anonim indirir.

**Tech Stack:** Python 3.11+, starlette>=0.41, uvicorn[standard]>=0.32, yt-dlp>=2025.1.1.

---

## Dosya Yapısı

| Dosya | Sorumluluk |
|-------|------------|
| `youtube-dl-server.py` | Starlette app, üç route, indirme fonksiyonu |
| `requirements.txt` | Üç bağımlılık (starlette, uvicorn, yt-dlp) |
| `README.md` | Çalıştırma + endpoint belgelendirmesi |
| `docs/superpowers/specs/2026-07-24-youtube-dl-server-yeniden-yazimi-design.md` | Tasarım (zaten var) |

Silinenler: `templates/index.html`, `templates/`, `youtube-dl-server.png`.

---

### Task 1: requirements.txt'i sadeleştir

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: requirements.txt'i güncelle**

Tüm içeriği şu satırlarla değiştir:

```
starlette>=0.41
uvicorn[standard]>=0.32
yt-dlp>=2025.1.1
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore(deps): bump starlette, uvicorn, yt-dlp; drop jinja2/aiofiles/multipart"
```

---

### Task 2: youtube-dl-server.py'i baştan yaz

**Files:**
- Create: `youtube-dl-server.py` (mevcut dosyanın üzerine yazılır)

- [ ] **Step 1: Mevcut dosyayı sil, yeniden oluştur**

`youtube-dl-server.py` içeriğini tamamen şununla değiştir:

```python
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
```

- [ ] **Step 2: Sentaks kontrolü**

```bash
python -c "import youtube_dl_server; print('ok')"
```

Eğer modül ismi hata verirse (tire içerdiği için), bu komutu çalıştır:

```bash
python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','youtube-dl-server.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('app:', m.app)"
```

Expected: `app: <starlette.applications.Starlette object>` veya `ok`.

- [ ] **Step 3: Servisi manuel başlat ve üç endpoint'i doğrula**

Üç terminal gerekir. Bunları arka arkaya (background değil) çalıştır ve gözlemle:

Terminal A — sunucuyu başlat:
```bash
python -m uvicorn youtube-dl-server:app --port 8123 --host 127.0.0.1
```

Çıktıda `Uvicorn running on http://127.0.0.1:8123` görmelisin.

Terminal B (yeni sekme/pencere) — sağlık kontrolü:
```bash
curl -s http://127.0.0.1:8123/healthz
```

Expected: `{"ok":true}`

Terminal C — servis bilgisi:
```bash
curl -s http://127.0.0.1:8123/
```

Expected: `{"service":"youtube-dl-server","yt_dlp_version":"2025.x.x"}`

Terminal D — indirme tetikle:
```bash
curl -s "http://127.0.0.1:8123/q?url=https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

Expected: `{"success":true,"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}` (hemen döner)

Terminal A'da loglarda `[download] starting` ve `[download] done` görmelisin. `/root/music/` altında bir mp3 dosyası oluşmalı:
```bash
ls -la /root/music/
```

Sunucuyu durdurmak için Terminal A'da Ctrl+C.

- [ ] **Step 4: Hata senaryosunu doğrula (eksik url)**

```bash
curl -s -w "\nHTTP %{http_code}\n" "http://127.0.0.1:8123/q"
```

Expected:
```
{"success":false,"error":"missing url"}
HTTP 400
```

- [ ] **Step 5: Commit**

```bash
git add youtube-dl-server.py
git commit -m "feat: rewrite youtube-dl-server with current starlette/yt-dlp

- Drop HTML UI, format selection, update endpoint, jinja2/aiofiles/multipart
- /q uses BackgroundTask, returns immediately with success JSON
- yt-dlp options fixed: bestaudio -> mp3 192kbps, /root/music output
- cookies.txt auto-attached only when /root/web/cookies.txt exists
- noplaylist: True so playlist URLs still download single video"
```

---

### Task 3: Eski HTML UI ve screenshot'ı kaldır

**Files:**
- Delete: `templates/index.html`
- Delete: `templates/` (boş kaldıktan sonra)
- Delete: `youtube-dl-server.png`

- [ ] **Step 1: Dosyaları sil**

```bash
rm -rf templates youtube-dl-server.png
```

- [ ] **Step 2: git'ten untrack et**

```bash
git rm -r templates youtube-dl-server.png
```

Expected: dizin ve dosya kaldırılır.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove HTML UI and screenshot (API-only service)"
```

---

### Task 4: README.md'i güncelle

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README'yi sıfırdan yaz**

`README.md` içeriğini tamamen şununla değiştir:

```markdown
# youtube-dl-server

`yt-dlp` üzerine kurulu minimal JSON API. `GET /q?url=<URL>` gelen YouTube (veya diğer desteklenen siteler) videosunu indirir, mp3'e çevirir ve `/root/music/` altına kaydeder.

## Çalıştırma

```bash
python -m uvicorn youtube-dl-server:app --port 8123 --host 0.0.0.0
```

## Endpoint'ler

| Method | Path | Yanıt |
|--------|------|-------|
| GET | `/` | Servis bilgisi ve yt-dlp sürümü |
| GET | `/healthz` | `{"ok": true}` |
| GET | `/q?url=<URL>` | `{"success": true, "url": "<URL>"}` (indirme arka planda) |

### Örnek

```bash
curl 'http://localhost:8123/q?url=https://www.youtube.com/watch?v=oJltjDAEJJ0'
```

## Cookies

`/root/web/cookies.txt` dosyası mevcutsa yt-dlp'ye otomatik olarak geçirilir. Üye olmayan içerik veya yaş doğrulamalı videolar için gereklidir.

## Yapılandırma

`youtube-dl-server.py` içinde sabit ayarlar:
- Çıktı: `/root/music/%(title).200s [%(id)s].%(ext)s`
- Format: `bestaudio/best` → mp3 (192 kbps)
- Playlist: yok sayılır, tek video indirilir
- Cookie dosyası: `/root/web/cookies.txt` (varsa)

## Deploy

`git push` + `fab deploy`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for API-only youtube-dl-server"
```

---

### Task 5: Push ve deploy doğrulaması

**Files:** yok

- [ ] **Step 1: Lokal branch durumunu kontrol et**

```bash
git status
git log --oneline -8
```

Expected: çalışma ağacı temiz, 4 yeni commit var (Task 2'de bazen commit birleşir, sayı farklı olabilir).

- [ ] **Step 2: Push**

```bash
git push
```

- [ ] **Step 3: Sunucuya deploy et**

```bash
fab deploy
```

Bu komut mevcut `fabfile.py` akışını çalıştırır; sunucu reposunu günceller, varsa service'i yeniden başlatır.

- [ ] **Step 4: Sunucuda endpoint'leri doğrula**

```bash
curl -s https://youtubedl.nameocean.org/healthz
curl -s 'https://youtubedl.nameocean.org/q?url=https://www.youtube.com/watch?v=oJltjDAEJJ0'
```

Expected: ilk komut `{"ok":true}`, ikinci komut `{"success":true,"url":"..."}`. Birkaç saniye sonra sunucuda `/root/music/` altında mp3 dosyası görünmeli:

```bash
ssh sunucu 'ls -la /root/music/ | tail -5'
```

(SSH sadece okuma amaçlı — CLAUDE.md kuralı.)

---

## Tamamlandı

Tüm görevler bittiğinde:
- `requirements.txt` sadeleştirilmiş
- `youtube-dl-server.py` Starlette + yt-dlp ile baştan yazılmış
- `templates/` ve `youtube-dl-server.png` kaldırılmış
- `README.md` API odaklı güncellenmiş
- `git push` + `fab deploy` ile sunucu güncellenmiş
- Sunucuda endpoint'ler ve mp3 indirme çalışıyor
