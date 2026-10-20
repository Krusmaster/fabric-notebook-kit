# fabric-notebook-kit

Three quiet production failures in Fabric notebooks, and the code that prevents them.

## Problem 1 — the parameter that never arrived

Fabric injects pipeline parameters as a *new cell*, placed *after* the cell you tagged
`parameters`. Declare and use a parameter in the same cell and you read the default, every run.
Interactively everything works, so nobody notices — until you find the production pipeline has
been writing to the test environment for three weeks. Green runs, wrong data.

`resolve()` reads the parameters in the *next* cell, fails loudly if a required value is missing
or still equals an obviously-wrong sentinel default, and prints what it resolved as the first log
line — so the failure shows in run history instead of in data.

```python
# Cell 1 — tagged "parameters". Declarations only.
source_table = ""
run_date = "1900-01-01"

# Cell 2
from fabric_notebook_kit import resolve
p = resolve(globals(), required=["source_table", "run_date"], sentinels={"run_date": "1900-01-01"})
```

## Problem 2 — the success that looks like a crash

`notebookutils.notebook.exit()` ends a notebook by raising an exception internally. An
orchestrator that treats "the child raised" as "the child failed" marks every clean run red.
Retry logic does what it is built to do, and a step that already wrote its data runs again.
Three retries, three copies of every row.

`NotebookRun` separates *finished* from *failed*. Exactly one exit call, always with a JSON
payload carrying a `status` field. Real exceptions still propagate (the step fails) but with a
structured error payload.

```python
from fabric_notebook_kit import NotebookRun
with NotebookRun(run_id=f"{p.source_table}-{p.run_date}") as run:
    rows = load_and_write(p.source_table)
    run.finish("ok", rows=rows)
```

Orchestrator side: `parse_exit_value(result)` → read `status`, not whether the call raised.

## Problem 3 — the retry that duplicates

Retries will happen on any platform. An append on retry duplicates data.

`merge_by_key()` merges on business key, stamps a `_run_id` on every written row, never deletes
and never appends. Reruns become boring.

```python
from fabric_notebook_kit import merge_by_key
merge_by_key(spark, df, "silver.orders", keys=["order_id"], run_id=run.payload["run_id"])
```

## Install

```
%pip install git+https://github.com/Krusmaster/fabric-notebook-kit
```

or add it to a Fabric Environment so every notebook has it. See `templates/` for the three cells
(parameters, usage, orchestrator) ready to copy.

## Testing

`resolve` and `NotebookRun` are pure Python and tested offline. `merge_by_key` needs Spark + Delta
and is exercised in a Fabric notebook.

## Works on

| Platform | Status |
| --- | --- |
| Fabric | yes — all three |
| Databricks | `resolve` yes; `NotebookRun(exit_fn=dbutils.notebook.exit)` yes; `merge_by_key` yes (Delta) |
| Snowflake | no Spark/Delta — `resolve` and `NotebookRun` work in any Python; `merge_by_key` does not |
| Local Python | `resolve`, `NotebookRun` yes; `merge_by_key` with local PySpark + Delta |

## License

MIT
