#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
git_common="$(cd "$repo" && cd "$(git rev-parse --git-common-dir)" && pwd)"
git_dir="$(git -C "$repo" rev-parse --absolute-git-dir)"
docker build -q -t labnotes-vhs "$here" > /dev/null
mkdir -p "$here/../public/demos"
for tape in "$here"/*.tape; do
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$repo:/labnotes" -v "$git_common:$git_common:ro" \
    -e GIT_DIR="$git_dir" -e GIT_WORK_TREE=/labnotes \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
    -w /labnotes/docs/demos labnotes-vhs "$(basename "$tape")"
done
