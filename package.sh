#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARCHIVE_DIR=$(dirname -- "$ROOT")
ARCHIVE_NAME="adfo_son_hali_share.tar.gz"
OUT_FILE="$ARCHIVE_DIR/$ARCHIVE_NAME"

tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.venv-linux' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='bin/app' \
  --exclude='*.tar.gz' \
  -czf "$OUT_FILE" \
  -C "$ROOT" .

echo "Created: $OUT_FILE"