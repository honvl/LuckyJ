#!/usr/bin/env bash
# Prepare a player thread's cloud sandbox. The agent runs this at the start of a thread and
# again whenever /workspace/.setup-done is missing (a recycled container starts empty).
# Every step skips work that is already done, so running it twice is harmless.
#
# Mounted by service/thread.py (read-only, under /mnt/session/uploads/):
#   setup.sh                        this script
#   mortal/model.py, mortal/mortal.pth   the Mortal policy the guide scripts load
#   luckyj/luckyj_tenhou.tar.gz     LuckyJ's games as tenhou.net/6 logs
#   player/games.tar.gz             the player's games plus index.json (their seat per game)
#   player/games-<n>.tar.gz         games added later, with the index.json that lists them all
#   cache/libriichi-*.whl           optional: a libriichi wheel built by an earlier thread
set -euo pipefail

U=/mnt/session/uploads
W=/workspace
REPO=$W/LuckyJ
PY=$REPO/.venv/bin/python
MORTAL_COMMIT=0cff2b52982be5b1163aa9a62fb01f03ce91e0d2
OUT=/mnt/session/outputs

if [ -f "$W/.setup-done" ]; then
  echo "setup already done"
  exit 0
fi

echo "== guide repository"
if [ ! -d "$REPO/.git" ]; then
  git clone --depth 1 https://github.com/honvl/LuckyJ.git "$REPO"
fi

echo "== python packages"
if [ ! -x "$PY" ]; then
  python3.12 -m venv "$REPO/.venv"
fi
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.12.1
"$PY" -m pip install -q numpy==2.5.0 mahjong==2.0.0 pillow maturin

echo "== libriichi (Mortal's Rust engine)"
if ! "$PY" -c "import libriichi" 2>/dev/null; then
  WHEEL=$(ls "$U"/cache/libriichi-*.whl 2>/dev/null | head -1 || true)
  if [ -z "$WHEEL" ]; then
    if [ ! -d "$W/Mortal/.git" ]; then
      git clone https://github.com/Equim-chan/Mortal.git "$W/Mortal"
    fi
    git -C "$W/Mortal" checkout -q "$MORTAL_COMMIT"
    # Same one-line patch as the local checkout: name the Python module libriichi.
    sed -i 's/^name = "riichi"$/name = "libriichi"/' "$W/Mortal/libriichi/Cargo.toml"
    "$REPO/.venv/bin/maturin" build --release -q -i "$PY" -m "$W/Mortal/libriichi/Cargo.toml"
    WHEEL=$(ls "$W"/Mortal/target/wheels/libriichi-*.whl | head -1)
    # Leave a copy in the outputs so the service can mount it in later threads.
    mkdir -p "$OUT/cache"
    cp "$WHEEL" "$OUT/cache/"
  fi
  "$PY" -m pip install -q "$WHEEL"
fi

echo "== Mortal policy weights"
mkdir -p "$HOME/Downloads"
ln -sfn "$U/mortal" "$HOME/Downloads/mortal_model_policy"

echo "== LuckyJ games"
mkdir -p "$REPO/data/local_sources"
if [ ! -d "$REPO/data/local_sources/luckyj_tenhou" ]; then
  tar -xzf "$U/luckyj/luckyj_tenhou.tar.gz" -C "$REPO/data/local_sources"
fi

echo "== player games"
mkdir -p "$REPO/data/self_games/majsoul"
tar -xzf "$U/player/games.tar.gz" -C "$REPO/data/self_games/majsoul"
# Later archives (thread.py games tops a player up to their newest 100) hold newer games and a
# fuller index.json, so they go over the first, oldest first.
for extra in $(ls "$U"/player/games-*.tar.gz 2>/dev/null | sort -V); do
  tar -xzf "$extra" -C "$REPO/data/self_games/majsoul"
done

echo "== check"
cd "$REPO"
"$PY" - <<'EOF'
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import build_mortal_analysis as bma
engine = bma.load_mortal_engine(bma.DEFAULT_MODEL)
games = json.loads(Path("data/self_games/majsoul/index.json").read_text())
luckyj = list(Path("data/local_sources/luckyj_tenhou").glob("*.json"))
print(f"Mortal loaded ({type(engine).__name__}); player games: {len(games)}; LuckyJ games: {len(luckyj)}")
EOF

touch "$W/.setup-done"
echo "setup done"
