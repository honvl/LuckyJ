#!/bin/sh
# Set up the local tensoul checkout used by scripts/fetch_majsoul_games.py.
#
#   sh tools/tensoul/install.sh
#
# Clones Equim-chan/tensoul into tmp/tensoul (gitignored), applies the patch
# that makes it speak to the current Unity WebGL ("v4") Mahjong Soul client,
# adds the record-listing and batch-conversion scripts, and installs the npm
# dependencies. Afterwards create tmp/tensoul/.env (see tmp/tensoul/.env.example).
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$ROOT/tmp/tensoul"
if [ ! -d "$DEST/.git" ]; then
  git clone --depth 1 https://github.com/Equim-chan/tensoul.git "$DEST"
fi
cd "$DEST"
# a fresh upstream clone needs the patch; a checkout that already carries it does not
if ! grep -q requestConnection client.js; then
  git apply "$ROOT/tools/tensoul/v4-client.patch"
fi
cp "$ROOT/tools/tensoul/config.js" "$ROOT/tools/tensoul/records.js" "$ROOT/tools/tensoul/fetch_many.js" .
cp "$ROOT/tools/tensoul/env.example" .env.example
npm install --silent
echo "tensoul ready in $DEST; write $DEST/.env next (see .env.example)"
