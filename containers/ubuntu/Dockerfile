FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-venv \
    python3-pip \
    zsh \
    tmux \
    unzip \
    tar \
    gzip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dev-container-fortress

COPY ft/pyproject.toml ./ft/pyproject.toml
COPY ft/src ./ft/src
COPY ft/tools ./ft/tools

RUN python3 -m pip install --no-cache-dir uv
RUN uv run --with ./ft ft \
    --manifest ft/tools/tools.toml \
    --target ubuntu \
    install \
    --tool tenv
