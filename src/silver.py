import os
from pyspark.sql.types import StructType, StructField, StringType, DecimalType
from pyspark.sql.functions import col
from pyspark.sql import SparkSession

def ingestao_silver():

    # Keep managed table data in a writable mounted directory.
    warehouse_root = "/opt/airflow/src/warehouse"
    os.makedirs(warehouse_root, exist_ok=True)

    # Initialize Spark session
    spark = (
        SparkSession.builder.appName("etl_spark_hive")
        .config("spark.hadoop.hive.metastore.uris", "thrift://metastore:9083")
        .config("spark.sql.warehouse.dir", warehouse_root)
        .enableHiveSupport()
        .getOrCreate()
    )

    schema = StructType([
        StructField("id", StringType()),
        StructField("name", StringType()),
        StructField("brewery_type", StringType()),
        StructField("address_1", StringType()),
        StructField("address_2", StringType()),
        StructField("address_3", StringType()),
        StructField("city", StringType()),
        StructField("state_province", StringType()),
        StructField("postal_code", StringType()),
        StructField("country", StringType()),
        StructField("longitude", StringType()),
        StructField("latitude", StringType()),
        StructField("phone", StringType()),
        StructField("website_url", StringType()),
        StructField("state", StringType()),
        StructField("street", StringType())
    ])

    # Convert the JSON data to a DataFrame
    df = spark.read.schema(schema).json("/tmp/breweries.json")


    decimal_type = DecimalType(18, 15)
    df = (df.withColumn("longitude", col("longitude").cast(decimal_type))
          .withColumn("latitude", col("latitude").cast(decimal_type))
    )

    df.show()

    table = "breweries"
    database = "silver"
    db_path = f"{warehouse_root}/{database}.db"
    table_path = f"{db_path}/{table}"

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {database} LOCATION '{db_path}'")

    # Save as Hive table with explicit location to avoid permission issues in default warehouse path.
    (
        df.write.mode("overwrite")
        .format("parquet")
        .option("path", table_path)
        .saveAsTable(f"{database}.{table}")
    )

    spark.stop()
