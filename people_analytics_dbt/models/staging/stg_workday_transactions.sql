with raw_transactions as (
    select * from {{ source('hr_system', 'raw_workday_transactions') }}
),

renamed_and_cast as (
    select
        cast(transaction_id as varchar) as transaction_id,
        cast(employee_id as varchar) as employee_id,
        cast(event_date as date) as event_date,
        cast(event_type as varchar) as event_type,
        cast(reason_code as varchar) as reason_code,

        cast(previous_department as varchar) as previous_department,
        cast(new_department as varchar) as new_department,
        cast(previous_job_family as varchar) as previous_job_family,
        cast(new_job_family as varchar) as new_job_family,
        cast(previous_job_level as varchar) as previous_job_level,
        cast(new_job_level as varchar) as new_job_level,
        cast(previous_base_salary_usd as decimal(18, 2)) as previous_base_salary_usd,
        cast(new_base_salary_usd as decimal(18, 2)) as new_base_salary_usd,
        cast(termination_type as varchar) as termination_type,
        cast(extract_date as date) as extract_date

    from raw_transactions
)

select * from renamed_and_cast
