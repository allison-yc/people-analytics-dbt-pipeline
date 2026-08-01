"""Display a sample of employees with multiple SCD Type 2 snapshot versions."""

import os

import duckdb


DATABASE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "people_analytics.duckdb"
)

QUERY = """
with employees_with_history as (
    select employee_id
    from snapshots.snp_employee_history
    group by employee_id
    having count(*) > 1
)

select
    history.employee_id,
    history.department,
    history.job_level,
    history.base_salary_usd,
    history.dbt_valid_from,
    history.dbt_valid_to
from snapshots.snp_employee_history as history
inner join employees_with_history
    on history.employee_id = employees_with_history.employee_id
order by history.employee_id, history.dbt_valid_from
limit 6
"""


def main():
    connection = duckdb.connect(DATABASE_FILE, read_only=True)
    try:
        print(connection.execute(QUERY).df())
    finally:
        connection.close()


if __name__ == "__main__":
    main()
