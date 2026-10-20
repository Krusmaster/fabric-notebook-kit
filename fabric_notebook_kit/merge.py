"""Idempotent writes for Delta tables in Fabric.

Retries will happen. An append on retry duplicates data; a merge on business key does not.

    from fabric_notebook_kit import merge_by_key
    merge_by_key(spark, df, "silver.orders", keys=["order_id"], run_id=run_id)

Requires PySpark + Delta (present in every Fabric Spark runtime). Imported lazily so the rest
of the package works without Spark.
"""
from __future__ import annotations

from typing import Iterable


def merge_by_key(
    spark,
    df,
    target: str,
    keys: Iterable[str],
    run_id: str | None = None,
    update_columns: Iterable[str] | None = None,
    create_if_missing: bool = True,
) -> dict:
    """MERGE df into `target` on `keys`. Updates matched rows, inserts new ones, never deletes.

    run_id: if given, a `_run_id` column is stamped on every written row (audit + rerun tracing).
    update_columns: restrict which columns an UPDATE touches (default: all non-key columns).
    Returns a dict with the operation metrics from Delta history.
    """
    from delta.tables import DeltaTable  # type: ignore
    from pyspark.sql import functions as F  # type: ignore

    keys = list(keys)
    if run_id is not None:
        df = df.withColumn("_run_id", F.lit(run_id))

    if not spark.catalog.tableExists(target):
        if not create_if_missing:
            raise ValueError(f"target {target} does not exist")
        df.write.format("delta").saveAsTable(target)
        return {"operation": "CREATE", "rows": df.count()}

    cond = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    cols = update_columns or [c for c in df.columns if c not in keys]
    set_map = {c: f"s.`{c}`" for c in cols}

    (DeltaTable.forName(spark, target).alias("t")
        .merge(df.alias("s"), cond)
        .whenMatchedUpdate(set=set_map)
        .whenNotMatchedInsertAll()
        .execute())

    hist = DeltaTable.forName(spark, target).history(1).collect()[0]
    return {"operation": hist["operation"], **{k: v for k, v in (hist["operationMetrics"] or {}).items()}}


def merge_condition(keys: Iterable[str], left: str = "t", right: str = "s") -> str:
    """Pure helper (no Spark) so the join condition is unit-testable."""
    return " AND ".join(f"{left}.`{k}` = {right}.`{k}`" for k in keys)
