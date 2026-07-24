# URL Path Uyumluluğu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bookmarklet URL'inin (`/youtube-dl/q?url=...`) çalışması için Starlette route'unu `/youtube-dl/q` path'ine taşı.

**Architecture:** Tek satır değişiklik. nginx zaten `/youtube-dl/q` için auth'suz bir `location` bloğuna sahip (`/etc/nginx/conf.d/web.conf`); backend `/q` dinliyor, o yüzden 404 alıyoruz. Starlette route'unu `/youtube-dl/q`'ya çevirince URL uyumlu olur. Eski `/q` de bonus olarak korunur.

**Tech Stack:** Python, Starlette (mevcut).

---

## Dosya Yapısı

| Dosya | Değişiklik |
|-------|-----------|
| `youtube-dl-server.py` | Route path: `/q` → `/youtube-dl/q` (+ `/q` korunur) |

Nginx veya başka bir dosya değişmiyor. Plan tamamlandığında bookmarklet URL'i (`https://youtubedl.nameocean.org/youtube-dl/q?url=...`) auth olmadan çalışacak.

---

### Task 1: Route path'ini değiştir

**Files:**
- Modify: `youtube-dl-server.py:73`

- [ ] **Step 1: `youtube-dl-server.py` içindeki `routes` listesini güncelle**

Mevcut hali (satır 70-74):

```python
routes = [
    Route("/", endpoint=index),
    Route("/healthz", endpoint=healthz),
    Route("/q", endpoint=q_put, methods=["GET"]),
]
```

Şununla değiştir:

```python
routes = [
    Route("/", endpoint=index),
    Route("/healthz", endpoint=healthz),
    Route("/youtube-dl/q", endpoint=q_put, methods=["GET"]),
    Route("/q", endpoint=q_put, methods=["GET"]),
]
```

- [ ] **Step 2: Lokal doğrulama**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','youtube-dl-server.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('app:', m.app)"
pyenv exec python -m uvicorn youtube-dl-server:app --port 8123 --host 127.0.0.1 &
SERVER_PID=$!
sleep 3
echo "--- /youtube-dl/q valid ---"
curl -s "http://127.0.0.1:8123/youtube-dl/q?url=https://www.youtube.com/watch?v=jNQXAC9IVRw"; echo
echo "--- /youtube-dl/q missing ---"
curl -s -w "\nHTTP %{http_code}\n" "http://127.0.0.1:8123/youtube-dl/q"
echo "--- /q valid (backward compat) ---"
curl -s "http://127.0.0.1:8123/q?url=https://www.youtube.com/watch?v=jNQXAC9IVRw"; echo
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

Expected:
- `/youtube-dl/q?url=...` → `{"success":true,"url":"..."}`
- `/youtube-dl/q` (eksik) → `{"success":false,"error":"missing url"}` HTTP 400
- `/q?url=...` → `{"success":true,"url":"..."}`

- [ ] **Step 3: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add youtube-dl-server.py
git commit -m "feat(api): expose /youtube-dl/q route to keep existing bookmarklet working

nginx already proxies /youtube-dl/q without auth (see /etc/nginx/conf.d/web.conf),
but the app was listening on /q. Aligning the route fixes 404 from the bookmarklet
URL https://youtubedl.nameocean.org/youtube-dl/q?url=... .

Also keep /q as a fallback."
```

---

### Task 2: Push + fab deploy

**Files:** yok (sadece deploy)

- [ ] **Step 1: fab deploy çalıştır**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec fab deploy
```

Expected: `git push` → `git pull` → `pip install -r requirements.txt` (no-op) → `supervisorctl restart youtubedl` (`youtubedl: stopped` → `youtubedl: started`).

---

### Task 3: Sunucuda bookmarklet URL'ini doğrula

**Files:** yok

- [ ] **Step 1: `/youtube-dl/q` path'ini auth olmadan çağır**

```bash
curl -s "https://youtubedl.nameocean.org/youtube-dl/q?url=https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

Expected: `{"success":true,"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}` (HTTP 200, auth yok).

- [ ] **Step 2: 400 path'i doğrula**

```bash
curl -s -w "\nHTTP %{http_code}\n" "https://youtubedl.nameocean.org/youtube-dl/q"
```

Expected: `{"success":false,"error":"missing url"}` HTTP 400.

- [ ] **Step 3: Gerçek indirmeyi bekle ve dosyayı kontrol et**

```bash
sleep 10
ssh music "ls -la /root/music/ | tail -5"
```

Expected: yeni bir `.mp3` dosyası (`Me at the zoo [jNQXAC9IVRw].mp3` benzeri).

---

## Tamamlandı

- Starlette route `/q` → `/youtube-dl/q` (eski `/q` de korunur)
- `fab deploy` ile sunucu güncellendi
- Bookmarklet URL'i (`/youtube-dl/q?url=...`) auth olmadan çalışıyor
- `/root/music/` altında mp3 dosyası oluşuyor
