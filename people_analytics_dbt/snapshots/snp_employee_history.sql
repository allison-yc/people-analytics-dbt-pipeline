{% snapshot snp_employee_history %}

{%- set tracked_columns = [
    'manager_id',
    'department',
    'job_family',
    'job_level',
    'flsa_status',
    'base_salary_usd',
    'variable_pay_pct',
    'work_state',
    'termination_date',
    'termination_type',
    'termination_reason'
] -%}

{{
    config(
        target_schema='snapshots',
        unique_key='employee_id',
        strategy='check',
        check_cols=tracked_columns,
        invalidate_hard_deletes=false
    )
}}

select *
from {{ ref('stg_workday_employees') }}

{% endsnapshot %}
