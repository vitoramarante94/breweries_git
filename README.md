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
![image](https://github.com/aaliashraf/airflow-spark-hive-azure-docker-workflow/assets/56219554/a79ca824-72c7-4dfa-aca6-41186e0e3553)


- Example Airflow DAG Web UI displaying a running workflow.
![image](https://github.com/aaliashraf/airflow-spark-hive-azure-docker-workflow/assets/56219554/3fc69ff7-8c24-452f-b920-79d6c963755f)







### Spark

- Go To [http://localhost:8181](http://localhost:8181)
![image](https://github.com/aaliashraf/airflow-spark-hive-azure-docker-workflow/assets/56219554/b3790ed2-d478-469f-b70c-b8628bd93c01)




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

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/dag_orquestrador_script.png)

## Bronze layer

- In the bronze layer, we make paginated requests to the API [https://api.openbrewerydb.org/v1/breweries](https://api.openbrewerydb.org/v1/breweries), fetching 100 records per page and iterating until the API returns an empty page, so the full dataset is always captured regardless of size. The collected records are assembled with pandas and saved as a newline-delimited JSON file at `/tmp/breweries.json`. Ideally, the ingestion would be done in a Data Lake in a Bronze container, but in this project, I had some difficulties ingesting into HDFS.

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/bronze.png)

## Silver layer

- To perform the ingestion in the silver layer, I use Spark for processing and the Hive Metastore to persist the data in parquet format. In this script, I start a Spark session, define the structure of the source JSON file that is in the Bronze layer, read this file by passing the schema and transforming it into a dataframe, and finally make a change to the longitude and latitude columns to the DECIMAL format. Before writing this file to Hive, I define the table name and database, and create the database if it does not exist. After that, I save the file in parquet format.

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/silver.png)

## Gold layer

- In the gold layer, I use Spark and Hive again, creating a dedicated database for the gold layer. The idea is that this database contains only ready-to-consume data, with aggregations, joins, and transformations. This database will store views and materializations. In the script, we read the table generated in the Silver database and create a view in the gold database, aggregating the breweries by type and country. After that, we perform a select on this view to display the result in the log.

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/gold.png)

## DAG Execution

### LOG Bronze

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/log_bronze.png)

### LOG Validation Bronze

The `validacao_bronze` task confirms the JSON file was written correctly: it checks that the file exists, that the row count is ≥ 100, and that every row contains the required fields (`id`, `name`, `brewery_type`, `country`). The validated row count is returned so Airflow records it in the task log.

### LOG Silver

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/log_silver.png)

### LOG Validation Silver

The `validacao_silver` task queries the Hive table directly with Spark. It asserts the table is non-empty, that no `id` values are NULL, and that row loss versus the bronze file is below 5%. These checks catch silent failures such as a failed schema cast or a partial write.

### LOG Gold

![image](https://github.com/vitoramarante94/breweries_git/blob/main/imagens/log_gold.png)


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