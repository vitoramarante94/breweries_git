from pyspark.sql.types import StructType, StructField, StringType, DecimalType
from pyspark.sql.functions import col
from pyspark.sql import SparkSession

def ingestao_silver():

    # Initialize Spark session
    spark = (
        SparkSession.builder.appName("etl_spark_hive")
        .config("spark.hadoop.hive.metastore.uris", "thrift://metastore:9083")
        .config("spark.sql.warehouse.dir", "/opt/airflow/metastore")
        .enableHiveSupport()
        .getOrCreate()
    )

    schema = StructType([
        StructField("id", StringType()),
        StructField("name", StringType()),
        StructField("brewery_type", StringType()),
        StructField("street", StringType()),
        StructField("city", StringType()),
        StructField("state", StringType()),
        StructField("postal_code", StringType()),
        StructField("country", StringType()),
        StructField("longitude", StringType()),
        StructField("latitude", StringType()),
        StructField("phone", StringType()),
        StructField("website_url", StringType())
    ])

    # Convert the JSON data to a DataFrame
    df = spark.read.schema(schema).json("/tmp/breweries.json")

    df.show()

    decimal_type = DecimalType(18, 15)
    df = (df.withColumn("longitude", col("longitude").cast(decimal_type))
          .withColumn("latitude", col("latitude").cast(decimal_type))
    )

    df.show()

    table = "breweries"
    database = "silver"

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {database}")

    # Save the DataFrame in Parquet format to Hive
    df.write.mode("overwrite").format("parquet").saveAsTable(f"{database}.{table}") 

    spark.stop()
