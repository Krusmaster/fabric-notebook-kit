"""Clean notebook exit for orchestrated Fabric notebooks.

`notebookutils.notebook.exit()` ends a notebook by raising internally. An orchestrator that
treats "child raised" as "child failed" marks every successful run red, and retry logic then
re-runs steps that already wrote their data.

This module separates *finishing* from *failing*:

    from fabric_notebook_kit import NotebookRun

    with NotebookRun() as run:
        rows = load_and_write(source_table)
        run.finish("ok", rows=rows)
    # on the way out: exactly one notebookutils.notebook.exit(json) with a status field

Real exceptions still propagate (so the step fails) but the exit payload carries status=error
and the message, so the orchestrator can read a structured result either way.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any


class _OrchestratorExit(Exception):
    """Signals an intentional finish. Never an error."""


class NotebookRun:
    def __init__(self, exit_fn=None, run_id: str | None = None, echo: bool = True):
        """exit_fn: defaults to notebookutils.notebook.exit when available (Fabric), else print."""
        self.payload: dict[str, Any] = {"status": "unknown", "run_id": run_id, "started_at": _now()}
        self.echo = echo
        self._exit_fn = exit_fn or _default_exit()

    # ---- inside the block -------------------------------------------------
    def finish(self, status: str = "ok", **fields: Any) -> None:
        """Mark the run finished with a status and any extra fields, then leave the block."""
        self.payload.update({"status": status, **fields})
        raise _OrchestratorExit()

    def set(self, **fields: Any) -> None:
        """Attach fields to the payload without finishing (progress counters, warnings)."""
        self.payload.update(fields)

    # ---- context manager --------------------------------------------------
    def __enter__(self) -> "NotebookRun":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is _OrchestratorExit:
            handled = True                           # intentional: swallow
        elif exc_type is None:
            if self.payload["status"] == "unknown":
                self.payload["status"] = "ok"        # fell off the end without finish(): fine
            handled = True
        else:
            self.payload.update({
                "status": "error",
                "error_type": exc_type.__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc_type, exc, tb))[-4000:],
            })
            handled = False                          # re-raise so the step fails
        self.payload["finished_at"] = _now()
        body = json.dumps(self.payload, default=str)
        if self.echo:
            print(f"exit payload: {body}")
        self._exit_fn(body)
        return handled


def parse_exit_value(exit_value: str | None) -> dict[str, Any]:
    """Orchestrator side: turn a child's exitValue into a dict. Missing/invalid → status=unknown."""
    if not exit_value:
        return {"status": "unknown"}
    try:
        d = json.loads(exit_value)
        return d if isinstance(d, dict) else {"status": "unknown", "raw": exit_value}
    except json.JSONDecodeError:
        return {"status": "unknown", "raw": exit_value}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_exit():
    try:  # pragma: no cover — only exists inside Fabric
        import notebookutils  # type: ignore
        return notebookutils.notebook.exit
    except Exception:
        return lambda body: None
