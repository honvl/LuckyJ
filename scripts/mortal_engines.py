#!/usr/bin/env python3
"""Build libriichi engines from Mortal checkpoints: the local policy model, or any v4 checkpoint with a value head.

``policy_engine()`` is the local policy model (``~/Downloads/mortal_model_policy``), the one every guide chapter uses.
``q_engine(path)`` loads a checkpoint that holds ``mortal`` and ``current_dqn`` state dicts (a standard Mortal training
checkpoint, or an inference-only file with just those two); its reactions carry Q-values in final-placement points
(6/4/2/0, so 2 a place). Checkpoints are read with ``weights_only=True``, so nothing inside the file can run; the
network classes come from the local policy model's model.py.
"""

from __future__ import annotations

import importlib.util
import os
import sys

POLICY_MODEL = os.path.expanduser("~/Downloads/mortal_model_policy/model.py")
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


def engine(spec: str, name: str | None = None, quick_eval: bool = False):
    """``policy`` for the local policy model, otherwise a checkpoint path."""
    if spec == "policy":
        e = policy_engine()
        e.name = name or "policy"
        e.enable_quick_eval = quick_eval
        return e
    return q_engine(spec, name or "q", quick_eval)
