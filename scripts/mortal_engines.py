#!/usr/bin/env python3
"""Build libriichi engines from Mortal checkpoints.

``default_engine()`` is the project's model: Mortal-S42 (haor/Mortal-S42 on Hugging Face, Apache-2.0 weights, a v4
network with a value head). Its Q-values are turned into the probabilities every script reads from a reaction
(``meta.q_values``) with a softmax at ``TEMPERATURE``; the action it plays is the highest Q either way.

``policy_engine()`` is the earlier local policy model (``~/Downloads/mortal_model_policy``), which guide chapters up
to 52 and the first ladder comparison used. ``q_engine(path)`` loads any checkpoint that holds ``mortal`` and
``current_dqn`` state dicts and leaves the Q-values raw (final-placement points, 6/4/2/0, so 2 a place).
Checkpoints are read with ``weights_only=True``, so nothing inside the file can run; the network classes come from
the local policy model's model.py.
"""

from __future__ import annotations

import importlib.util
import os
import sys

# the folder holding the local policy model's model.py and mortal.pth; MORTAL_POLICY_DIR moves it (CI runners)
POLICY_MODEL = os.path.join(os.path.expanduser(os.environ.get("MORTAL_POLICY_DIR", "~/Downloads/mortal_model_policy")),
                            "model.py")
# the project's model; MORTAL_S42_WEIGHTS moves the file (CI runners, the tutor's sandbox)
S42_WEIGHTS = os.path.expanduser(os.environ.get("MORTAL_S42_WEIGHTS", "~/Downloads/mortal_q/s42-inference.pth"))
# Softmax temperature in Q points (2 a place). At 0.6 S42's percentages are as spread out as the earlier policy
# model's on 168 of the user's Jade games (103,678 decisions): mean top probability 0.854 against 0.862, mean entropy
# 0.363 against 0.369, and the total variation between the two models' distributions is at its lowest (0.132).
# See analysis/mortal-s42-switch-2026-11-20.md.
TEMPERATURE = 0.6
_MOD = None


def model_module():
    """The local model.py as a module (Brain, DQN, MortalEngine), with libriichi's submodules importable by name."""
    global _MOD
    if _MOD is None:
        import libriichi
        import torch
        torch.set_num_threads(1)
        # PyTorch hands convolutions on batches of 16 or more to NNPACK, which is about 37 times slower per sample
        # for this network (measured on Apple silicon, torch 2.12). The arena plays many games at once, so it
        # reaches those batches; replays through Bot are batches of one and never did.
        torch.backends.nnpack.set_flags(False)
        for name in ["mjai", "consts", "dataset", "state", "arena", "stat"]:
            if hasattr(libriichi, name):
                sys.modules[f"libriichi.{name}"] = getattr(libriichi, name)
        spec = importlib.util.spec_from_file_location("mortal_policy_model", POLICY_MODEL)
        _MOD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MOD)
    return _MOD


def policy_engine():
    return model_module().get_engine()


def q_engine(path: str, name: str = "q", quick_eval: bool = False):
    import torch
    mod = model_module()
    state = torch.load(os.path.expanduser(path), map_location="cpu", weights_only=True)
    cfg = state.get("config") or {}
    version = (cfg.get("control") or {}).get("version", 4)
    resnet = cfg.get("resnet") or {"conv_channels": 192, "num_blocks": 40}
    brain = mod.Brain(version=version, num_blocks=resnet["num_blocks"], conv_channels=resnet["conv_channels"]).eval()
    dqn = mod.DQN(version=version).eval()
    brain.load_state_dict(state["mortal"])
    dqn.load_state_dict(state["current_dqn"])
    return mod.MortalEngine(brain, dqn, is_oracle=False, version=version, device=torch.device("cpu"),
                            enable_amp=False, enable_quick_eval=quick_eval, enable_rule_based_agari_guard=True,
                            name=name)


def with_probabilities(e, temperature: float = TEMPERATURE):
    """Make a value-head engine report softmax(Q / temperature) over the legal actions in place of raw Q-values."""
    import torch
    raw = e._react_batch

    def _react_batch(obs, masks, invisible_obs):
        actions, q, masks_out, greedy = raw(obs, masks, invisible_obs)
        probs = torch.softmax(torch.tensor(q, dtype=torch.float64) / temperature, dim=-1)  # illegal actions are -inf
        return actions, probs.tolist(), masks_out, greedy

    e._react_batch = _react_batch
    return e


# The AI Tutor's sandbox: the player's games and their amae-koromo records and stats live here.
TUTOR_GAMES = os.environ.get("MORTAL_TUTOR_GAMES", "/workspace/LuckyJ/data/self_games/majsoul")
CELESTIAL = 10701  # Mahjong Soul rank ids: 10701 and up are Celestial levels


def tutor_rank() -> int | None:
    """In a tutor sandbox, the player's latest Mahjong Soul rank id: their seat in the newest game of
    amae-koromo-records.json, else the rank in amae-koromo-stats.json. None outside a sandbox or with no records."""
    import json
    if not (os.path.isdir("/mnt/session") or os.environ.get("MORTAL_TUTOR_GAMES")):
        return None
    folder = TUTOR_GAMES
    try:
        names = {g.get("hero_name") for g in json.load(open(os.path.join(folder, "index.json"), encoding="utf-8"))}
    except (OSError, ValueError):
        names = set()
    best = None
    try:
        for game in json.load(open(os.path.join(folder, "amae-koromo-records.json"), encoding="utf-8")):
            start, players = game[1], game[4]
            for p in players:
                if p[1] in names and (best is None or start > best[0]):
                    best = (start, int(p[2]))
    except (OSError, ValueError, IndexError, TypeError):
        pass
    if best:
        return best[1]
    try:
        stats = json.load(open(os.path.join(folder, "amae-koromo-stats.json"), encoding="utf-8"))
        return int(((stats.get("player_stats") or {}).get("level") or {}).get("id") or 0) or None
    except (OSError, ValueError, TypeError):
        return None


def reviewer() -> str:
    """Which Mortal reviews: ``policy`` or ``s42``. MORTAL_REVIEWER sets it. In a tutor sandbox it follows the player's
    rank: below Celestial the earlier policy model, whose reward (3 / 1.5 / 0 / -4.5 by place) prices a fourth about
    as Saint 3 and the Houou dans do; Celestials get Mortal-S42, whose reward (6 / 4 / 2 / 0) counts only the average
    place, as Celestial points do (guide chapter 56). Elsewhere, S42."""
    chosen = os.environ.get("MORTAL_REVIEWER", "").strip().lower()
    if chosen in ("policy", "s42"):
        return chosen
    rank = tutor_rank()
    if rank is not None and rank < CELESTIAL:
        return "policy"
    return "s42"


def default_engine(quick_eval: bool = False):
    """The reviewer (``reviewer()``) with probabilities. Where S42's weights are not on disk (a tutor thread started
    before the switch), the earlier policy model answers and a line on stderr says so."""
    pick = reviewer()
    if pick == "s42" and not os.path.exists(S42_WEIGHTS):
        print(f"mortal_engines: {S42_WEIGHTS} not found, using the earlier policy model", file=sys.stderr)
        pick = "policy"
    if pick == "policy":
        if not os.environ.get("MORTAL_REVIEWER"):
            rank = tutor_rank()
            if rank is not None and rank < CELESTIAL:
                print(f"mortal_engines: rank {rank} is below Celestial, reviewing with the earlier policy model", file=sys.stderr)
        e = policy_engine()
        e.enable_quick_eval = quick_eval
        return e
    return with_probabilities(q_engine(S42_WEIGHTS, "s42", quick_eval))


POLICY_LABEL = "Mortal policy model (local weights)"


def default_label() -> str:
    """What ``default_engine()`` is, for files that record which model made their numbers."""
    if reviewer() == "policy" or not os.path.exists(S42_WEIGHTS):
        return POLICY_LABEL
    return f"Mortal-S42 (softmax of Q at {TEMPERATURE})"


def engine(spec: str, name: str | None = None, quick_eval: bool = False):
    """``policy`` for the local policy model, otherwise a checkpoint path."""
    if spec == "policy":
        e = policy_engine()
        e.name = name or "policy"
        e.enable_quick_eval = quick_eval
        return e
    return q_engine(spec, name or "q", quick_eval)
