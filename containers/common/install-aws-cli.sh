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

cd "${tmp_dir}"
curl -LsS "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update
