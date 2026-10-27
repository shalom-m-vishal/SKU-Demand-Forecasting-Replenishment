import sqlite3


def save_to_sqlite(data, db_path="replenishment.db"):
    with sqlite3.connect(db_path) as connection:
        for table_name, df in data.items():
            df.to_sql(
                table_name,
                connection,
                if_exists="replace",
                index=False
            )

    return db_path
