"""
config_io.py — save/load named input sets ("scenarios") to/from JSON.

Streamlit-free on purpose: it operates on plain dicts/lists so the save→load
round-trip can be unit-tested without a UI. The app builds a state dict from
st.session_state, hands it here, and reloads it the same way.

A saved config is the FULL input set so a scenario reproduces exactly:
    {
      "version": 1,
      "name": "weak hotel deal",
      "inputs": { ... every input value ... },
      "custom_costs": [ {registry-shaped dict}, ... ]
    }

This is deliberately the same shape v2's scenario-compare will diff.
"""

import json
import re
from pathlib import Path

CONFIG_VERSION = 1
DEFAULT_DIR = Path(__file__).parent / "configs"


def _slug(name):
    """Filesystem-safe slug for a human scenario name ('Weak Hotel!' -> 'weak-hotel')."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "scenario"


def to_state(inputs, custom_costs, name=""):
    """Bundle inputs + custom costs into a serializable state dict."""
    return {
        "version": CONFIG_VERSION,
        "name": name,
        "inputs": dict(inputs),
        "custom_costs": [dict(c) for c in (custom_costs or [])],
    }


def from_state(state):
    """Unpack a state dict back into (inputs, custom_costs). Tolerant of missing keys."""
    return dict(state.get("inputs", {})), [dict(c) for c in state.get("custom_costs", [])]


def _dir(configs_dir):
    return Path(configs_dir) if configs_dir else DEFAULT_DIR


def config_path(name, configs_dir=None):
    return _dir(configs_dir) / f"{_slug(name)}.json"


def save_config(name, inputs, custom_costs, configs_dir=None):
    """Write a named scenario to configs/<slug>.json. Returns the path written."""
    d = _dir(configs_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_slug(name)}.json"
    state = to_state(inputs, custom_costs, name=name)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


def load_config(name, configs_dir=None):
    """Load a scenario by display name (or slug). Returns (inputs, custom_costs)."""
    path = config_path(name, configs_dir)
    state = json.loads(path.read_text(encoding="utf-8"))
    return from_state(state)


def list_configs(configs_dir=None):
    """Return the display names of saved scenarios, sorted. Empty if none."""
    d = _dir(configs_dir)
    if not d.exists():
        return []
    names = []
    for f in sorted(d.glob("*.json")):
        try:
            state = json.loads(f.read_text(encoding="utf-8"))
            names.append(state.get("name") or f.stem)
        except (json.JSONDecodeError, OSError):
            continue  # skip a corrupt/unreadable file rather than crash the app
    return names
