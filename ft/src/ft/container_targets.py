"""Data-driven registry of disposable container targets managed by ft.

Adding a container target should mean adding one entry to ``CONTAINER_TARGETS``
plus its Dockerfile and manifest assets, rather than editing scattered
target-specific branches.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerTarget:
    """One disposable container target and its fixed operator metadata.

    Attributes:
        name: Short target name used on the CLI and in ``containers/<name>``.
        ssh_host_port: Loopback host port forwarded to the container's sshd.
        architectures: Normalized host architectures the image can be built for.
        release_build_arg: Dockerfile build argument that selects the base OS
            release, or None when the target has no release selection.
    """

    name: str
    ssh_host_port: int
    architectures: tuple[str, ...] = ("amd64", "arm64")
    release_build_arg: str | None = None

    @property
    def ssh_host_target_name(self) -> str:
        """Return the default ``hosts.toml`` target name for this container.

        Returns:
            The host-target name, for example ``dev-fortress-ubuntu``.
        """
        return f"dev-fortress-{self.name}"

    def supports_architecture(self, architecture: str) -> bool:
        """Return whether this target can be built for one architecture.

        Args:
            architecture: Normalized architecture such as ``amd64`` or ``arm64``.

        Returns:
            True when the architecture is supported for this target.
        """
        return architecture in self.architectures


CONTAINER_TARGETS: dict[str, ContainerTarget] = {
    target.name: target
    for target in (
        ContainerTarget(
            name="ubuntu", ssh_host_port=2222, release_build_arg="UBUNTU_RELEASE"
        ),
        ContainerTarget(name="alpine", ssh_host_port=2223),
        # The official archlinux image is published for amd64 only.
        ContainerTarget(name="arch", ssh_host_port=2224, architectures=("amd64",)),
    )
}

KNOWN_CONTAINER_TARGETS: tuple[str, ...] = tuple(CONTAINER_TARGETS)
