"""Append a dated Workday extract batch to the DuckDB raw layer."""

import argparse
import os

import duckdb

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(CURRENT_DIR, "people_analytics.duckdb")
BATCHES = {
    "month_1": {
        "extract_date": "2026-06-30",
        "employees": "us_workday_employee_raw.csv",
        "transactions": "us_workday_transactions_raw.csv",
    },
    "month_2": {
        "extract_date": "2026-08-31",
        "employees": "us_workday_employee_month_2_raw.csv",
        "transactions": "us_workday_transactions_month_2_raw.csv",
    },
}


def table_exists(connection, table_name):
    return connection.execute(
        "select count(*) from information_schema.tables where table_schema = 'main' and table_name = ?",
        [table_name],
    ).fetchone()[0] == 1


def migrate_extract_date_column(connection, table_name, month_1_extract_date):
    """Make pre-existing Month 1 tables append-compatible without recreating them."""
    connection.execute(f"alter table {table_name} add column if not exists extract_date date")
    connection.execute(
        f"update {table_name} set extract_date = cast(? as date) where extract_date is null",
        [month_1_extract_date],
    )


def append_batch(connection, table_name, csv_path, extract_date):
    if not table_exists(connection, table_name):
        connection.execute(
            f"create table {table_name} as select * from read_csv_auto(?)",
            [csv_path],
        )
        return

    migrate_extract_date_column(connection, table_name, BATCHES["month_1"]["extract_date"])
    already_loaded = connection.execute(
        f"select count(*) from {table_name} where extract_date = cast(? as date)",
        [extract_date],
    ).fetchone()[0]
    if already_loaded:
        raise ValueError(f"{table_name} already contains the {extract_date} extract; refusing to duplicate it.")
    connection.execute(f"insert into {table_name} by name select * from read_csv_auto(?)", [csv_path])


def main():
    parser = argparse.ArgumentParser(description="Append a Workday raw extract batch to DuckDB.")
    parser.add_argument("--batch", choices=BATCHES, required=True)
    args = parser.parse_args()
    batch = BATCHES[args.batch]
    employee_path = os.path.join(CURRENT_DIR, batch["employees"])
    transaction_path = os.path.join(CURRENT_DIR, batch["transactions"])

    for path in (employee_path, transaction_path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Batch input file not found: {path}")

    connection = duckdb.connect(database=DATABASE_FILE, read_only=False)
    try:
        append_batch(connection, "raw_workday_employees", employee_path, batch["extract_date"])
        append_batch(connection, "raw_workday_transactions", transaction_path, batch["extract_date"])
        employee_count = connection.execute("select count(*) from raw_workday_employees").fetchone()[0]
        transaction_count = connection.execute("select count(*) from raw_workday_transactions").fetchone()[0]
        print(f"[SUCCESS] Appended {args.batch}; raw tables now contain {employee_count:,} employee rows and {transaction_count:,} event rows.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
