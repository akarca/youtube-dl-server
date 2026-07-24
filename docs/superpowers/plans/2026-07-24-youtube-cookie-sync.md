# YouTube Cookie Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Firefox extension üzerinden YouTube cookie'lerini youtube-dl-server'a otomatik göndermek ve `/root/web/cookies.txt`'yi güncel tutmak.

**Architecture:** Sunucu `POST /youtube-dl/cookies` endpoint'i (bearer token korumalı) browser.cookies API formatındaki cookie listesini alıp `YoutubeDLCookieJar` ile Netscape formatında `/root/web/cookies.txt`'ye yazar. Firefox extension her dakika `cookies.getAll({domain: ".youtube.com"})` çağırıp POST eder. Token `/root/web/.env`'den runtime'da okunur (supervisor config değişikliği gerektirmez).

**Tech Stack:** Starlette (mevcut), `yt_dlp.cookies.YoutubeDLCookieJar` (yt-dlp[default] ile birlikte), Firefox WebExtensions API (manifest v2).

---

## Dosya Yapısı

| Dosya | Değişiklik |
|-------|-----------|
| `youtube-dl-server.py` | MODIFY: yeni route + token loader + `_build_cookie` helper |
| `.env` | MODIFY: `YDL_COOKIE_SYNC_TOKEN` ekle (gitignore) |
| `cookie-sync/manifest.json` | CREATE |
| `cookie-sync/background.js` | CREATE (token placeholder) |
| `cookie-sync/popup.html` | CREATE |
| `cookie-sync/popup.js` | CREATE |
| `cookie-sync/icon.png` | CREATE (16x16 PNG placeholder) |
| `README.md` | MODIFY: extension kurulum notu |

---

### Task 1: Token üret + .env güncelle

**Files:**
- Modify: `.env`

- [ ] **Step 1: Token üret**

```bash
cd /Users/serdar/workspace/youtube-dl-server
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Üretilen token'ı not al — ileride birden fazla yerde lazım olacak. `<YDL_COOKIE_SYNC_TOKEN>` placeholder'ı bundan sonra senin ürettiğin gerçek değeri ifade ediyor.

- [ ] **Step 2: .env'i güncelle**

Mevcut `.env`:

```
YDL_UPDATE_TIME=False
YDL_OUTPUT_TEMPLATE=/root/music/%(title)s.%(ext)s
YDL_FORMAT="mp4"
YDL_EXTRACT_AUDIO_FORMAT="m4a"
```

Şu hale getir:

```
YDL_UPDATE_TIME=False
YDL_OUTPUT_TEMPLATE=/root/music/%(title)s.%(ext)s
YDL_FORMAT="mp4"
YDL_EXTRACT_AUDIO_FORMAT="m4a"
YDL_COOKIE_SYNC_TOKEN=<YDL_COOKIE_SYNC_TOKEN>
```

- [ ] **Step 3: .env commit edilmez**

`.env` `.gitignore`'da. Commit etmiyoruz; sadece lokal + sunucuda olacak.

---

### Task 2: Server'a save_cookies endpoint'i ekle

**Files:**
- Modify: `youtube-dl-server.py`

- [ ] **Step 1: youtube-dl-server.py'yi şu hale getir**

Use Write tool to overwrite the entire file. Read it first to confirm current state.

```python
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
```

- [ ] **Step 2: Sentaks kontrolü**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','youtube-dl-server.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('app:', m.app); print('token loaded:', bool(m._load_cookie_sync_token()))"
```

Expected:
- `app: <starlette.applications.Starlette object>`
- `token loaded: True`

- [ ] **Step 3: Lokal test — endpoint çalışıyor mu**

```bash
cd /Users/serdar/workspace/youtube-dl-server
mkdir -p /tmp/cookie-test
pyenv exec python -c "
import importlib.util
import uvicorn
spec = importlib.util.spec_from_file_location('m', 'youtube-dl-server.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.COOKIES_PATH = '/tmp/cookie-test/cookies.txt'
uvicorn.run(m.app, host='127.0.0.1', port=8124, log_level='warning')
" &
SERVER_PID=$!
sleep 3

TOKEN=\$(grep ^YDL_COOKIE_SYNC_TOKEN /Users/serdar/workspace/youtube-dl-server/.env | cut -d= -f2)

echo "--- 401 (no auth) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8124/youtube-dl/cookies -H "Content-Type: application/json" -d '{"cookies":[]}'
echo ""

echo "--- 401 (wrong token) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8124/youtube-dl/cookies -H "Authorization: Bearer wrong" -H "Content-Type: application/json" -d '{"cookies":[]}'
echo ""

echo "--- 400 (bad JSON) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8124/youtube-dl/cookies -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d 'not-json'
echo ""

echo "--- 200 (valid cookies) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8124/youtube-dl/cookies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cookies":[{"name":"VISITOR_PRIVACY_METADATA","value":"CgJ","domain":".youtube.com","path":"/","secure":true,"httpOnly":false,"sameSite":"no_restriction","expirationDate":1800478328.5},{"name":"PREF","value":"f6=40000000","domain":".youtube.com","path":"/","secure":false,"httpOnly":false,"sameSite":"lax","expirationDate":1788472349}]}'
echo ""

echo "--- cookies.txt contents ---"
cat /tmp/cookie-test/cookies.txt

kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

Expected:
- 401 (no auth) → `{"error":"Unauthorized"}` HTTP 401
- 401 (wrong token) → `{"error":"Unauthorized"}` HTTP 401
- 400 (bad JSON) → `{"error":"Invalid JSON"}` HTTP 400
- 200 (valid cookies) → `{"success":true,"count":2}` HTTP 200
- `cookies.txt` Netscape formatında 2 entry (VISITOR_PRIVACY_METADATA + PREF)

- [ ] **Step 4: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add youtube-dl-server.py
git commit -m "feat(api): add POST /youtube-dl/cookies endpoint for cookie sync

Accepts browser.cookies API format cookie list, converts via YoutubeDLCookieJar
to Netscape format and writes to /root/web/cookies.txt. Bearer token read from
/root/web/.env at request time (no supervisor config changes needed)."
```

---

### Task 3: Extension dosyalarını yaz

**Files:**
- Create: `cookie-sync/manifest.json`
- Create: `cookie-sync/background.js`
- Create: `cookie-sync/popup.html`
- Create: `cookie-sync/popup.js`
- Create: `cookie-sync/icon.png`

- [ ] **Step 1: Dizin oluştur**

```bash
mkdir -p /Users/serdar/workspace/youtube-dl-server/cookie-sync
```

- [ ] **Step 2: manifest.json yaz**

`/Users/serdar/workspace/youtube-dl-server/cookie-sync/manifest.json` içeriği:

```json
{
  "manifest_version": 2,
  "name": "YouTube Cookie Sync",
  "version": "1.0",
  "description": "Auto-sync YouTube cookies to youtubedl-server",
  "permissions": [
    "cookies",
    "storage",
    "alarms",
    "https://*.youtube.com/*",
    "https://youtubedl.nameocean.org/*"
  ],
  "browser_action": {
    "default_popup": "popup.html",
    "default_icon": "icon.png"
  },
  "background": {
    "scripts": ["background.js"]
  },
  "browser_specific_settings": {
    "gecko": {
      "id": "youtube-cookie-sync@nameocean.org"
    }
  }
}
```

- [ ] **Step 3: background.js yaz (placeholder token ile)**

`/Users/serdar/workspace/youtube-dl-server/cookie-sync/background.js` içeriği:

```javascript
const SERVER_URL = "https://youtubedl.nameocean.org/youtube-dl/cookies";
const TOKEN = "PLACEHOLDER_TOKEN";
const INTERVAL_MINUTES = 1;

async function syncCookies() {
  try {
    const stores = await browser.cookies.getAllCookieStores();
    const cookieMap = new Map();

    for (const store of stores) {
      const cookies = await browser.cookies.getAll({
        domain: ".youtube.com",
        storeId: store.id,
      });
      for (const c of cookies) {
        cookieMap.set(c.domain + "|" + c.name, c);
      }
    }

    const allCookies = Array.from(cookieMap.values());

    if (allCookies.length === 0) {
      await browser.storage.local.set({
        lastError: new Date().toLocaleTimeString() + " — No YouTube cookies found",
      });
      return;
    }

    const resp = await fetch(SERVER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + TOKEN,
      },
      body: JSON.stringify({ cookies: allCookies }),
    });

    const ts = new Date().toLocaleTimeString();
    if (resp.ok) {
      const data = await resp.json();
      await browser.storage.local.set({
        lastSync: ts + " — " + data.count + " cookies synced",
        lastError: "",
      });
    } else {
      const data = await resp.json().catch(() => ({}));
      await browser.storage.local.set({
        lastError: ts + " — " + (data.error || resp.statusText),
      });
    }
  } catch (err) {
    await browser.storage.local.set({
      lastError: new Date().toLocaleTimeString() + " — " + err.message,
    });
  }
}

browser.runtime.onMessage.addListener((msg) => {
  if (msg.action === "sync_now") syncCookies();
});

syncCookies();
browser.alarms.create("cookie-sync", { periodInMinutes: INTERVAL_MINUTES });
browser.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "cookie-sync") syncCookies();
});
```

- [ ] **Step 4: popup.html yaz**

`/Users/serdar/workspace/youtube-dl-server/cookie-sync/popup.html` içeriği:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { width: 280px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 16px; margin: 0; }
  h3 { margin: 0 0 12px; font-size: 14px; }
  button { width: 100%; padding: 10px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; color: white; background: #dc2626; margin-bottom: 10px; }
  button:hover { background: #b91c1c; }
  #status { font-size: 11px; line-height: 1.5; }
  .ok { color: #059669; }
  .err { color: #dc2626; }
  .muted { color: #9ca3af; font-size: 11px; text-align: center; }
</style>
</head>
<body>
  <h3>YouTube Cookie Sync</h3>
  <button id="sync">Sync Now</button>
  <div id="status">Loading...</div>
  <div class="muted">Auto-sync every 1 min</div>
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 5: popup.js yaz**

`/Users/serdar/workspace/youtube-dl-server/cookie-sync/popup.js` içeriği:

```javascript
document.addEventListener("DOMContentLoaded", async () => {
  const data = await browser.storage.local.get(["lastSync", "lastError"]);
  updateStatus(data);
});

browser.storage.onChanged.addListener(() => {
  browser.storage.local.get(["lastSync", "lastError"]).then(updateStatus);
});

function updateStatus(data) {
  const el = document.getElementById("status");
  let html = "";
  if (data.lastSync) html += `<div class="ok">${data.lastSync}</div>`;
  if (data.lastError) html += `<div class="err">${data.lastError}</div>`;
  if (!data.lastSync && !data.lastError) html = "Waiting for first sync...";
  el.innerHTML = html;
}

document.getElementById("sync").addEventListener("click", () => {
  browser.runtime.sendMessage({ action: "sync_now" });
  document.getElementById("status").innerHTML = '<div class="ok">Syncing...</div>';
});
```

- [ ] **Step 6: icon.png placeholder oluştur (16x16 kırmızı)**

```bash
python3 -c "
import struct, zlib
def make_png(w, h, color):
    sig = b'\x89PNG\r\n\x1a\n'
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes(color) * w
    idat = zlib.compress(raw)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
open('/Users/serdar/workspace/youtube-dl-server/cookie-sync/icon.png', 'wb').write(make_png(16, 16, [220, 38, 38]))
print('icon created')
"
file /Users/serdar/workspace/youtube-dl-server/cookie-sync/icon.png
```

Expected: `PNG image data, 16 x 16, 8-bit RGB, non-interlaced`

- [ ] **Step 7: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add cookie-sync/manifest.json cookie-sync/background.js cookie-sync/popup.html cookie-sync/popup.js cookie-sync/icon.png
git commit -m "feat(extension): add Firefox extension for YouTube cookie sync

Auto-syncs YouTube cookies from all containers to youtubedl-server every
minute. Manual sync via popup. PLACEHOLDER_TOKEN in background.js must be
replaced with the actual YDL_COOKIE_SYNC_TOKEN before use."
```

---

### Task 4: Token'ı extension'a enjekte et

**Files:**
- Modify: `cookie-sync/background.js`

- [ ] **Step 1: Token'ı replace et**

`background.js`'deki `PLACEHOLDER_TOKEN` yerine Task 1'de ürettiğin gerçek token'ı koy:

```bash
cd /Users/serdar/workspace/youtube-dl-server
# TOKEN_DEGER'i kendi token'ınla değiştir
sed -i '' 's|PLACEHOLDER_TOKEN|TOKEN_DEGER|' cookie-sync/background.js
grep TOKEN cookie-sync/background.js | head -1
```

Expected: `const TOKEN = "TOKEN_DEGER";`

- [ ] **Step 2: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add cookie-sync/background.js
git commit -m "chore(extension): inject actual cookie sync token"
```

**Güvenlik notu:** Token repoya girerse herkes okuyabilir. Trade-off kabul edildi (spec'inde): token rotate edilebilir, cookie sync saldırı yüzeyi sadece YouTube cookie'lerini kabul etmek, başka risk yok.

---

### Task 5: README'yi güncelle

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README'ye extension bölümü ekle**

Mevcut `README.md`'in sonuna şu bölümü ekle:

```markdown
## Cookie Sync (Firefox Extension)

YouTube sık sık bot koruması tetikler; oturum cookie'leri sayesinde yt-dlp güvenilir şekilde indirir. `cookie-sync/` dizinindeki Firefox extension'ı her dakika YouTube cookie'lerini sunucuya POST eder.

### Kurulum

1. Firefox'ta `about:debugging` → "This Firefox" → "Load Temporary Add-on"
2. `cookie-sync/manifest.json` dosyasını seç
3. Extension aktif olur, toolbar'da görünür
4. Popup'taki "Sync Now" butonuyla manuel tetikleyebilirsin

### Token

`cookie-sync/background.js` içindeki `TOKEN` değişkeni, sunucudaki `YDL_COOKIE_SYNC_TOKEN` env değişkeniyle eşleşmeli. Yeni sunucu deploy'unda token rotate edildiğinde extension dosyasını da güncelle.

### Nasıl Çalışır

- Extension her dakika tüm Firefox container'lardan `.youtube.com` cookie'lerini toplar
- `POST /youtube-dl/cookies` endpoint'ine bearer token ile gönderir
- Sunucu `YoutubeDLCookieJar` ile Netscape formatına çevirip `/root/web/cookies.txt` üzerine yazar
- yt-dlp yeni indirmelerde otomatik olarak güncel cookie'leri kullanır
```

- [ ] **Step 2: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add README.md
git commit -m "docs: document cookie sync extension"
```

---

### Task 6: Deploy + sunucuda doğrulama

**Files:** yok

- [ ] **Step 1: fab deploy**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec fab deploy
```

Expected: `git push` → `git pull` → `pip install` (no-op) → `setup` (no-op) → `supervisorctl restart youtubedl`.

- [ ] **Step 2: Sunucuda .env'i güncelle**

`.env` repoda ignore edildiği için sunucuda manual eklenir:

```bash
ssh music "grep -q YDL_COOKIE_SYNC_TOKEN /root/web/.env || echo 'YDL_COOKIE_SYNC_TOKEN=TOKEN_DEGER' >> /root/web/.env"
ssh music "cat /root/web/.env"
```

Expected: 5 satır, son satır `YDL_COOKIE_SYNC_TOKEN=TOKEN_DEGER`.

- [ ] **Step 3: Sunucuda endpoint'i doğrula**

```bash
TOKEN=$(grep ^YDL_COOKIE_SYNC_TOKEN /Users/serdar/workspace/youtube-dl-server/.env | cut -d= -f2)

echo "--- 200 (valid token) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST https://youtubedl.nameocean.org/youtube-dl/cookies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cookies":[{"name":"TEST","value":"foo","domain":".youtube.com","path":"/","secure":true,"httpOnly":false,"sameSite":"no_restriction","expirationDate":1800000000}]}'
echo ""

echo "--- 401 (wrong token) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST https://youtubedl.nameocean.org/youtube-dl/cookies \
  -H "Authorization: Bearer wrong" \
  -H "Content-Type: application/json" -d '{"cookies":[]}'
```

Expected:
- 200 → `{"success":true,"count":1}` HTTP 200
- 401 → `{"error":"Unauthorized"}` HTTP 401

- [ ] **Step 4: cookies.txt dosyası oluştu mu**

```bash
ssh music "cat /root/web/cookies.txt"
```

Expected: Netscape formatında `TEST` cookie entry.

---

### Task 7: Extension kurulumu (kullanıcı adımı)

Bu task kullanıcı tarafından manuel yapılır. Bot burada duruyor.

- [ ] **Kullanıcı adımı: Firefox'a extension yükle**

1. Firefox'ta `about:debugging` aç
2. "This Firefox" sekmesi → "Load Temporary Add-on"
3. `/Users/serdar/workspace/youtube-dl-server/cookie-sync/manifest.json` seç
4. Extension toolbar'da görünür
5. YouTube'a giriş yap (youtube.com)
6. Extension simgesine tıkla → "Sync Now"
7. Popup'ta "X cookies synced" mesajı görünmeli

- [ ] **Doğrulama: gerçek cookie sync end-to-end**

Manuel sync sonrası:

```bash
sleep 2
ssh music "wc -l /root/web/cookies.txt; head -5 /root/web/cookies.txt"
echo "---"
curl -s "https://youtubedl.nameocean.org/youtube-dl/q?url=https://www.youtube.com/watch?v=oJltjDAEJJ0" -w "\nHTTP %{http_code}\n"
sleep 15
ssh music "ls -lt /root/music/ | head -3"
```

Expected: cookies.txt 15+ satır (çoklu cookie), mp3 yeni dosya.

---

## Tamamlandı

- `POST /youtube-dl/cookies` endpoint'i bearer token korumalı, .env'den token okur
- `YoutubeDLCookieJar` browser.cookies API formatını Netscape'e çeviriyor
- `cookie-sync/` extension manifest + background + popup hazır
- Token extension'a inject edildi
- README güncellendi
- End-to-end test (gerçek Firefox + YouTube girişi) geçti
