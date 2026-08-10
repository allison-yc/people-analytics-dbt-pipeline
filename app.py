"""Interactive People Analytics Executive Dashboard."""

from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st


DATABASE_FILE = Path(__file__).with_name("people_analytics.duckdb")
AUGUST_2026 = "2026-08-01"

st.set_page_config(
    page_title="People Analytics Executive Dashboard",
    page_icon="👥",
    layout="wide",
)


def relation_name(connection, table_name):
    """Use the marts schema when configured, otherwise this project's main schema."""
    schemas = connection.execute(
        """
        select table_schema
        from information_schema.tables
        where table_name = ? and table_schema in ('marts', 'main')
        order by case table_schema when 'marts' then 1 else 2 end
        limit 1
        """,
        [table_name],
    ).fetchone()
    if not schemas:
        raise RuntimeError(f"Could not find the dbt model: {table_name}")
    return f"{schemas[0]}.{table_name}"


@st.cache_data(ttl=60)
def load_dashboard_data():
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_FILE}")

    connection = duckdb.connect(str(DATABASE_FILE), read_only=True)
    try:
        turnover_table = relation_name(connection, "agg_monthly_turnover")
        employees_table = relation_name(connection, "dim_employees")
        events_table = relation_name(connection, "fact_employee_events")

        august_turnover = connection.execute(
            f"""
            select department, beginning_headcount, ending_headcount, terminations, turnover_rate
            from {turnover_table}
            where reporting_month = date '{AUGUST_2026}'
            order by turnover_rate desc nulls last, department
            """
        ).df()
        current_employees = connection.execute(
            f"""
            select department, job_level, base_salary_usd
            from {employees_table}
            where is_current = true and is_active = true
            """
        ).df()
        workforce_flow = connection.execute(
            f"""
            with years as (
                select unnest(generate_series(2018, 2026)) as year
            ),
            annual_events as (
                select
                    year(event_date) as year,
                    event_type,
                    count(*) as event_count
                from {events_table}
                where event_type in ('Hire', 'Termination')
                group by 1, 2
            )
            select
                years.year,
                coalesce(sum(case when event_type = 'Hire' then event_count end), 0) as hires,
                coalesce(sum(case when event_type = 'Termination' then event_count end), 0) as terminations
            from years
            left join annual_events on years.year = annual_events.year
            group by 1
            order by 1
            """
        ).df()
    finally:
        connection.close()

    return august_turnover, current_employees, workforce_flow


st.title("People Analytics Executive Dashboard")
st.caption("Workforce health, compensation, and talent-flow indicators")

try:
    august_turnover, current_employees, workforce_flow = load_dashboard_data()
except Exception as error:
    st.error(f"Unable to load dashboard data: {error}")
    st.stop()

total_headcount = len(current_employees)
august_terminations = int(august_turnover["terminations"].sum())
average_headcount = (
    august_turnover["beginning_headcount"].sum()
    + august_turnover["ending_headcount"].sum()
) / 2
turnover_rate = august_terminations / average_headcount if average_headcount else 0

kpi_headcount, kpi_terminations, kpi_turnover = st.columns(3)
kpi_headcount.metric("Total Headcount", f"{total_headcount:,}")
kpi_terminations.metric("August 2026 Terminations", f"{august_terminations:,}")
kpi_turnover.metric("August 2026 Turnover Rate", f"{turnover_rate:.2%}")

turnover_chart, salary_chart = st.columns(2)
with turnover_chart:
    st.subheader("August Turnover Rate by Department")
    turnover_figure = px.bar(
        august_turnover,
        x="department",
        y="turnover_rate",
        text=august_turnover["turnover_rate"].map(lambda value: f"{value:.2%}"),
        labels={"department": "Department", "turnover_rate": "Turnover Rate"},
        color="turnover_rate",
        color_continuous_scale="Reds",
    )
    turnover_figure.update_yaxes(tickformat=".0%")
    turnover_figure.update_layout(coloraxis_showscale=False, margin=dict(t=20, l=10, r=10, b=10))
    st.plotly_chart(turnover_figure, use_container_width=True)

with salary_chart:
    st.subheader("Base Salary Distribution by Department")
    salary_figure = px.box(
        current_employees,
        x="department",
        y="base_salary_usd",
        color="department",
        points="outliers",
        labels={"department": "Department", "base_salary_usd": "Base Salary (USD)"},
    )
    salary_figure.update_layout(showlegend=False, margin=dict(t=20, l=10, r=10, b=10))
    salary_figure.update_yaxes(tickprefix="$", tickformat=",")
    st.plotly_chart(salary_figure, use_container_width=True)

st.subheader("Long-term Workforce Flow")
flow_figure = px.line(
    workforce_flow.melt(id_vars="year", var_name="event_type", value_name="employee_count"),
    x="year",
    y="employee_count",
    color="event_type",
    markers=True,
    labels={"year": "Year", "employee_count": "Employees", "event_type": "Event Type"},
    color_discrete_map={"hires": "#2E8B57", "terminations": "#D62728"},
)
flow_figure.update_xaxes(dtick=1)
flow_figure.update_layout(legend_title_text="", margin=dict(t=20, l=10, r=10, b=10))
st.plotly_chart(flow_figure, use_container_width=True)
