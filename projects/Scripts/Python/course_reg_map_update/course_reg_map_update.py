from datetime import datetime
from tqdm import tqdm
import pymysql
import time
import pytz  # For WAT time zone support in Python 3.8

def update_course_dept_reg_map_test():
    # ============================
    # Prompt user for session input
    # ============================
    session_id_fk = input("Enter the session_id_fk to update.../n")

    # ============================
    # Start timing the operation
    # ============================
    start_time = time.time()

    # ============================
    # Establish database connection
    # ============================
    # Update your DB credentials here
    connection = pymysql.connect(
        host='127.0.0.1',
        user='uirms',
        password='Uirmsui123@#',
        database='uirms',
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor
    )
    cursor = connection.cursor()

    # ======================================
    # Fetch aggregated data for the session
    # ======================================
    cursor.execute("""
        SELECT 
            course_id_fk,
            course_dept_id_fk,
            student_dept_id_fk,
            session_id_fk,
            semester_id_fk,
            COUNT(DISTINCT student_id_fk) as no_of_students,
            COUNT(DISTINCT CASE WHEN result REGEXP '^[0-9]+$' THEN student_id_fk END) as no_of_results
        FROM tbl_course_registered_test
        WHERE session_id_fk = %s
        GROUP BY course_id_fk, course_dept_id_fk, student_dept_id_fk, session_id_fk, semester_id_fk
    """, (session_id_fk,))
    course_dept_data = cursor.fetchall()

    # ==================================================
    # Get all existing keys for the session in the target
    # ==================================================
    cursor.execute(
        "SELECT `key` FROM course_dept_reg_map_test WHERE session_id_fk = %s", 
        (session_id_fk,)
    )
    existing_keys = set(row[0] for row in cursor.fetchall())

    # =================================
    # Prepare insert and update queries
    # =================================
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

    update_query = """
        UPDATE course_dept_reg_map_test
        SET 
            semester = %s,
            no_of_students = %s,
            no_of_results = %s,
            last_mod_by = %s,
            last_mod_ts = %s
        WHERE `key` = %s
    """

    # ======================================
    # Prepare counters and West Africa Time
    # ======================================
    nigeria_tz = pytz.timezone('Africa/Lagos')
    current_time = datetime.now(nigeria_tz).strftime('%Y-%m-%d %H:%M:%S')
    inserted_rows = 0
    updated_rows = 0

    # ======================================
    # Main loop: Insert or Update aggregates
    # ======================================
    for row in tqdm(course_dept_data, desc="  Populating course_dept_reg_map_test:"):
        (
            course_id_fk,
            course_dept_id_fk,
            student_dept_id_fk,
            session_id_fk_out,
            semester,
            no_of_students,
            no_of_results
        ) = row
        # Generate the unique key for each record
        key = f"{course_id_fk}:{course_dept_id_fk}:{student_dept_id_fk}:{session_id_fk_out}"

        if key in existing_keys:
            # --- Update existing record ---
            cursor.execute(update_query, (
                semester,
                no_of_students,
                no_of_results,
                '111111',        # last_mod_by for updates
                current_time,    # last_mod_ts for updates
                key
            ))
            updated_rows += 1
            continue

        # --- Insert new record ---
        try:
            cursor.execute(insert_query, (
                course_id_fk,
                course_dept_id_fk,
                student_dept_id_fk,
                session_id_fk_out,
                semester,
                no_of_students,
                no_of_results,
                key,
                '654321',         # last_mod_by for inserts
                current_time,     # last_mod_ts for inserts
                0,
                0,
                0
            ))
            inserted_rows += 1
        except pymysql.err.IntegrityError:
            # If duplicate (rare), fallback to update
            cursor.execute(update_query, (
                semester,
                no_of_students,
                no_of_results,
                '111111',
                current_time,
                key
            ))
            updated_rows += 1

    # ===================
    # Commit and cleanup
    # ===================
    connection.commit()
    cursor.close()
    connection.close()

    # ===================
    # Print stats/results
    # ===================
    print(f"  ✓ Inserted {inserted_rows} new records into course_dept_reg_map_test")
    print(f"  ~ Updated {updated_rows} existing records in course_dept_reg_map_test")

    # ===================
    # Print processing time
    # ===================
    end_time = time.time()
    elapsed = end_time - start_time
    minutes = elapsed // 60
    seconds = elapsed % 60
    print(f"\nTOTAL PROCESSING TIME: {int(minutes)} minutes {seconds:.2f} seconds")
    print("\nOPERATION COMPLETED SUCCESSFULLY")

# ======================================================
# Entry point: Only runs if called as a script, not import
# ======================================================
if __name__ == "__main__":
    update_course_dept_reg_map_test()