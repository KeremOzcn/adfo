#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="$ROOT/bin"
OUT_EXE="$BIN_DIR/app"

mkdir -p "$BIN_DIR"

CC_CMD=""
if command -v cc >/dev/null 2>&1; then
  CC_CMD=cc
elif command -v gcc >/dev/null 2>&1; then
  CC_CMD=gcc
else
  echo "No C compiler found (cc or gcc)." >&2
  exit 1
fi

"$CC_CMD" -std=c11 -O2 -I"$ROOT/include" \
  "$ROOT/src/main.c" \
  "$ROOT/src/warehouse.c" \
  "$ROOT/src/routing.c" \
  "$ROOT/src/instances.c" \
  "$ROOT/src/depso.c" \
  "$ROOT/src/baselines.c" \
  "$ROOT/src/rbrs_ae_algorithm.c" \
  -o "$OUT_EXE" -lm

echo "Built: $OUT_EXE"
