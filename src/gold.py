from pyspark.sql import SparkSession

def ingestao_gold():

    # Initialize Spark session
    spark = (
        SparkSession.builder.appName("etl_spark_hive")
        .config("spark.hadoop.hive.metastore.uris", "thrift://metastore:9083")
        .config("spark.sql.warehouse.dir", "/opt/airflow/metastore")
        .enableHiveSupport()
        .getOrCreate()
    )

    source_database = "silver"
    dest_database = "gold"

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {dest_database}")

    query = (f'''
    CREATE OR REPLACE VIEW {dest_database}.vw_qnt_breweries_local_type   
    AS     
    SELECT 
        brewery_type,
        country,
        COUNT(*) AS quantity
    FROM 
    {source_database}.breweries
    GROUP BY brewery_type, country  
    ORDER BY country, brewery_type;
    ''')
    spark.sql(query).show()

    df = spark.sql(f"SELECT * FROM {dest_database}.vw_qnt_breweries_local_type")

    df.show()


    spark.stop()