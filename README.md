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
