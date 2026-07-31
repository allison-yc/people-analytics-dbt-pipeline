with employee_history as (
    select *
    from {{ ref('snp_employee_history') }}
)

select
    dbt_scd_id as employee_scd_key,
    employee_id,
    first_name,
    last_name,
    email,
    gender,
    manager_id,
    department,
    job_family,
    job_level,
    flsa_status,
    base_salary_usd,
    variable_pay_pct,
    hire_date,
    termination_date,
    termination_type,
    termination_reason,
    work_state,
    eeo_ethnicity_category,
    is_active,
    dbt_valid_from as valid_from,
    dbt_valid_to as valid_to,
    dbt_valid_to is null as is_current

from employee_history
