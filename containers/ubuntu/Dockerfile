ARG UV_DISTROLESS_IMAGE=ghcr.io/astral-sh/uv:latest
# Ubuntu image tag for the base layer: the current LTS by default. Workspace
# profiles can set os_release to trial another release, such as rolling.
ARG UBUNTU_RELEASE=26.04
ARG CORPORATE_CA_CERT_DIR=""
ARG SHELL_CONFIG_SOURCE="github"
ARG SHELL_CONFIG_REPO_URL="https://github.com/GrndZero101/shell-config.git"
ARG SHELL_CONFIG_BRANCH="main"
ARG SHELL_CONFIG_LOCAL_DIR=""
ARG SHELL_CONFIG_PROFILE_DEFAULT="zsh-tll-citadel-dev-fortress"
ARG SHELL_CONFIG_INSTALL_ZINIT="1"
ARG WORKSPACE_TOOL_LAYER_GITFORGE="0"
ARG WORKSPACE_TOOL_LAYER_SECRETS="0"
ARG WORKSPACE_TOOL_LAYER_AWS="0"
# warm installs the Homebrew floor into the image; cold leaves the prefix
# empty for ft-brew-floor to fill on first start. CI publishes cold images.
ARG HOMEBREW_FLOOR="warm"

FROM ${UV_DISTROLESS_IMAGE} AS uv-distroless

FROM ubuntu:${UBUNTU_RELEASE} AS ubuntu-base

ENV DEBIAN_FRONTEND=noninteractive

# build-essential, file, and procps are Homebrew's Linux prerequisites.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    openssl \
    curl \
    file \
    fzf \
    git \
    gzip \
    openssh-server \
    procps \
    python3-apt \
    python3 \
    python3-venv \
    sudo \
    tar \
    tmux \
    unzip \
    xdg-utils \
    zsh \
  && rm -rf /var/lib/apt/lists/*

RUN if id -u ubuntu >/dev/null 2>&1; then \
      rm -f /var/mail/ubuntu; \
      userdel -r ubuntu || true; \
    fi

FROM ubuntu-base AS corporate-ca-source

ARG CORPORATE_CA_CERT_DIR=""

# Copy only the requested certificate directory out of the build context.
# The next stage copies this output, which BuildKit keys on content, so edits
# elsewhere in the context leave every layer below it cached.
RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    mkdir -p /corporate-ca \
  && case "${CORPORATE_CA_CERT_DIR}" in \
       ""|/*) ;; \
       *) if [ -d "/tmp/build-context/${CORPORATE_CA_CERT_DIR}" ]; then \
            mkdir -p "/corporate-ca/${CORPORATE_CA_CERT_DIR}" \
            && cp -a "/tmp/build-context/${CORPORATE_CA_CERT_DIR}/." "/corporate-ca/${CORPORATE_CA_CERT_DIR}/"; \
          fi ;; \
     esac

FROM ubuntu-base AS ubuntu-trusted

ARG CORPORATE_CA_CERT_DIR=""

COPY containers/common/install-corporate-ca.sh /usr/local/bin/install-corporate-ca
COPY --from=corporate-ca-source /corporate-ca /tmp/corporate-ca
RUN chmod 0755 /usr/local/bin/install-corporate-ca \
  && /usr/local/bin/install-corporate-ca /tmp/corporate-ca "${CORPORATE_CA_CERT_DIR}" \
  && rm -rf /tmp/corporate-ca

FROM ubuntu-trusted AS brew-floor-list

ARG WORKSPACE_TOOL_LAYER_AWS="0"

COPY --from=uv-distroless /uv /usr/local/bin/
COPY ft /tmp/dev-container-fortress/ft
COPY .python-version /tmp/dev-container-fortress/.python-version

# Write the floor list in its own stage. The runtime stage copies only the
# list, so a change under ft/ that leaves the list alone keeps the floor
# cached. Tool layers that come from Homebrew extend the list, so their
# formulae also reach a workspace volume seeded before the layer was added.
RUN cd /tmp/dev-container-fortress \
  && UV_PYTHON_PREFERENCE=only-managed uv tool run --python "$(cat .python-version)" --from ./ft \
       ft tool formulae --manifest ft/tools/tool-pool.toml > /brew-floor.txt \
  && if [ "${WORKSPACE_TOOL_LAYER_AWS}" = "1" ]; then echo awscli >> /brew-floor.txt; fi

FROM ubuntu-trusted AS ubuntu-runtime

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
# warm installs the Homebrew floor into the image; cold leaves the prefix
# empty for ft-brew-floor to fill on first start. CI publishes cold images.
ARG HOMEBREW_FLOOR="warm"

COPY --from=uv-distroless /uv /uvx /usr/local/bin/
# Only what the Homebrew floor needs comes before it; the other helpers follow
# the floor, so editing them does not rebuild it.
COPY --chmod=0755 containers/common/brew-floor.sh /usr/local/bin/ft-brew-floor
COPY containers/common/gitconfig /etc/gitconfig

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
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/bin \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share/dev-container-fortress \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share/zoxide \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share/atuin \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/share/claude \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.claude \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.local/state \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.cache \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.config \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.config/gh \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/${USERNAME}/.config/glab-cli \
  && install -d -o ${USER_UID} -g ${USER_GID} /home/linuxbrew /home/linuxbrew/.linuxbrew \
  && install -d -o ${USER_UID} -g ${USER_GID} /workspaces \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshenv \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshrc \
  && chown ${USER_UID}:${USER_GID} /home/${USERNAME}/.zshenv /home/${USERNAME}/.zshrc \
  && chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}/.local /home/${USERNAME}/.cache /home/${USERNAME}/.config \
  && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-${USERNAME} \
  && chmod 0440 /etc/sudoers.d/90-${USERNAME}

ENV HOME=/home/${USERNAME}
ENV XDG_CACHE_HOME=${HOME}/.cache
ENV XDG_DATA_HOME=${HOME}/.local/share
ENV XDG_CONFIG_HOME=${HOME}/.config
ENV XDG_STATE_HOME=${HOME}/.local/state
# Mounted checkouts are shared with the host, so keep the container's project
# environment beside the host .venv instead of overwriting it. uv resolves
# this relative path per project root, and the directory ignores itself.
ENV UV_PROJECT_ENVIRONMENT=.venv-container
ENV HOMEBREW_PREFIX=/home/linuxbrew/.linuxbrew
ENV HOMEBREW_CELLAR=${HOMEBREW_PREFIX}/Cellar
ENV HOMEBREW_REPOSITORY=${HOMEBREW_PREFIX}/Homebrew
# Homebrew's git reads its system config from the prefix, which lives on the
# brew volume; point every git at the image-managed file instead.
ENV GIT_CONFIG_SYSTEM=/etc/gitconfig
ENV PATH=${HOME}/.local/bin:${HOMEBREW_PREFIX}/bin:${HOMEBREW_PREFIX}/sbin:${PATH}

WORKDIR ${HOME}

USER ${USERNAME}

# The floor comes before anything keyed on the shell-config build args or the
# ft source, so devcontainer and ft builds share it and ft edits keep it.
COPY --from=brew-floor-list --chown=${USER_UID}:${USER_GID} /brew-floor.txt ${XDG_DATA_HOME}/dev-container-fortress/brew-floor.txt
# A warm image carries the floor, so a fresh workspace volume seeds from it in
# seconds. The download cache stays out of the image.
RUN --mount=type=cache,target=/home/vscode/.cache/Homebrew,uid=1000,gid=1000 \
    case "${HOMEBREW_FLOOR}" in \
      warm) ft-brew-floor ;; \
      cold) ;; \
      *) echo "HOMEBREW_FLOOR must be warm or cold, not ${HOMEBREW_FLOOR}" >&2; exit 1 ;; \
    esac

COPY --chmod=0755 containers/common/ft-host-browser-open.sh /usr/local/bin/ft-host-browser-open
COPY --chmod=0755 containers/common/install-shell-config.sh /usr/local/bin/install-shell-config
COPY --chmod=0755 containers/common/start-test-target.sh /usr/local/bin/start-test-target
COPY --chmod=0755 containers/common/ensure-claude-code.sh /usr/local/bin/ft-ensure-claude-code

ARG SHELL_CONFIG_SOURCE="github"
ARG SHELL_CONFIG_REPO_URL="https://github.com/GrndZero101/shell-config.git"
ARG SHELL_CONFIG_BRANCH="main"
ARG SHELL_CONFIG_LOCAL_DIR=""
ARG SHELL_CONFIG_PROFILE_DEFAULT="zsh-tll-citadel-dev-fortress"
ARG SHELL_CONFIG_INSTALL_ZINIT="1"
ARG WORKSPACE_TOOL_LAYER_GITFORGE="0"
ARG WORKSPACE_TOOL_LAYER_SECRETS="0"
ARG WORKSPACE_TOOL_LAYER_AWS="0"

# The devcontainers pass an unset variable as an empty build arg, so fall back
# to the default profile here as install-shell-config does.
ENV SHELL_CONFIG_PROFILE=${SHELL_CONFIG_PROFILE_DEFAULT:-zsh-tll-citadel-dev-fortress}

COPY --chown=${USER_UID}:${USER_GID} ft ${XDG_DATA_HOME}/dev-container-fortress/ft
COPY --chown=${USER_UID}:${USER_GID} .python-version ${XDG_DATA_HOME}/dev-container-fortress/.python-version

RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    /usr/local/bin/install-shell-config /tmp/build-context
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
# The repo-root .python-version is the one Python pin for Dev Fortress code.
RUN uv python install "$(cat ${XDG_DATA_HOME}/dev-container-fortress/.python-version)"
RUN uv tool install --python "$(cat ${XDG_DATA_HOME}/dev-container-fortress/.python-version)" \
    ${XDG_DATA_HOME}/dev-container-fortress/ft
RUN ft completion install zsh
RUN if [ "${WORKSPACE_TOOL_LAYER_SECRETS}" = "1" ]; then \
      sudo apt-get update \
      && sudo apt-get install -y --no-install-recommends gnupg pass pinentry-curses \
      && sudo rm -rf /var/lib/apt/lists/*; \
    fi

RUN uv --version \
  && test -f ${XDG_DATA_HOME}/dev-container-fortress/completions/zsh/_ft \
  && test -s ${XDG_DATA_HOME}/dev-container-fortress/brew-floor.txt \
  && if [ "${HOMEBREW_FLOOR}" = "warm" ]; then \
       tenv --version && starship --version && zoxide --version && atuin --version \
       && nvim --version && rg --version && gh --version && glab --version \
       && if [ "${WORKSPACE_TOOL_LAYER_AWS}" = "1" ]; then aws --version; fi; \
     fi \
  && if [ "${WORKSPACE_TOOL_LAYER_SECRETS}" = "1" ]; then gpg --version && pass --version; fi \
  && fzf --version
