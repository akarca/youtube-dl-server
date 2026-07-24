# YouTube Cookie Sync Tasarımı

**Tarih:** 2026-07-24
**Durum:** Onaylandı
**Hedef:** Firefox extension üzerinden YouTube cookie'lerini youtube-dl-server'a otomatik olarak göndermek, böylece `/root/web/cookies.txt` her zaman güncel olsun.

## Amaç

YouTube sık sık bot koruması için kullanıcı oturum açma gerektiriyor. Cookie'ler eskidiğinde indirmeler başarısız oluyor. Firefox extension her dakika YouTube cookie'lerini alıp sunucuya POST eder; sunucu bunları Netscape formatına çevirip `/root/web/cookies.txt` dosyasına yazar. yt-dlp zaten bu dosyayı kullandığı için indirmeler her zaman güncel oturumla yapılır.

## Kapsam

### Kapsam içi
- **Sunucu**: `POST /youtube-dl/cookies` endpoint'i (bearer token korumalı)
- **Sunucu**: Cookie → `YoutubeDLCookieJar` → `/root/web/cookies.txt` yazma
- **Extension**: `cookie-sync/` dizininde browser extension (manifest v2, Firefox)
- **Extension**: Her dakika + manuel sync popup
- **Token dağıtımı**: `.env`'de `YDL_COOKIE_SYNC_TOKEN`, extension source'unda hard-code

### Kapsam dışı
- Chrome/Chromium desteği (MVP'de gerek yok)
- Çoklu hesap/merge (sadece son sync yazar)
- Cookie şifreleme (storage zaten local; HTTPS zorunlu)
- Eski cookie'leri expiration'a göre temizleme (yt-dlp bunu zaten yapıyor)

## Mimari

```
Firefox Tarayıcı                        youtube-dl-server
    │                                          │
    │ 1. her 1 dakika:                          │
    │    browser.cookies.getAll({domain:        │
    │    ".youtube.com"}, storeId=X)            │
    │                                          │
    │ 2. POST /youtube-dl/cookies              │
    │    Authorization: Bearer <token>          │
    │    {cookies: [...]}                       │
    │ ────────────────────────────────────────► │
    │                                          │
    │                              3. Cookie → http.cookiejar.Cookie
    │                                          │
    │                              4. YoutubeDLCookieJar.save()
    │                                          │
    │ ◄─────────────────────────────────────── │
    │    {success: true, count: N}              │
    │                                          │
    │ 5. Kullanıcı indir:                       │
    │    GET /youtube-dl/q?url=...              │
    │ ────────────────────────────────────────► │
    │                                          │
    │                              6. yt-dlp cookies.txt'yi okur
    │                                  (güncel hali)
    │                                  /root/music/...mp3
```

## Bileşenler

### 1. Sunucu — `youtube-dl-server.py`

Yeni route + yardımcı fonksiyonlar:

```python
COOKIE_SYNC_TOKEN = os.environ.get("YDL_COOKIE_SYNC_TOKEN", "")

async def save_cookies(request: Request) -> JSONResponse:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != COOKIE_SYNC_TOKEN:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = json.loads(request.body)
    except (ValueError, json.JSONDecodeError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    raw_cookies = body.get("cookies", [])
    if not isinstance(raw_cookies, list):
        return JSONResponse({"error": "cookies must be a list"}, status_code=400)

    jar = YoutubeDLCookieJar()
    for c in raw_cookies:
        cookie = _build_cookie(c)
        if cookie is not None:
            jar.set_cookie(cookie)

    Path(COOKIES_PATH).parent.mkdir(parents=True, exist_ok=True)
    jar.save(COOKIES_PATH, ignore_discard=True, ignore_expires=True)

    return JSONResponse({"success": True, "count": len(list(jar))})
```

`_build_cookie`: browser.cookies API alanlarını (name, value, domain, path, secure, httpOnly, expirationDate, sameSite) `http.cookiejar.Cookie` constructor'a uygun şekilde eşler. `expirationDate` (saniye, float) → `expires` (saniye, int). `httpOnly` → cookie'nin başına `#HttpOnly_` prefix ekleme (YoutubeDLCookieJar bunu otomatik yapar).

**Route:** `Route("/youtube-dl/cookies", endpoint=save_cookies, methods=["POST"])`

### 2. Sunucu — `.env`

Mevcut `.env`'e yeni satır:

```
YDL_COOKIE_SYNC_TOKEN=<rastgele-32-karakter-secret>
```

Üretim için: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 3. Extension — `cookie-sync/manifest.json`

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

### 4. Extension — `cookie-sync/background.js`

```javascript
const SERVER_URL = "https://youtubedl.nameocean.org/youtube-dl/cookies";
const TOKEN = "<YDL_COOKIE_SYNC_TOKEN>";  // build sırasında .env'den enjekte edilir
const INTERVAL_MINUTES = 1;

async function syncCookies() {
  try {
    const stores = await browser.cookies.getAllCookieStores();
    let allCookies = [];
    const cookieMap = new Map();

    for (const store of stores) {
      const cookies = await browser.cookies.getAll({
        domain: ".youtube.com",
        storeId: store.id,
      });
      // Her domain+name için sadece son değeri tut (üzerine yaz)
      for (const c of cookies) {
        cookieMap.set(c.domain + "|" + c.name, c);
      }
    }
    allCookies = Array.from(cookieMap.values());

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

### 5. Extension — `popup.html` / `popup.js`

`aiblog`'un pattern'i (basit "Sync Now" butonu + durum).

## Cookie Format Dönüşümü

`browser.cookies.getAll()` döndürür:
```json
{
  "name": "VISITOR_PRIVACY_METADATA",
  "value": "CgJ...",
  "domain": ".youtube.com",
  "path": "/",
  "secure": true,
  "httpOnly": false,
  "sameSite": "no_restriction",
  "expirationDate": 1800478328.5,
  "storeId": "firefox-default"
}
```

`http.cookiejar.Cookie` constructor:
```python
Cookie(
    version=0, name=str, value=str,
    port=None, port_specified=False,
    domain=str, domain_specified=bool, domain_initial_dot=bool,
    path=str, path_specified=bool,
    secure=bool, expires=int_or_None, discard=bool,
    comment=None, comment_url=None, rest={},
    rfc2109=False
)
```

Eşleme:
- `domain`: `.youtube.com` → `domain=".youtube.com"`, `domain_specified=True`, `domain_initial_dot=True`
- `expirationDate`: float → `expires=int(x)` — session cookie ise (no expirationDate) → `expires=None`
- `sameSite`: "no_restriction" → `rest={"SameSite": "none"}`

`YoutubeDLCookieJar.save()` Netscape formatına otomatik yazar (`#HttpOnly_` prefix dahil).

## HTTP API

### POST /youtube-dl/cookies

**Headers:**
- `Authorization: Bearer <YDL_COOKIE_SYNC_TOKEN>`
- `Content-Type: application/json`

**Body:**
```json
{
  "cookies": [
    {"name": "...", "value": "...", "domain": ".youtube.com", "path": "/", "secure": true, "httpOnly": false, "sameSite": "no_restriction", "expirationDate": 1800478328.5},
    ...
  ]
}
```

**Yanıtlar:**
- `200 {"success": true, "count": 42}` — başarılı
- `400 {"error": "Invalid JSON"}` — JSON parse hatası
- `400 {"error": "cookies must be a list"}` — body yanlış
- `401 {"error": "Unauthorized"}` — bearer token yok/yanlış

## Dosya Yapısı

```
youtube-dl-server/
├── youtube-dl-server.py        # MODIFY: yeni route + helper
├── .env                         # MODIFY: YDL_COOKIE_SYNC_TOKEN ekle
├── README.md                    # MODIFY: extension kurulum notları
├── cookie-sync/                 # NEW: extension
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html
│   ├── popup.js
│   └── icon.png
└── ...
```

Yeni pip bağımlılığı yok — `yt_dlp.cookies.YoutubeDLCookieJar` zaten `yt-dlp[default]` ile geliyor.

## Cookie Conflict Stratejisi

Birden fazla Firefox container (Personal, Work, vb.) olabilir. aiblog'da her container ayrı hesap olarak kaydediliyordu; biz tek hesap istiyoruz. **Seçilen strateji:** server tarafında cookie'leri üzerine yaz (en son sync kazanır). Firefox'ta zaten aktif container'dan alınan cookie'ler baskın olur çünkü browser.cookies.getAll her container'ı döner, biz hepsini birleştirip tek jar'a yazarız — yt-dlp mevcut tüm cookie'leri görür, doğru kullanıcıyı otomatik seçer.

**Alternatif (reddedildi):** Container başına dosya. Çok karmaşık, indirirken hangi container'ın kullanılacağı belirsiz.

## Token Üretimi

`fab deploy` script'inde yeni bir `setup` task'ı eklemek yerine, token elle üretilir ve `.env`'e yazılır. Sebep: token rotation ihtiyacı düşük, otomatik üretim senaryo gerektirmez.

Üretim:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Test Stratejisi

### 1. Lokal
- Token `.env`'e yazılır
- `curl -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"cookies":[...]}' http://127.0.0.1:8123/youtube-dl/cookies`
- `/root/web/cookies.txt` dosyası doğru formatta oluşmalı

### 2. Sunucu
- `fab deploy` → sunucu güncellenir
- `curl -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d @test-cookies.json https://youtubedl.nameocean.org/youtube-dl/cookies`
- Sunucuda `cat /root/web/cookies.txt` Netscape formatında

### 3. Extension
- Firefox'a `cookie-sync/` load edilir (geliştirici modunda)
- `about:debugging` → "This Firefox" → "Load Temporary Add-on"
- Sync Now butonu çalışıyor mu?

### 4. End-to-end
- Mozilla Firefox'ta YouTube'a giriş yap
- Extension sync yapar
- `curl 'https://youtubedl.nameocean.org/youtube-dl/q?url=...'` → başarı, mp3 oluşur

## Göç

Deployment sırası:
1. Sunucu tarafı (kod + .env) deploy edilir, token `.env`'e eklenir
2. `/youtube-dl/cookies` endpoint'i hazır
3. Extension kullanıcı tarafından kurulur, token extension source'unda set edilir
4. End-to-end test

Mevcut `/root/web/cookies.txt` zaten var; yeni flow onu üzerine yazacak. Sorun değil — yeni cookie'ler daha güncel.
