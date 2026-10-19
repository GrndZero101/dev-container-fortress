ARG UV_DISTROLESS_IMAGE=ghcr.io/astral-sh/uv:latest
ARG ARCH_BASE_IMAGE=archlinux:base
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

FROM ${ARCH_BASE_IMAGE} AS arch-base

# Arch is a rolling release. Pin every pacman transaction to one Arch Linux
# Archive snapshot so the same date always yields the same package set. Bump
# this date deliberately, the same way manifest tool versions are bumped.
ARG ARCH_ARCHIVE_DATE="2026/10/01"

ENV LANG=C.UTF-8

# base-devel, file, and procps-ng are Homebrew's Linux prerequisites. Refresh
# the keyring first so snapshot packages signed by newer keys verify.
# -Suu then allows downgrades, so packages in the base image converge on the
# snapshot even when the base image is newer than the snapshot date.
RUN printf 'Server = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "${ARCH_ARCHIVE_DATE}" \
    > /etc/pacman.d/mirrorlist \
  && pacman-key --init \
  && pacman-key --populate archlinux \
  && pacman -Syy --noconfirm archlinux-keyring \
  && pacman -Suu --noconfirm --needed \
    base-devel \
    ca-certificates \
    openssl \
    curl \
    file \
    fzf \
    git \
    gzip \
    openssh \
    procps-ng \
    python \
    rsync \
    sudo \
    tar \
    tmux \
    unzip \
    which \
    xdg-utils \
    zsh \
  && pacman -Scc --noconfirm

RUN cat > /etc/profile.d/10-dev-container-fortress-path.sh <<'EOF' \
  && chmod 0644 /etc/profile.d/10-dev-container-fortress-path.sh
case ":${PATH}:" in
  *":${XDG_BIN_HOME:-$HOME/.local/bin}:"*) ;;
  *) export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:${PATH}" ;;
esac
EOF

FROM arch-base AS arch-runtime

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
ARG WORKSPACE_TOOL_LAYER_GITFORGE="0"
ARG WORKSPACE_TOOL_LAYER_SECRETS="0"
ARG WORKSPACE_TOOL_LAYER_AWS="0"
# warm installs the Homebrew floor into the image; cold leaves the prefix
# empty for ft-brew-floor to fill on first start. CI publishes cold images.
ARG HOMEBREW_FLOOR="warm"

COPY --from=uv-distroless /uv /uvx /usr/local/bin/
COPY containers/common/install-corporate-ca.sh /usr/local/bin/install-corporate-ca
COPY containers/common/ft-host-browser-open.sh /usr/local/bin/ft-host-browser-open
COPY containers/common/install-shell-config.sh /usr/local/bin/install-shell-config
COPY containers/common/start-test-target.sh /usr/local/bin/start-test-target
COPY containers/common/ensure-claude-code.sh /usr/local/bin/ft-ensure-claude-code
COPY containers/common/brew-floor.sh /usr/local/bin/ft-brew-floor

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
  && install -d -o ${USER_UID} -g ${USER_GID} /home/linuxbrew /home/linuxbrew/.linuxbrew \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshenv \
  && printf '%s\n' '# Managed by dev-container-fortress.' > /home/${USERNAME}/.zshrc \
  && chown ${USER_UID}:${USER_GID} /home/${USERNAME}/.zshenv /home/${USERNAME}/.zshrc \
  && chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}/.local /home/${USERNAME}/.cache /home/${USERNAME}/.config \
  && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-${USERNAME} \
  && chmod 0440 /etc/sudoers.d/90-${USERNAME}

RUN chmod 0755 /usr/local/bin/install-corporate-ca /usr/local/bin/ft-host-browser-open /usr/local/bin/install-shell-config /usr/local/bin/start-test-target /usr/local/bin/ft-ensure-claude-code /usr/local/bin/ft-brew-floor
RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    /usr/local/bin/install-corporate-ca /tmp/build-context "${CORPORATE_CA_CERT_DIR}"

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
ENV PATH=${HOME}/.local/bin:${HOMEBREW_PREFIX}/bin:${HOMEBREW_PREFIX}/sbin:${PATH}
ENV SHELL_CONFIG_PROFILE=${SHELL_CONFIG_PROFILE_DEFAULT}

WORKDIR ${HOME}

COPY --chown=${USER_UID}:${USER_GID} ft ${XDG_DATA_HOME}/dev-container-fortress/ft
COPY --chown=${USER_UID}:${USER_GID} .python-version ${XDG_DATA_HOME}/dev-container-fortress/.python-version

USER ${USERNAME}

RUN --mount=type=bind,source=.,target=/tmp/build-context,readonly \
    /usr/local/bin/install-shell-config /tmp/build-context
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
# The repo-root .python-version is the one Python pin for Dev Fortress code.
RUN uv python install "$(cat ${XDG_DATA_HOME}/dev-container-fortress/.python-version)"
RUN uv tool install --python "$(cat ${XDG_DATA_HOME}/dev-container-fortress/.python-version)" \
    ${XDG_DATA_HOME}/dev-container-fortress/ft
RUN ft completion install zsh
# Tool layers that come from Homebrew extend the floor list, so their formulae
# also reach a workspace volume that was seeded before the layer was added.
RUN ft tool formulae --manifest ${XDG_DATA_HOME}/dev-container-fortress/ft/tools/tool-pool.toml \
    > ${XDG_DATA_HOME}/dev-container-fortress/brew-floor.txt \
  && if [ "${WORKSPACE_TOOL_LAYER_AWS}" = "1" ]; then \
       echo awscli >> ${XDG_DATA_HOME}/dev-container-fortress/brew-floor.txt; \
     fi
# A warm image carries the floor, so a fresh workspace volume seeds from it in
# seconds. The download cache stays out of the image.
RUN --mount=type=cache,target=/home/vscode/.cache/Homebrew,uid=1000,gid=1000 \
    case "${HOMEBREW_FLOOR}" in \
      warm) ft-brew-floor ;; \
      cold) ;; \
      *) echo "HOMEBREW_FLOOR must be warm or cold, not ${HOMEBREW_FLOOR}" >&2; exit 1 ;; \
    esac

# Optional layers come from the official repositories, so pacman verifies
# package signatures against the pinned archive snapshot.
RUN if [ "${WORKSPACE_TOOL_LAYER_SECRETS}" = "1" ]; then \
      sudo pacman -S --noconfirm --needed gnupg pass pinentry \
      && sudo pacman -Scc --noconfirm; \
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
