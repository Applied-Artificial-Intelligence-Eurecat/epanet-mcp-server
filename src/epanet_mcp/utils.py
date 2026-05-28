"""Shared utility helpers for serialising ePyT data into plain dicts."""

from __future__ import annotations

import os
from typing import Any

import numpy as np


def to_python(obj: Any) -> Any:
    """Recursively convert numpy scalars / arrays to plain Python types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_python(v) for v in obj]
    return obj


def safe_list(val: Any) -> list:
    """Ensure val is a plain Python list."""
    if val is None:
        return []
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, (list, tuple)):
        return [to_python(v) for v in val]
    return [to_python(val)]


def resolve_network_path(path: str) -> str:
    """
    Resolve a network file path.  Supports:
      * absolute paths
      * paths relative to cwd
      * bare network names resolved against ePyT's bundled networks directory
    """
    if os.path.isabs(path):
        return path
    if os.path.exists(path):
        return os.path.abspath(path)
    # try ePyT bundled networks
    import epyt
    networks_dir = os.path.join(os.path.dirname(epyt.__file__), "networks")
    # search recursively
    for root, _dirs, files in os.walk(networks_dir):
        for f in files:
            if f.lower() == path.lower() or f.lower() == path.lower() + ".inp":
                return os.path.join(root, f)
    # fall back – let ePyT raise its own error
    return path
