#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
docker build -q -t labnotes-vhs "$here" > /dev/null
mkdir -p "$here/../public/demos"
for tape in "$here"/*.tape; do
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$repo:/labnotes" -w /labnotes/docs/demos labnotes-vhs "$(basename "$tape")"
done
