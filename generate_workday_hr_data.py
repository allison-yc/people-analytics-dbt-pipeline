"""Generate dated Workday employee extracts and incremental HR event batches."""

import argparse
import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
NUM_EMPLOYEES = 3_000
TERMINATION_RATE = 0.17
EMPLOYEE_OUTPUT_FILE = "us_workday_employee_raw.csv"
TRANSACTION_OUTPUT_FILE = "us_workday_transactions_raw.csv"
MONTH_2_EMPLOYEE_OUTPUT_FILE = "us_workday_employee_month_2_raw.csv"
MONTH_2_TRANSACTION_OUTPUT_FILE = "us_workday_transactions_month_2_raw.csv"
HIRE_DATE_START = date(2018, 1, 1)
MONTH_1_EXTRACT_DATE = date(2026, 6, 30)
# The current simulated extract intentionally includes recent August 2026 events.
MONTH_2_EXTRACT_DATE = date(2026, 8, 31)

LEVEL_SALARY_BANDS = {
    "IC1": (60_000, 80_000), "IC2": (80_000, 105_000), "IC3": (105_000, 135_000),
    "IC4": (135_000, 160_000), "IC5": (160_000, 195_000), "M1": (130_000, 165_000),
    "M2": (165_000, 200_000), "M3": (200_000, 240_000), "Director": (220_000, 280_000),
    "VP": (280_000, 380_000),
}
LEVEL_WEIGHTS = {"IC1": .20, "IC2": .22, "IC3": .18, "IC4": .12, "IC5": .08,
                 "M1": .08, "M2": .05, "M3": .03, "Director": .02, "VP": .02}
LEVEL_PROGRESSION = ["IC1", "IC2", "IC3", "IC4", "IC5"]
DEPARTMENTS = {"Engineering": .30, "Sales": .25, "Product": .12, "HR": .08,
               "Finance": .10, "Marketing": .09, "Legal": .06}
DEPT_JOB_FAMILIES = {
    "Engineering": ["Software Engineering", "Data Engineering", "QA Engineering", "Security Engineering", "Infrastructure / DevOps"],
    "Sales": ["Account Management", "Sales Development", "Enterprise Sales", "Revenue Operations", "Customer Success"],
    "Product": ["Product Management", "UX / Design", "Product Operations"],
    "HR": ["Talent Acquisition", "HR Business Partnering", "Total Rewards", "People Operations", "Learning & Development"],
    "Finance": ["Financial Planning & Analysis", "Accounting", "Tax", "Treasury", "Internal Audit"],
    "Marketing": ["Demand Generation", "Content Marketing", "Brand", "Product Marketing", "Marketing Operations"],
    "Legal": ["Corporate Legal", "Employment Law", "Compliance", "Privacy & Data"],
}
WORK_STATES, STATE_WEIGHTS = ["CA", "NY", "TX", "FL", "NJ", "IL", "WA"], [.28, .22, .16, .10, .08, .10, .06]
EEO_CATEGORIES, EEO_WEIGHTS = ["White", "Hispanic or Latino", "Black or African American", "Asian", "Two or More Races"], [.60, .18, .12, .07, .03]
GENDERS, GENDER_WEIGHTS = ["Male", "Female", "Non-Binary / Third Gender"], [.48, .49, .03]
VOLUNTARY_REASONS, INVOLUNTARY_REASONS = ["Career Move", "Personal Reasons", "Compensation"], ["Performance", "Reorganization"]
DEPT_VARIABLE_PAY = {"Engineering": (0, .15), "Sales": (.05, .30), "Product": (0, .15), "HR": (0, .12), "Finance": (0, .15), "Marketing": (0, .18), "Legal": (0, .10)}
EXEC_LEVELS = {"M3", "Director", "VP"}
NON_EXEMPT_COMBOS = {("Sales", "IC1"), ("Sales", "IC2"), ("HR", "IC1"), ("Finance", "IC1"), ("Marketing", "IC1"), ("Legal", "IC1")}


def reset_randomness():
    random.seed(SEED)
    np.random.seed(SEED)
    Faker.seed(SEED)


def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def assign_flsa(department, level):
    return "Non-Exempt" if (department, level) in NON_EXEMPT_COMBOS else "Exempt"


def assign_variable_pay(department, level):
    low, high = DEPT_VARIABLE_PAY[department]
    return round(random.uniform(max(low, .15) if level in EXEC_LEVELS else low, high), 4)


def salary_for_level(level):
    low, high = LEVEL_SALARY_BANDS[level]
    return round(random.uniform(low, high) / 1_000) * 1_000


def generate_email(first, last, used_emails):
    base = "".join(c for c in f"{first.lower()}.{last.lower()}".replace("'", "") if c.isascii() and (c.isalnum() or c == "."))
    email, suffix = f"{base}@techcorp.com", 1
    while email in used_emails:
        email, suffix = f"{base}{suffix}@techcorp.com", suffix + 1
    used_emails.add(email)
    return email


def build_org_hierarchy(employee_ids, levels):
    by_level = {}
    for employee_id, level in zip(employee_ids, levels):
        by_level.setdefault(level, []).append(employee_id)

    def manager(pool):
        candidates = [employee_id for level in pool for employee_id in by_level.get(level, [])]
        return random.choice(candidates) if candidates else None

    pools = {"VP": [], "Director": ["VP"], "M3": ["Director", "VP"], "M2": ["M3", "Director"], "M1": ["M2", "M3"]}
    return {employee_id: manager(pools.get(level, ["M1", "M2"])) for employee_id, level in zip(employee_ids, levels)}


def next_level(level):
    if level not in LEVEL_PROGRESSION or level == LEVEL_PROGRESSION[-1]:
        return level
    return LEVEL_PROGRESSION[LEVEL_PROGRESSION.index(level) + 1]


def add_transaction(events, employee_id, event_date, event_type, reason_code,
                    transaction_prefix="TXN", **changes):
    events.append({
        "transaction_id": f"{transaction_prefix}-{len(events) + 1:07d}", "employee_id": employee_id,
        "event_date": event_date, "event_type": event_type, "reason_code": reason_code,
        "previous_department": changes.get("previous_department"), "new_department": changes.get("new_department"),
        "previous_job_family": changes.get("previous_job_family"), "new_job_family": changes.get("new_job_family"),
        "previous_job_level": changes.get("previous_job_level"), "new_job_level": changes.get("new_job_level"),
        "previous_base_salary_usd": changes.get("previous_base_salary_usd"), "new_base_salary_usd": changes.get("new_base_salary_usd"),
        "termination_type": changes.get("termination_type"),
    })


def generate_datasets(n=NUM_EMPLOYEES):
    reset_randomness()
    fake = Faker("en_US")
    employee_ids = [f"EMP-{number:04d}" for number in range(1, n + 1)]
    levels = random.choices(list(LEVEL_WEIGHTS), weights=LEVEL_WEIGHTS.values(), k=n)
    departments = random.choices(list(DEPARTMENTS), weights=DEPARTMENTS.values(), k=n)
    genders = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=n)
    used_emails, employees, events = set(), [], []

    print(f"[INFO] Generating {n:,} employee current-state records and transaction events …")
    for employee_id, level, department, gender in zip(employee_ids, levels, departments, genders):
        first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        if gender == "Non-Binary / Third Gender":
            first_name = fake.first_name()
        hire_date = random_date(HIRE_DATE_START, MONTH_1_EXTRACT_DATE - timedelta(days=30))
        employee = {"employee_id": employee_id, "first_name": first_name, "last_name": fake.last_name(),
                    "corporate_email": None, "gender": gender, "manager_id": None, "hire_date": hire_date,
                    "termination_date": None, "termination_type": None, "termination_reason": None,
                    "department": department, "job_family": random.choice(DEPT_JOB_FAMILIES[department]),
                    "job_level": level, "flsa_status": assign_flsa(department, level),
                    "base_salary_usd": salary_for_level(level), "variable_pay_pct": assign_variable_pay(department, level),
                    "work_state": random.choices(WORK_STATES, weights=STATE_WEIGHTS)[0],
                    "eeo_ethnicity_category": random.choices(EEO_CATEGORIES, weights=EEO_WEIGHTS)[0]}
        employee["corporate_email"] = generate_email(employee["first_name"], employee["last_name"], used_emails)
        add_transaction(events, employee_id, hire_date, "Hire", "New Hire",
                        new_department=department, new_job_family=employee["job_family"], new_job_level=level,
                        new_base_salary_usd=employee["base_salary_usd"])

        latest_change_date = hire_date
        final_event_date = MONTH_1_EXTRACT_DATE - timedelta(days=1)
        if (final_event_date - hire_date).days >= 90:
            change_count = random.choices([0, 1, 2], weights=[.35, .45, .20])[0]
            for _ in range(change_count):
                earliest_event_date = latest_change_date + timedelta(days=30)
                if earliest_event_date > final_event_date:
                    break
                event_date = random_date(earliest_event_date, final_event_date)
                latest_change_date = event_date
                event_type = random.choices(["Promotion", "Transfer", "Compensation Change"], weights=[.30, .25, .45])[0]
                if event_type == "Promotion" and employee["job_level"] not in LEVEL_PROGRESSION[:-1]:
                    event_type = "Compensation Change"
                old = employee.copy()
                if event_type == "Promotion":
                    employee["job_level"] = next_level(employee["job_level"])
                    employee["base_salary_usd"] = salary_for_level(employee["job_level"])
                    employee["flsa_status"] = assign_flsa(employee["department"], employee["job_level"])
                    reason = "Merit Promotion"
                elif event_type == "Transfer":
                    choices = [dept for dept in DEPARTMENTS if dept != employee["department"]]
                    employee["department"] = random.choice(choices)
                    employee["job_family"] = random.choice(DEPT_JOB_FAMILIES[employee["department"]])
                    employee["variable_pay_pct"] = assign_variable_pay(employee["department"], employee["job_level"])
                    employee["flsa_status"] = assign_flsa(employee["department"], employee["job_level"])
                    reason = "Internal Transfer"
                else:
                    employee["base_salary_usd"] = round(old["base_salary_usd"] * random.uniform(1.03, 1.12) / 1_000) * 1_000
                    reason = random.choice(["Merit Increase", "Market Adjustment"])
                add_transaction(events, employee_id, event_date, event_type, reason,
                                previous_department=old["department"], new_department=employee["department"],
                                previous_job_family=old["job_family"], new_job_family=employee["job_family"],
                                previous_job_level=old["job_level"], new_job_level=employee["job_level"],
                                previous_base_salary_usd=old["base_salary_usd"], new_base_salary_usd=employee["base_salary_usd"])

        if random.random() < TERMINATION_RATE and (MONTH_1_EXTRACT_DATE - latest_change_date).days >= 30:
            termination_date = random_date(latest_change_date + timedelta(days=30), MONTH_1_EXTRACT_DATE)
            termination_type = random.choices(["Voluntary", "Involuntary"], weights=[.65, .35])[0]
            reason = random.choice(VOLUNTARY_REASONS if termination_type == "Voluntary" else INVOLUNTARY_REASONS)
            employee.update({"termination_date": termination_date, "termination_type": termination_type, "termination_reason": reason})
            add_transaction(events, employee_id, termination_date, "Termination", reason, termination_type=termination_type)
        employees.append(employee)

    manager_map = build_org_hierarchy(employee_ids, [employee["job_level"] for employee in employees])
    for employee in employees:
        employee["manager_id"] = manager_map[employee["employee_id"]]
    employee_extract = pd.DataFrame(employees)
    transaction_extract = pd.DataFrame(events).sort_values(["employee_id", "event_date", "transaction_id"])
    employee_extract["extract_date"] = MONTH_1_EXTRACT_DATE
    transaction_extract["extract_date"] = MONTH_1_EXTRACT_DATE
    return employee_extract, transaction_extract


def generate_month_2_datasets():
    """Create an August current-state extract and only August change events."""
    if not os.path.exists(EMPLOYEE_OUTPUT_FILE):
        raise FileNotFoundError(
            f"Month 1 extract not found: {EMPLOYEE_OUTPUT_FILE}. Run --batch month_1 first."
        )

    random.seed(SEED + 2)
    employees = pd.read_csv(EMPLOYEE_OUTPUT_FILE)
    employees["extract_date"] = MONTH_2_EXTRACT_DATE
    employees["termination_date"] = pd.to_datetime(employees["termination_date"], errors="coerce")
    active_ids = employees.loc[employees["termination_date"].isna(), "employee_id"].tolist()
    random.shuffle(active_ids)

    # The groups are disjoint so each employee has one unambiguous Month 2 change.
    promotion_ids = [employee_id for employee_id in active_ids if employees.loc[employees.employee_id.eq(employee_id), "job_level"].iloc[0] in LEVEL_PROGRESSION[:-1]][:75]
    remaining_ids = [employee_id for employee_id in active_ids if employee_id not in promotion_ids]
    compensation_ids = remaining_ids[:150]
    transfer_ids = remaining_ids[150:200]
    termination_ids = remaining_ids[200:240]
    events = []

    def event_date():
        return random_date(MONTH_2_EXTRACT_DATE.replace(day=1), MONTH_2_EXTRACT_DATE)

    for employee_id in promotion_ids + compensation_ids + transfer_ids + termination_ids:
        row_index = employees.index[employees["employee_id"] == employee_id][0]
        old = employees.loc[row_index].copy()
        effective_date = event_date()

        if employee_id in promotion_ids:
            new_level = next_level(old["job_level"])
            new_salary = max(float(old["base_salary_usd"]) * 1.08, salary_for_level(new_level))
            new_salary = round(new_salary / 1_000) * 1_000
            employees.loc[row_index, ["job_level", "base_salary_usd", "flsa_status"]] = [
                new_level, new_salary, assign_flsa(old["department"], new_level)
            ]
            add_transaction(events, employee_id, effective_date, "Promotion", "Merit Promotion", "TXN-M2-AUG2026",
                            previous_department=old["department"], new_department=old["department"],
                            previous_job_family=old["job_family"], new_job_family=old["job_family"],
                            previous_job_level=old["job_level"], new_job_level=new_level,
                            previous_base_salary_usd=old["base_salary_usd"], new_base_salary_usd=new_salary)
        elif employee_id in compensation_ids:
            new_salary = round(float(old["base_salary_usd"]) * random.uniform(1.03, 1.08) / 1_000) * 1_000
            employees.loc[row_index, "base_salary_usd"] = new_salary
            add_transaction(events, employee_id, effective_date, "Compensation Change", "Merit Increase", "TXN-M2-AUG2026",
                            previous_department=old["department"], new_department=old["department"],
                            previous_job_family=old["job_family"], new_job_family=old["job_family"],
                            previous_job_level=old["job_level"], new_job_level=old["job_level"],
                            previous_base_salary_usd=old["base_salary_usd"], new_base_salary_usd=new_salary)
        elif employee_id in transfer_ids:
            new_department = random.choice([department for department in DEPARTMENTS if department != old["department"]])
            new_job_family = random.choice(DEPT_JOB_FAMILIES[new_department])
            employees.loc[row_index, ["department", "job_family", "variable_pay_pct", "flsa_status"]] = [
                new_department, new_job_family, assign_variable_pay(new_department, old["job_level"]),
                assign_flsa(new_department, old["job_level"])
            ]
            add_transaction(events, employee_id, effective_date, "Transfer", "Internal Transfer", "TXN-M2-AUG2026",
                            previous_department=old["department"], new_department=new_department,
                            previous_job_family=old["job_family"], new_job_family=new_job_family,
                            previous_job_level=old["job_level"], new_job_level=old["job_level"],
                            previous_base_salary_usd=old["base_salary_usd"], new_base_salary_usd=old["base_salary_usd"])
        else:
            termination_type = random.choices(["Voluntary", "Involuntary"], weights=[.65, .35])[0]
            reason = random.choice(VOLUNTARY_REASONS if termination_type == "Voluntary" else INVOLUNTARY_REASONS)
            employees.loc[row_index, ["termination_date", "termination_type", "termination_reason"]] = [
                pd.Timestamp(effective_date), termination_type, reason
            ]
            add_transaction(events, employee_id, effective_date, "Termination", reason, "TXN-M2-AUG2026",
                            termination_type=termination_type)

    transactions = pd.DataFrame(events).sort_values(["employee_id", "event_date", "transaction_id"])
    transactions["extract_date"] = MONTH_2_EXTRACT_DATE
    employees["termination_date"] = employees["termination_date"].dt.date
    return employees, transactions


def main():
    parser = argparse.ArgumentParser(description="Generate a dated Workday extract batch.")
    parser.add_argument("--batch", choices=["month_1", "month_2"], default="month_2")
    args = parser.parse_args()

    if args.batch == "month_1":
        employees, transactions = generate_datasets()
        employee_file, transaction_file = EMPLOYEE_OUTPUT_FILE, TRANSACTION_OUTPUT_FILE
    else:
        employees, transactions = generate_month_2_datasets()
        employee_file, transaction_file = MONTH_2_EMPLOYEE_OUTPUT_FILE, MONTH_2_TRANSACTION_OUTPUT_FILE

    employees.to_csv(employee_file, index=False)
    transactions.to_csv(transaction_file, index=False)
    print(f"[SUCCESS] {args.batch} employee extract: {employee_file} ({len(employees):,} rows)")
    print(f"[SUCCESS] {args.batch} transaction events: {transaction_file} ({len(transactions):,} rows)")


if __name__ == "__main__":
    main()
