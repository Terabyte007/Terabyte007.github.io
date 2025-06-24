# Script Documentation: `stud_creation.py`

## Overview

This script processes student/course registration data from an Excel file, populates several tables in a MySQL database, and maintains logs for all major actions and exceptions. The tables involved include:

- `students_courses`
- `tbl_students_master_test`
- `tbl_courses_test`
- `tbl_students_transactions_test`
- `student_users_test`
- `tbl_course_registered_test`
- `course_dept_reg_map_test`

All steps are logged, and errors or skipped records are written to CSV and Excel for auditing.

---

## Detailed Steps

### 1. **Configuration and Setup**

- Prompts for a session ID (`session_id_fk`) to be used in all registration records.
- Loads an Excel sheet (`studentdata.xlsx`) and processes column headers to uniform naming.

### 2. **Database Connection**

- Connects to a MySQL database using the provided credentials.

### 3. **Load Reference Data**

- Loads mapping dictionaries for faculty, department, and course codes from the respective tables.
- If the Excel file contains a `programme` column, loads all programme descriptions and IDs from `tbl_programmes` for mapping.

### 4. **Insert Missing Courses**

- If any course in the Excel is not found in `tbl_courses_test` (by normalized code), it is inserted with its details including department and level (extracted from the course code).
- All new courses added are logged.

### 5. **Create `students_courses` Table (If Needed)**

- Ensures the `students_courses` table exists with all required columns, including a default value for `utme_no`.

### 6. **Populate `students_courses` Table**

- For each row in the Excel:
  - Extracts and parses student and course details.
  - **Programme Mapping:**
    - If the `programme` column exists in the Excel file, the script matches its value (case-insensitive, stripped) to `tbl_programmes.description` to get the `programme_id`.
    - If the field is missing or not matched, defaults `programme_id` to `0`.
  - **UTME Number:**
    - The `utme_no` field in `students_courses` is still present (with a default if not otherwise specified).
  - **Registration Data:**
    - All parsed/extracted data is inserted into the `students_courses` table, matching the field order in the table.

### 7. **Populate/Update `tbl_students_master_test`**

- For each unique student (`matricNo`):
  - If the student doesn't exist, inserts a new row with their details.
  - If the student exists and their department has changed, updates the record, logs the change, and syncs related tables.

### 8. **Populate `tbl_students_transactions_test`**

- For each unique student/level/session:
  - Inserts a transaction record if not already present, used for tracking registration status.

### 9. **Populate `student_users_test`**

- For each unique student in `students_courses`:
  - **Password Logic:**
    - The script now fetches the **UTME number from `tbl_students_master_test`** (not from the Excel or `students_courses`).
    - If `utme_no` is present and non-empty, it is used as the `userpassword`.
    - If `utme_no` is missing or empty, the student's **surname** (uppercased) is used as the password.
    - If both are missing, the password falls back to the matric number.
  - Records accounts where the UTME number is missing, for review.

### 10. **Populate Other Tables**

- `tbl_course_registered_test` and `course_dept_reg_map_test` are updated based on course and registration data, including normalization and mapping as needed.

### 11. **Logging and Output**

- All significant actions (skipped students, new courses, department changes, failed transactions, etc.) are logged into CSVs and compiled into an Excel file (`import_logs.xlsx`), with empty sheets containing explanatory notes.

### 12. **Completion**

- The script prints a summary and elapsed time.

---

## Key Logic Changes Reflected

- **Programme ID in `students_courses`:**
  - Dynamically determined from the Excel column and `tbl_programmes` mapping; defaults to `0` if not matched.
- **User Passwords in `student_users_test`:**
  - Now strictly sourced from `tbl_students_master_test.utme_no`, with fallback to surname or matric number as described.
- **Course Insertion:**
  - All missing courses are checked and inserted into `tbl_courses_test` before any population occurs.
- **Robust Logging:**
  - All skipped or exceptional cases are logged for review, and all logs are consolidated into a single Excel workbook.

---

## Notes

- Ensure all reference tables (`tbl_programmes`, `tbl_faculty`, `tbl_departments`, etc.) are up-to-date for proper mapping.
- Review the logs after each run to address any data quality or mapping issues.
- If the Excel format or DB schema changes, update this script and documentation accordingly.
