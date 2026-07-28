import duckdb
import os
# 1. Define paths
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_file_path = os.path.join(current_dir, 'us_workday_employee_raw.csv')
db_file_path = os.path.join(current_dir, 'people_analytics.duckdb')

print("Starting DuckDB connection...")

# 2. Connect to DuckDB (creates the file if it doesn't exist)
con = duckdb.connect(database=db_file_path, read_only=False)

try:
    # 3. Load data from CSV into a table
    con.execute("DROP TABLE IF EXISTS raw_workday_employees")
    print(f"Loading data from {csv_file_path}...")
    
    con.execute(f"CREATE TABLE raw_workday_employees AS SELECT * FROM read_csv_auto('{csv_file_path}')")
    
    # 4. Verify the load
    result = con.execute("SELECT COUNT(*) FROM raw_workday_employees").fetchone()
    print(f"[SUCCESS] Loaded {result[0]} employee records into DuckDB.")
    
    # Preview the first 3 rows
    print("\n--- Table Preview (Top 3 Rows) ---")
    preview = con.execute("SELECT employee_id, first_name, last_name, department FROM raw_workday_employees LIMIT 3").fetchdf()
    print(preview.to_markdown())

except Exception as e:
    print(f"[ERROR] An error occurred: {e}")

finally:
    # 5. Close the connection
    con.close()
    print("\nDuckDB connection closed.")