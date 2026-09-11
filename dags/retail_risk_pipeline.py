"""
DAG для пайплайна розничных кредитных рисков (МСФО 9).

Этот DAG запускает последовательность шагов:
1. Генерация тестовых данных (или загрузка из источника)
2. Построение измерений (dim_clients, dim_loans, dim_dates)
3. Построение факта платежей (связка графика с оплатами)
4. Расчет витрины статусов (МСФО 9 стадии)
5. Проверка качества данных

Расписание: ежемесячно, 1-го числа в 02:00
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Настройки по умолчанию
default_args = {
    'owner': 'risk-analytics-team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Описание DAG
dag = DAG(
    dag_id='retail_risk_ifrs9_pipeline',
    default_args=default_args,
    description='Пайплайн расчета витрины МСФО 9 для розничного портфеля',
    schedule_interval='0 2 1 * *',  # Ежемесячно, 1-го числа в 02:00
    start_date=days_ago(1),
    catchup=False,
    tags=['risk', 'ifrs9', 'retail'],
)

# === Функции для тасков ===

def task_generate_data(**context):
    """Шаг 1: Генерация/загрузка сырых данных."""
    import subprocess
    result = subprocess.run(['python', 'src/generators/data_generator.py'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Ошибка генерации данных: {result.stderr}")
    print("Данные сгенерированы успешно")

def task_build_dimensions(**context):
    """Шаг 2: Построение витрин измерений."""
    import subprocess
    result = subprocess.run(['python', 'src/transform/build_dimensions.py'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Ошибка построения измерений: {result.stderr}")
    print("Измерения построены")

def task_build_fact_payments(**context):
    """Шаг 3: Построение факта платежей."""
    import subprocess
    result = subprocess.run(['python', 'src/transform/build_fact_payments.py'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Ошибка построения факта платежей: {result.stderr}")
    print("Факт платежей построен")

def task_build_fact_status(**context):
    """Шаг 4: Расчет витрины статусов МСФО 9."""
    import subprocess
    result = subprocess.run(['python', 'src/transform/build_fact_status.py'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Ошибка расчета статусов: {result.stderr}")
    print("Витрина статусов рассчитана")

def task_validate_data(**context):
    """Шаг 5: Проверка качества данных."""
    import pandas as pd
    
    # Загружаем результат
    df = pd.read_csv('data/processed/fact_loan_status_monthly.csv')
    
    # Проверяем базовые правила
    assert len(df) > 0, "Витрина пустая!"
    assert df.duplicated(subset=['loan_id', 'report_date']).sum() == 0, "Найдены дубликаты!"
    assert (df['dpd'] >= 0).all(), "Найдены отрицательные DPD!"
    assert df['ifrs9_stage'].isin([1, 2, 3]).all(), "Некорректные стадии!"
    
    print(f"✓ Валидация пройдена. Записей: {len(df)}")

# === Определение тасков ===

t1_generate = PythonOperator(
    task_id='generate_raw_data',
    python_callable=task_generate_data,
    dag=dag,
)

t2_dimensions = PythonOperator(
    task_id='build_dimensions',
    python_callable=task_build_dimensions,
    dag=dag,
)

t3_fact_payments = PythonOperator(
    task_id='build_fact_payments',
    python_callable=task_build_fact_payments,
    dag=dag,
)

t4_fact_status = PythonOperator(
    task_id='build_fact_status',
    python_callable=task_build_fact_status,
    dag=dag,
)

t5_validate = PythonOperator(
    task_id='validate_data',
    python_callable=task_validate_data,
    dag=dag,
)

# === Зависимости тасков ===
t1_generate >> t2_dimensions >> t3_fact_payments >> t4_fact_status >> t5_validate