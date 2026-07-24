import sys

from fabric import task

if not sys.warnoptions:
    import warnings

    warnings.simplefilter("ignore")

HOSTS = ["music"]
REPO_DIR = "/root/web"
PYENV_PIP = "/root/.pyenv/versions/youtubedl/bin/pip"
SERVICE_NAME = "youtubedl"


@task(hosts=HOSTS)
def deploy(c):
    c.local("git push")
    print("Deploying to %s" % c.original_host)
    with c.cd(REPO_DIR):
        c.run("git pull origin main")
        c.run("%s install -r requirements.txt" % PYENV_PIP)
    c.run("supervisorctl restart %s" % SERVICE_NAME)
