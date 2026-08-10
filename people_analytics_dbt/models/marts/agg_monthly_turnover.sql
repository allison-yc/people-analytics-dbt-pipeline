with months as (
    select
        cast(month_start as date) as month_start,
        least(
            cast(month_start + interval '1 month' - interval '1 day' as date),
            current_date
        ) as month_end
    from unnest(
        generate_series(date '2018-01-01', current_date, interval '1 month')
    ) as calendar(month_start)
),

departments as (
    select distinct department
    from {{ ref('dim_employees') }}
    where department is not null
),

monthly_headcount as (
    select
        months.month_start,
        departments.department,
        count(distinct case
            when employees.is_active
                and employees.valid_from <= cast(months.month_start as timestamp)
                and (
                    employees.valid_to is null
                    or employees.valid_to > cast(months.month_start as timestamp)
                )
            then employees.employee_id
        end) as beginning_headcount,
        count(distinct case
            when employees.is_active
                and employees.valid_from <= cast(months.month_end as timestamp)
                and (
                    employees.valid_to is null
                    or employees.valid_to > cast(months.month_end as timestamp)
                )
            then employees.employee_id
        end) as ending_headcount
    from months
    cross join departments
    left join {{ ref('dim_employees') }} as employees
        on employees.department = departments.department
        and employees.valid_from <= cast(months.month_end as timestamp)
        and (
            employees.valid_to is null
            or employees.valid_to > cast(months.month_start as timestamp)
        )
    group by 1, 2
),

monthly_terminations as (
    select
        date_trunc('month', events.event_date) as month_start,
        coalesce(
            events.new_department,
            events.previous_department,
            employees.department
        ) as department,
        count(*) as terminations
    from {{ ref('fact_employee_events') }} as events
    left join {{ ref('dim_employees') }} as employees
        on events.employee_scd_key = employees.employee_scd_key
    where events.event_type = 'Termination'
    group by 1, 2
),

monthly_turnover as (
    select
        headcount.month_start,
        headcount.department,
        headcount.beginning_headcount,
        headcount.ending_headcount,
        coalesce(terminations.terminations, 0) as terminations
    from monthly_headcount as headcount
    left join monthly_terminations as terminations
        on headcount.month_start = terminations.month_start
        and headcount.department = terminations.department
)

select
    cast(month_start as varchar) || '|' || department as monthly_department_key,
    month_start as reporting_month,
    department,
    beginning_headcount,
    ending_headcount,
    terminations,
    terminations / nullif((beginning_headcount + ending_headcount) / 2.0, 0) as turnover_rate
from monthly_turnover
where beginning_headcount > 0
    or ending_headcount > 0
