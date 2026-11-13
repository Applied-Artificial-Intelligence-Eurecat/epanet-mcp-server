"""Validation helpers that fail before an ePyT model is mutated."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Iterable, Sequence

from epanet_mcp.utils import safe_list


def finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number.")
    return result


def positive_number(name: str, value: Any) -> float:
    result = finite_number(name, value)
    if result <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return result


def nonnegative_number(name: str, value: Any) -> float:
    result = finite_number(name, value)
    if result < 0:
        raise ValueError(f"{name} must be greater than or equal to 0.")
    return result


def integer_value(name: str, value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be an integer greater than or equal to {minimum}."
        )
    if value < minimum:
        raise ValueError(
            f"{name} must be an integer greater than or equal to {minimum}."
        )
    return value


def nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def choice(name: str, value: Any, allowed: Iterable[str]) -> str:
    normalized = nonempty_string(name, value).upper()
    choices = tuple(allowed)
    if normalized not in choices:
        raise ValueError(f"{name} must be one of {list(choices)}; got {value!r}.")
    return normalized


def numeric_sequence(
    name: str,
    values: Sequence[Any],
    *,
    nonnegative: bool = False,
    nonempty: bool = True,
) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a sequence of finite numbers.")
    if nonempty and not values:
        raise ValueError(f"{name} must not be empty.")
    validator = nonnegative_number if nonnegative else finite_number
    return [validator(f"{name}[{index}]", value) for index, value in enumerate(values)]


def node_index(d: Any, node_id: str, *, kind: str | None = None) -> int:
    node_id = nonempty_string("node_id", node_id)
    if kind == "junction":
        names = safe_list(d.getNodeJunctionNameID())
    elif kind == "tank":
        names = safe_list(d.getNodeTankNameID())
    elif kind == "reservoir":
        names = safe_list(d.getNodeReservoirNameID())
    else:
        names = safe_list(d.getNodeNameID())
    if node_id not in names:
        label = f" {kind}" if kind else ""
        raise ValueError(f"Unknown{label} node id={node_id!r}. Available ids: {names}")
    if kind in {"junction", "tank", "reservoir"}:
        all_names = safe_list(d.getNodeNameID())
        return all_names.index(node_id) + 1
    return names.index(node_id) + 1


def link_index(d: Any, link_id: str, *, kind: str | None = None) -> int:
    link_id = nonempty_string("link_id", link_id)
    if kind == "pipe":
        names = safe_list(d.getLinkPipeNameID())
    elif kind == "pump":
        names = safe_list(d.getLinkPumpNameID())
    elif kind == "valve":
        names = safe_list(d.getLinkValveNameID())
    else:
        names = safe_list(d.getLinkNameID())
    if link_id not in names:
        label = f" {kind}" if kind else ""
        raise ValueError(f"Unknown{label} link id={link_id!r}. Available ids: {names}")
    if kind in {"pipe", "pump", "valve"}:
        all_names = safe_list(d.getLinkNameID())
        return all_names.index(link_id) + 1
    return names.index(link_id) + 1


def strictly_increasing(name: str, values: Sequence[float]) -> None:
    if any(current <= previous for previous, current in zip(values, values[1:])):
        raise ValueError(f"{name} must be strictly increasing.")
