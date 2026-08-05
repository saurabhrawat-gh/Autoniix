# Ultimate parity image: ubuntu:24.04 amd64 with Phase 7 toolchains pinned.
# Built by `bash scripts/ci-local.sh --docker`. Rebuilds only when versions.env changes.

FROM ubuntu:24.04

ARG NODE_VERSION=22.23.1
ARG NPM_VERSION=10.9.8
ARG PYTHON_VERSION=3.12.7

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC LC_ALL=C.UTF-8 LANG=C.UTF-8 \
    PATH=/root/.local/bin:/root/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl wget git gnupg lsb-release \
      pkg-config libssl-dev ffmpeg jq unzip xz-utils \
      python3-dev libpq-dev iproute2 \
      libbz2-dev libncursesw5-dev libreadline-dev libsqlite3-dev libxml2-dev \
      libxmlsec1-dev libffi-dev liblzma-dev tk-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (so ci-local can talk to the host daemon via mounted socket)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Postgres 15 client for migrations
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && apt-get install -y --no-install-recommends postgresql-client-15 && \
    rm -rf /var/lib/apt/lists/*

# Node + npm
RUN curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh" | bash && \
    . "/root/.nvm/nvm.sh" && \
    nvm install "${NODE_VERSION}" && nvm use "${NODE_VERSION}" && \
    npm install -g "npm@${NPM_VERSION}" && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/node" /usr/local/bin/node && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/npm"  /usr/local/bin/npm && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/npx"  /usr/local/bin/npx

# Python via pyenv (exact match to CI setup-python)
RUN curl -fsSL https://pyenv.run | bash && \
    export PYENV_ROOT="/root/.pyenv" && \
    export PATH="$PYENV_ROOT/bin:$PATH" && \
    pyenv install "${PYTHON_VERSION}" && pyenv global "${PYTHON_VERSION}" && \
    ln -sf "$PYENV_ROOT/versions/${PYTHON_VERSION}/bin/python3" /usr/local/bin/python3 && \
    ln -sf "$PYENV_ROOT/versions/${PYTHON_VERSION}/bin/pip3"    /usr/local/bin/pip3

# Common Python tooling (ruff/mypy/pytest/pip-audit) — installed once
RUN pip3 install --no-cache-dir --break-system-packages \
      ruff mypy pytest pytest-asyncio pip-audit cyclonedx-bom

WORKDIR /work
CMD ["bash", "scripts/ci-local.sh", "--full"]
