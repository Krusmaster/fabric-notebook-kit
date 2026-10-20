# Cell 2 — the parameters are injected between cell 1 and this cell. Read them here.
from fabric_notebook_kit import resolve, NotebookRun, merge_by_key

p = resolve(globals(), required=["source_table", "run_date"], optional=["target_env"],
            sentinels={"run_date": "1900-01-01"})

with NotebookRun(run_id=f"{p.source_table}-{p.run_date}") as run:
    df = spark.table(p.source_table).where(f"load_date = '{p.run_date}'")
    metrics = merge_by_key(spark, df, f"silver.{p.source_table}", keys=["business_key"], run_id=run.payload["run_id"])
    run.finish("ok", **metrics)
