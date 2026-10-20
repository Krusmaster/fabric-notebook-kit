"""Parameter handling for Fabric notebooks.

Fabric injects pipeline parameters as a NEW cell placed AFTER the cell tagged `parameters`.
If you declare and use a parameter in the same cell you read the default, never the pipeline
value. This module gives you a second-cell helper that validates what actually arrived.

Usage (cell 2, after the tagged parameters cell):

    from fabric_notebook_kit import resolve
    p = resolve(globals(), required=["source_table", "run_date"], sentinels={"run_date": "1900-01-01"})
    # p.source_table, p.run_date ... and the resolved values are already printed to the log
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping


class ParameterError(ValueError):
    """A required parameter is missing or still holds its sentinel default."""


@dataclass
class Params:
    values: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.values[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __getitem__(self, name: str) -> Any:
        return self.values[name]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


def resolve(
    namespace: Mapping[str, Any],
    required: list[str],
    optional: list[str] | None = None,
    sentinels: Mapping[str, Any] | None = None,
    log: bool = True,
) -> Params:
    """Read parameters from the notebook namespace and fail loudly if any did not arrive.

    namespace: pass `globals()` from the notebook.
    required:  names that must be present and must not equal their sentinel.
    optional:  names that are read if present.
    sentinels: {name: obviously-wrong default} — a required param still equal to its sentinel
               means the pipeline value never landed (classic same-cell bug).
    log:       print `param=value` lines first thing, so the run history shows what ran.
    """
    sentinels = dict(sentinels or {})
    missing, stale = [], []
    out: dict[str, Any] = {}

    for name in required:
        if name not in namespace:
            missing.append(name)
            continue
        val = namespace[name]
        if name in sentinels and val == sentinels[name]:
            stale.append(name)
        if val is None or val == "":
            missing.append(name)
        out[name] = val

    for name in optional or []:
        if name in namespace:
            out[name] = namespace[name]

    if log:
        for k, v in out.items():
            print(f"param {k}={v!r}")

    if missing or stale:
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if stale:
            parts.append(
                f"still at sentinel default: {', '.join(stale)} "
                "(declared and used in the same cell? Fabric injects parameters AFTER the tagged cell)"
            )
        raise ParameterError("; ".join(parts))

    return Params(out)


def parse_date(value: str | date | datetime, fmt: str = "%Y-%m-%d") -> date:
    """Pipeline parameters arrive as strings; normalise to date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), fmt).date()
