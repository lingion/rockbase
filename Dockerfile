FROM docker.1ms.run/library/python:3.12.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROCKBASE_CONSOLE_HOST=0.0.0.0 \
    ROCKBASE_CONSOLE_PORT=8790 \
    ROCKBASE_CONSOLE_ALLOW_REMOTE=1 \
    ROCKBASE_CONSOLE_BASE_DIR=/var/lib/rockbase/console \
    ROCKBASE_CONSOLE_REPO_ROOT=/opt/rockbase

RUN groupadd --system rockbase && useradd --system --gid rockbase --home-dir /opt/rockbase --no-create-home rockbase
WORKDIR /opt/rockbase

COPY --chown=rockbase:rockbase console ./console
COPY --chown=rockbase:rockbase scripts ./scripts
COPY --chown=rockbase:rockbase rockbase ./rockbase
COPY --chown=rockbase:rockbase pyproject.toml README.md ./

RUN mkdir -p /var/lib/rockbase/console/state /var/lib/rockbase/console/approvals \
    && chown -R rockbase:rockbase /var/lib/rockbase

USER rockbase
EXPOSE 8790
VOLUME ["/var/lib/rockbase/console"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8790/api/health', timeout=2)"

CMD ["python3", "-m", "console.server"]
