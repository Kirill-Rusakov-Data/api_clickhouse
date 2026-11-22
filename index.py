import requests
import pandas as pd
import clickhouse_connect
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

API_URL = "https://jsonplaceholder.typicode.com/comments"

CLICKHOUSE_CONFIG = {
    "host": "localhost",
    "port": 8123,
    "username": "default",
    "password": "de_password",
    "database": "default",
}


def extract():
    """Забирает комментарии из JSONPlaceholder."""
    logger.info("Забираю данные из API...")
    response = requests.get(API_URL, timeout=15)
    response.raise_for_status()
    data = response.json()
    logger.info(f"Получено {len(data)} записей")
    return data


def transform(raw_data):
    """Оставляем нужные поля, приводим типы."""
    df = pd.DataFrame(raw_data)
    df = df[["id", "postId", "name", "email", "body"]]
    df["id"] = df["id"].astype("int64")
    df["postId"] = df["postId"].astype("int64")
    df["name"] = df["name"].astype(str)
    df["email"] = df["email"].astype(str)
    df["body"] = df["body"].astype(str)
    logger.info(f"После transform: {len(df)} строк, колонки: {list(df.columns)}")
    return df


def run_dq_checks(df):
    """
    Смешанные проверки:
    - критичные (падаем): null в email, дубли по id
    - некритичные (только лог): пустой body
    """
    errors = []

    null_emails = df["email"].isna().sum()
    if null_emails > 0:
        errors.append(f"Найдено {null_emails} строк с пустым email")

    dup_ids = df["id"].duplicated().sum()
    if dup_ids > 0:
        errors.append(f"Найдено {dup_ids} дубликатов по id")

    if errors:
        for err in errors:
            logger.error(err)
        raise ValueError("Критичные DQ-проверки провалены. Останавливаю пайплайн.")

    logger.info("Критичные DQ-проверки пройдены.")

    empty_bodies = (df["body"].str.len() < 10).sum()
    if empty_bodies > 0:
        logger.warning(f"Найдено {empty_bodies} строк с подозрительно коротким body (не критично, пропускаем)")

    logger.info("Все DQ-проверки завершены.")


def load(df):
    """Загружает данные в ClickHouse. Пересоздаёт таблицу при каждом запуске."""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)

    client.command("DROP TABLE IF EXISTS comments")
    client.command("""
        CREATE TABLE comments (
            id UInt64,
            post_id UInt64,
            name String,
            email String,
            body String
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    logger.info("Таблица comments создана (или пересоздана).")

    rows = df.rename(columns={"postId": "post_id"}).to_dict("records")
    data = [[r["id"], r["post_id"], r["name"], r["email"], r["body"]] for r in rows]

    client.insert("comments", data, column_names=["id", "post_id", "name", "email", "body"])
    logger.info(f"Загружено {len(data)} строк в comments.")

    result = client.query("SELECT count() FROM comments")
    count_in_db = result.result_rows[0][0]
    if count_in_db != len(df):
        raise ValueError(f"После загрузки в БД {count_in_db} строк, ожидалось {len(df)}")
    logger.info(f"Пост-проверка пройдена: в БД {count_in_db} строк.")

    client.close()


def main():
    logger.info("Старт")
    raw = extract()
    df = transform(raw)
    run_dq_checks(df)
    load(df)
    logger.info("Завершён успешно")


if __name__ == "__main__":
    main()