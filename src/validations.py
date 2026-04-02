import json
import logging
import os

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"id", "name", "brewery_type", "country"}
BRONZE_PATH = "/tmp/breweries.json"
MIN_EXPECTED_ROWS = 100


def validate_bronze():
    """
    Validates the bronze JSON file produced by ingestao_bronze:
    - File must exist and be non-empty.
    - Required fields must be present in every row.
    - Row count must be above the minimum threshold.
    """
    assert os.path.exists(BRONZE_PATH), f"Bronze file not found at {BRONZE_PATH}"

    rows = []
    with open(BRONZE_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    assert len(rows) > 0, "Bronze file is empty — API may have returned no data"
    assert len(rows) >= MIN_EXPECTED_ROWS, (
        f"Unusually low record count from API: {len(rows)} rows (expected >= {MIN_EXPECTED_ROWS})"
    )

    for i, row in enumerate(rows):
        missing = REQUIRED_FIELDS - row.keys()
        assert not missing, f"Row {i} is missing required fields: {missing}"

    logger.info("Bronze validation passed: %d rows, all required fields present.", len(rows))
    return len(rows)


def validate_silver():
    """
    Validates the silver Hive table produced by ingestao_silver:
    - Table must have rows.
    - No NULL values in the 'id' column.
    - Row count must be consistent with the bronze file (< 5% loss).
    """
    from pyspark.sql import SparkSession

    warehouse_root = "/opt/airflow/src/warehouse"

    spark = (
        SparkSession.builder.appName("validate_silver")
        .config("spark.hadoop.hive.metastore.uris", "thrift://metastore:9083")
        .config("spark.sql.warehouse.dir", warehouse_root)
        .enableHiveSupport()
        .getOrCreate()
    )

    try:
        df = spark.sql("SELECT * FROM silver.breweries")
        silver_count = df.count()

        assert silver_count > 0, "Silver table is empty after load"

        null_ids = df.filter(df["id"].isNull()).count()
        assert null_ids == 0, f"Silver table has {null_ids} rows with NULL id"

        # Compare with bronze row count to detect silent data loss.
        if os.path.exists(BRONZE_PATH):
            with open(BRONZE_PATH) as f:
                bronze_count = sum(1 for line in f if line.strip())
            loss_pct = (bronze_count - silver_count) / bronze_count * 100
            assert loss_pct < 5, (
                f"Data loss detected between bronze and silver: "
                f"bronze={bronze_count}, silver={silver_count} ({loss_pct:.1f}% loss)"
            )
            logger.info(
                "Silver validation passed: %d rows (%.1f%% of bronze).",
                silver_count, (silver_count / bronze_count * 100),
            )
        else:
            logger.info("Silver validation passed: %d rows.", silver_count)
    finally:
        spark.stop()
