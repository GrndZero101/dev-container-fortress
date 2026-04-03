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

COPY containers/common/pyproject.toml ./pyproject.toml
COPY containers/common/tools ./tools

RUN python3 -m pip install --no-cache-dir uv
RUN uv run python tools/install_tools.py --target ubuntu --manifest tools/tools.toml

