# WSL Bootstrap Notes

WSL2 Ubuntu uses the same one-command onramp as any Ubuntu machine: follow the
[Zero to Hero Quickstart](quickstart.md). This page collects what is specific
to WSL2.

The model:

- Windows is the outer host, and the Ubuntu WSL2 distro is the Dev Fortress
  target
- the bootstrap runs inside the distro against `localhost`, so no SSH is needed
- native Windows shell setup and Windows host management are out of scope

## :checkered_flag: Clean Start on Windows

The path inside the distro is the same as on any Ubuntu machine. What WSL2
adds is the Windows side around it:

1. **Install WSL2 and Ubuntu.** In PowerShell, run `wsl --install` on a
   machine without WSL (then reboot), list the releases with
   `wsl --list --online`, and install one with `wsl --install -d <name>`, for
   example the newest Ubuntu LTS. Create your Linux user when it opens.
2. **Inside the distro,** from `~`, follow the [quickstart](quickstart.md).
   Skip its font command; the font belongs on Windows. To work on Dev Fortress
   itself, the [developer path](../DEVELOPMENT.md#rocket-zero-to-hero-developer-path)
   adds a few steps on top of the same install.
3. **On Windows,** install JetBrainsMono Nerd Font as
   [quickstart step 5](quickstart.md#abc-5-set-the-terminal-font-recommended)
   describes, and select it in the Windows Terminal profile for the distro.
4. **VS Code on Windows,** with the WSL and Dev Containers extensions. Add the
   `dev.containers.executeInWSL` settings from the
   [devcontainer usage guide](guides/devcontainer-usage.md), and keep Docker
   Desktop's WSL integration off for this distro, so devcontainers use the
   distro's Docker CE.
5. **Open a workbench** from a distro terminal with
   `code ~/workbenches/<name>`, which opens VS Code connected to WSL, then
   choose "Reopen in Container".

## :clipboard: Before the Installer

> [!IMPORTANT]
> Start from the Linux filesystem, for example `~`, and keep the checkout
> there. A checkout under `/mnt/c/...` gives slow, unrepresentative shell,
> Ansible, and Homebrew behavior.

The installer needs `systemd`, because the Docker role manages Docker CE as a
systemd service. Recent Ubuntu store images enable it. If it is off, the
installer stops with the fix:

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

Then run `wsl --shutdown` from Windows, reopen the distro, and re-run the
installer.

## :whale: Docker

Dev Fortress installs Docker CE inside the distro, the same baseline as an
Ubuntu cloud host. Docker Desktop's WSL integration is not part of the Dev
Fortress contract; if you already use it in this distro, choose one runtime
rather than mixing them.

After the first run, open a new terminal before using Docker without `sudo`,
so your user picks up the `docker` group.

## :link: Windows Interop

WSL2 interop lets Linux run Windows programs: `wsl.exe`, `cmd.exe`, `wslview`
for opening browsers, and the Windows Git credential manager.

> [!WARNING]
> All WSL2 distros share one kernel, so stopping any other distro can switch
> off interop for every distro. Restore it with:
>
> ```sh
> sudo systemctl restart systemd-binfmt
> ```
>
> Dev Fortress does not rely on interop for the bootstrap, so a run still
> converges while it is off.

## :key: SSH From Windows

VS Code on Windows reads the Windows OpenSSH config, not the one inside WSL.
Write a host entry there from WSL with:

```sh
ft host ssh-config <target> --install --windows
```

Pass `--windows-ssh-dir /mnt/c/Users/<you>/.ssh` when interop is off, because
the Windows profile lookup needs it.

## :hammer_and_wrench: Developing on WSL

To work on WSL support itself, keep a WSL-native checkout, open it through VS
Code Remote - WSL or an equivalent, and run the Dev Fortress loop from inside
the distro. Path, shell, Homebrew, and Ansible behavior has to be checked in
the real WSL environment rather than inferred from macOS or EC2.
