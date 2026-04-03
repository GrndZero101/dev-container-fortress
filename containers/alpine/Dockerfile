FROM alpine:3.22

RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    git \
    python3 \
    py3-pip \
    zsh \
    tmux \
    unzip \
    tar \
    gzip

WORKDIR /opt/dev-container-fortress

COPY ft/pyproject.toml ./ft/pyproject.toml
COPY ft/src ./ft/src
COPY ft/tools ./ft/tools

RUN python3 -m pip install --no-cache-dir uv
RUN uv run --with ./ft ft \
    --manifest ft/tools/tools.toml \
    --target alpine \
    install \
    --tool tenv
