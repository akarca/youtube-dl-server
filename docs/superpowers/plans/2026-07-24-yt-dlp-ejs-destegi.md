# yt-dlp EJS Desteği Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube'dan video indirmeyi yeniden mümkün kılmak için sunucuya deno runtime + yt-dlp-ejs python paketi kurulumunu otomatikleştirmek.

**Architecture:** `yt-dlp[default]` pip extra'sı `yt-dlp-ejs` paketini de kurar. Yeni `fabfile setup` task'ı deno'yu idempotent olarak `/root/.deno/bin/deno`'ya kurar. yt-dlp config dosyası (`/root/.config/yt-dlp/config`) deno'nun tam yolunu ve remote-components fallback'ini belirler. Supervisor'a dokunulmaz.

**Tech Stack:** fabric, deno, yt-dlp[default].

---

## Dosya Yapısı

| Dosya | Değişiklik |
|-------|-----------|
| `requirements.txt` | `yt-dlp` → `yt-dlp[default]` |
| `fabfile.py` | `setup` task'ı ekle, `deploy` task'ı `setup`'ı çağırsın |
| `/root/.config/yt-dlp/config` (sunucuda) | yt-dlp config dosyası (fabfile task'ıyla oluşur) |

---

### Task 1: requirements.txt'i güncelle

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: requirements.txt'te yt-dlp satırını değiştir**

Mevcut `yt-dlp>=2025.1.1` satırını `yt-dlp[default]>=2025.1.1` ile değiştir. `default` extra'sı `yt-dlp-ejs` python paketini de kurar.

- [ ] **Step 2: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add requirements.txt
git commit -m "chore(deps): switch yt-dlp to [default] extra to pull yt-dlp-ejs"
```

---

### Task 2: fabfile'a setup task'ı ekle

**Files:**
- Modify: `fabfile.py`

- [ ] **Step 1: fabfile.py'yi şu hale getir**

Tüm içeriği şununla değiştir:

```python
import sys

from fabric import task

if not sys.warnoptions:
    import warnings

    warnings.simplefilter("ignore")

HOSTS = ["music"]
REPO_DIR = "/root/web"
PYENV_PIP = "/root/.pyenv/versions/youtubedl/bin/pip"
SERVICE_NAME = "youtubedl"
DENO_PATH = "/root/.deno/bin/deno"
YT_DLP_CONFIG_DIR = "/root/.config/yt-dlp"
YT_DLP_CONFIG_PATH = "%s/config" % YT_DLP_CONFIG_DIR
YT_DLP_CONFIG_BODY = (
    "--js-runtimes deno:%s\n"
    "--remote-components ejs:github\n"
) % DENO_PATH


@task(hosts=HOSTS)
def setup(c):
    """Idempotent: deno + yt-dlp config dosyası kurulumu. yt-dlp EJS challenge solver için gerekli."""
    if c.run("test -x %s" % DENO_PATH, hide=True, warn=True).ok:
        print("deno already installed at %s" % DENO_PATH)
    else:
        print("Installing deno...")
        c.run("curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/root/.deno sh -s -- -y")
        print("deno installed")

    if c.run("test -f %s" % YT_DLP_CONFIG_PATH, hide=True, warn=True).ok:
        print("yt-dlp config already exists at %s" % YT_DLP_CONFIG_PATH)
    else:
        print("Writing yt-dlp config...")
        c.run("mkdir -p %s" % YT_DLP_CONFIG_DIR)
        c.run("printf '%s' %s > %s" % (YT_DLP_CONFIG_BODY, "", YT_DLP_CONFIG_PATH))
        print("yt-dlp config written")


@task(hosts=HOSTS)
def deploy(c):
    c.local("git push")
    print("Deploying to %s" % c.original_host)
    with c.cd(REPO_DIR):
        c.run("git pull origin main")
        c.run("%s install --upgrade -r requirements.txt" % PYENV_PIP)
    setup(c)
    c.run("supervisorctl restart %s" % SERVICE_NAME)
```

**Not:** İçeride `printf '%s' %s > path` çalışsın diye body'de tek tırnak kullanılmadı; yerine Python tarafında string'in doğru biçimde gelmesi gerekiyor. **Aslında yukarıdaki `printf '%s' %s` iki argüman istiyor (format, value) ama bizim body birden çok satır.** Bunu fabric'in put-string'i ile yapalım — daha güvenli. `setup` task'ını şu şekilde düzelt:

```python
@task(hosts=HOSTS)
def setup(c):
    """Idempotent: deno + yt-dlp config dosyası kurulumu. yt-dlp EJS challenge solver için gerekli."""
    if c.run("test -x %s" % DENO_PATH, hide=True, warn=True).ok:
        print("deno already installed at %s" % DENO_PATH)
    else:
        print("Installing deno...")
        c.run("curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/root/.deno sh -s -- -y")
        print("deno installed")

    if c.run("test -f %s" % YT_DLP_CONFIG_PATH, hide=True, warn=True).ok:
        print("yt-dlp config already exists at %s" % YT_DLP_CONFIG_PATH)
    else:
        print("Writing yt-dlp config...")
        c.run("mkdir -p %s" % YT_DLP_CONFIG_DIR)
        c.put(io.StringIO(YT_DLP_CONFIG_BODY), YT_DLP_CONFIG_PATH)
        print("yt-dlp config written")
```

Ve dosyanın başına `import io` ekle. Tam hali:

```python
import io
import sys

from fabric import task

if not sys.warnoptions:
    import warnings

    warnings.simplefilter("ignore")

HOSTS = ["music"]
REPO_DIR = "/root/web"
PYENV_PIP = "/root/.pyenv/versions/youtubedl/bin/pip"
SERVICE_NAME = "youtubedl"
DENO_PATH = "/root/.deno/bin/deno"
YT_DLP_CONFIG_DIR = "/root/.config/yt-dlp"
YT_DLP_CONFIG_PATH = "%s/config" % YT_DLP_CONFIG_DIR
YT_DLP_CONFIG_BODY = (
    "--js-runtimes deno:%s\n"
    "--remote-components ejs:github\n"
) % DENO_PATH


@task(hosts=HOSTS)
def setup(c):
    """Idempotent: deno + yt-dlp config dosyası kurulumu. yt-dlp EJS challenge solver için gerekli."""
    if c.run("test -x %s" % DENO_PATH, hide=True, warn=True).ok:
        print("deno already installed at %s" % DENO_PATH)
    else:
        print("Installing deno...")
        c.run("curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/root/.deno sh -s -- -y")
        print("deno installed")

    if c.run("test -f %s" % YT_DLP_CONFIG_PATH, hide=True, warn=True).ok:
        print("yt-dlp config already exists at %s" % YT_DLP_CONFIG_PATH)
    else:
        print("Writing yt-dlp config...")
        c.run("mkdir -p %s" % YT_DLP_CONFIG_DIR)
        c.put(io.StringIO(YT_DLP_CONFIG_BODY), YT_DLP_CONFIG_PATH)
        print("yt-dlp config written")


@task(hosts=HOSTS)
def deploy(c):
    c.local("git push")
    print("Deploying to %s" % c.original_host)
    with c.cd(REPO_DIR):
        c.run("git pull origin main")
        c.run("%s install --upgrade -r requirements.txt" % PYENV_PIP)
    setup(c)
    c.run("supervisorctl restart %s" % SERVICE_NAME)
```

- [ ] **Step 2: Sentaks kontrolü**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec python -c "import ast; ast.parse(open('fabfile.py').read()); print('ok')"
pyenv exec fab --list
```

Expected: `ok` ve:

```
Available tasks:

  deploy
  setup
```

- [ ] **Step 3: Commit**

```bash
cd /Users/serdar/workspace/youtube-dl-server
git add fabfile.py
git commit -m "feat(deploy): add idempotent setup task for deno + yt-dlp EJS config

- setup() installs deno to /root/.deno/bin/deno if missing
- setup() writes /root/.config/yt-dlp/config if missing
  (sets --js-runtimes deno path and --remote-components ejs:github)
- deploy() now invokes setup() before restarting supervisor"
```

---

### Task 3: Push + fab deploy

**Files:** yok

- [ ] **Step 1: fab deploy çalıştır**

```bash
cd /Users/serdar/workspace/youtube-dl-server
pyenv exec fab deploy
```

Expected: `git push` → `git pull` → `pip install --upgrade -r requirements.txt` (yt-dlp[default] + yt-dlp-ejs yükselir) → `setup()` çağrılır (deno indirilir, yt-dlp config yazılır) → `supervisorctl restart youtubedl`.

Bu deploy 5-10 dakika sürebilir (deno binary download).

- [ ] **Step 2: Sunucuda doğrula**

```bash
ssh music "/root/.deno/bin/deno --version"
ssh music "cat /root/.config/yt-dlp/config"
ssh music "/root/.pyenv/versions/youtubedl/bin/yt-dlp --list-formats --cookies /root/web/cookies.txt 'https://www.youtube.com/watch?v=oJltjDAEJJ0' 2>&1 | head -30"
```

Expected:
- `deno --version` → `deno 2.x.x`
- `cat config` → `--js-runtimes deno:/root/.deno/bin/deno\n--remote-components ejs:github\n`
- `--list-formats` çıktısı storyboard'lar yerine audio+video formatları gösteriyor (`140 m4a`, `251 webm`, vb.)

Eğer hala storyboard-only ise, yt-dlp-ejs python paketi yt-dlp sürümüyle senkron olmayabilir. Bu durumda sunucuda:

```bash
ssh music "/root/.pyenv/versions/youtubedl/bin/pip install --upgrade 'yt-dlp[default]'"
```

---

### Task 4: End-to-end doğrulama

**Files:** yok

- [ ] **Step 1: Gerçek indirmeyi tetikle**

```bash
curl -s "https://youtubedl.nameocean.org/youtube-dl/q?url=https://www.youtube.com/watch?v=oJltjDAEJJ0" -w "\nHTTP %{http_code}\n"
```

Expected: `{"success":true,"url":"..."}` HTTP 200.

- [ ] **Step 2: mp3 dosyasının oluşmasını bekle ve kontrol et**

```bash
sleep 20
ssh music "ls -lt /root/music/ | head -3"
ssh music "tail -30 /var/log/supervisor/youtubedl-stdout---supervisor-*.log 2>/dev/null | grep -iE 'download|extractor|error' | tail -10"
```

Expected:
- Yeni bir mp3 dosyası (`... [oJltjDAEJJ0].mp3`) listenin başında
- Log'da hata yok; `[download] Destination` ve `[ExtractAudio] Destination` benzeri satırlar

---

## Tamamlandı

- `yt-dlp[default]` pip extra'sı: `yt-dlp-ejs` python paketi kurulur
- `fab setup` task'ı: deno'yu idempotent olarak kurar
- `/root/.config/yt-dlp/config`: yt-dlp'ye deno yolunu söyler
- `fab deploy`: setup'ı çağırır, supervisor'u restart eder
- YouTube videoları tekrar indirilebilir
