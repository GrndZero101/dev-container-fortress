ARG UV_DISTROLESS_IMAGE=ghcr.io/astral-sh/uv:latest
ARG CORPORATE_CA_CERT_DIR=""
ARG SHELL_CONFIG_SOURCE="github"
ARG SHELL_CONFIG_REPO_URL="https://github.com/GrndZero101/shell-config.git"
ARG SHELL_CONFIG_BRANCH="main"
ARG SHELL_CONFIG_LOCAL_DIR=""
ARG SHELL_CONFIG_PROFILE_DEFAULT="zsh-tll-citadel-dev-fortress"
ARG SHELL_CONFIG_INSTALL_ZINIT="1"

FROM ${UV_DISTROLESS_IMAGE} AS uv-distroless

FROM ubuntu:24.04 AS ubuntu-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    openssl \
    curl \
    fzf \
    git \
    gzip \
    python3 \
    python3-venv \
    sudo \
    tar \
    tmux \
    unzip \
    zsh \
  && rm -rf /var/lib/apt/lists/*

RUN if id -u ubuntu >/dev/null 2>&1; then \
      rm -f /var/mail/ubuntu; \
      userdel -r ubuntu || true; \
    fi

FROM ubuntu-base AS ubuntu-runtime

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
ARG CORPORATE_CA_CERT_DIR=""
ARG SHELL_CONFIG_SOURCE="github"
ARG SHELL_CONFIG_REPO_URL="https://github.com/GrndZero101/shell-config.git"
ARG SHELL_CONFIG_BRANCH="main"
ARG SHELL_CONFIG_LOCAL_DIR=""
ARG SHELL_CONFIG_PROFILE_DEFAULT="zsh-tll-citadel-dev-fortress"
ARG SHELL_CONFIG_INSTALL_ZINIT="1"

COPY --from=uv-distroless /uv /uvx /usr/local/bin/
COPY containers/common/install-corporate-ca.sh /usr/local/bin/install-corporate-ca
COPY containers/common/install-shell-config.sh /usr/local/bin/install-shell-config

RUN if getent group ${USERNAME} >/dev/null 2>&1; then \
      groupmod --gid ${USER_GID} ${USERNAME}; \
    elif getent group ${USER_GID} >/dev/null 2>&1; then \
      groupmod --new-name ${USERNAME} "$(getent group ${USER_GID} | cut -d: -f1)"; \
    else \
      groupadd --gid ${USER_GID} ${USERNAME}; \
    fi \
  && if id -u ${USERNAME} >/dev/null 2>&1; then \
      usermod --uid ${USER_UID} --gid ${USER_GID} --shell /usr/bin/zsh ${USERNAME}; \
    elif getent passwd ${USER_UID} >/dev/null 2>&1; then \
      usermod --login ${USERNAME} --home /home/${USERNAME} --move-home --gid ${USER_GID} --shell /usr/bin/zsh "$(getent passwd ${USER_UID} | cut -d: -f1)"; \
    else \
      useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /usr/bin/zsh ${USERNAME}; \
    fi \
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

RUN chmod 0755 /usr/local/bin/install-corporate-ca /usr/local/bin/install-shell-config
RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    /usr/local/bin/install-corporate-ca /tmp/build-context "${CORPORATE_CA_CERT_DIR}"

ENV HOME=/home/${USERNAME}
ENV XDG_CACHE_HOME=${HOME}/.cache
ENV XDG_DATA_HOME=${HOME}/.local/share
ENV XDG_CONFIG_HOME=${HOME}/.config
ENV PATH=${HOME}/.local/bin:${PATH}
ENV SHELL_CONFIG_PROFILE=${SHELL_CONFIG_PROFILE_DEFAULT}

WORKDIR ${HOME}

COPY --chown=${USER_UID}:${USER_GID} ft ${XDG_DATA_HOME}/dev-container-fortress/ft

USER ${USERNAME}

RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    /usr/local/bin/install-shell-config /tmp/build-context
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
RUN uv python install 3.14
RUN uv tool install --python 3.14 ${XDG_DATA_HOME}/dev-container-fortress/ft
RUN ft install \
    --manifest ${XDG_DATA_HOME}/dev-container-fortress/ft/tools/tools.toml \
    --target ubuntu

RUN uv --version \
  && ft plan --manifest ${XDG_DATA_HOME}/dev-container-fortress/ft/tools/tools.toml --target ubuntu \
  && tenv --version \
  && starship --version \
  && zoxide --version \
  && atuin --version \
  && fzf --version
