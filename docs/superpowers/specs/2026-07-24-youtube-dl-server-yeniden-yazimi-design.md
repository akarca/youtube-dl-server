# youtube-dl-server Yeniden Yazımı - Tasarım

**Tarih:** 2026-07-24
**Durum:** Onaylandı
**Hedef:** Mevcut `youtube-dl-server.py`'yi güncel kütüphanelerle sıfırdan yazmak.

## Amaç

`GET /q?url=<youtube_url>` isteğine gelen videoyu `yt-dlp` ile indirip mp3'e çevirip `/root/music/` klasörüne yazan minimal bir JSON API.

## Kapsam

### Kapsam içi
- GET `/` — servis bilgisi
- GET `/q?url=<URL>` — arka planda indirme (BackgroundTask)
- GET `/healthz` — basit sağlık kontrolü
- `/root/web/cookies.txt` varsa yt-dlp'ye otomatik olarak geçirilmesi
- Playlist URL'lerinde tek video indirilmesi (`noplaylist: True`)

### Kapsam dışı
- HTML arayüzü (templates/index.html kaldırılır)
- `/youtube-dl/update` endpoint'i (yt-dlp artık kendini güncellemez; deploy sırasında pip ile güncellenecek)
- Format seçimi parametresi (sabit mp3)
- Video format dönüşümü (sadece ses)

## Mimari

Tek dosya: `youtube-dl-server.py`. Starlette + uvicorn + yt-dlp.

```
HTTP isteği
   │
   ▼
Starlette Route (/q)
   │
   ├── JSONResponse({"success": true, "url": ...}) ──► istemciye 200
   │
   └── BackgroundTask(download, url) ──► arka planda
          │
          ▼
       yt-dlp (bestaudio → mp3 postprocess → /root/music/)
```

## Bileşenler

### `youtube-dl-server.py`
- `app` — Starlette uygulaması, üç route
- `index(request)` — servis bilgisi JSON
- `healthz(request)` — `{"ok": true}`
- `q_put(request)` — URL doğrular, BackgroundTask ile indirir
- `download(url)` — yt-dlp options hazırlayıp `ydl.download([url])` çağırır; hata exception fırlatır
- `build_ydl_options()` — sabit options; `cookies.txt` varsa `cookiefile` ekler

### `requirements.txt`
- `starlette>=0.41`
- `uvicorn[standard]>=0.32`
- `yt-dlp>=2025.1.1`

### `.env`
Mevcut içerik korunur (`YDL_UPDATE_TIME=False`); yeni kod bu değişkeni kullanmaz, sadece geriye dönük bilgi olarak kalır.

## Endpoint'ler

| Method | Path | Yanıt |
|--------|------|-------|
| GET | `/` | `{"service": "youtube-dl-server", "yt_dlp_version": "..."}` |
| GET | `/q?url=<URL>` | `{"success": true, "url": "<URL>"}` (indirme arka planda) |
| GET | `/healthz` | `{"ok": true}` |

### Hata davranışı
- `url` query param eksik → `400 {"success": false, "error": "missing url"}`
- `url` boş string → `400 {"success": false, "error": "missing url"}`
- yt-dlp hatası → BackgroundTask içinde exception fırlatır, Starlette log'a yazar; istemciye 200 döndürülmüştür

## yt-dlp Options

```python
{
    "format": "bestaudio/best",
    "outtmpl": "/root/music/%(title).200s [%(id)s].%(ext)s",
    "noplaylist": True,
    "updatetime": False,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    # aşağıdaki sadece dosya varsa eklenir:
    "cookiefile": "/root/web/cookies.txt",
}
```

### Cookie davranışı
- `os.path.isfile("/root/web/cookies.txt")` → `True` ise options'a `cookiefile` eklenir
- Dosya yoksa eklenmez; yt-dlp anonim indirir

## Çalıştırma

```bash
python -m uvicorn youtube-dl-server:app --port 8123 --host 0.0.0.0
```

Mevcut README'deki komutla birebir aynı, değişiklik yok.

## Test stratejisi

Manuel doğrulama (CLAUDE.md'deki deploy akışıyla):
1. Lokal `python -m uvicorn youtube-dl-server:app` ile servis ayağa kalkıyor mu
2. `curl localhost:8123/healthz` → `{"ok": true}`
3. `curl 'localhost:8123/q?url=https://www.youtube.com/watch?v=<video_id>'` → `{"success": true}`
4. `/root/music/` altında mp3 dosyası oluştu mu
5. `git push` + `fab deploy` ile sunucuya deploy

## Göç (Migration)

- `templates/` dizini silinir (`index.html` dahil)
- `youtube-dl-server.png` silinir (artık HTML arayüzü yok)
- `youtube-dl-server.py` baştan yazılır
- `requirements.txt` sadeleştirilir (jinja2, aiofiles, python-multipart çıkar)
- `.env` korunur (geriye dönük bilgi)
- `README.md` sadeleştirilir (artık starlette/yt-dlp/cookies.txt davranışı belgelendirilir)

## Silinen/Bağlantısız Özellikler

| Eski | Yeni | Sebep |
|------|------|-------|
| `/youtube-dl` HTML UI | yok | Sadece API |
| `/youtube-dl/update` | yok | yt-dlp artık kendini güncellemez; deploy pipeline'da pip ile güncellenecek |
| `format` query param | yok | Sabit mp3 |
| `recode_video` postprocessor | yok | Sadece ses |
| `YDL_*` env değişkenleri | okunmaz | Sabit davranış yeterli |
