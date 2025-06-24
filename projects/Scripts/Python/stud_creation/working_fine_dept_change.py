# --- IMPORTS AND CONFIGURATION ---
import pandas as pd
import pymysql
import csv
import numpy as np
from datetime import datetime
import os
from openpyxl import Workbook
from tqdm import tqdm
import time
import re

start_time = time.time()

# === 1. Configuration ===
excel_file_path = 'studentdata.xlsx'
sheet_name = 'Sheet1'
table_name = 'students_courses'
skipped_output_file = 'skipped_students.csv'

# === 2. Prompt for session_id_fk ===
print("\n=== SESSION CONFIGURATION ===")
session_id_fk = input("Enter the session_id_fk to associate with these records: ").strip()
print(f"Academic session ID set to: {session_id_fk}\n")

# === 3. Load Excel Data ===
print("=== DATA LOADING PHASE ===")
print("Step 1/4: Loading and preparing student course data from Excel...")
df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
df = df.replace({np.nan: None})
df.columns = [col.strip().replace(" ", "_").lower() for col in df.columns]
df = df.where(pd.notnull(df), None)

# === 4. Connect to MySQL ===
print("Step 2/4: Establishing database connection...")
connection = pymysql.connect(
    host='127.0.0.1',
    user='uirms',
    password='Uirmsui123@#',
    database='uirms',
    autocommit=False,
    cursorclass=pymysql.cursors.Cursor
)
cursor = connection.cursor()

# === 5. Fetch faculty and department mappings ===
print("Step 3/4: Loading reference data from database...")
cursor.execute("SELECT id, faculty FROM tbl_faculty")
faculty_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}

cursor.execute("SELECT id, title FROM tbl_departments")
department_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}
cursor.execute("SELECT id, title FROM tbl_departments")
dept_id_to_name = {row[0]: row[1].strip() for row in cursor.fetchall()}

cursor.execute("SELECT _id, code FROM tbl_courses_test")
course_code_map = {
    row[1].replace(" ", "").lower(): row[0] for row in cursor.fetchall() if row[1]
}

# === NEW: Insert missing courses into tbl_courses_test ===
new_courses_inserted = []
for _, row in df.iterrows():
    course_code_raw = str(row.get("course_code")).strip()
    normalized_code = course_code_raw.replace(" ", "").lower()
    if normalized_code not in course_code_map:
        course_title = str(row.get("course_title") or '').strip()
        course_unit = int(row.get("course_unit") or 0)
        course_dept_name = str(row.get("course_department") or '').strip().lower()
        dept_id = department_map.get(course_dept_name)
        if not dept_id:
            continue
        match = re.match(r"[a-zA-Z]+(\d)", course_code_raw)
        level_id_fk = int(match.group(1)) if match else 1
        insert_course_sql = """
            INSERT INTO tbl_courses_test (title, code, unit, dept_id_fk, lev_id_fk)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_course_sql, (
            course_title, course_code_raw, course_unit, dept_id, level_id_fk
        ))
        connection.commit()
        new_course_id = cursor.lastrowid
        course_code_map[normalized_code] = new_course_id
        new_courses_inserted.append({
            'course_id': new_course_id,
            'course_code': course_code_raw,
            'title': course_title,
            'department': course_dept_name,
            'level': level_id_fk,
            'unit': course_unit,
            'dept_id': dept_id
        })
if new_courses_inserted:
    new_courses_csv = 'new_courses.csv'
    with open(new_courses_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_courses_inserted[0].keys())
        writer.writeheader()
        writer.writerows(new_courses_inserted)

# === 6. Create students_courses Table ===
print("Step 4/4: Creating students_courses Table...\n")
cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        _id INT AUTO_INCREMENT PRIMARY KEY,
        matric_no VARCHAR(20) NOT NULL,
        surname VARCHAR(100),
        firstname VARCHAR(100),
        middlename VARCHAR(100),
        utme_no VARCHAR(100) DEFAULT '202330573455HF',
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
        result_session_id INT,
        remark VARCHAR(20)
    )
""")
connection.commit()

# === 7. Setup for data tracking and mapping ===
unmatched_faculties = set()
unmatched_departments = set()
skipped_student_master_rows = 0
skipped_student_records = []
skipped_courses_log = []
dept_changes_count = 0
dept_changes_log = []

status_map = {
    'compulsory': 'C',
    'required': 'R',
    'external': 'E',
    'elective': 'E',
    '': 'C',
    None: 'C'
}
level_map = {
    '100': 1, '200': 2, '300': 3, '400': 4, '500': 5, '600': 6,
    '200_de': 2, '300_de': 3
}

# === 8. Insert Query for students_courses ===
insert_course_query = f"""
    INSERT INTO {table_name} (
        matric_no, surname, firstname, middlename, utme_no, level_id, mode_id,
        gender, student_department, student_faculty, course_title, course_code, course_id,
        semester_id, course_department, course_unit, course_status,
        faculty_id, departments_id, programme_id, result_session_id, remark
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# === 9. Insert Course Records into tbl_students_master_test and department sync ===
print("=== DATABASE TABLES UPDATES PHASE ===")
print("✓ Students_courses table successfully updated\n")
print("1/4: Inserting records into tbl_students_master_test table...")
inserted_course_rows = 0
skipped_rows = 0
new_student_master_rows = 0
unique_matric_set = set()
skipped_missing_courses = []

for _, row in tqdm(df.iterrows(), total=len(df), desc="  Progress level:"):
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
    course_status = status_map.get(status_raw, 'C')

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

    if not course_id:
        skipped_missing_courses.append({
            "matricNo": matric_no,
            "course_code": course_code_raw,
            "reason": "Course code not found in tbl_courses_test"
        })

    if skipped_missing_courses:
        with open('skipped_courses.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=skipped_missing_courses[0].keys())
            writer.writeheader()
            writer.writerows(skipped_missing_courses)

    programme_id = None
    result_session_id = int(session_id_fk)

    required_fields = [
        matric_no, firstname, surname, row.get("course_code"),
        row.get("course_title"), row.get("student_department")
    ]
    remark = "complete" if all(required_fields) else "incomplete"

    data_tuple = (
        matric_no, surname, firstname, middlename, '202330573455HF', level_id, mode_id, gender,
        row.get("student_department"), faculty_raw, row.get("course_title"),
        course_code_raw, course_id, semester_id, row.get("course_department"),
        row.get("course_unit"), course_status, faculty_id, departments_id,
        programme_id, result_session_id, remark
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

    # === DEPARTMENT SYNC/UPDATE LOGIC ===
    cursor.execute("SELECT _id, department_id_fk, session_admitted_id_fk FROM tbl_students_master_test WHERE matricNo = %s", (matric_no,))
    master_row = cursor.fetchone()
    if not master_row:
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
        new_student_master_rows += 1
    else:
        student_master_id, db_dept_id, db_session_id = master_row
        if db_dept_id != departments_id and departments_id is not None:
            prev_dept_name = dept_id_to_name.get(db_dept_id, "")
            new_dept_name = dept_id_to_name.get(departments_id, "")
            dept_changes_log.append({
                "matricNo": matric_no,
                "previous_dept_name": prev_dept_name,
                "previous_dept_id": db_dept_id,
                "new_dept_name": new_dept_name,
                "new_dept_id": departments_id
            })
            cursor.execute("""
                UPDATE tbl_students_master_test
                SET 
                    previous_dept = %s,
                    prev_session_admitted_id_fk_ch = %s,
                    department_id_fk = %s
                WHERE matricNo = %s
            """, (db_dept_id, db_session_id, departments_id, matric_no))

            cursor.execute("""
                UPDATE tbl_course_registered_test
                SET student_dept_id_fk = %s
                WHERE student_id_fk = %s AND session_id_fk = %s
            """, (departments_id, student_master_id, result_session_id))

            cursor.execute("""
                UPDATE course_dept_reg_map_test
                SET student_dept_id_fk = %s
                WHERE student_dept_id_fk = %s AND session_id_fk = %s
            """, (departments_id, db_dept_id, result_session_id))

            dept_changes_count += 1

connection.commit()

if skipped_student_records:
    keys = skipped_student_records[0].keys()
    with open(skipped_output_file, 'w', newline='') as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(skipped_student_records)
    print(f"  ! Warning: {len(skipped_student_records)} students skipped due to missing faculty/department mappings")
    print(f"    → Details saved to: skipped_students sheet\n")

print(f"✓ Department changed for {dept_changes_count} students\n")

# === Export department changes log to CSV for later import into Excel ===
if dept_changes_log:
    with open('dept_changes.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=dept_changes_log[0].keys())
        writer.writeheader()
        writer.writerows(dept_changes_log)

# === 10. Insert into tbl_students_transactions_test ===
print("2/4: Inserting records into tbl_students_transactions_test table...")
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

for matric_no, level_id in tqdm(student_courses, desc="Progess level:"):
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

print(f"  ✓ Created {transaction_rows_inserted} registration transactions")
print(f"    → Details saved to: skipped_transactions sheet\n")

# === 11. Insert into student_users_test ===
print("3/4: Creating student_user accounts...")

cursor.execute("SELECT username FROM student_users_test")
existing_usernames = set(row[0] for row in cursor.fetchall())

cursor.execute("""
    SELECT matric_no, utme_no
    FROM students_courses
""")
students_master_data = cursor.fetchall()

user_insert_query = """
    INSERT INTO student_users_test (
        username, userpassword, userType, sq_id_fk, sq_answer,
        is_new, authcode, isAuthenticated, auth_key, auth_time
    ) VALUES (%s, %s, %s, %s, %s, '', '', 0, '', '') 
"""

user_rows_inserted = 0
skipped_user_rows = []
seen_usernames = set()

for matric_no, utme_no in tqdm(students_master_data, desc="  Progress level:"):
    if matric_no in existing_usernames or matric_no in seen_usernames:
        continue

    if not utme_no or str(utme_no).strip() == '':
        password = matric_no
        skipped_user_rows.append({'matric_no': matric_no, 'reason': 'Missing UTME number; used matric_no as password'})
    else:
        password = str(utme_no).upper()

    cursor.execute(user_insert_query, (
        matric_no, password, 1, 0, ''
    ))
    user_rows_inserted += 1
    seen_usernames.add(matric_no)

print(f"  ✓ Created {user_rows_inserted} new user accounts")
print(f"  ! {len(skipped_user_rows)} accounts had issues (logged in skipped_student_users sheet for review)\n")

if skipped_user_rows:
    with open('skipped_student_users.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=skipped_user_rows[0].keys())
        writer.writeheader()
        writer.writerows(skipped_user_rows)

connection.commit()

# === 12. Export Skipped Transactions ===
filtered_skipped_transactions = [
    row for row in skipped_transaction_records
    if not (isinstance(row.get('reason'), str) and "Duplicate entry" in row['reason'])
]

if filtered_skipped_transactions:
    with open('skipped_transactions.csv', 'w', newline='') as f:
        all_keys = set()
        for record in filtered_skipped_transactions:
            all_keys.update(record.keys())
        writer = csv.DictWriter(f, fieldnames=list(all_keys))
        writer.writeheader()
        writer.writerows(filtered_skipped_transactions)

# === 13. Insert into tbl_course_registered_test ===
print("4/4: Populating tbl_course_registered table...")

# Get initial count before inserting
cursor.execute("SELECT COUNT(*) FROM tbl_course_registered_test")
initial_count = cursor.fetchone()[0]

cursor.execute("SELECT CONCAT(student_id_fk, ':', course_id_fk, ':', session_id_fk) FROM tbl_course_registered_test")
existing_keys = set(row[0] for row in cursor.fetchall())

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

cursor.execute("SELECT id, title, faculty_id_fk FROM tbl_departments")
dept_data = cursor.fetchall()
dept_map = {row[1].strip().lower(): (row[0], row[2]) for row in dept_data}

cursor.execute("SELECT _id, matricNo, department_id_fk FROM tbl_students_master_test")
student_data = cursor.fetchall()
student_map = {row[1]: (row[0], row[2]) for row in student_data}

cursor.execute("SELECT code, unit FROM tbl_courses_test")
unit_data = dict((code.strip().replace(" ", "").lower(), unit) for code, unit in cursor.fetchall())

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

for record in tqdm(course_records, desc="  Progress level:"):
    matric_no, course_id, course_code, course_unit, level_id, semester_id, course_status, session_id, course_dept = record

    if not all([matric_no, course_id, course_code, level_id, semester_id, session_id]):
        skipped_rows.append({'matric_no': matric_no, 'reason': 'Missing essential data'})
        continue

    student_info = student_map.get(matric_no)
    if not student_info:
        skipped_rows.append({'matric_no': matric_no, 'reason': 'Student not found in master table'})
        continue
    student_id_fk, student_dept_id_fk = student_info

    normalized_code = course_code.strip().replace(" ", "").lower()
    unit_from_courses = unit_data.get(normalized_code, 0)

    try:
        course_units = abs(int(course_unit))
        if course_units == 0:
            course_units = unit_from_courses
    except:
        course_units = unit_from_courses

    course_status = course_status if course_status else ' '

    dept_info = dept_map.get(course_dept.strip().lower()) if course_dept else None

    if dept_info:
        course_dept_id_fk, course_faculty_id_fk = dept_info
    else:
        normalized_code_db = course_code.strip().replace(" ", "").lower()
        cursor.execute("SELECT dept_id_fk FROM tbl_courses_test WHERE REPLACE(LOWER(code), ' ', '') = %s", (normalized_code_db,))
        dept_result = cursor.fetchone()

        if dept_result:
            course_dept_id_fk = dept_result[0]
            cursor.execute("SELECT faculty_id_fk FROM tbl_departments WHERE id = %s", (course_dept_id_fk,))
            fac_result = cursor.fetchone()
            course_faculty_id_fk = fac_result[0] if fac_result else None
        else:
            skipped_rows.append({
                'matric_no': matric_no,
                'reason': f'Course code "{course_code}" not found in tbl_courses_test'
            })
            continue

    key = f"{student_id_fk}:{course_id}:{session_id}"
    if key in existing_keys:
        continue

    date_registered = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    course_status = 'C' if not course_status or not course_status.strip() else course_status

    data_tuple = (
        student_id_fk, student_dept_id_fk, course_id, course_dept_id_fk,
        course_faculty_id_fk, course_code, course_units, level_id,
        semester_id, course_status, date_registered, session_id, session_id,
        '', '', '', '', '', '', '', '', 0, 0, 0, 0, semester_id, '',
        0, 0, key, 0, 0
    )

    try:
        cursor.execute(insert_query, data_tuple)
        inserted_rows += 1
    except pymysql.err.IntegrityError as e:
        if "Duplicate entry" in str(e):
            continue
        skipped_rows.append({'matric_no': matric_no, 'reason': f'IntegrityError: {str(e)}'})

cursor.execute("SELECT COUNT(*) FROM tbl_course_registered_test")
final_count = cursor.fetchone()[0]
newly_inserted = final_count - initial_count
print(f"  ✓ Registered {newly_inserted} new course records (total in table: {final_count})")

print(f"  Courses not found in the database are logged into the skipped_courses sheet")
print(f"  ! {len(skipped_rows)} course registrations skipped (see skipped_registrations sheet for details)\n")

if skipped_rows:
    with open('skipped_course_registered.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=skipped_rows[0].keys())
        writer.writeheader()
        writer.writerows(skipped_rows)

connection.commit()

# === 14. Update course_dept_reg_map_test table ===
print("5/5: Updating course_dept_reg_map_test table...")

cursor.execute("""
    SELECT 
        course_id_fk,
        course_dept_id_fk,
        student_dept_id_fk,
        session_id_fk,
        semester_id_fk,
        COUNT(DISTINCT student_id_fk) as no_of_students,
        COUNT(DISTINCT CASE WHEN result IS NOT NULL OR result != 'NA' THEN student_id_fk END) as no_of_results
    FROM tbl_course_registered_test
    GROUP BY course_id_fk, course_dept_id_fk, student_dept_id_fk, session_id_fk, semester_id_fk
""")
course_dept_data = cursor.fetchall()

cursor.execute("SELECT `key` FROM course_dept_reg_map_test")
existing_keys = set(row[0] for row in cursor.fetchall())

insert_query = """
    INSERT INTO course_dept_reg_map_test (
        course_id_fk,
        course_dept_id_fk,
        student_dept_id_fk,
        session_id_fk,
        semester,
        no_of_students,
        no_of_results,
        `key`,
        last_mod_by,
        last_mod_ts,
        is_new,
        is_AFM,
        old_course_dept_id_fk
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

current_time = datetime.now().strftime('%d-%m-%y %H:%M')
inserted_rows = 0
skipped_rows = 0

for row in tqdm(course_dept_data, desc="  Progress level:"):
    course_id_fk, course_dept_id_fk, student_dept_id_fk, session_id_fk, semester, no_of_students, no_of_results = row
    key = f"{course_id_fk}:{course_dept_id_fk}:{student_dept_id_fk}:{session_id_fk}"
    
    if key in existing_keys:
        skipped_rows += 1
        continue
    
    try:
        cursor.execute(insert_query, (
            course_id_fk,
            course_dept_id_fk,
            student_dept_id_fk,
            session_id_fk,
            semester,
            no_of_students,
            no_of_results,
            key,
            '654321',
            current_time,
            0,
            0,
            0
        ))
        inserted_rows += 1
    except pymysql.err.IntegrityError as e:
        if "Duplicate entry" in str(e):
            skipped_rows += 1
            continue
        raise e

connection.commit()
cursor.close()
connection.close()

print(f"  ✓ Inserted {inserted_rows} new records into course_dept_reg_map_test")
print(f"  ! Skipped {skipped_rows} duplicate records\n")

# === 15. Compile all logs into Excel ===
log_files = [
    ('new_courses', 'new_courses.csv'),
    ('skipped_students', 'skipped_students.csv'),
    ('skipped_transactions', 'skipped_transactions.csv'),
    ('skipped_student_users', 'skipped_student_users.csv'),
    ('skipped_courses', 'skipped_courses.csv'),
    ('skipped_registrations', 'skipped_course_registered.csv'),
    ('dept_changes', 'dept_changes.csv')
]

output_excel = 'import_logs.xlsx'

if os.path.exists(output_excel):
    os.remove(output_excel)

existing_csvs = [f for f in log_files if os.path.exists(f[1])]

if existing_csvs:
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        for sheet_name, csv_file in existing_csvs:
            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                os.remove(csv_file)
            except Exception as e:
                print(f"  ! Warning: Could not process {csv_file}: {str(e)}")
                continue
        
    print(f"  ✓ Logs compiled into: {output_excel}")
else:
    wb = Workbook()
    ws = wb.active
    ws.title = "No skipped records"
    ws['A1'] = "No records were skipped during processing"
    wb.save(output_excel)
    print(f"  ✓ Created empty log file: {output_excel} (no records were skipped)")

end_time = time.time()
total_time = end_time - start_time
minutes, seconds = divmod(total_time, 60)
print(f"\nTOTAL PROCESSING TIME: {int(minutes)} minutes {seconds:.2f} seconds")
print("\nOPERATION COMPLETED SUCCESSFULLY")