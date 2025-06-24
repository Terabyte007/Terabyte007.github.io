import pandas as pd
import pymysql
import csv
import numpy as np
from tqdm import tqdm
import time

start_time = time.time()

# === 1. SETUP: FILE PATHS, TABLE NAMES, ETC. ===
excel_file_path = 'freshers_data.xlsx'
sheet_name = 'Sheet1'
skipped_output_file = 'skipped_students.csv'
changes_log_file = 'full_update_changes.xlsx'

# === 2. PROMPT FOR SESSION ID ===
print("\n=== PROMPT FOR SESSION ID ===")
session_id_fk = input("Enter the session_id_fk to associate with these records: ").strip()
print(f"Academic session ID set to: {session_id_fk}\n")

# === 3. LOAD EXCEL DATA ===
print("=== LOADING EXCEL DATA ===")
df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
df = df.replace({np.nan: None})
# Normalize column names: lowercase, underscores for spaces/hyphens
df.columns = [col.strip().replace(" ", "_").replace("-", "_").lower() for col in df.columns]
df = df.where(pd.notnull(df), None)

# === 4. CONNECT TO MYSQL DATABASE ===
print("=== CONNECTING TO DATABASE ===")
connection = pymysql.connect(
    host='127.0.0.1',
    user='uirms',
    password='Uirmsui123@#',
    database='uirms',
    autocommit=False,
    cursorclass=pymysql.cursors.Cursor
)
cursor = connection.cursor()

# === 5. LOAD FACULTY AND DEPARTMENT MAPPINGS ===
print("=== LOADING FACULTY AND DEPARTMENT MAPPINGS ===")
cursor.execute("SELECT id, faculty FROM tbl_faculty")
faculty_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}
cursor.execute("SELECT id, title FROM tbl_departments")
department_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}
cursor.execute("SELECT id, title FROM tbl_departments")
dept_id_to_name = {row[0]: row[1].strip() for row in cursor.fetchall()}

# === 6. GET ALL TABLE COLUMNS FOR DYNAMIC UPDATES ===
cursor.execute("SHOW COLUMNS FROM tbl_students_master_test")
table_columns = [row[0] for row in cursor.fetchall()]
if '_id' in table_columns:
    table_columns.remove('_id')  # Exclude the PK

# === 7. MAP EXCEL & DB COLUMNS, PREPARE LOGS ===
excel_col_map = {col.lower(): col for col in df.columns}
db_matric_col = next((col for col in table_columns if col.lower() == 'matricno'), None)
excel_matric_col = next((col for col in df.columns if col.lower() == 'matric_number'), None)
if not db_matric_col or not excel_matric_col:
    raise Exception("Matric number column is missing in either DB or Excel.")

skipped_student_records = []
changes_log = []

# === 8. MAIN LOOP: PROCESS EACH STUDENT ===
for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing students"):
    matric_no = row.get(excel_matric_col)
    if not matric_no:
        continue

    # --- 8.1 EXTRACT AND SPLIT NAMES ROBUSTLY ---
    full_name = row.get("full_name")
    surname, firstname, middlename = '', '', ''
    if full_name and isinstance(full_name, str):
        # Split assuming Surname Firstname Middlename [others...]
        name_parts = full_name.strip().split()
        surname    = name_parts[0].capitalize() if len(name_parts) >= 1 else ''
        firstname  = name_parts[1].capitalize() if len(name_parts) >= 2 else ''
        middlename = " ".join([part.capitalize() for part in name_parts[2:]]) if len(name_parts) >= 3 else ''
    # For DB update/insert, override these fields with the split values
    name_override = {
        "surname": surname,
        "firstname": firstname,
        "middlename": middlename
    }

    # --- 8.2 BUILD UPDATE/INSERT DATA DICT ---
    update_data = {}
    for db_col in table_columns:
        val = None
        db_col_lower = db_col.lower()
        # Special mappings
        if db_col_lower == "matricno":
            val = matric_no
        elif db_col_lower == "faculty_id_fk" and "faculty" in df.columns:
            faculty_raw = str(row.get("faculty")).strip().lower() if row.get("faculty") else ''
            val = faculty_map.get(faculty_raw)
        elif db_col_lower == "department_id_fk" and "department" in df.columns:
            department_raw = str(row.get("department")).strip().lower() if row.get("department") else ''
            val = department_map.get(department_raw)
        elif db_col_lower == "session_admitted_id_fk":
            val = int(session_id_fk)
        elif db_col_lower in name_override:
            val = name_override[db_col_lower]
        elif db_col_lower == "gender_id" and "gender" in df.columns:
            gender_raw = str(row.get("gender")).strip().lower() if row.get("gender") else ''
            if gender_raw == 'male':
                val = 'Male'
            elif gender_raw == 'female':
                val = 'Female'
            else:
                val = 'NA'
        elif db_col_lower == "dob" and "date_of_birth" in df.columns:
            raw_dob = row.get("date_of_birth")
            if raw_dob:
                # If it's a pandas Timestamp or datetime, convert to date string
                if hasattr(raw_dob, 'date'):
                    val = str(raw_dob.date())
                else:
                    # If it's a string, split off the time part if present
                    val = str(raw_dob).split()[0]
            else:
                val = '0000-00-00'
        elif db_col_lower == "nationality":
            val = "Nigerian"
        elif db_col_lower == "mode_id" and "mode_of_entry" in df.columns:
            val = 2 if (str(row.get("mode_of_entry") or '').lower().find('de') != -1) else 1
        elif db_col_lower in excel_col_map:
            val = row.get(excel_col_map[db_col_lower])
        else:
            val = None
        update_data[db_col] = val

    # --- 8.3 CHECK FOR MISSING FACULTY/DEPARTMENT ---
    if ("faculty_id_fk" in update_data and update_data["faculty_id_fk"] is None) or \
       ("department_id_fk" in update_data and update_data["department_id_fk"] is None):
        skipped_student_records.append({
            "matricNo": matric_no,
            "faculty": row.get("faculty"),
            "department": row.get("department")
        })
        continue

    # --- 8.4 CHECK IF STUDENT EXISTS ---
    cursor.execute(f"SELECT {', '.join(table_columns)} FROM tbl_students_master_test WHERE {db_matric_col} = %s", (matric_no,))
    current = cursor.fetchone()
    if current:
        # --- 8.5 UPDATE EXISTING STUDENT: COMPARE & LOG CHANGES ---
        old_row = dict(zip(table_columns, current))
        changes = {}
        for col in table_columns:
            excel_val = update_data.get(col)
            db_val = old_row.get(col) if isinstance(old_row, dict) else old_row[table_columns.index(col)]
            # Handle None vs '' as equal for updates
            if (excel_val is not None and str(excel_val).strip() != str(db_val).strip()):
                changes[col] = {'old': db_val, 'new': excel_val}
        if changes:
            set_clause = ', '.join([f"{col}=%s" for col in update_data.keys() if update_data[col] is not None])
            values = [update_data[col] for col in update_data.keys() if update_data[col] is not None]
            values.append(matric_no)
            cursor.execute(f"UPDATE tbl_students_master_test SET {set_clause} WHERE {db_matric_col} = %s", values)
            changes_log.append({'matricNo': matric_no, 'changes': changes})
    else:
        # --- 8.6 INSERT NEW STUDENT ---
        columns = ', '.join([col for col in update_data if update_data[col] is not None])
        placeholders = ', '.join(['%s']*len([col for col in update_data if update_data[col] is not None]))
        values = [update_data[col] for col in update_data if update_data[col] is not None]
        cursor.execute(
            f"INSERT INTO tbl_students_master_test ({columns}) VALUES ({placeholders})",
            values
        )

# === 9. COMMIT CHANGES & LOG OUTPUTS ===
connection.commit()

# Save field-by-field changes to Excel
if changes_log:
    flat_log = []
    for entry in changes_log:
        matric = entry['matricNo']
        for col, vals in entry['changes'].items():
            flat_log.append({'matricNo': matric, 'field': col, 'old': vals['old'], 'new': vals['new']})
    pd.DataFrame(flat_log).to_excel(changes_log_file, index=False)
    print(f"✓ Changes logged in: {changes_log_file}")

if skipped_student_records:
    keys = skipped_student_records[0].keys()
    with open(skipped_output_file, 'w', newline='') as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(skipped_student_records)
    print(f"  ! Warning: {len(skipped_student_records)} students skipped due to missing faculty/department mappings")
    print(f"    → Details saved to: {skipped_output_file}")

# === 10. SUMMARY ===
end_time = time.time()
total_time = end_time - start_time
minutes, seconds = divmod(total_time, 60)
print(f"\nTOTAL PROCESSING TIME: {int(minutes)} minutes {seconds:.2f} seconds")
print("\nOPERATION COMPLETED SUCCESSFULLY")