#!/bin/sh

# Install AWS CLI v2 through the repo-owned container helper path.
# The underlying payload still comes from AWS, but the image contract stays
# Dev Fortress-owned and can be reused consistently across container targets.

set -eu

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

# AWS names its Linux bundles after the kernel machine name, so map the build
# architecture explicitly and fail clearly on anything AWS does not publish.
machine="$(uname -m)"
case "${machine}" in
  x86_64 | amd64) aws_arch="x86_64" ;;
  aarch64 | arm64) aws_arch="aarch64" ;;
  *)
    echo "install-aws-cli: unsupported architecture: ${machine}" >&2
    exit 1
    ;;
esac

cd "${tmp_dir}"
curl -LsS "https://awscli.amazonaws.com/awscli-exe-linux-${aws_arch}.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
