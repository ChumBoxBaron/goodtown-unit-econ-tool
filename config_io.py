"""
config_io.py — save/load named input sets ("scenarios") to/from JSON.

Streamlit-free on purpose: it operates on plain dicts/lists so the save→load
round-trip can be unit-tested without a UI. The app builds a state dict from
st.session_state, hands it here, and reloads it the same way.

A saved config is the FULL input set so a scenario reproduces exactly:
    {
      "version": 2,
      "name": "weak hotel deal",
      "inputs": { ... every input value ... },
      "custom_costs": [ {registry-shaped dict}, ... ]
    }

Older (v1) saves used a single blended rate / utilization / room count; from_state
migrates them onto the two-pod schema on load (see _migrate_inputs).
"""

import json
import re
from pathlib import Path

CONFIG_VERSION = 2
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


def _migrate_inputs(inputs):
    """Bring a saved input set up to the current schema (v1 → v2, in place-ish).

    v1 modeled the hub as N identical rooms: one blended_hourly_rate, one
    utilization_pct, one prime_hours_per_month, and a rooms_per_hub count. v2
    models two distinct pods. We map the single v1 values onto BOTH pods so an old
    scenario reproduces its prior numbers, then drop the dead keys.

    Idempotent: a v2 payload (already has pod keys) passes straight through.
    """
    if "pod2_hourly_rate" in inputs:        # already v2 — nothing to do
        return inputs
    rate = inputs.pop("blended_hourly_rate", 30)
    util = inputs.pop("utilization_pct", 0.20)
    hrs = inputs.pop("prime_hours_per_month", 300)
    # Door count is now fixed at 2 by the PODS topology; an old rooms_per_hub != 2
    # can't be represented, so we drop it (the scenario's lock count snaps to 2).
    inputs.pop("rooms_per_hub", None)
    for p in ("pod2", "pod4"):
        inputs.setdefault(f"{p}_hourly_rate", rate)
        inputs.setdefault(f"{p}_utilization_pct", util)
        inputs.setdefault(f"{p}_bookable_hours_per_month", hrs)
    inputs.setdefault("util_multiplier", 1.0)
    inputs.setdefault("rate_multiplier", 1.0)
    return inputs


def from_state(state):
    """Unpack a state dict back into (inputs, custom_costs). Tolerant of missing keys."""
    inputs = _migrate_inputs(dict(state.get("inputs", {})))
    return inputs, [dict(c) for c in state.get("custom_costs", [])]


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
