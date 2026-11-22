# JSONPlaceholder → ClickHouse: Data Quality Pipeline

ETL-пайплайн с проверками качества данных перед и после загрузки в ClickHouse.

## Что делает

1. Забирает 500 комментариев из публичного API JSONPlaceholder.
2. Трансформирует данные (приводит типы, переименовывает `postId` → `post_id`).
3. Прогоняет DQ-проверки:
   - **Критичные (пайплайн падает):** null в `email`, дубли по `id`.
   - **Некритичные (только лог):** подозрительно короткий `body`.
4. Загружает данные в ClickHouse.
5. Пост-проверка: сверяет количество строк в БД с ожидаемым.

## Стек

- Python 3 (requests, pandas, clickhouse-connect)
- ClickHouse (Docker)
- DBeaver (для визуальной проверки)

## Запуск - 1

```bash
pip install -r requirements.txt
docker compose up -d
```

## Проверка: 

```bash
curl "http://localhost:8123/?query=SELECT%20count()%20FROM%20comments"
```

## Запуск - 2

```bash
python index.py
```

<img width="1155" height="266" alt="Снимок экрана от 2026-11-22 19-42-15" src="https://github.com/user-attachments/assets/e44af170-4204-4240-87e9-4009634eee2a" />

