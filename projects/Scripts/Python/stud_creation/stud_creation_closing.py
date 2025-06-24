# Your imports and configuration remain unchanged
import pandas as pd
import pymysql
import csv
from datetime import datetime

# === 1. Configuration ===
excel_file_path = 'studentdata.xlsx'
sheet_name = 'Sheet1'
table_name = 'students_courses'
skipped_output_file = 'skipped_students.csv'

# === 2. Prompt for session_id_fk ===
session_id_fk = input("Enter session_id_fk: ").strip()

# === 3. Load Excel Data ===
df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
df.columns = [col.strip().replace(" ", "_").lower() for col in df.columns]
df = df.where(pd.notnull(df), None)

# === 4. Connect to MySQL ===
connection = pymysql.connect(
    host='127.0.0.1',
    user='uirms',
    password='Uirmsui123@#',
    database='uirms'
)
cursor = connection.cursor()

# === 5. Fetch faculty and department mappings ===
cursor.execute("SELECT id, faculty FROM tbl_faculty")
faculty_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}

cursor.execute("SELECT id, title FROM tbl_departments")
department_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}

# === 5b. Fetch course_code to course_id mapping (normalized) ===
cursor.execute("SELECT _id, code FROM tbl_courses")
course_code_map = {
    row[1].replace(" ", "").lower(): row[0] for row in cursor.fetchall() if row[1]
}

# === 6. Drop and Recreate students_courses Table ===
cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
cursor.execute(f"""
    CREATE TABLE {table_name} (
        _id INT AUTO_INCREMENT PRIMARY KEY,
        matric_no VARCHAR(20) NOT NULL,
        surname VARCHAR(100),
        firstname VARCHAR(100),
        middlename VARCHAR(100),
        level_id INT,
        mode_id INT,
        gender VARCHAR(10),
        student_department VARCHAR(100),
        student_faculty VARCHAR(100),
        course_title VARCHAR(200),
        course_code VARCHAR(20),
        course_id INT,
        semester_id INT,
        course_department VARCHAR(100),
        course_unit INT,
        course_status VARCHAR(1),
        faculty_id INT,
        departments_id INT,
        programme_id INT,
        result_session_id INT
    )
""")
connection.commit()

# === 7. Tracking sets ===
unmatched_faculties = set()
unmatched_departments = set()
skipped_student_master_rows = 0
skipped_student_records = []

# === 8. Supporting maps ===
status_map = {
    'compulsory': 'C',
    'required': 'R',
    'external': 'E',
    'elective': 'E'
}
level_map = {
    '100': 1, '200': 2, '300': 3, '400': 4, '500': 5, '600': 6,
    '200_de': 2, '300_de': 3
}

# === 9. Insert Query for students_courses ===
insert_course_query = f"""
    INSERT INTO {table_name} (
        matric_no, surname, firstname, middlename, level_id, mode_id,
        gender, student_department, student_faculty, course_title, course_code, course_id,
        semester_id, course_department, course_unit, course_status,
        faculty_id, departments_id, programme_id, result_session_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# === 10. Insert Course Records ===
inserted_course_rows = 0
skipped_rows = 0
unique_matric_set = set()

for _, row in df.iterrows():
    matric_no = row.get("student_number")
    if not matric_no:
        skipped_rows += 1
        continue

    full_name = str(row.get("full_name")).strip() if row.get("full_name") else ""
    name_parts = full_name.split()
    firstname = name_parts[0].capitalize() if len(name_parts) >= 1 else ''
    surname = name_parts[1].upper() if len(name_parts) >= 2 else ''
    middlename = name_parts[2].capitalize() if len(name_parts) >= 3 else ''

    level_raw = str(row.get("level")).lower() if row.get("level") else ''
    level_id = level_map.get(level_raw, None)
    mode_id = 2 if 'de' in level_raw else 1

    sex_raw = str(row.get("sex")).strip().lower() if row.get("sex") else ''
    gender = 'Male' if sex_raw == 'male' else 'Female' if sex_raw == 'female' else 'NA'

    semester_text = str(row.get("session_name")).strip().lower() if row.get("session_name") else ''
    semester_id = 1 if semester_text in ['', 'first'] else 2

    status_raw = str(row.get("course_status")).strip().lower() if row.get("course_status") else ''
    course_status = status_map.get(status_raw, None)

    faculty_raw = str(row.get("student_faculty"))[11:].strip() if row.get("student_faculty") else ''
    department_raw = str(row.get("student_department")).strip().lower() if row.get("student_department") else ''

    faculty_id = faculty_map.get(faculty_raw.lower())
    if faculty_id is None:
        unmatched_faculties.add(faculty_raw.lower())

    departments_id = department_map.get(department_raw)
    if departments_id is None:
        unmatched_departments.add(department_raw)

    course_code_raw = str(row.get("course_code")) if row.get("course_code") else ''
    normalized_code = course_code_raw.replace(" ", "").lower()
    course_id = course_code_map.get(normalized_code)

    programme_id = None
    result_session_id = int(session_id_fk)

    data_tuple = (
        matric_no, surname, firstname, middlename, level_id, mode_id, gender,
        row.get("student_department"), faculty_raw, row.get("course_title"),
        course_code_raw, course_id, semester_id, row.get("course_department"),
        row.get("course_unit"), course_status, faculty_id, departments_id,
        programme_id, result_session_id
    )

    cursor.execute(insert_course_query, data_tuple)
    inserted_course_rows += 1

    if faculty_id is None or departments_id is None:
        skipped_student_master_rows += 1
        skipped_student_records.append({
            "matricNo": matric_no,
            "surname": surname,
            "firstname": firstname,
            "middlename": middlename,
            "gender": gender,
            "faculty_raw": faculty_raw,
            "department_raw": department_raw
        })
        continue

    if matric_no not in unique_matric_set:
        unique_matric_set.add(matric_no)
        cursor.execute("SELECT 1 FROM tbl_students_master_test WHERE matricNo = %s", (matric_no,))
        if not cursor.fetchone():
            insert_student_query = """
                INSERT INTO tbl_students_master_test (
                    matricNo, surname, firstname, middlename, gender_id, dob, nationality,
                    session_admitted_id_fk, faculty_id_fk, department_id_fk, programme_id_fk,
                    mode_id, is_new, is_new_level, is_AFM, previous_dept, point_system, prev_session_admitted_id_fk_ch
                ) VALUES (%s, %s, %s, %s, %s, '0000-00-00', 'Nigerian', %s, %s, %s, 44, %s, '', '', '', '', '', '')
            """
            student_data = (
                matric_no, surname, firstname, middlename, gender, result_session_id,
                faculty_id, departments_id, mode_id
            )
            cursor.execute(insert_student_query, student_data)

connection.commit()
cursor.close()
connection.close()

# === Export Skipped Students ===
if skipped_student_records:
    keys = skipped_student_records[0].keys()
    with open(skipped_output_file, 'w', newline='') as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(skipped_student_records)

# === Reconnect for transaction and user table insertions ===
connection = pymysql.connect(
    host='127.0.0.1',
    user='uirms',
    password='Uirmsui123@#',
    database='uirms'
)
cursor = connection.cursor()

# === 13a. Insert into tbl_students_transactions_test ===
cursor.execute("SELECT _id, matricNo FROM tbl_students_master_test")
student_master_dict = {row[1]: row[0] for row in cursor.fetchall()}

cursor.execute("SELECT `key` FROM tbl_students_transactions_test")
existing_keys = set(row[0] for row in cursor.fetchall())

cursor.execute(f"SELECT DISTINCT matric_no, level_id FROM {table_name}")
student_courses = cursor.fetchall()

transaction_insert_query = """
    INSERT INTO tbl_students_transactions_test (
        student_id_fk, session_id_fk, semester_id_fk, lev_id_fk, has_registered,
        last_mod_by, last_mod_ts, is_new, `key`, matricno, academic_status, remark
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

transaction_rows_inserted = 0
skipped_transaction_records = []

for matric_no, level_id in student_courses:
    student_id_fk = student_master_dict.get(matric_no)
    if not student_id_fk:
        skipped_transaction_records.append({"matricNo": matric_no, "reason": "Matric number not found in tbl_students_master_test"})
        continue

    session_id = int(session_id_fk)
    key = f"{student_id_fk}:{session_id}"

    if key in existing_keys:
        skipped_transaction_records.append({"matricNo": matric_no, "student_id_fk": student_id_fk, "reason": f"Key '{key}' already exists"})
        continue

    last_mod_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute(transaction_insert_query, (
            student_id_fk, session_id, 1, level_id, 1, '', last_mod_ts, 0,
            key, matric_no, 'active', 'filled by script'
        ))
        transaction_rows_inserted += 1
    except pymysql.err.IntegrityError as e:
        skipped_transaction_records.append({
            "matricNo": matric_no,
            "student_id_fk": student_id_fk,
            "key": key,
            "reason": f"IntegrityError: {str(e)}"
        })

# === 13b. Insert into student_users_test ===
cursor.execute("SELECT username FROM student_users_test")
existing_usernames = set(row[0] for row in cursor.fetchall())

cursor.execute("SELECT matricNo, surname FROM tbl_students_master_test")
students_master_data = cursor.fetchall()

user_insert_query = """
    INSERT INTO student_users_test (
        username, userpassword, userType, sq_id_fk, sq_answer,
        is_new, authcode, isAuthenticated, auth_key, auth_time
    ) VALUES (%s, %s, %s, %s, %s, '', '', 0, '', '') 
"""

user_rows_inserted = 0

for matric_no, surname in students_master_data:
    if matric_no in existing_usernames:
        continue
    cursor.execute(user_insert_query, (
        matric_no, surname, 1, 0, ''
    ))
    user_rows_inserted += 1

connection.commit()
cursor.close()
connection.close()

# === Export Skipped Transactions ===
if skipped_transaction_records:
    with open('skipped_transactions.csv', 'w', newline='') as f:
        keys = skipped_transaction_records[0].keys()
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(skipped_transaction_records)

# === Reconnect for transaction and tbl_course_registered_test table insertions ===
connection = pymysql.connect(
    host='127.0.0.1',
    user='uirms',
    password='Uirmsui123@#',
    database='uirms'
)
cursor = connection.cursor()
# === 14. Insert into tbl_course_registered_test ===

# Fetch existing keys to avoid duplicates
cursor.execute("SELECT CONCAT(student_id_fk, ':', course_id_fk, ':', session_id_fk) FROM tbl_course_registered_test")
existing_keys = set(row[0] for row in cursor.fetchall())

# Fetch necessary data from students_courses
cursor.execute(f"""
    SELECT
        sc.matric_no,
        sc.course_id,
        sc.course_code,
        sc.course_unit,
        sc.level_id,
        sc.semester_id,
        sc.course_status,
        sc.result_session_id,
        sc.course_department
    FROM {table_name} sc
    WHERE sc.course_id IS NOT NULL
""")
course_records = cursor.fetchall()

# Prepare department and faculty mappings
cursor.execute("SELECT id, title, faculty_id_fk FROM tbl_departments")
dept_data = cursor.fetchall()
dept_map = {row[1].strip().lower(): (row[0], row[2]) for row in dept_data}

# Prepare student_id_fk and student_dept_id_fk mappings
cursor.execute("SELECT _id, matricNo, department_id_fk FROM tbl_students_master_test")
student_data = cursor.fetchall()
student_map = {row[1]: (row[0], row[2]) for row in student_data}

# Prepare insert query
insert_query = """
    INSERT INTO tbl_course_registered_test (
        student_id_fk, student_dept_id_fk, course_id_fk, course_dept_id_fk,
        course_faculty_id_fk, course_code, course_units, level_id_fk,
        semester_id_fk, status, date_registered, session_id_fk, session,
        ca, exam, result, old_result, new_result, ca_remark, exam_remark,
        result_remark, grade_id_fk, gp7, gp5, gp4, semester, last_update_batch,
        is_approved, is_unreg, `key`, is_new, blank_first_semester
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

inserted_rows = 0
skipped_rows = []

for record in course_records:
    matric_no, course_id, course_code, course_unit, level_id, semester_id, course_status, session_id, course_dept = record

    # Skip if any essential information is missing
    if not all([matric_no, course_id, course_code, course_unit, level_id, semester_id, course_status, session_id, course_dept]):
        skipped_rows.append({'matric_no': matric_no, 'reason': 'Missing essential data'})
        continue

    student_info = student_map.get(matric_no)
    if not student_info:
        skipped_rows.append({'matric_no': matric_no, 'reason': 'Student not found in master table'})
        continue
    student_id_fk, student_dept_id_fk = student_info

    dept_info = dept_map.get(course_dept.strip().lower())
    if not dept_info:
        skipped_rows.append({'matric_no': matric_no, 'reason': f'Course department "{course_dept}" not found'})
        continue
    course_dept_id_fk, course_faculty_id_fk = dept_info

    key = f"{student_id_fk}:{course_id}:{session_id}"
    if key in existing_keys:
        continue  # Skip existing records

    date_registered = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    data_tuple = (
        student_id_fk, student_dept_id_fk, course_id, course_dept_id_fk,
        course_faculty_id_fk, course_code, course_unit, level_id,
        semester_id, course_status, date_registered, session_id, session_id,
        '', '', '', '', '', '', '', '', 0, 0, 0, 0, semester_id, '',
        0, 0, key, 0, 0
    )

    try:
        cursor.execute(insert_query, data_tuple)
        inserted_rows += 1
    except pymysql.err.IntegrityError as e:
        skipped_rows.append({'matric_no': matric_no, 'reason': f'IntegrityError: {str(e)}'})

connection.commit()
cursor.close()
connection.close()

# Export skipped rows
if skipped_rows:
    with open('skipped_course_registered.csv', 'w', newline='') as f:
        keys = skipped_rows[0].keys()
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(skipped_rows)

# === 14. Summary ===
print("\n=== Import Summary ===")
print(f"Total records in Excel: {len(df)}")
print(f"Course rows inserted into `{table_name}`: {inserted_course_rows}")
print(f"Rows skipped due to missing student number: {skipped_rows}")
print(f"Unique students processed: {len(unique_matric_set)}")
print(f"New student records added to `tbl_students_master_test`: {len(unique_matric_set) - skipped_student_master_rows}")
print(f"Student records skipped due to unmatched faculty/department: {skipped_student_master_rows}")
print(f"Skipped student details exported to: {skipped_output_file}")
print(f"\nInserted {transaction_rows_inserted} rows into tbl_students_transactions_test.")
print(f"Skipped {len(skipped_transaction_records)} transaction records. See 'skipped_transactions.csv' for details.")
print(f"Inserted {user_rows_inserted} new users into student_users_test.")
print(f"\nInserted {inserted_rows} rows into tbl_course_registered_test.")
print(f"Skipped {len(skipped_rows)} rows. See 'skipped_course_registered.csv' for details.")

if unmatched_faculties:
    print("\n⚠️ Unmatched Faculties:")
    for fac in unmatched_faculties:
        print(f" - {fac}")

if unmatched_departments:
    print("\n⚠️ Unmatched Departments:")
    for dept in unmatched_departments:
        print(f" - {dept}")