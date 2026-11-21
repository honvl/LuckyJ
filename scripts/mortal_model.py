"""The project's Mortal model as a model.py: ``get_engine()`` for every script that loads one by path.

It is Mortal-S42 with probabilities (see ``mortal_engines.default_engine``). The earlier policy model is still
loadable by passing its own model.py (``~/Downloads/mortal_model_policy/model.py``) where a script takes ``--model``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mortal_engines  # noqa: E402


def get_engine():
    return mortal_engines.default_engine()
