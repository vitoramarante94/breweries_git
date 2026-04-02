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