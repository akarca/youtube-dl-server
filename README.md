[![Docker Stars Shield](https://img.shields.io/docker/stars/kmb32123/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/kmb32123/youtube-dl-server/)
[![Docker Pulls Shield](https://img.shields.io/docker/pulls/kmb32123/youtube-dl-server.svg?style=flat-square)](https://hub.docker.com/r/kmb32123/youtube-dl-server/)
[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://raw.githubusercontent.com/manbearwiz/youtube-dl-server/master/LICENSE)
![Workflow](https://github.com/manbearwiz/youtube-dl-server/actions/workflows/docker-image.yml/badge.svg)

# youtube-dl-server

Very spartan Web and REST interface for downloading youtube videos onto a server. [`starlette`](https://github.com/encode/starlette) + [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

![screenshot][1]

### Python

If you have python ^3.6.0 installed in your PATH you can simply run like this, providing optional environment variable overrides inline.

```shell
python -m uvicorn youtube-dl-server:app --port 8123 --host 0.0.0.0
```

## Usage

### Start a download remotely

Downloads can be triggered by supplying the `{{url}}` of the requested video through the Web UI or through the REST interface via curl, etc.

#### HTML

Just navigate to `http://{{host}}:8080/youtube-dl` and enter the requested `{{url}}`.


```

#### Bookmarklet

Add the following bookmarklet to your bookmark bar so you can conviently send the current page url to your youtube-dl-server instance.

```javascript
javascript:!function(){window.location="http://${host}:8123/youtube-dl/q?url=" + window.location.href}();
```

## Implementation

The server uses [`starlette`](https://github.com/encode/starlette) for the web framework and [`youtube-dl`](https://github.com/rg3/youtube-dl) to handle the downloading. The integration with youtube-dl makes use of their [python api](https://github.com/rg3/youtube-dl#embedding-youtube-dl).

This docker image is based on [`python:alpine`](https://registry.hub.docker.com/_/python/) and consequently [`alpine:3.8`](https://hub.docker.com/_/alpine/).

[1]:youtube-dl-server.png
