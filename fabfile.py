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
