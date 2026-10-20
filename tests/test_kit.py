import json
import pytest
from fabric_notebook_kit import NotebookRun, ParameterError, merge_condition, parse_date, parse_exit_value, resolve


# ---- params -----------------------------------------------------------------
def test_resolve_reads_values():
    ns = {"source_table": "sales", "run_date": "2026-10-20", "other": 1}
    p = resolve(ns, required=["source_table", "run_date"], optional=["other"], log=False)
    assert p.source_table == "sales" and p["run_date"] == "2026-10-20" and p.other == 1


def test_resolve_detects_sentinel_default():
    ns = {"source_table": "sales", "run_date": "1900-01-01"}
    with pytest.raises(ParameterError, match="sentinel"):
        resolve(ns, required=["source_table", "run_date"], sentinels={"run_date": "1900-01-01"}, log=False)


def test_resolve_detects_missing_and_empty():
    with pytest.raises(ParameterError, match="missing: source_table, run_date"):
        resolve({"source_table": ""}, required=["source_table", "run_date"], log=False)


def test_resolve_logs_resolved_values(capsys):
    resolve({"a": 1}, required=["a"])
    assert "param a=1" in capsys.readouterr().out


def test_parse_date():
    assert parse_date("2026-10-20").isoformat() == "2026-10-20"


# ---- exit -------------------------------------------------------------------
def _capture():
    box = {}
    return box, (lambda body: box.update(json.loads(body)))


def test_finish_is_not_an_error():
    box, fn = _capture()
    with NotebookRun(exit_fn=fn, run_id="r1", echo=False) as run:
        run.finish("ok", rows=42)
        raise AssertionError("unreachable")
    assert box["status"] == "ok" and box["rows"] == 42 and box["run_id"] == "r1"


def test_falling_off_the_end_is_ok():
    box, fn = _capture()
    with NotebookRun(exit_fn=fn, echo=False) as run:
        run.set(progress=3)
    assert box["status"] == "ok" and box["progress"] == 3


def test_real_exception_propagates_with_error_payload():
    box, fn = _capture()
    with pytest.raises(ValueError):
        with NotebookRun(exit_fn=fn, echo=False):
            raise ValueError("boom")
    assert box["status"] == "error" and box["error_type"] == "ValueError" and "boom" in box["message"]


def test_parse_exit_value():
    assert parse_exit_value('{"status":"ok"}') == {"status": "ok"}
    assert parse_exit_value(None)["status"] == "unknown"
    assert parse_exit_value("not json")["status"] == "unknown"


# ---- merge (pure part) -----------------------------------------------------
def test_merge_condition():
    assert merge_condition(["a", "b"]) == "t.`a` = s.`a` AND t.`b` = s.`b`"
