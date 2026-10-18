"""Optional host bootstrap components for ft.

Some components, such as agentic coding tools, are large and not wanted on
every machine, so the host bootstrap installs them only when selected. The
selection is resolved here and handed to Ansible as inventory variables; the
roles never decide on their own. Most options are on/off and set one boolean
each. Options that share an Ansible variable, such as the tmux profiles, are
one pick-one choice: at most one of them may be selected, and the variable
takes its value, or ``none`` when no member is selected.

Precedence, highest first: an explicit ``--options`` value, the
``DEV_CONTAINER_FORTRESS_OPTIONS`` environment variable, the saved
``options.toml`` file, and finally no options at all. ``none`` selects nothing.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

OPTIONS_ENV = "DEV_CONTAINER_FORTRESS_OPTIONS"
NONE_KEYWORD = "none"


@dataclass(frozen=True)
class BootstrapOption:
    """One optional component of the host bootstrap.

    Attributes:
        name: The identifier used in flags, the environment, and the config file.
        summary: A one-line description for listings and the picker.
        ansible_var: The inventory variable that enables the component's role.
        value: For a pick-one choice, the value ``ansible_var`` takes when this
            option is selected; ``None`` for an on/off option.
    """

    name: str
    summary: str
    ansible_var: str
    value: str | None = None


TMUX_PROFILE_VAR = "dev_container_fortress_tmux_profile"


# The catalog is ordered as the picker shows it.
CATALOG: tuple[BootstrapOption, ...] = (
    BootstrapOption(
        name="claude-code",
        summary="Claude Code via its native installer (about 270 MB; updates itself)",
        ansible_var="dev_container_fortress_claude_code_manage",
    ),
    BootstrapOption(
        name="tmux-minimal",
        summary="tmux profile: plain tmux settings, no plugins or downloads",
        ansible_var=TMUX_PROFILE_VAR,
        value="minimal",
    ),
    BootstrapOption(
        name="tmux-full",
        summary="tmux profile: catppuccin, tpm plugins, sesh picker, gitmux status",
        ansible_var=TMUX_PROFILE_VAR,
        value="full",
    ),
    BootstrapOption(
        name="tmux-raidboss",
        summary="tmux profile: tmux-full plus a second status line of system modules",
        ansible_var=TMUX_PROFILE_VAR,
        value="raidboss",
    ),
)


@dataclass(frozen=True)
class OptionSelection:
    """A resolved option selection and where it came from.

    Attributes:
        names: The selected option names, in catalog order.
        source: ``flag``, ``environment``, ``config``, or ``default``.
    """

    names: tuple[str, ...]
    source: str


def options_config_path() -> Path:
    """Return the XDG-aligned path of the saved option selection.

    Returns:
        ``${XDG_CONFIG_HOME}/dev-container-fortress/options.toml``.
    """
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg_config_home / "dev-container-fortress" / "options.toml"


def parse_option_names(values: list[str] | str) -> tuple[str, ...]:
    """Validate option names and return them in catalog order.

    Args:
        values: Option names, each of which may itself be comma-separated.
            ``none`` on its own selects nothing.

    Returns:
        The unique selected names, ordered as in the catalog.

    Raises:
        ValueError: When a name is not in the catalog, ``none`` is mixed
            with other names, or two members of one pick-one choice are selected.
    """
    raw = [values] if isinstance(values, str) else values
    names = {
        name.strip().lower()
        for value in raw
        for name in value.split(",")
        if name.strip()
    }
    if NONE_KEYWORD in names:
        if len(names) > 1:
            raise ValueError(f"'{NONE_KEYWORD}' cannot be combined with other options")
        return ()
    known = {option.name for option in CATALOG}
    unknown = sorted(names - known)
    if unknown:
        supported = ", ".join([*sorted(known), NONE_KEYWORD])
        raise ValueError(
            f"unknown option(s): {', '.join(unknown)} (supported: {supported})"
        )
    selected = tuple(option for option in CATALOG if option.name in names)
    _check_pick_one(selected)
    return tuple(option.name for option in selected)


def _check_pick_one(selected: tuple[BootstrapOption, ...]) -> None:
    """Reject a selection with two members of one pick-one choice.

    Args:
        selected: The selected catalog entries.

    Raises:
        ValueError: When two selected options share a pick-one variable.
    """
    seen: dict[str, str] = {}
    for option in selected:
        if option.value is None:
            continue
        if option.ansible_var in seen:
            raise ValueError(
                f"choose one of {seen[option.ansible_var]} and {option.name}, not both"
            )
        seen[option.ansible_var] = option.name


def load_saved_options(path: Path | None = None) -> tuple[str, ...] | None:
    """Read the saved option selection.

    Args:
        path: The config file; defaults to :func:`options_config_path`.

    Returns:
        The saved names, or ``None`` when no config file exists.

    Raises:
        ValueError: When the file is not valid TOML or names unknown options.
    """
    config_path = path or options_config_path()
    if not config_path.is_file():
        return None
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{config_path} is not valid TOML: {error}") from error
    enabled = data.get("enabled", [])
    if not isinstance(enabled, list) or not all(isinstance(n, str) for n in enabled):
        raise ValueError(f"{config_path}: 'enabled' must be a list of option names")
    try:
        return parse_option_names(enabled) if enabled else ()
    except ValueError as error:
        raise ValueError(f"{config_path}: {error}") from error


def save_options(names: tuple[str, ...], path: Path | None = None) -> Path:
    """Write the option selection to the config file.

    Args:
        names: Validated option names.
        path: The config file; defaults to :func:`options_config_path`.

    Returns:
        The path written.
    """
    config_path = path or options_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    enabled = ", ".join(f'"{name}"' for name in names)
    config_path.write_text(
        "# Optional Dev Fortress host bootstrap components.\n"
        "# Edit by hand or run `ft options pick`; `ft options` lists the choices.\n"
        f"enabled = [{enabled}]\n",
        encoding="utf-8",
    )
    return config_path


def resolve_options(
    explicit: list[str] | None = None, path: Path | None = None
) -> OptionSelection:
    """Resolve the option selection from flags, environment, and config.

    Args:
        explicit: ``--options`` values; ``None`` or empty when not given.
        path: The config file; defaults to :func:`options_config_path`.

    Returns:
        The selection and the source that decided it.

    Raises:
        ValueError: When any source names unknown options.
    """
    if explicit:
        return OptionSelection(parse_option_names(explicit), "flag")
    environment = os.environ.get(OPTIONS_ENV, "").strip()
    if environment:
        try:
            return OptionSelection(parse_option_names(environment), "environment")
        except ValueError as error:
            raise ValueError(f"{OPTIONS_ENV}: {error}") from error
    saved = load_saved_options(path)
    if saved is not None:
        return OptionSelection(saved, "config")
    return OptionSelection((), "default")


def option_ansible_vars(names: tuple[str, ...]) -> dict[str, bool | str]:
    """Map a selection to the inventory variables of every catalog entry.

    Args:
        names: Validated option names.

    Returns:
        A boolean per on/off option, ``True`` only when selected, and per
        pick-one variable the selected member's value, or ``none``.
    """
    variables: dict[str, bool | str] = {}
    for option in CATALOG:
        if option.value is None:
            variables[option.ansible_var] = option.name in names
        elif option.name in names:
            variables[option.ansible_var] = option.value
        else:
            variables.setdefault(option.ansible_var, NONE_KEYWORD)
    return variables
