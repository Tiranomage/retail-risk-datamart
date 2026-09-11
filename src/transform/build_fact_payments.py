import pandas as pd
import numpy as np

def load_data():
    """Загрузка графика платежей и фактических оплат."""
    print("Загрузка данных для построения фактов...")
    schedule = pd.read_csv('data/raw/raw_schedule.csv', parse_dates=['due_date'])
    payments = pd.read_csv('data/raw/raw_payments.csv', parse_dates=['payment_date'])
    return schedule, payments

def build_fact_payments(schedule: pd.DataFrame, payments: pd.DataFrame) -> pd.DataFrame:
    """
    Связывает график платежей с фактическими оплатами.
    Так как в сырых данных нет явной связи (ID), мы используем временные окна:
    считаем, что оплата относится к текущему платежу, если она совершена 
    после даты текущего платежа и до даты следующего платежа.
    """
    print("Связывание графика платежей с фактическими оплатами...")
    
    # 1. Сортируем график и добавляем дату следующего платежа для определения "окна"
    schedule = schedule.sort_values(['loan_id', 'due_date'])
    schedule['next_due_date'] = schedule.groupby('loan_id')['due_date'].shift(-1)
    # Для последнего платежа ставим далекую дату, чтобы окно было открытым
    schedule['next_due_date'] = schedule['next_due_date'].fillna(pd.Timestamp('2100-01-01'))
    
    # 2. Слияние: ищем все оплаты, которые относятся к каждому кредиту
    # Используем left join, чтобы сохранить даже те платежи, по которым не было оплат
    merged = pd.merge(schedule, payments, on='loan_id', how='left', suffixes=('_sch', '_pay'))
    
    # 3. Фильтрация: оставляем только те оплаты, которые попали в временное окно текущего платежа
    # Окно: от даты текущего платежа (включительно) до даты следующего платежа (не включительно)
    condition = (merged['payment_date'] >= merged['due_date']) & \
                (merged['payment_date'] < merged['next_due_date'])
    
    matched = merged[condition].copy()
    
    # 4. Агрегация: на случай, если по одному платежу было несколько оплат (частичные оплаты)
    if not matched.empty:
        agg_payments = matched.groupby('schedule_id').agg({
            'payment_id': 'count',
            'amount_paid': 'sum',
            'payment_date': 'max' # Берем дату последней оплаты в окне
        }).reset_index()
        
        agg_payments.rename(columns={
            'payment_id': 'payments_count',
            'amount_paid': 'total_paid',
            'payment_date': 'last_payment_date'
        }, inplace=True)
        
        # Джойним агрегированные оплаты к исходному графику
        fact = pd.merge(schedule, agg_payments, on='schedule_id', how='left')
    else:
        fact = schedule.copy()
        fact['payments_count'] = 0
        fact['total_paid'] = 0.0
        fact['last_payment_date'] = pd.NaT

    # 5. Обработка пропусков (если оплаты не было вовсе)
    fact['payments_count'] = fact['payments_count'].fillna(0).astype(int)
    fact['total_paid'] = fact['total_paid'].fillna(0.0)
    
    # 6. Расчет показателей качества платежа
    # Флаг: оплачен ли платеж полностью
    fact['is_paid'] = fact['total_paid'] >= fact['total_due']
    
    # Флаг: была ли частичная оплата
    fact['is_partial'] = (fact['total_paid'] > 0) & (fact['total_paid'] < fact['total_due'])
    
    # Расчет задержки в днях (только для оплаченных платежей)
    # Для неоплаченных мы посчитаем просрочку на отчетную дату в следующем шаге
    fact['delay_days'] = np.where(
        fact['is_paid'],
        (fact['last_payment_date'] - fact['due_date']).dt.days,
        np.nan 
    )
    
    # Флаги для МСФО 9 (пороги просрочки)
    fact['is_dpd_30'] = fact['delay_days'] > 30
    fact['is_dpd_90'] = fact['delay_days'] > 90
    
    # Выбираем финальные колонки для витрины
    fact = fact[[
        'schedule_id', 'loan_id', 'due_date', 'principal_due', 'interest_due', 
        'total_due', 'remaining_balance', 'total_paid', 'payments_count', 
        'is_paid', 'is_partial', 'delay_days', 'is_dpd_30', 'is_dpd_90'
    ]]
    
    return fact

def main():
    schedule, payments = load_data()
    fact_payments = build_fact_payments(schedule, payments)
    
    print("Сохранение факта платежей...")
    fact_payments.to_csv('data/processed/fact_payments.csv', index=False, encoding='utf-8-sig')
    
    # Вывод статистики для проверки качества данных
    total_scheduled = fact_payments['total_due'].sum()
    total_paid = fact_payments['total_paid'].sum()
    unpaid_count = len(fact_payments[~fact_payments['is_paid']])
    
    print(f"\n--- Отчет по качеству портфеля ---")
    print(f"Всего плановых платежей: {len(fact_payments)}")
    print(f"Оплачено полностью: {fact_payments['is_paid'].sum()}")
    print(f"Не оплачено или оплачено частично: {unpaid_count}")
    print(f"Платежей с просрочкой > 30 дней: {fact_payments['is_dpd_30'].sum()}")
    print(f"Платежей с просрочкой > 90 дней (Стадия 3): {fact_payments['is_dpd_90'].sum()}")

if __name__ == "__main__":
    main()