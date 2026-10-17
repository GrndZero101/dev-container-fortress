# AWS Arch AMI

This stack turns the official Arch Linux cloud image into a private AMI so the
disposable host stack in [`../aws-disposable-ubuntu/`](../aws-disposable-ubuntu/)
can boot Arch hosts with `os = "arch"`.

It exists because the only public Arch AMIs in `ap-southeast-1` come from an
unverified community publisher. Importing the image ourselves keeps the trust
chain on Arch Linux's own signing key.

> [!NOTE]
> The AMI is a reusable image, not a disposable host. Keep this stack applied
> while you still test Arch hosts, and destroy it once you stop. Hosts launched
> from the AMI do not depend on this stack after they boot.

## Trust Chain

1. `prepare-image.zsh` downloads `Arch-Linux-x86_64-cloudimg-<version>.qcow2`
   from `geo.mirror.pkgbuild.com`, the image published by the Arch
   [arch-boxes](https://gitlab.archlinux.org/archlinux/arch-boxes) project.
2. It checks the published SHA256 and then verifies the detached signature in
   a throwaway GnuPG home against `arch-boxes.asc`.
3. `arch-boxes.asc` is the release CI key copied from the arch-boxes README on
   `gitlab.archlinux.org`. The script also requires the signature's primary key
   fingerprint to equal `1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F`.
4. Only then does it convert the image to a stream-optimized VMDK.

> [!WARNING]
> The arch-boxes signing subkey expires on 2027-05-28. When verification starts
> failing after that date, re-copy the key block from the arch-boxes README and
> confirm the primary fingerprint has not changed before updating the pin.

## Image Facts

- GPT with a BIOS boot partition and an EFI system partition, so the AMI uses
  `boot_mode = "uefi-preferred"`
- btrfs root filesystem, grown to the root volume size by cloud-init on boot
- generic initramfs including NVMe and Xen block drivers, so Nitro and Xen
  instance families both boot
- cloud-init creates the `arch` login user from the EC2 key pair
- `/usr/bin/python3` is present because cloud-init depends on it, which
  satisfies the Ansible interpreter contract
- no SSM agent, so Session Manager is not available on Arch hosts

## Usage

Prepare the image. It prints the VMDK path as its last line and caches
downloads under `${XDG_CACHE_HOME:-~/.cache}/dev-container-fortress/arch-ami`:

```bash
image_path=$(infra/aws-arch-ami/prepare-image.zsh | tail -n 1)
```

Register the AMI:

```bash
terraform -chdir=infra/aws-arch-ami init
terraform -chdir=infra/aws-arch-ami apply \
  -var image_version=20261015.611680 \
  -var "image_path=${image_path}"
```

The snapshot import usually takes 10 to 20 minutes.

To bump the image, set `ARCH_CLOUDIMG_VERSION` to a newer arch-boxes release,
rerun `prepare-image.zsh`, and apply with the matching `image_version`. The
host stack picks the newest self-owned AMI named `dev-fortress-arch-*`.

## Resources

- one private S3 staging bucket and the uploaded VMDK
- one VM Import service role with read access to that bucket
- one EBS snapshot import
- one AMI registered from that snapshot

## Cost and Teardown

The bucket holds about 0.6 GiB and the snapshot about 2 GiB, which costs a few
US cents per month. Destroy the stack when Arch host testing is finished:

```bash
terraform -chdir=infra/aws-arch-ami destroy \
  -var image_version=20261015.611680 \
  -var "image_path=${image_path}"
```
