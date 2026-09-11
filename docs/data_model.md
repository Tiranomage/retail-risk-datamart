# Целевая модель витрины данных для розничных рисков (МСФО 9)

## 1. Описание
Витрина предназначена для расчета просрочки (DPD) и определения стадий обесценения (Stage 1, 2, 3) по портфелю розничных кредитов на ежемесячной основе.

## 2. Схема данных
Используется схема "Звезда". Центральная таблица фактов: `fact_loan_status`.

### Таблица: dim_clients
| Поле | Тип | Описание | Источник |
|---|---|---|---|
| client_id | VARCHAR | Уникальный ИД клиента | raw_clients.client_id |
| full_name | VARCHAR | ФИО | Конкатенация first_name + last_name |
| age | INT | Возраст клиента на текущую дату | Рассчитывается из birth_date |
| gender | VARCHAR | Пол | raw_clients.gender |

### Таблица: dim_loans
| Поле | Тип | Описание | Источник |
|---|---|---|---|
| loan_id | VARCHAR | Уникальный ИД договора | raw_loans.loan_id |
| client_id | VARCHAR | Ссылка на клиента (FK) | raw_loans.client_id |
| product_name | VARCHAR | Тип кредитного продукта | raw_loans.product_name |
| initial_amount | DECIMAL | Сумма при выдаче | raw_loans.principal_amount |
| interest_rate | DECIMAL | Годовая ставка | raw_loans.interest_rate |
| issue_date | DATE | Дата выдачи | raw_loans.issue_date |
| term_months | INT | Срок кредита | raw_loans.term_months |

### Таблица: dim_dates
| Поле | Тип | Описание | Источник |
|---|---|---|---|
| date | DATE | Календарная дата | Генерация календаря |
| year_month | VARCHAR | Год и месяц (формат 2023-10) | Расчет |
| is_end_of_month | BOOLEAN | Флаг конца месяца | Расчет |