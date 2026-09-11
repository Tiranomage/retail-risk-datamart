import pandas as pd
from datetime import datetime

def load_raw_data():
    """Загрузка сырых данных из слоя raw."""
    print("Загрузка сырых данных...")
    clients = pd.read_csv('data/raw/raw_clients.csv', dtype={'client_id': str})
    loans = pd.read_csv('data/raw/raw_loans.csv', dtype={'client_id': str, 'loan_id': str})
    return clients, loans

def build_dim_clients(df_clients: pd.DataFrame) -> pd.DataFrame:
    """Очистка и трансформация данных по клиентам."""
    df = df_clients.copy()
    
    # Приводим даты к типу datetime
    df['birth_date'] = pd.to_datetime(df['birth_date'], format='%Y-%m-%d')
    
    # Рассчитываем возраст
    today = pd.Timestamp.today()
    df['age'] = (today - df['birth_date']).dt.days // 365.25
    
    # Создаем полное имя
    df['full_name'] = df['first_name'] + ' ' + df['last_name']
    
    # Выбираем только нужные колонки для витрины
    dim_clients = df[['client_id', 'full_name', 'age', 'gender']].copy()
    
    return dim_clients

def build_dim_loans(df_loans: pd.DataFrame) -> pd.DataFrame:
    """Очистка и трансформация данных по кредитам."""
    df = df_loans.copy()
    
    # Приводим даты к типу datetime
    df['issue_date'] = pd.to_datetime(df['issue_date'], format='%Y-%m-%d')
    df['maturity_date'] = pd.to_datetime(df['maturity_date'], format='%Y-%m-%d')
    
    # Для аналитики рисков полезно знать количество дней с даты выдачи
    today = pd.Timestamp.today()
    df['days_since_issue'] = (today - df['issue_date']).dt.days
    
    dim_loans = df[[
        'loan_id', 'client_id', 'product_name', 
        'principal_amount', 'interest_rate', 
        'issue_date', 'term_months', 'days_since_issue'
    ]].copy()
    
    # Переименовываем колонку для соответствия ТЗ
    dim_loans.rename(columns={'principal_amount': 'initial_amount'}, inplace=True)
    
    return dim_loans

def build_dim_dates(start_date: str, end_date: str) -> pd.DataFrame:
    """Генерация календаря дат."""
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    df = pd.DataFrame({'date': dates})
    
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['year_month'] = df['date'].dt.to_period('M').astype(str)
    
    # Флаг последнего дня месяца
    df['is_end_of_month'] = df['date'].dt.is_month_end
    
    return df

def main():
    # 1. Загружаем сырые данные
    raw_clients, raw_loans = load_raw_data()
    
    print("Построение измерений...")
    
    # 2. Трансформируем
    dim_clients = build_dim_clients(raw_clients)
    dim_loans = build_dim_loans(raw_loans)
    
    # Календарь генерируем с небольшим запасом (от начала выдачи кредитов до конца следующего года)
    min_issue_date = raw_loans['issue_date'].min()
    dim_dates = build_dim_dates(min_issue_date, '2026-12-31')
    
    # 3. Сохраняем в слой processed
    print("Сохранение витрин измерений...")
    dim_clients.to_csv('data/processed/dim_clients.csv', index=False, encoding='utf-8-sig')
    dim_loans.to_csv('data/processed/dim_loans.csv', index=False, encoding='utf-8-sig')
    dim_dates.to_csv('data/processed/dim_dates.csv', index=False, encoding='utf-8-sig')
    
    print(f"Готово!")
    print(f"Клиентов в витрине: {len(dim_clients)}")
    print(f"Кредитов в витрине: {len(dim_loans)}")
    print(f"Дат в календаре: {len(dim_dates)}")

if __name__ == "__main__":
    main()