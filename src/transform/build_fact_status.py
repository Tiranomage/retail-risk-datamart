import pandas as pd
import numpy as np
from datetime import datetime

def load_data():
    """Загрузка сырых данных для расчета статусов."""
    print("Загрузка данных для расчета витрины статусов...")
    schedule = pd.read_csv('data/raw/raw_schedule.csv', parse_dates=['due_date'])
    payments = pd.read_csv('data/raw/raw_payments.csv', parse_dates=['payment_date'])
    loans = pd.read_csv('data/processed/dim_loans.csv', parse_dates=['issue_date'])
    return schedule, payments, loans

def create_reporting_grid(loans: pd.DataFrame) -> pd.DataFrame:
    """
    Создает сетку отчетных дат для каждого кредита.
    Для каждого кредита генерируем список концов месяцев 
    от даты выдачи до даты погашения (или текущей даты).
    """
    print("Создание сетки отчетных дат...")
    
    # Проверяем, что данные есть
    if loans.empty:
        print("ВНИМАНИЕ: DataFrame loans пустой!")
        return pd.DataFrame(columns=['loan_id', 'report_date'])
    
    # Определяем глобальный диапазон дат
    min_date = loans['issue_date'].min()
    max_date = pd.Timestamp('2026-09-11')  # Текущая дата
    
    print(f"Диапазон дат: {min_date.date()} — {max_date.date()}")
    
    # Генерируем все концы месяцев в диапазоне
    # Правильная логика: первый день месяца + MonthEnd(0) = конец этого месяца
    start_date = min_date.replace(day=1)
    end_date = max_date + pd.offsets.MonthEnd(1)
    
    all_month_ends = pd.date_range(
        start=start_date,
        end=end_date,
        freq='ME'  # Исправлено: 'ME' вместо 'M'
    )
    
    print(f"Всего концов месяцев в диапазоне: {len(all_month_ends)}")
    
    # Для каждого кредита выбираем только те месяцы, когда кредит активен
    grid = []
    for _, loan in loans.iterrows():
        loan_id = loan['loan_id']
        issue = loan['issue_date']
        # Кредит активен от даты выдачи до даты погашения
        maturity = issue + pd.DateOffset(months=loan['term_months'])
        
        # Фильтруем концы месяцев для этого кредита
        valid_dates = all_month_ends[
            (all_month_ends >= issue) & 
            (all_month_ends <= min(maturity, max_date))
        ]
        
        for date in valid_dates:
            grid.append({
                'loan_id': loan_id,
                'report_date': date
            })
    
    print(f"Создано {len(grid)} отчетных точек (кредит × месяц)")
    
    if len(grid) == 0:
        print("ВНИМАНИЕ: Сетка пустая! Пример первой строки loans:")
        print(loans.head(1))
    
    return pd.DataFrame(grid)

def compute_dpd(loan_schedule: pd.DataFrame, cum_paid: float, report_date: pd.Timestamp) -> int:
    """
    Рассчитывает DPD (Days Past Due) для кредита на отчетную дату.
    
    Логика: идем по графику платежей по порядку и находим первый платеж,
    который не покрыт фактическими оплатами к отчетной дате.
    DPD = количество дней от даты этого платежа до отчетной даты.
    """
    # Берем только те платежи, которые должны были быть оплачены к отчетной дате
    sched_due = loan_schedule[loan_schedule['due_date'] <= report_date].sort_values('due_date')
    
    if sched_due.empty:
        return 0
    
    # Идем по платежам накопительным итогом
    cumulative_scheduled = 0.0
    for _, row in sched_due.iterrows():
        cumulative_scheduled += row['total_due']
        # Если накопленный долг превышает накопленные оплаты — этот платеж не покрыт
        if cumulative_scheduled > cum_paid + 0.01:  # +0.01 для избежания ошибок округления
            dpd = (report_date - row['due_date']).days
            return max(0, dpd)
    
    return 0  # Все платежи покрыты

def build_fact_status(schedule: pd.DataFrame, payments: pd.DataFrame, 
                      loans: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    """
    Основная функция расчета витрины статусов.
    Для каждого кредита и каждой отчетной даты рассчитывает:
    - Остаток долга
    - Просрочку
    - DPD
    - Стадию МСФО 9
    """
    print("Расчет статусов кредитов (это может занять время)...")
    
    results = []
    
    # Группируем данные по кредитам для ускорения
    schedule_grouped = schedule.groupby('loan_id')
    payments_grouped = payments.groupby('loan_id')
    
    for idx, row in grid.iterrows():
        loan_id = row['loan_id']
        report_date = row['report_date']
        
        # Получаем данные по кредиту
        try:
            loan_schedule = schedule_grouped.get_group(loan_id)
        except KeyError:
            continue
            
        try:
            loan_payments = payments_grouped.get_group(loan_id)
        except KeyError:
            loan_payments = pd.DataFrame(columns=['payment_date', 'amount_paid'])
        
        # 1. Сумма, которая должна была быть уплачена к отчетной дате
        sched_due = loan_schedule[loan_schedule['due_date'] <= report_date]
        cum_scheduled = sched_due['total_due'].sum()
        
        # 2. Сумма, которая фактически была уплачена к отчетной дате
        paid_by_date = loan_payments[loan_payments['payment_date'] <= report_date]
        cum_paid = paid_by_date['amount_paid'].sum()
        
        # 3. Просрочка (если должны больше, чем заплатили)
        overdue_amount = max(0, cum_scheduled - cum_paid)
        
        # 4. Остаток основного долга
        # Берем остаток из последней строки графика, где дата платежа <= отчетной
        if not sched_due.empty:
            outstanding_principal = sched_due.iloc[-1]['remaining_balance']
        else:
            # Если платежей еще не было, остаток = начальная сумма
            outstanding_principal = loan_schedule.iloc[0]['remaining_balance'] if not loan_schedule.empty else 0
        
        # 5. Расчет DPD
        dpd = compute_dpd(loan_schedule, cum_paid, report_date)
        
        # 6. Определение стадии МСФО 9
        if dpd == 0:
            stage = 1
        elif dpd <= 30:
            stage = 1  # Стадия 1: нет значительного роста кредитного риска
        elif dpd <= 90:
            stage = 2  # Стадия 2: значительный рост кредитного риска
        else:
            stage = 3  # Стадия 3: кредитно-обесцененный
        
        results.append({
            'loan_id': loan_id,
            'report_date': report_date,
            'year_month': report_date.strftime('%Y-%m'),
            'cum_scheduled': round(cum_scheduled, 2),
            'cum_paid': round(cum_paid, 2),
            'overdue_amount': round(overdue_amount, 2),
            'outstanding_principal': round(outstanding_principal, 2),
            'dpd': dpd,
            'ifrs9_stage': stage
        })
        
        # Прогресс-бар (каждые 1000 записей)
        if (idx + 1) % 1000 == 0:
            print(f"  Обработано {idx + 1} записей из {len(grid)}...")
    
    return pd.DataFrame(results)

def add_loan_attributes(fact: pd.DataFrame, loans: pd.DataFrame) -> pd.DataFrame:
    """Добавляет атрибуты кредита в витрину."""
    if fact.empty:
        print("ВНИМАНИЕ: fact_status пустой, пропускаем merge")
        return fact
    
    fact = fact.merge(
        loans[['loan_id', 'client_id', 'product_name', 'initial_amount']],
        on='loan_id',
        how='left'
    )
    return fact

def main():
    # 1. Загрузка данных
    schedule, payments, loans = load_data()
    
    # 2. Создание сетки отчетных дат
    grid = create_reporting_grid(loans)
    
    # Проверяем, что сетка не пустая
    if grid.empty:
        print("ОШИБКА: Сетка отчетных дат пустая! Прерываем выполнение.")
        return
    
    # 3. Расчет витрины
    fact_status = build_fact_status(schedule, payments, loans, grid)
    
    # Проверяем, что витрина не пустая
    if fact_status.empty:
        print("ОШИБКА: Витрина статусов пустая! Прерываем выполнение.")
        return
    
    # 4. Добавление атрибутов кредита
    fact_status = add_loan_attributes(fact_status, loans)
    
    # 5. Сортировка и сохранение
    fact_status = fact_status.sort_values(['loan_id', 'report_date']).reset_index(drop=True)
    
    # Переупорядочиваем колонки
    fact_status = fact_status[[
        'loan_id', 'client_id', 'product_name', 'report_date', 'year_month',
        'initial_amount', 'outstanding_principal', 'cum_scheduled', 'cum_paid',
        'overdue_amount', 'dpd', 'ifrs9_stage'
    ]]
    
    print("\nСохранение витрины статусов...")
    fact_status.to_csv('data/processed/fact_loan_status_monthly.csv', index=False, encoding='utf-8-sig')
    
    # 6. Вывод статистики
    print(f"\n{'='*50}")
    print(f"ВИТРИНА СТАТУСОВ КРЕДИТОВ ПОСТРОЕНА")
    print(f"{'='*50}")
    print(f"Всего записей (кредит × месяц): {len(fact_status)}")
    print(f"Уникальных кредитов: {fact_status['loan_id'].nunique()}")
    print(f"Диапазон дат: {fact_status['report_date'].min().date()} — {fact_status['report_date'].max().date()}")
    print(f"\nРаспределение по стадиям МСФО 9:")
    stage_counts = fact_status['ifrs9_stage'].value_counts().sort_index()
    for stage, count in stage_counts.items():
        pct = count / len(fact_status) * 100
        print(f"  Стадия {stage}: {count} записей ({pct:.1f}%)")
    
    print(f"\nСредний DPD по стадиям:")
    avg_dpd = fact_status.groupby('ifrs9_stage')['dpd'].mean()
    for stage, dpd in avg_dpd.items():
        print(f"  Стадия {stage}: {dpd:.0f} дней")

if __name__ == "__main__":
    main()