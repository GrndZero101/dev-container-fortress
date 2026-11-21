"""Tests for workbench definitions, rendering, and the ft workbench commands."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from ft.cli import _load_workspace_profile_manifest, app
from ft.devcontainer import browser_bridge_settings
from ft.workbench import (
    WorkbenchDefinition,
    guardrail_violations,
    load_workbench,
    render_workbench,
    repo_dir_name,
    workbench_directory,
    workbench_toml,
)
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "workbench" / "example.toml"
runner = CliRunner()


def _render(definition: WorkbenchDefinition, toml_path: Path) -> dict[str, object]:
    """Render a workbench and return its parsed devcontainer definition.

    Args:
        definition: The workbench.
        toml_path: Its TOML file path.

    Returns:
        The parsed ``devcontainer.json``.
    """
    files = render_workbench(definition, toml_path, _load_workspace_profile_manifest())
    path = workbench_directory(definition, toml_path) / ".devcontainer"
    return json.loads(files[path / "devcontainer.json"])


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("https://github.com/owner/repo.git", "repo"),
        ("https://gitlab.com/group/sub/repo/", "repo"),
        ("git@github.com:owner/repo.git", "repo"),
        ("git@host:repo", "repo"),
    ],
)
def test_repo_dir_name_matches_git_clone(url: str, name: str) -> None:
    """Repos clone into the folder name git itself would pick."""
    assert repo_dir_name(url) == name


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"options": ["tmux-full"]}, "host-only"),
        ({"mounts": ["home"]}, "unknown mounts home"),
        ({"repos": ["https://a/x.git", "git@b:y/x.git"]}, "same folder: x"),
        ({"name": "Has Spaces"}, "should match pattern"),
        ({"trust": "sealed"}, "trust"),
    ],
)
def test_definition_rejects_invalid_settings(
    fields: dict[str, object], message: str
) -> None:
    """Invalid options, mounts, repos, names, and trust levels fail validation."""
    with pytest.raises(ValueError, match=message):
        WorkbenchDefinition.model_validate({"name": "wb", **fields})


def test_toml_round_trips(tmp_path: Path) -> None:
    """The commented TOML a workbench writes loads back unchanged."""
    definition = WorkbenchDefinition(
        name="wb",
        options=["claude-code"],
        mounts=["aws"],
        repos=["https://github.com/owner/one.git", "https://github.com/owner/two.git"],
    )
    path = tmp_path / "wb.toml"
    path.write_text(workbench_toml(definition), encoding="utf-8")
    assert load_workbench(path) == definition
    assert "# local_build = " in path.read_text(encoding="utf-8")


def test_directory_defaults_and_resolves_against_the_file(tmp_path: Path) -> None:
    """Unset means ~/workbenches/<name>; relative paths follow the TOML file."""
    toml_path = tmp_path / "conf" / "wb.toml"
    assert workbench_directory(WorkbenchDefinition(name="wb"), toml_path) == (
        Path.home() / "workbenches" / "wb"
    )
    relative = WorkbenchDefinition(name="wb", directory="../out")
    assert workbench_directory(relative, toml_path) == tmp_path / "out"


def test_render_uses_profile_mounts_and_selected_options(tmp_path: Path) -> None:
    """Profile mounts, extras, and selected options shape the definition."""
    definition = WorkbenchDefinition(
        name="wb", profile="ubuntu-gitforge", local_build=str(REPO_ROOT)
    )
    content = _render(definition, tmp_path / "wb.toml")
    sources = [mount["source"] for mount in content["mounts"]]
    assert "dev-fortress-wb-wb-cache" in sources
    assert "dev-fortress-wb-wb-brew" in sources
    assert not any("claude" in source for source in sources)
    assert content["containerEnv"]["DEV_CONTAINER_FORTRESS_OPTIONS"] == ""
    assert "CLAUDE_CONFIG_DIR" not in content["containerEnv"]
    assert content["postStartCommand"] == "ft-brew-floor"

    selected = definition.model_copy(update={"options": ["claude-code"]})
    content = _render(selected, tmp_path / "wb.toml")
    assert content["containerEnv"]["CLAUDE_CONFIG_DIR"] == "/home/vscode/.claude"
    assert content["postStartCommand"] == "ft-brew-floor && ft-ensure-claude-code"


def test_render_wires_the_browser_bridge_within_the_guardrails(
    tmp_path: Path,
) -> None:
    """A workbench gets the browser bridge for CLI terminal mode."""
    content = _render(WorkbenchDefinition(name="wb"), tmp_path / "wb.toml")
    bridge = browser_bridge_settings()
    assert content["initializeCommand"] == bridge["initializeCommand"]
    assert bridge["mount"] in content["mounts"]
    for name, value in bridge["containerEnv"].items():
        assert content["containerEnv"][name] == value
    assert guardrail_violations(content) == []


def test_render_local_build_adds_layers_relative_to_the_definition(
    tmp_path: Path,
) -> None:
    """A local build points at the checkout and turns on the profile's layers."""
    definition = WorkbenchDefinition(
        name="wb",
        profile="ubuntu-full-rolling",
        local_build=str(REPO_ROOT),
        directory=str(tmp_path / "wb"),
    )
    build = _render(definition, tmp_path / "wb.toml")["build"]
    assert build["dockerfile"] == str(REPO_ROOT / "containers/ubuntu/Dockerfile")
    assert build["context"] == str(REPO_ROOT)
    assert build["args"]["WORKSPACE_TOOL_LAYER_SECRETS"] == "1"
    assert build["args"]["UBUNTU_RELEASE"] == "rolling"

    # A checkout cloned inside the workbench stays relative, so the folder moves.
    clone = tmp_path / "wb" / "repos" / "dev-container-fortress"
    shutil.copytree(REPO_ROOT / "containers", clone / "containers")
    inside = definition.model_copy(
        update={"local_build": "repos/dev-container-fortress"}
    )
    build = _render(inside, tmp_path / "wb.toml")["build"]
    assert build["dockerfile"] == (
        "../repos/dev-container-fortress/containers/ubuntu/Dockerfile"
    )
    assert build["context"] == "../repos/dev-container-fortress"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"profile": "nope"}, "unknown profile 'nope'"),
        ({"profile": "ubuntu-gitforge"}, "no published image"),
        ({"local_build": "/nonexistent"}, "local_build has no ubuntu Dockerfile"),
    ],
)
def test_render_rejects_unbuildable_definitions(
    tmp_path: Path, fields: dict[str, object], message: str
) -> None:
    """Unknown profiles, unpublished images, and bad checkouts fail clearly."""
    with pytest.raises(ValueError, match=message):
        _render(WorkbenchDefinition(name="wb", **fields), tmp_path / "wb.toml")


def test_example_workbench_is_rendered() -> None:
    """The checked-in example matches a fresh render."""
    result = runner.invoke(app, ["workbench", "render", str(EXAMPLE), "--check"])
    assert result.exit_code == 0, result.output


# One forbidden item per case: a devcontainer.json fragment and the reason
# `render --check` must report for it.
GUARDRAIL_CASES = {
    "docker-socket": (
        {
            "mounts": [
                {
                    "source": "/var/run/docker.sock",
                    "target": "/var/run/docker.sock",
                    "type": "bind",
                }
            ]
        },
        "container-runtime socket",
    ),
    "podman-socket-string": (
        {
            "mounts": [
                "source=/run/user/1000/podman/podman.sock,"
                "target=/run/podman/podman.sock,type=bind"
            ]
        },
        "container-runtime socket",
    ),
    "docker-socket-run-arg": (
        {"runArgs": ["-v", "/var/run/docker.sock:/var/run/docker.sock"]},
        "container-runtime socket",
    ),
    "host-home": (
        {"mounts": ["source=${localEnv:HOME},target=/host,type=bind"]},
        "host home directory",
    ),
    "host-home-cross-platform": (
        {
            "mounts": [
                "source=${localEnv:HOME}${localEnv:USERPROFILE},target=/host,type=bind"
            ]
        },
        "host home directory",
    ),
    "host-home-path": (
        {"runArgs": ["--mount", "type=bind,src=/home/someone,dst=/host"]},
        "host home directory",
    ),
    "host-root": (
        {"mounts": [{"source": "/", "target": "/host", "type": "bind"}]},
        "host root filesystem",
    ),
    "windows-drive": (
        {"mounts": ["source=/mnt/c,target=/c,type=bind"]},
        "Windows drive",
    ),
    "windows-drive-workspace-mount": (
        {"workspaceMount": "source=/mnt/c/Users/me,target=/workspace,type=bind"},
        "Windows drive",
    ),
    "privileged-run-arg": ({"runArgs": ["--privileged"]}, "runs privileged"),
    "privileged-property": ({"privileged": True}, "runs privileged"),
    "cap-add-run-arg": ({"runArgs": ["--cap-add=SYS_ADMIN"]}, "adds capabilities"),
    "cap-add-property": ({"capAdd": ["SYS_PTRACE"]}, "adds capabilities"),
    "host-network": ({"runArgs": ["--network=host"]}, "host network"),
    "host-network-net": ({"runArgs": ["--net", "host"]}, "host network"),
}


@pytest.mark.parametrize(
    ("fragment", "reason"), GUARDRAIL_CASES.values(), ids=GUARDRAIL_CASES.keys()
)
def test_render_check_fails_on_guardrail_breach(
    tmp_path: Path, fragment: dict[str, object], reason: str
) -> None:
    """`render --check` names each forbidden socket, mount, privilege, or network."""
    folder = tmp_path / "example"
    shutil.copytree(EXAMPLE.parent, folder)
    devcontainer = folder / ".devcontainer" / "devcontainer.json"
    content = json.loads(devcontainer.read_text(encoding="utf-8"))
    for key, value in fragment.items():
        if key == "mounts":
            content["mounts"] = [*content["mounts"], *value]
        else:
            content[key] = value
    devcontainer.write_text(json.dumps(content), encoding="utf-8")

    result = runner.invoke(
        app, ["workbench", "render", str(folder / "example.toml"), "--check"]
    )
    assert result.exit_code == 1
    guardrail_lines = [
        line for line in result.output.splitlines() if line.startswith("guardrail:")
    ]
    assert any(reason in line for line in guardrail_lines), result.output


def test_guardrail_allows_volumes_repo_binds_and_other_sockets() -> None:
    """Named volumes, binds below home, other sockets, and bridge networks pass."""
    content = {
        "mounts": [
            {"source": "dev-fortress-wb-x-cache", "target": "/c", "type": "volume"},
            "source=${localEnv:SSH_AUTH_SOCK},target=/ssh-agent,type=bind",
            "source=/home/someone/.1password/agent.sock,target=/a.sock,type=bind",
            {"source": "/home/someone/src/repo", "target": "/r", "type": "bind"},
        ],
        "runArgs": ["--network=bridge", "-v", "named:/data", "--init"],
        "privileged": False,
    }
    assert guardrail_violations(content) == []


def test_render_refuses_a_guardrail_breach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The renderer refuses to emit a definition that breaks a guardrail."""
    monkeypatch.setattr(
        "ft.workbench.volume_mounts",
        lambda paths, source: [
            {"source": "/var/run/docker.sock", "target": "/s", "type": "bind"}
        ],
    )
    with pytest.raises(ValueError, match="workbench guardrails: .*runtime socket"):
        _render(WorkbenchDefinition(name="wb"), tmp_path / "wb.toml")


def test_example_workbench_passes_guardrail_check() -> None:
    """The shipped example renders clean and passes `render --check`."""
    devcontainer = EXAMPLE.parent / ".devcontainer" / "devcontainer.json"
    content = json.loads(devcontainer.read_text(encoding="utf-8"))
    assert guardrail_violations(content) == []
    result = runner.invoke(app, ["workbench", "render", str(EXAMPLE), "--check"])
    assert result.exit_code == 0, result.output


def test_init_writes_renders_and_refuses_to_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`init` writes the XDG file and the folder; a second `init` needs --force."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    args = [
        "workbench",
        "init",
        "wb",
        "--options",
        "claude-code",
        "--directory",
        str(tmp_path / "wb"),
        "--repo",
        "https://github.com/owner/one.git",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    toml_path = (
        tmp_path / "config" / "dev-container-fortress" / "workbenches" / "wb.toml"
    )
    assert load_workbench(toml_path).options == ["claude-code"]
    workspace = json.loads((tmp_path / "wb" / "wb.code-workspace").read_text())
    assert workspace["folders"] == [{"path": "."}, {"path": "repos/one"}]
    assert (tmp_path / "wb" / ".devcontainer" / "devcontainer.json").is_file()

    assert runner.invoke(app, args).exit_code == 1
    assert runner.invoke(app, [*args, "--force"]).exit_code == 0

    listed = runner.invoke(app, ["workbench", "list"])
    assert "wb" in listed.output and "claude-code" in listed.output


def test_render_check_reports_a_hand_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`render --check` fails after a hand edit, and `render` repairs it."""
    folder = tmp_path / "example"
    shutil.copytree(EXAMPLE.parent, folder)
    toml_path = folder / "example.toml"
    workspace = folder / "example.code-workspace"
    workspace.write_text("{}\n", encoding="utf-8")

    result = runner.invoke(app, ["workbench", "render", str(toml_path), "--check"])
    assert result.exit_code == 1
    assert "stale: example.code-workspace" in result.output
    assert runner.invoke(app, ["workbench", "render", str(toml_path)]).exit_code == 0
    assert workspace.read_text() == (EXAMPLE.parent / workspace.name).read_text()


def test_clone_skips_present_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`clone` clones only the repos missing from repos/."""
    toml_path = tmp_path / "wb.toml"
    toml_path.write_text(
        workbench_toml(
            WorkbenchDefinition(
                name="wb",
                directory=".",
                repos=["https://github.com/o/one.git", "https://github.com/o/two.git"],
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "repos" / "one").mkdir(parents=True)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "ft.cli._run_streaming_command",
        lambda command: (
            commands.append(command) or subprocess.CompletedProcess(command, 0)
        ),
    )
    result = runner.invoke(app, ["workbench", "clone", str(toml_path)])
    assert result.exit_code == 0, result.output
    assert commands == [
        [
            "git",
            "clone",
            "https://github.com/o/two.git",
            str(tmp_path / "repos" / "two"),
        ]
    ]
