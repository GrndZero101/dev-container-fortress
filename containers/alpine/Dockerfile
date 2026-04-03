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

COPY containers/common/pyproject.toml ./pyproject.toml
COPY containers/common/tools ./tools

RUN python3 -m pip install --no-cache-dir uv
RUN uv run python tools/install_tools.py --target alpine --manifest tools/tools.toml

