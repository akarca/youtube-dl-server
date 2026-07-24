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
| GET | `/youtube-dl/q?url=<URL>` | `{"success": true, "url": "<URL>"}` (indirme arka planda) |
| GET | `/q?url=<URL>` | `/youtube-dl/q` ile aynı (geriye uyumluluk) |
| POST | `/youtube-dl/cookies` | Bearer token korumalı, browser.cookies API formatında cookie listesi alır, `/root/web/cookies.txt` üzerine yazar |

### Örnek

```bash
curl 'http://localhost:8123/youtube-dl/q?url=https://www.youtube.com/watch?v=oJltjDAEJJ0'
```

## Cookies

`/root/web/cookies.txt` dosyası mevcutsa yt-dlp'ye otomatik olarak geçirilir. Üye olmayan içerik veya yaş doğrulamalı videolar için gereklidir.

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

## Yapılandırma

`youtube-dl-server.py` içinde sabit ayarlar:
- Çıktı: `/root/music/%(title).200s [%(id)s].%(ext)s`
- Format: `bestaudio/best` → mp3 (192 kbps)
- Playlist: yok sayılır, tek video indirilir
- Cookie dosyası: `/root/web/cookies.txt` (varsa)

## Deploy

`git push` + `fab deploy`.
