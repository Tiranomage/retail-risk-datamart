import os
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from faker import Faker


fake = Faker('ru_RU')
np.random.seed(42)

# Конфигурация объемов данных
NUM_CLIENTS = 500
NUM_LOANS = 700

def generate_raw_clients(n: int) -> pd.DataFrame:
    """Генерирует сырую таблицу клиентов."""
    clients = []
    for i in range(1, n + 1):
        clients.append({
            "client_id": f"CLT_{i:05d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "birth_date": fake.date_of_birth(minimum_age=18, maximum_age=75).strftime('%Y-%m-%d'),
            "gender": random.choice(["M", "F"]),
            "phone": fake.phone_number(),
            "registration_date": fake.date_between(start_date='-5y', end_date='-1y').strftime('%Y-%m-%d')
        })
    return pd.DataFrame(clients)

def generate_raw_loans(n: int, clients_df: pd.DataFrame) -> pd.DataFrame:
    """Генерирует выданные кредиты с привязкой к клиентам."""
    products = ["Кредит наличными", "Кредитная карта", "POS-кредит"]
    loans = []
    client_ids = clients_df["client_id"].tolist()
    
    # Явно задаем диапазон дат выдачи (2024-2025 годы)
    start_issue = datetime(2024, 1, 1)
    end_issue = datetime(2025, 12, 31)
    
    for i in range(1, n + 1):
        # Генерируем дату выдачи в фиксированном диапазоне
        issue_date = fake.date_between_dates(date_start=start_issue, date_end=end_issue)
        term_months = random.choice([6, 12, 24, 36])
        # Дата окончания кредита = дата выдачи + срок
        maturity_date = issue_date + timedelta(days=int(term_months * 30.44))
        
        loans.append({
            "loan_id": f"LN_{i:05d}",
            "client_id": random.choice(client_ids),
            "product_name": random.choice(products),
            "principal_amount": round(random.randint(50_000, 2_000_000), 2),
            "interest_rate": round(random.uniform(0.08, 0.25), 4),
            "term_months": term_months,
            "issue_date": issue_date.strftime('%Y-%m-%d'),
            "maturity_date": maturity_date.strftime('%Y-%m-%d')
        })
    return pd.DataFrame(loans)

def generate_raw_schedule(loans_df: pd.DataFrame) -> pd.DataFrame:
    """
    Рассчитывает график платежей. 
    Используем схему: Тело долга делится равными долями + проценты на остаток.
    """
    schedule = []
    sch_id = 1
    
    for _, loan in loans_df.iterrows():
        loan_id = loan["loan_id"]
        principal = loan["principal_amount"]
        rate_monthly = loan["interest_rate"] / 12
        term = loan["term_months"]
        
        # Ежемесячная сумма основного долга
        principal_monthly = principal / term
        remaining_principal = principal
        
        issue_date = datetime.strptime(loan["issue_date"], '%Y-%m-%d')
        
        for m in range(1, term + 1):
            # Дата платежа (примерно через m месяцев)
            due_date = issue_date + timedelta(days=m * 30.44)
            
            # Проценты на текущий остаток долга
            interest_due = remaining_principal * rate_monthly
            total_due = principal_monthly + interest_due
            
            schedule.append({
                "schedule_id": f"SCH_{sch_id:06d}",
                "loan_id": loan_id,
                "due_date": due_date.strftime('%Y-%m-%d'),
                "principal_due": round(principal_monthly, 2),
                "interest_due": round(interest_due, 2),
                "total_due": round(total_due, 2),
                "remaining_balance": round(remaining_principal, 2)
            })
            
            remaining_principal -= principal_monthly
            sch_id += 1
            
    return pd.DataFrame(schedule)

def generate_raw_payments(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """
    Генерирует фактические оплаты с симуляцией просрочек для МСФО 9.
    - 75% платят вовремя (0 дней просрочки)
    - 15% платят с просрочкой 1-30 дней
    - 8% платят с просрочкой 31-90 дней
    - 2% не платят вовсе (дефолт, DPD > 90)
    """
    payments = []
    pay_id = 1
    
    for _, row in schedule_df.iterrows():
        rand = random.random()
        due_date = datetime.strptime(row["due_date"], '%Y-%m-%d')
        
        # Если это не платеж (случай 2% дефолта) - просто пропускаем запись в факты
        if rand > 0.98:
            continue
            
        if rand < 0.75:
            # Оплатил вовремя
            delay = random.randint(-3, 0) # Иногда платят заранее
            amount = row["total_due"]
        elif rand < 0.90:
            # Просрочка 1-30 дней
            delay = random.randint(1, 30)
            amount = row["total_due"]
        else:
            # Просрочка 31-90 дней (Стадия 3 по МСФО9!)
            delay = random.randint(31, 90)
            amount = row["total_due"]
            
        # Имитация частичной оплаты (иногда клиент платит не всю сумму)
        if random.random() < 0.05:
            amount = amount * random.uniform(0.3, 0.9)

        payments.append({
            "payment_id": f"PAY_{pay_id:07d}",
            "loan_id": row["loan_id"],
            "payment_date": (due_date + timedelta(days=delay)).strftime('%Y-%m-%d'),
            "amount_paid": round(amount, 2),
            "system_timestamp": fake.date_time_this_year().strftime('%Y-%m-%d %H:%M:%S')
        })
        pay_id += 1
        
    return pd.DataFrame(payments)

def main():
    print("Начинаем генерацию сырых данных...")
    
    # 1. Генерация сущностей
    df_clients = generate_raw_clients(NUM_CLIENTS)
    df_loans = generate_raw_loans(NUM_LOANS, df_clients)
    
    # 2. Генерация транзакционных данных
    df_schedule = generate_raw_schedule(df_loans)
    df_payments = generate_raw_payments(df_schedule)
    
    # 3. Сохранение в CSV
    output_dir = "data/raw"
    os.makedirs(output_dir, exist_ok=True)
    
    df_clients.to_csv(f"{output_dir}/raw_clients.csv", index=False, encoding='utf-8-sig')
    df_loans.to_csv(f"{output_dir}/raw_loans.csv", index=False, encoding='utf-8-sig')
    df_schedule.to_csv(f"{output_dir}/raw_schedule.csv", index=False, encoding='utf-8-sig')
    df_payments.to_csv(f"{output_dir}/raw_payments.csv", index=False, encoding='utf-8-sig')
    
    print(f"Готово! Сгенерировано:")
    print(f"- Клиентов: {len(df_clients)}")
    print(f"- Кредитов: {len(df_loans)}")
    print(f"- Записей в графике: {len(df_schedule)}")
    print(f"- Фактических оплат: {len(df_payments)}")

if __name__ == "__main__":
    main()