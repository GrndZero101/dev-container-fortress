ARG UV_DISTROLESS_IMAGE=ghcr.io/astral-sh/uv:latest

FROM ${UV_DISTROLESS_IMAGE} AS uv-distroless

FROM alpine:3.22 AS alpine-runtime

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    git \
    gzip \
    python3 \
    sudo \
    tar \
    tmux \
    unzip \
    zsh

COPY --from=uv-distroless /uv /uvx /usr/local/bin/

RUN if getent group ${USERNAME} >/dev/null 2>&1; then \
      delgroup ${USERNAME}; \
    fi \
  && if getent group ${USER_GID} >/dev/null 2>&1; then \
      delgroup "$(getent group ${USER_GID} | cut -d: -f1)"; \
    fi \
  && addgroup -g ${USER_GID} ${USERNAME} \
  && if id -u ${USERNAME} >/dev/null 2>&1; then \
      deluser ${USERNAME}; \
    fi \
  && if getent passwd ${USER_UID} >/dev/null 2>&1; then \
      deluser "$(getent passwd ${USER_UID} | cut -d: -f1)"; \
    fi \
  && adduser -D -u ${USER_UID} -G ${USERNAME} -s /bin/zsh ${USERNAME} \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/bin \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share/dev-container-fortress \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.cache \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.config \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshenv \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshrc \
  && chown ${USER_UID}:${USER_GID} /home/${USERNAME}/.zshenv /home/${USERNAME}/.zshrc \
  && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-${USERNAME} \
  && chmod 0440 /etc/sudoers.d/90-${USERNAME}

ENV HOME=/home/${USERNAME}
ENV XDG_CACHE_HOME=${HOME}/.cache
ENV XDG_DATA_HOME=${HOME}/.local/share
ENV XDG_CONFIG_HOME=${HOME}/.config
ENV PATH=${HOME}/.local/bin:${PATH}

WORKDIR ${HOME}

COPY --chown=${USER_UID}:${USER_GID} ft ${XDG_DATA_HOME}/dev-container-fortress/ft

USER ${USERNAME}

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
RUN uv python install 3.14
RUN uv tool install --python 3.14 ${XDG_DATA_HOME}/dev-container-fortress/ft
RUN ft install \
    --manifest ${XDG_DATA_HOME}/dev-container-fortress/ft/tools/tools.toml \
    --target alpine \
    --tool tenv

RUN uv --version \
  && ft plan --manifest ${XDG_DATA_HOME}/dev-container-fortress/ft/tools/tools.toml --target alpine --tool tenv \
  && tenv --version
