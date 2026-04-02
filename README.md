# Breweries data pipeline
To optimize the time in project development, I used an existing Docker project with the necessary services to create a data pipeline using Spark, Airflow, and Hive. Here is the project link: https://github.com/aaliashraf/airflow-spark-hive-azure-docker-workflow?tab=readme-ov-file

### The WorkSpace contains the following Dependencies


| Tool | Version | Description |
| -----| ------- | -------- |
| Docker | `24.0.7` | See Mac installation [instructions](https://docs.docker.com/desktop/install/windows-install/).
| Java 17 SDK | `openjdk-17-jre-headless` | In DockerFile "RUN apt-get install -y openjdk-17-jre-headless".
| Airflow | `apache/airflow:2.8.4-python3.10` | Base Image. See release history [here](https://hub.docker.com/layers/apache/hive/4.0.0-alpha-2/images/sha256-69e482fdcebb9e07610943b610baea996c941bb36814cf233769b8a4db41f9c1?context=explore)
| Spark | `version 3.5.1` | `spark:3.5.1` See release history [here](https://hub.docker.com/_/spark).
| Hive | `apache/hive:4.0.0-alpha-2` | See release history [here](https://hub.docker.com/layers/apache/hive/4.0.0-alpha-2/images/sha256-69e482fdcebb9e07610943b610baea996c941bb36814cf233769b8a4db41f9c1?context=explore).
| Python | `3.10` | Installed using `apache/airflow:2.8.4-python3.10` Image .
| PySpark | `version 3.5.1` | This should match the Spark version.

## Getting Started

- ### Clone Repo
  
Clone the repository to your local machine
``` shell
git clone https://github.com/vitoramarante94/breweries_git.git
```

Navigate to the Repo directory
``` shell
cd breweries_git
```

- ### Build Docker Image

``` shell
docker-compose build
```
Run the following command to generate the .env file containing the required Airflow UID 

``` shell
echo AIRFLOW_UID=50000 > .env
```

- ### Bringing Up Container Services

``` shell
docker-compose up
```

- ### Check if the Docker services are online
![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/docker_services.png)

## Accessing Services

After starting the containers, you can access the services through the following URLs:

### Airflow
**Username:** airflow  
**Password:** airflow
- Go To [http://localhost:8080](http://localhost:8080)
![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/airflow_services.png)


### Spark

- Go To [http://localhost:8181](http://localhost:8181)
![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/spark_services.png)




### Hive

- Go To [http://localhost:10002](http://localhost:10002)
![image](https://github.com/aaliashraf/airflow-spark-hive-azure-docker-workflow/assets/56219554/09401f86-10bd-4b12-b438-dfd43d3c9701)


## Contents

- **/dags**: Contains Airflow DAGs and workflows for ETL tasks.
- **/logs**: Airflow logs.
- **/plugins**: Airflow plugins.
- **/src**: Utility scripts, PySpark code, and JARs.
  - `bronze.py` — Paginated API ingestion, saves raw JSON to `/tmp/breweries.json`.
  - `silver.py` — PySpark job that reads the bronze JSON, casts coordinates to DECIMAL, and writes a Hive parquet table.
  - `gold.py` — PySpark job that creates a Hive view aggregating brewery counts by type and country.
  - `validations.py` — Data quality checks for bronze (file existence, row count, required fields) and silver (non-empty table, no NULL ids, < 5% row loss vs. bronze).
- **/metastore**: Contains Hive database and tables locally.
- **Dockerfile**: Dockerfiles for building custom Docker images.
- **docker-compose.yaml**: Docker Compose file for orchestrating containers.


## Pipeline Airflow

- I created a pipeline in Airflow to perform ETL by reading from the API [https://api.openbrewerydb.org/breweries](https://api.openbrewerydb.org/breweries), loading it into a temporary bronze layer, normalizing the data for the silver layer, and finally implementing business rules in the gold layer.

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/airflow_orquestrador_dag.png)

- Here is the Airflow DAG script to call the ingestion functions for bronze, silver, and gold layers, defining the load schedule, retries, and task execution order.

```python
import os
import sys
from airflow import DAG
from airflow.utils.email import send_email
from datetime import datetime, timedelta
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bronze import ingestao_bronze
from src.silver import ingestao_silver
from src.gold import ingestao_gold
from src.validations import validate_bronze, validate_silver


def notify_failure(context):
  task_id = context["task_instance"].task_id
  dag_id  = context["task_instance"].dag_id
  log_url = context["task_instance"].log_url
  send_email(
    to="vitoramarante.94@gmail.com",
    subject=f"[AIRFLOW FAILURE] {dag_id} > {task_id}",
    html_content=(
      f"Task <b>{task_id}</b> in DAG <b>{dag_id}</b> failed after all retries.<br>"
      f"Logs: <a href='{log_url}'>{log_url}</a>"
    ),
  )

default_args = {
  "on_failure_callback": notify_failure,
  "retries": 1,
  "retry_delay": timedelta(seconds=15),
}

with DAG(
  'orquestrador',
  start_date=datetime(2026, 4, 1),
  schedule_interval='@once',
  catchup=False,
  default_args=default_args,
) as dag:

  ingest_bronze = PythonOperator(
    task_id='ingestao_bronze',
    python_callable=ingestao_bronze,
  )

  check_bronze = PythonOperator(
    task_id='validacao_bronze',
    python_callable=validate_bronze,
  )

  ingest_silver = PythonOperator(
    task_id='ingestao_silver',
    python_callable=ingestao_silver,
  )

  check_silver = PythonOperator(
    task_id='validacao_silver',
    python_callable=validate_silver,
  )

  ingest_gold = PythonOperator(
    task_id='ingestao_gold',
    python_callable=ingestao_gold,
  )

  ingest_bronze >> check_bronze >> ingest_silver >> check_silver >> ingest_gold
```

## Bronze layer

- In the bronze layer, we make paginated requests to the API [https://api.openbrewerydb.org/v1/breweries](https://api.openbrewerydb.org/v1/breweries), fetching 100 records per page and iterating until the API returns an empty page, so the full dataset is always captured regardless of size. The collected records are assembled with pandas and saved as a newline-delimited JSON file at `/tmp/breweries.json`. Ideally, the ingestion would be done in a Data Lake in a Bronze container, but in this project, I had some difficulties ingesting into HDFS.

```python
import pandas as pd
import requests
from itertools import count

def ingestao_bronze():
  # Buscar dados da API com paginacao
  per_page = 100
  data = []

  for page in count(1):
    params = {"page": page, "per_page": per_page}
    response = requests.get("https://api.openbrewerydb.org/v1/breweries", params=params)
    response.raise_for_status()
    page_data = response.json()

    if not page_data:
      break

    data.extend(page_data)

  # Converter a lista de dados em um DataFrame do Pandas
  df = pd.DataFrame(data)

  # Salvar o DataFrame no formato JSON
  df.to_json("/tmp/breweries.json", orient="records", lines=True)
```

### Validation Bronze

The `validacao_bronze` task confirms the JSON file was written correctly: it checks that the file exists, that the row count is ≥ 100, and that every row contains the required fields (`id`, `name`, `brewery_type`, `country`). The validated row count is returned so Airflow records it in the task log.

```python
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
```

## Silver layer

- To perform the ingestion in the silver layer, I use Spark for processing and the Hive Metastore to persist the data in parquet format. In this script, I start a Spark session, define the structure of the source JSON file that is in the Bronze layer, read this file by passing the schema and transforming it into a dataframe, and finally make a change to the longitude and latitude columns to the DECIMAL format. Before writing this file to Hive, I define the table name and database, and create the database if it does not exist. After that, I save the file in parquet format.

```python
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
```

### Validation Silver

The `validacao_silver` task queries the Hive table directly with Spark. It asserts the table is non-empty, that no `id` values are NULL, and that row loss versus the bronze file is below 5%. These checks catch silent failures such as a failed schema cast or a partial write.

```python
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
```

## Gold layer

- In the gold layer, I use Spark and Hive again, creating a dedicated database for the gold layer. The idea is that this database contains only ready-to-consume data, with aggregations, joins, and transformations. This database will store views and materializations. In the script, we read the table generated in the Silver database and create a view in the gold database, aggregating the breweries by type and country. After that, we perform a select on this view to display the result in the log.

```python
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
```

## Results


### Silver Dataframe

```text
+--------------------+--------------------+------------+--------------------+------------+---------+--------------+--------------+-----------+-------------+--------------------+-------------------+---------------+--------------------+-------------+--------------------+
|                  id|                name|brewery_type|           address_1|   address_2|address_3|          city|state_province|postal_code|      country|           longitude|           latitude|          phone|         website_url|        state|              street|
+--------------------+--------------------+------------+--------------------+------------+---------+--------------+--------------+-----------+-------------+--------------------+-------------------+---------------+--------------------+-------------+--------------------+
|5128df48-79fc-4f0...|    (405) Brewing Co|       micro|      1716 Topeka St|        NULL|     NULL|        Norman|      Oklahoma| 73069-8224|United States| -97.468182220000000| 35.257388910000000|     4058160490|http://www.405bre...|     Oklahoma|      1716 Topeka St|
|9c5a66c8-cc13-416...|    (512) Brewing Co|       micro|407 Radam Ln Ste ...|        NULL|     NULL|        Austin|         Texas| 78745-1197|United States|                NULL|               NULL|     5129211545|http://www.512bre...|        Texas|407 Radam Ln Ste ...|
|34e8c68b-6146-453...|1 of Us Brewing C...|       micro| 8100 Washington Ave|        NULL|     NULL|Mount Pleasant|     Wisconsin| 53406-3920|United States| -87.883363502100000| 42.720108269000000|     2624847553|https://www.1ofus...|    Wisconsin| 8100 Washington Ave|
|6d14b220-8926-452...|10 Barrel Brewing Co|       large|       62970 18th St|        NULL|     NULL|          Bend|        Oregon| 97701-9847|United States|-121.281706000000000| 44.086835310000000|     5415851007|http://www.10barr...|       Oregon|       62970 18th St|
|e2e78bd8-80ff-4a6...|10 Barrel Brewing Co|       large|1135 NW Galveston...|        NULL|     NULL|          Bend|        Oregon| 97703-2465|United States|-121.328802100000000| 44.057564900000000|     5415851007|                NULL|       Oregon|1135 NW Galveston...|
|e432899b-7f58-455...|10 Barrel Brewing Co|       large| 1411 NW Flanders St|        NULL|     NULL|      Portland|        Oregon| 97209-2620|United States|-122.685505600000000| 45.525978600000000|     5032241700|http://www.10barr...|       Oregon| 1411 NW Flanders St|
|ef970757-fe42-416...|10 Barrel Brewing Co|       large|           1501 E St|        NULL|     NULL|     San Diego|    California| 92101-6618|United States|-117.129593000000000| 32.714813000000000|     6195782311| http://10barrel.com|   California|           1501 E St|
|9f1852da-c312-42d...|10 Barrel Brewing...|       large|    62950 NE 18th St|        NULL|     NULL|          Bend|        Oregon|      97701|United States|-121.280953600000000| 44.091210900000000|     5415851007|                NULL|       Oregon|    62950 NE 18th St|
|ea4f30c0-bce6-416...|10 Barrel Brewing...|       large|    826 W Bannock St|        NULL|     NULL|         Boise|         Idaho| 83702-5857|United States|-116.202929000000000| 43.618516000000000|     2083445870|http://www.10barr...|        Idaho|    826 W Bannock St|
|1988eb86-f0a2-467...|10 Barrel Brewing...|       large|      2620 Walnut St|        NULL|     NULL|        Denver|      Colorado| 80205-2231|United States|-104.985365500000000| 39.759250800000000|     7205738992|                NULL|     Colorado|      2620 Walnut St|
|1ecc330f-6275-42a...|10 Torr Distillin...|       micro|         490 Mill St|        NULL|     NULL|          Reno|        Nevada|      89502|United States|-119.773201500000000| 39.517170200000000|     7755307014|http://www.10torr...|       Nevada|         490 Mill St|
|7531dbd8-afc9-4b5...|10-56 Brewing Com...|       micro|       400 Brown Cir|        NULL|     NULL|          Knox|       Indiana|      46534|United States| -86.627954000000000| 41.289715000000000|     6308165790|                NULL|      Indiana|       400 Brown Cir|
|49eaa1ab-5cee-40c...|1000 Hills Brewin...|     brewpub|   168 Old Main Road|Botha's Hill|     NULL|        Durban| KwaZulu-Natal|       3610| South Africa|  30.706300000000000|-29.771100000000000|+27 31 777 1566|https://1000hills...|KwaZulu-Natal|   168 Old Main Road|
|5ae467af-66dc-4d7...|101 North Brewing...|      closed| 1304 Scott St Ste D|        NULL|     NULL|      Petaluma|    California| 94954-7100|United States|-122.665055000000000| 38.270293810000000|     7077534934|http://www.101nor...|   California| 1304 Scott St Ste D|
|4ffda196-dd59-44a...| 105 West Brewing Co|       micro|        1043 Park St|        NULL|     NULL|   Castle Rock|      Colorado| 80109-1585|United States|-104.866720600000000| 39.382694950000000|     3033257321|http://www.105wes...|     Colorado|        1043 Park St|
|42aa37d5-8384-4ff...|         10K Brewing|       micro|        2005 2nd Ave|        NULL|     NULL|         Anoka|     Minnesota| 55303-2243|United States| -93.389525590000000| 45.198120390000000|     7633924753|  http://10KBrew.com|    Minnesota|        2005 2nd Ave|
|232e8f62-9afc-45f...|10th District Bre...|       micro|   491 Washington St|        NULL|     NULL|      Abington| Massachusetts| 02351-2419|United States| -70.945941490000000| 42.105917540000000|     7813071554|http://www.10thdi...|Massachusetts|   491 Washington St|
|08f78223-24f8-4b7...|11 Below Brewing ...|       micro|   6820 Bourgeois Rd|        NULL|     NULL|       Houston|         Texas| 77066-3107|United States| -95.518659100000000| 29.951546400000000|     2814442337|http://www.11belo...|        Texas|   6820 Bourgeois Rd|
|58293321-14ae-49d...|     1188 Brewing Co|     brewpub|       141 E Main St|        NULL|     NULL|      John Day|        Oregon| 97845-1210|United States|-118.921875400000000| 44.414656300000000|     5415751188|http://www.1188br...|       Oregon|       141 E Main St|
|e5f3e72a-fee2-481...|12 Acres Brewing ...|       micro|      Unnamed Street|    Clonmore|     NULL|     Killeshin|         Laois|   R93 X3X8|      Ireland|  -6.979343891000000| 52.849307630000000|   353599107299|https://12acresbr...|        Laois|      Unnamed Street|
+--------------------+--------------------+------------+--------------------+------------+---------+--------------+--------------+-----------+-------------+--------------------+-------------------+---------------+--------------------+-------------+--------------------+
```



### Gold Dataframe

```text
+------------+---------+--------+
|brewery_type|  country|quantity|
+------------+---------+--------+
|       large|Australia|      22|
|       micro|Australia|     491|
|    regional|Australia|       1|
|         bar|  Austria|       2|
|     brewpub|  Austria|       1|
|       large|  Austria|      10|
|        nano|  Austria|       2|
|     brewpub|   Canada|      68|
|      cidery|   Canada|       6|
|      closed|   Canada|      12|
|       micro|   Canada|     162|
|    regional|   Canada|       3|
|     brewpub|  England|      10|
|       large|  England|       1|
|       micro|  England|      40|
|     taproom|  England|      11|
|     brewpub|  Finland|      12|
|       micro|  Finland|      54|
|    regional|  Finland|       2|
|       micro|   France|       3|
+------------+---------+--------+
```


- In the pipeline execution logs, we can track the JSON reading and each transformation performed on the table and business view. The logs are also persisted in the repository.

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/log_repository.png)

## Monitoring & Alerting

The pipeline includes built-in monitoring at every stage to detect failures, data quality issues, and silent data loss before they reach downstream consumers.

### Pipeline Failure Alerts

Every task uses an `on_failure_callback` that sends an email alert when a task exhausts all retries, including the task name, DAG name, and a direct link to the Airflow log.

To enable email alerts, configure SMTP in Airflow (Admin → Connections → `smtp_default`) and update the recipient address in `dags/orquestrador.py`.

### Data Quality Validation Tasks

Two dedicated validation tasks run between the ingestion layers:

| Task | Checks |
|---|---|
| `validacao_bronze` | File exists · row count ≥ 100 · required fields present (`id`, `name`, `brewery_type`, `country`) |
| `validacao_silver` | Table non-empty · no NULL `id` values · < 5% row loss vs bronze |

Validation logic lives in `src/validations.py`.

### DAG Execution Order

```
ingestao_bronze → validacao_bronze → ingestao_silver → validacao_silver → ingestao_gold
```

If any validation fails the downstream tasks are blocked and an alert is fired immediately, without waiting for all retries.

### Log Persistence

All task logs are persisted in `./logs/` (mounted into Airflow containers) and accessible per-run in the Airflow UI at `http://localhost:8080`.

## Conclusion and future improvements

This was a very challenging project because Docker and Airflow are new tools for me, but it was very rewarding to achieve this result. Although it is far from ideal, I managed to deliver a good outcome. As a future improvement, I intend to create a Data Lake with containers to store the layers, implement Jupyter to have a clearer view of the project, adjust the orchestrator for reading Notebooks, migrate tables to Delta Tables, and integrate a dedicated data quality framework such as Great Expectations.