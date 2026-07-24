# yt-dlp EJS Desteği Ekleme - Tasarım

**Tarih:** 2026-07-24
**Durum:** Onaylandı
**Hedef:** yt-dlp 2026+ YouTube EJS challenge solving için deno runtime + yt-dlp-ejs python paketi kurulumunu otomatikleştirmek.

## Kök Neden

yt-dlp 2025+ sürümleri YouTube'dan video indirmek için artık **External JavaScript Scripts (EJS)** kullanıyor. EJS olmadan YouTube sadece `mhtml` storyboard döndürüyor; ses/video formatları erişilemiyor → `Requested format is not available` hatası.

EJS iki bileşenden oluşuyor:
1. **JavaScript runtime** (deno/node/quickjs) — challenge solver'ı çalıştırmak için
2. **yt-dlp-ejs python paketi** — challenge solver script'lerini içerir

Bu olmadan: hiçbir YouTube videosu indirilemiyor.

## Çözüm

1. **deno** kurulumu: `/root/.deno/bin/deno` (resmi install script ile, idempotent)
2. **yt-dlp-ejs**: `requirements.txt`'te `yt-dlp[default]` ile gelir
3. **deno PATH sorunu çözümü**: yt-dlp'ye `deno`'nun yerini söyleyen bir config dosyası (`/root/.config/yt-dlp/config` veya supervisor environment) — minimal invaziv seçim **config dosyası** (supervisor'a dokunmaz)

## Kapsam

### Kapsam içi
- `requirements.txt`: `yt-dlp>=2025.1.1` → `yt-dlp[default]>=2025.1.1`
- `fabfile.py`: yeni `setup` task'ı — deno kurulumu (idempotent)
- `fabfile.py`: `deploy` task'ı — `setup`'ı çağırır (idempotent olduğu için güvenli)
- yt-dlp config dosyası: `/root/.config/yt-dlp/config` içine `--js-runtimes deno:/root/.deno/bin/deno` ekle (sunucuda bir kez)
- Doğrulama: sunucuda deno kuruldu mu, yt-dlp-ejs yüklendi mi, gerçek indirme çalışıyor mu

### Kapsam dışı
- Supervisor config değişikliği (gerekmiyor — yt-dlp config dosyası yeterli)
- yt-dlp sürümünü eski sürüme pin'leme
- node/quickjs runtime desteği

## Bileşenler

### `requirements.txt`
```
starlette>=0.41
uvicorn[standard]>=0.32
yt-dlp[default]>=2025.1.1
fabric>=3.0
```

### `fabfile.py` — yeni `setup` task
Idempotent: deno zaten kuruluysa hiçbir şey yapmaz.

```python
@task(hosts=HOSTS)
def setup(c):
    """Idempotent: deno kurulu değilse kur. yt-dlp EJS challenge solver için gerekli."""
    deno_path = "/root/.deno/bin/deno"
    if c.run("test -x %s" % deno_path, hide=True, warn=True).ok:
        print("deno already installed at %s" % deno_path)
        return
    print("Installing deno...")
    c.run("curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/root/.deno sh -s -- -y")
    print("deno installed")
```

### `fabfile.py` — `deploy` task güncelleme
Mevcut task'ın başına `setup` çağrısı ekle. Idempotent olduğu için her deploy'da güvenli.

### yt-dlp config dosyası
`/root/.config/yt-dlp/config`:
```
--js-runtimes deno:/root/.deno/bin/deno
--remote-components ejs:github
```

`--remote-components ejs:github` opsiyonel güvenlik ağı: eğer `yt-dlp-ejs` python paketi yt-dlp sürümüyle senkron değilse GitHub'dan güncelleyebilir. `deno`'nun bu komut için de gerekli olduğunu unutma — bu yüzden deno kurulumu önce gelmeli.

## Doğrulama Stratejisi

1. **Lokal**: pyenv ortamında `pip install -U "yt-dlp[default]"` + deno kurulumu
2. **Sunucu**: `fab deploy` sonrası:
   - `deno --version` → bir sürüm
   - `yt-dlp --list-formats https://www.youtube.com/watch?v=oJltjDAEJJ0` → ses+video formatları görünüyor (artık sadece storyboard değil)
   - Gerçek indirme (`/q?url=...`) → mp3 oluşuyor
3. **End-to-end**: bookmarklet URL'inden mp3'e kadar

## Göç

- `requirements.txt`'te `yt-dlp` → `yt-dlp[default]`
- `fabfile.py`'ye `setup` task'ı eklenir
- `deploy` task'ı `setup`'ı çağırır
- Sunucuda bir kez: `/root/.config/yt-dlp/config` dosyası oluşturulur (fabfile task'ıyla)

## Riskler

- **Deno kurulumu network bağımlılığı**: GitHub'a erişim yoksa `deno.land/install.sh` başarısız olur. Çözüm: iddia — sunucu zaten GitHub'dan repo çekiyor, erişim var.
- **yt-dlp-ejs sürüm uyumsuzluğu**: yt-dlp yeni sürüme geçince eski yt-dlp-ejs uyumsuz olabilir. Çözüm: `pip install -U "yt-dlp[default]"` her zaman en güncel tutar.
- **deno binary location**: yt-dlp varsayılan olarak PATH'te `deno` arar; biz `/root/.deno/bin/deno`'ya kuruyoruz, config dosyası yolu söylüyor. **Supervisor'a gerek yok.**
