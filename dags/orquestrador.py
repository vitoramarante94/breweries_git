import os
import sys
from airflow import DAG
from datetime import datetime, timedelta
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bronze import ingestao_bronze
from src.silver import ingestao_silver
from src.gold import ingestao_gold

with DAG('orquestrador', start_date=datetime(2024, 8, 28), schedule_interval='@once', catchup=False) as dag:

    ingest_bronze = PythonOperator(
        task_id='ingestao_bronze',
        python_callable=ingestao_bronze,
        retries=3,
        retry_delay=timedelta(seconds=150)
    )

    ingest_silver = PythonOperator(
        task_id='ingestao_silver',
        python_callable=ingestao_silver,
        retries=3,
        retry_delay=timedelta(seconds=150)
    )

    ingest_gold = PythonOperator(
        task_id='ingestao_gold',
        python_callable=ingestao_gold,
        retries=3,
        retry_delay=timedelta(seconds=150)
    )

    ingest_bronze >> ingest_silver >> ingest_gold