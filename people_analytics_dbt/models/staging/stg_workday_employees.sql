with raw_employees as (
    select * from {{ source('hr_system', 'raw_workday_employees') }}
),

renamed_and_cast as (
    select
        cast(employee_id as varchar) as employee_id,
        cast(first_name as varchar) as first_name,
        cast(last_name as varchar) as last_name,
        cast(corporate_email as varchar) as email,
        cast(gender as varchar) as gender,

        cast(manager_id as varchar) as manager_id,
        cast(department as varchar) as department,
        cast(job_family as varchar) as job_family,
        cast(job_level as varchar) as job_level,
        cast(flsa_status as varchar) as flsa_status,

        cast(base_salary_usd as decimal(18, 2)) as base_salary_usd,
        cast(variable_pay_pct as decimal(8, 4)) as variable_pay_pct,

        cast(hire_date as date) as hire_date,
        cast(termination_date as date) as termination_date,
        cast(termination_type as varchar) as termination_type,
        cast(termination_reason as varchar) as termination_reason,
        case when termination_date is null then true else false end as is_active,
        cast(extract_date as date) as extract_date,

        cast(work_state as varchar) as work_state,
        cast(eeo_ethnicity_category as varchar) as eeo_ethnicity_category

    from raw_employees
),

latest_employee_extract as (
    select
        *,
        row_number() over (
            partition by employee_id
            order by extract_date desc
        ) as extract_rank
    from renamed_and_cast
)

select * exclude (extract_rank)
from latest_employee_extract
where extract_rank = 1
