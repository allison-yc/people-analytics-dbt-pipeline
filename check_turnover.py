"""Display monthly turnover metrics by department from the dbt mart."""

import os

import duckdb


DATABASE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "people_analytics.duckdb"
)

QUERY = """
select
    reporting_month,
    department,
    beginning_headcount,
    ending_headcount,
    terminations,
    round(turnover_rate * 100, 2) as turnover_rate_pct
from main.agg_monthly_turnover
order by reporting_month desc, department
"""


def main():
    connection = duckdb.connect(DATABASE_FILE, read_only=True)
    try:
        print("\n--- Monthly Turnover by Department ---")
        print(connection.execute(QUERY).df().to_string(index=False))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
