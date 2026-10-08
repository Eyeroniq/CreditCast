#!/usr/bin/env sh
# Regenerate the pinned, hash-checked lock files from the loose lists.
#
#   requirements.in        -> requirements.txt        (training + CI)
#   requirements-serve.in  -> requirements-serve.txt  (runtime image)
#
# The serve lock is constrained by the training lock, so the Docker runtime
# unpickles models with exactly the library versions that trained them.
# Targets Python 3.11 (Docker + CI); `--universal` adds markers for others.
#
#   sh scripts/lock-deps.sh              # keep current pins, add/remove only
#   sh scripts/lock-deps.sh --upgrade    # move everything to latest allowed
#
# Needs uv (pip install "uv==0.12.23"); CI checks the locks are up to date.
set -eu
cd "$(dirname "$0")/.."
UV="${UV:-uv}"
EXTRA="${1:-}"

$UV pip compile requirements.in --universal --python-version 3.11 \
    --generate-hashes --quiet $EXTRA -o requirements.txt
$UV pip compile requirements-serve.in --universal --python-version 3.11 \
    --generate-hashes --quiet $EXTRA --constraint requirements.txt \
    -o requirements-serve.txt
echo "lock files updated: requirements.txt, requirements-serve.txt"
