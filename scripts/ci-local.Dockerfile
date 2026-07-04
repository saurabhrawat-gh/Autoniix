# Ultimate parity image: ubuntu:24.04 amd64 with every toolchain pinned.
# Built by `bash scripts/ci-local.sh --docker`. Rebuilds only when versions.env changes.

FROM ubuntu:24.04

ARG RUST_VERSION=1.83.0
ARG NODE_VERSION=20.18.0
ARG NPM_VERSION=10.8.2
ARG PYTHON_VERSION=3.12.7
ARG GO_VERSION=1.22.10
ARG BUF_VERSION=1.47.2

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC LC_ALL=C.UTF-8 LANG=C.UTF-8 \
    PATH=/root/.cargo/bin:/usr/local/go/bin:/root/.local/bin:/root/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl wget git gnupg lsb-release \
      pkg-config libssl-dev protobuf-compiler ffmpeg jq unzip xz-utils \
      python3-dev libpq-dev iproute2 \
      libbz2-dev libncursesw5-dev libreadline-dev libsqlite3-dev libxml2-dev \
      libxmlsec1-dev libffi-dev liblzma-dev tk-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && apt-get install -y --no-install-recommends postgresql-client-15 && \
    rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- \
      -y --default-toolchain "${RUST_VERSION}" \
         --profile minimal --component clippy rustfmt

RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tgz && \
    tar -C /usr/local -xzf /tmp/go.tgz && rm /tmp/go.tgz

RUN curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh" | bash && \
    . "/root/.nvm/nvm.sh" && \
    nvm install "${NODE_VERSION}" && nvm use "${NODE_VERSION}" && \
    npm install -g "npm@${NPM_VERSION}" && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/node" /usr/local/bin/node && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/npm"  /usr/local/bin/npm && \
    ln -sf "/root/.nvm/versions/node/v${NODE_VERSION}/bin/npx"  /usr/local/bin/npx

RUN curl -fsSL https://pyenv.run | bash && \
    export PYENV_ROOT="/root/.pyenv" && \
    export PATH="$PYENV_ROOT/bin:$PATH" && \
    pyenv install "${PYTHON_VERSION}" && pyenv global "${PYTHON_VERSION}" && \
    ln -sf "$PYENV_ROOT/versions/${PYTHON_VERSION}/bin/python3" /usr/local/bin/python3 && \
    ln -sf "$PYENV_ROOT/versions/${PYTHON_VERSION}/bin/pip3"    /usr/local/bin/pip3

RUN curl -fsSL "https://github.com/bufbuild/buf/releases/download/v${BUF_VERSION}/buf-Linux-x86_64" \
      -o /usr/local/bin/buf && chmod +x /usr/local/bin/buf

RUN cargo install cargo-audit --locked --version 0.20.1

WORKDIR /work

RUN rustc --version    | grep -q "${RUST_VERSION}"   && \
    node --version     | grep -q "v${NODE_VERSION}"  && \
    npm --version      | grep -q "^${NPM_VERSION}$"  && \
    python3 --version  | grep -q "${PYTHON_VERSION}" && \
    go version         | grep -q "go${GO_VERSION}"   && \
    buf --version      | grep -q "${BUF_VERSION}"    && \
    echo "✅  ci-local image toolchain verified"

CMD ["bash"]
