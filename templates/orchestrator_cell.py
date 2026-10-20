# Orchestrator: read the child's status field, not whether the call raised.
from fabric_notebook_kit import parse_exit_value

result = notebookutils.notebook.run("nb_load_sales", 1800, {"source_table": "sales", "run_date": run_date})
status = parse_exit_value(result if isinstance(result, str) else getattr(result, "exitValue", None))
if status.get("status") != "ok":
    raise RuntimeError(f"child failed: {status}")
print("child ok:", status)
