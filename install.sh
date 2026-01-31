#!/bin/bash
# Install dedup globally using uv tool

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing dedup..."
uv tool install "$SCRIPT_DIR"

echo "Done. You can now run 'dedup' from anywhere."
