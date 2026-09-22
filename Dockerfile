FROM docker.1ms.run/library/python:3.12.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROCKBASE_CONSOLE_HOST=0.0.0.0 \
    ROCKBASE_CONSOLE_PORT=8790 \
    ROCKBASE_CONSOLE_ALLOW_REMOTE=1 \
    ROCKBASE_CONSOLE_BASE_DIR=/var/lib/rockbase/console \
    ROCKBASE_CONSOLE_REPO_ROOT=/opt/rockbase \
    ROCKBASE_SERVICE=console

RUN groupadd --system rockbase && useradd --system --gid rockbase --home-dir /opt/rockbase --no-create-home rockbase
WORKDIR /opt/rockbase

# The image contains the whole project, not only the control plane. Each
# Compose service selects a runtime role through ROCKBASE_SERVICE.
COPY --chown=rockbase:rockbase console ./console
COPY --chown=rockbase:rockbase scripts ./scripts
COPY --chown=rockbase:rockbase rockbase ./rockbase
COPY --chown=rockbase:rockbase skills ./skills
COPY --chown=rockbase:rockbase mailkit ./mailkit
COPY --chown=rockbase:rockbase templates ./templates
COPY --chown=rockbase:rockbase docs ./docs
COPY --chown=rockbase:rockbase deploy ./deploy
COPY --chown=rockbase:rockbase pyproject.toml README.md README.zh-CN.md .dockerignore ./
COPY --chown=rockbase:rockbase deploy/docker-entrypoint.sh /usr/local/bin/rockbase

# Drop the placeholder workbench/ before symlinking, so the running container's
# /opt/rockbase/workbench resolves to the mounted data volume.
RUN python3 -m venv /opt/rockbase/.venv \
    && /opt/rockbase/.venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/rockbase/.venv/bin/pip install --no-cache-dir -e '.[llm]' \
    && chmod 0755 /usr/local/bin/rockbase \
    && mkdir -p /var/lib/rockbase/console/state /var/lib/rockbase/console/approvals \
       /var/lib/rockbase/mailkit /var/lib/rockbase/state /var/lib/rockbase/data \
       /opt/rockbase/workbench \
    && ln -snf /var/lib/rockbase/data/workbench /opt/rockbase/workbench \
    && chown -R rockbase:rockbase /var/lib/rockbase /opt/rockbase

USER rockbase
EXPOSE 8790 8788
VOLUME ["/var/lib/rockbase"]

ENTRYPOINT ["/usr/local/bin/rockbase"]
