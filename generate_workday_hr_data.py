"""
================================================================================
  Enterprise HR Dataset Generator — US Workday HCM Simulation
  (Bulletproof Version for Any Python/Pandas Environment)
================================================================================
"""

import random
from datetime import date, timedelta
import numpy as np
import pandas as pd
from faker import Faker

# Seed everything for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

# ── 1. Constants & lookup tables ─────────────────────────────────────────────
NUM_EMPLOYEES   = 3_000
TERMINATION_RATE = 0.17          
DQ_NOISE_RATE    = 0             # 強制歸零：關閉所有會引發 Pandas 版本衝突的髒數據注入
OUTPUT_FILE      = "us_workday_employee_raw.csv"

HIRE_DATE_START  = date(2018, 1, 1)
HIRE_DATE_END    = date(2026, 3, 31)

LEVEL_SALARY_BANDS = {
    "IC1":      (60_000,  80_000),
    "IC2":      (80_000, 105_000),
    "IC3":     (105_000, 135_000),
    "IC4":     (135_000, 160_000),
    "IC5":     (160_000, 195_000),
    "M1":      (130_000, 165_000),
    "M2":      (165_000, 200_000),
    "M3":      (200_000, 240_000),
    "Director":(220_000, 280_000),
    "VP":      (280_000, 380_000),
}

LEVEL_WEIGHTS = {
    "IC1": 0.20, "IC2": 0.22, "IC3": 0.18, "IC4": 0.12, "IC5": 0.08,
    "M1":  0.08, "M2":  0.05, "M3":  0.03, "Director": 0.02, "VP": 0.02,
}

DEPARTMENTS = {
    "Engineering": 0.30,
    "Sales":       0.25,
    "Product":     0.12,
    "HR":          0.08,
    "Finance":     0.10,
    "Marketing":   0.09,
    "Legal":       0.06,
}

DEPT_JOB_FAMILIES = {
    "Engineering": ["Software Engineering", "Data Engineering", "QA Engineering", "Security Engineering", "Infrastructure / DevOps"],
    "Sales":       ["Account Management", "Sales Development", "Enterprise Sales", "Revenue Operations", "Customer Success"],
    "Product":     ["Product Management", "UX / Design", "Product Operations"],
    "HR":          ["Talent Acquisition", "HR Business Partnering", "Total Rewards", "People Operations", "Learning & Development"],
    "Finance":     ["Financial Planning & Analysis", "Accounting", "Tax", "Treasury", "Internal Audit"],
    "Marketing":   ["Demand Generation", "Content Marketing", "Brand", "Product Marketing", "Marketing Operations"],
    "Legal":       ["Corporate Legal", "Employment Law", "Compliance", "Privacy & Data"],
}

WORK_STATES = ["CA", "NY", "TX", "FL", "NJ", "IL", "WA"]
STATE_WEIGHTS = [0.28, 0.22, 0.16, 0.10, 0.08, 0.10, 0.06]

EEO_CATEGORIES = ["White", "Hispanic or Latino", "Black or African American", "Asian", "Two or More Races"]
EEO_WEIGHTS = [0.60, 0.18, 0.12, 0.07, 0.03]

GENDERS        = ["Male", "Female", "Non-Binary / Third Gender"]
GENDER_WEIGHTS = [0.48, 0.49, 0.03]

VOLUNTARY_REASONS   = ["Career Move", "Personal Reasons", "Compensation"]
INVOLUNTARY_REASONS = ["Performance", "Reorganization"]

DEPT_VARIABLE_PAY = {
    "Engineering": (0, 0.15),
    "Sales":       (0.05, 0.30),
    "Product":     (0, 0.15),
    "HR":          (0, 0.12),
    "Finance":     (0, 0.15),
    "Marketing":   (0, 0.18),
    "Legal":       (0, 0.10),
}

EXEC_LEVELS = {"M3", "Director", "VP"}

NON_EXEMPT_COMBOS = {
    ("Sales",   "IC1"), ("Sales",   "IC2"), ("HR",      "IC1"),
    ("Finance", "IC1"), ("Marketing","IC1"), ("Legal",   "IC1"),
}

# ── 2. Helper functions ──────────────────────────────────────────────────────
def random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def assign_flsa(department, level):
    if level in EXEC_LEVELS or level.startswith("M"):
        return "Exempt"
    if (department, level) in NON_EXEMPT_COMBOS:
        return "Non-Exempt"
    return "Exempt"

def assign_variable_pay(department, level):
    lo, hi = DEPT_VARIABLE_PAY[department]
    if level in EXEC_LEVELS:
        lo = max(lo, 0.15)
    return round(random.uniform(lo, hi), 4)

def generate_email(first, last, used_emails):
    base = f"{first.lower()}.{last.lower()}".replace(" ", "").replace("'", "")
    base = "".join(c for c in base if c.isascii() and (c.isalnum() or c == "."))
    email = f"{base}@techcorp.com"
    suffix = 1
    while email in used_emails:
        email = f"{base}{suffix}@techcorp.com"
        suffix += 1
    used_emails.add(email)
    return email

# ── 3. Organisational hierarchy builder ─────────────────────────────────────
def build_org_hierarchy(employee_ids, levels):
    by_level = {}
    for eid, lvl in zip(employee_ids, levels):
        by_level.setdefault(lvl, []).append(eid)

    manager_map = {}

    def pick_manager(pool_levels):
        candidates = []
        for lvl in pool_levels:
            candidates.extend(by_level.get(lvl, []))
        return random.choice(candidates) if candidates else None

    for eid, lvl in zip(employee_ids, levels):
        if lvl == "VP":
            manager_map[eid] = None
        elif lvl == "Director":
            manager_map[eid] = pick_manager(["VP"])
        elif lvl == "M3":
            manager_map[eid] = pick_manager(["Director", "VP"])
        elif lvl == "M2":
            manager_map[eid] = pick_manager(["M3", "Director"])
        elif lvl == "M1":
            manager_map[eid] = pick_manager(["M2", "M3"])
        else:
            manager_map[eid] = pick_manager(["M1", "M2"])

    return manager_map

# ── 4. Main dataset generator ────────────────────────────────────────────────
def generate_dataset(n=NUM_EMPLOYEES):
    print(f"[INFO] Generating {n:,} employee records …")
    employee_ids = [f"EMP-{str(i).zfill(4)}" for i in range(1, n + 1)]
    
    level_keys   = list(LEVEL_WEIGHTS.keys())
    level_wts    = list(LEVEL_WEIGHTS.values())
    levels       = random.choices(level_keys, weights=level_wts, k=n)

    dept_keys    = list(DEPARTMENTS.keys())
    dept_wts     = list(DEPARTMENTS.values())
    departments  = random.choices(dept_keys, weights=dept_wts, k=n)

    job_families = [random.choice(DEPT_JOB_FAMILIES[dept]) for dept in departments]

    genders = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=n)
    eeo     = random.choices(EEO_CATEGORIES, weights=EEO_WEIGHTS, k=n)

    first_names, last_names = [], []
    for g in genders:
        if g == "Male":
            first_names.append(fake.first_name_male())
        elif g == "Female":
            first_names.append(fake.first_name_female())
        else:
            first_names.append(fake.first_name_male() if random.random() < 0.5 else fake.first_name_female())
        last_names.append(fake.last_name())

    used_emails = set()
    emails = [generate_email(f, l, used_emails) for f, l in zip(first_names, last_names)]
    hire_dates = [random_date(HIRE_DATE_START, HIRE_DATE_END) for _ in range(n)]

    terminated_mask = [random.random() < TERMINATION_RATE for _ in range(n)]
    termination_dates, termination_types, termination_reasons = [], [], []

    for i in range(n):
        if not terminated_mask[i]:
            termination_dates.append(None)
            termination_types.append(None)
            termination_reasons.append(None)
        else:
            max_term_date = date.today()
            earliest_term = hire_dates[i] + timedelta(days=30)
            if earliest_term >= max_term_date:
                terminated_mask[i] = False
                termination_dates.append(None)
                termination_types.append(None)
                termination_reasons.append(None)
                continue
            term_date = random_date(earliest_term, max_term_date)
            termination_dates.append(term_date)

            t_type = random.choices(["Voluntary", "Involuntary"], weights=[0.65, 0.35])[0]
            termination_types.append(t_type)
            if t_type == "Voluntary":
                termination_reasons.append(random.choice(VOLUNTARY_REASONS))
            else:
                termination_reasons.append(random.choice(INVOLUNTARY_REASONS))

    base_salaries, variable_pays = [], []
    for lvl, dept in zip(levels, departments):
        lo, hi = LEVEL_SALARY_BANDS[lvl]
        salary = round(random.uniform(lo, hi) / 1_000) * 1_000
        base_salaries.append(salary)
        variable_pays.append(assign_variable_pay(dept, lvl))

    flsa_statuses = [assign_flsa(dept, lvl) for dept, lvl in zip(departments, levels)]
    work_states = random.choices(WORK_STATES, weights=STATE_WEIGHTS, k=n)

    print("[INFO] Building organisational hierarchy …")
    manager_map = build_org_hierarchy(employee_ids, levels)
    manager_ids = [manager_map[eid] for eid in employee_ids]

    df = pd.DataFrame({
        "employee_id":          employee_ids,
        "first_name":           first_names,
        "last_name":            last_names,
        "corporate_email":      emails,
        "gender":               genders,
        "manager_id":           manager_ids,
        "hire_date":            hire_dates,
        "termination_date":     termination_dates,
        "termination_type":     termination_types,
        "termination_reason":   termination_reasons,
        "department":           departments,
        "job_family":           job_families,
        "job_level":            levels,
        "flsa_status":          flsa_statuses,
        "base_salary_usd":      base_salaries,
        "variable_pay_pct":     variable_pays,
        "work_state":           work_states,
        "eeo_ethnicity_category": eeo,
    })

    return df

# ── 5. Entry point ───────────────────────────────────────────────────────────
def main():
    df = generate_dataset(NUM_EMPLOYEES)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[SUCCESS] File written → {OUTPUT_FILE}")
    print(f"[SUCCESS] Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")

if __name__ == "__main__":
    main()