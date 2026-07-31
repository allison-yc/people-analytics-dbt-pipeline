with employee_events as (
    select *
    from {{ ref('stg_workday_transactions') }}
),

employee_dimension as (
    select
        employee_scd_key,
        employee_id,
        valid_from,
        valid_to
    from {{ ref('dim_employees') }}
)

select
    events.transaction_id as employee_event_key,
    dimension.employee_scd_key,
    events.employee_id,
    events.event_date,
    events.event_type,
    events.reason_code,
    events.previous_department,
    events.new_department,
    events.previous_job_family,
    events.new_job_family,
    events.previous_job_level,
    events.new_job_level,
    events.previous_base_salary_usd,
    events.new_base_salary_usd,
    events.termination_type

from employee_events as events
left join employee_dimension as dimension
    on events.employee_id = dimension.employee_id
    and cast(events.event_date as timestamp) >= dimension.valid_from
    and (
        cast(events.event_date as timestamp) < dimension.valid_to
        or dimension.valid_to is null
    )
