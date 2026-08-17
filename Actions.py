import os
import time
import json
import requests
import numpy as np
import pandas as pd
import gspread
from datetime import datetime
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor

# -------------------- START TIMER --------------------
start_time = time.time()

# -------------------- ENV & AUTH --------------------
METABASE_API_KEY = os.getenv("METABASE_API_KEY")
service_account_json = os.getenv("SERVICE_ACCOUNT_JSON")

if not METABASE_API_KEY or not service_account_json:
    raise ValueError("❌ Missing environment variables. Check GitHub secrets.")
SHEET_KEY = "1doVV9vUf40AvASOteCKZhUHvIld1lpcM4AmprCMF7mw"

# -------------------- GOOGLE AUTH --------------------
service_info = json.loads(service_account_json)
creds = Credentials.from_service_account_info(
    service_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)
gc = gspread.authorize(creds)

# -------------------- METABASE AUTH --------------------
METABASE_HEADERS = {
    'Content-Type': 'application/json',
    'x-api-key': METABASE_API_KEY
}
# -------------------- UTILITIES --------------------
def mb_post(card_url, params=None):
    """POST to a Metabase card URL and return the response."""
    body = {"parameters": params or []}
    r = requests.post(card_url, headers=METABASE_HEADERS, json=body, timeout=120)
    r.raise_for_status()
    return r

def write_sheet(sheet_key, worksheet_name, df):
    """Clear and write a DataFrame to a Google Sheet."""
    print(f"🔄 Updating sheet: {worksheet_name}")
    for attempt in range(1, 6):
        try:
            sheet = gc.open_by_key(sheet_key)
            ws = sheet.worksheet(worksheet_name)
            ws.clear()
            ws.clear_basic_filter()
            set_with_dataframe(ws, df, include_index=False, include_column_header=True)
            print(f"✅ Successfully updated: {worksheet_name}")
            return
        except Exception as e:
            print(f"[Sheets] Attempt {attempt} failed for {worksheet_name}: {e}")
            if attempt < 5:
                time.sleep(20)
            else:
                print(f"❌ All attempts failed for {worksheet_name}.")
                raise

def clean_to_int(series):
    """Clean a series to integers, handling commas and floats."""
    return pd.to_numeric(
        series.astype(str)
              .str.replace(',', '')
              .str.replace(r'\.0$', '', regex=True)
              .str.strip(),
        errors='coerce'
    ).fillna(0).astype(int)

def fetch_6045_df():
    """Fetch base user info from Metabase card 6045."""
    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/6045/query/json')
    df = pd.DataFrame(r.json())
    df = df.rename(columns={'id': 'user_id'})
    return df

def fetch_8218_df():
    """Fetch onboarding data from Metabase card 8218."""
    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/8218/query/json')
    df = pd.DataFrame(r.json())
    return df

# -------------------- SECTION 1: GROOMING --------------------
def run_grooming():
    print("\n📌 Running: Grooming")

    EXPECTED_COLUMNS = [
        "session_id", "meeting_title", "participants_count", "session_type",
        "student_id", "student_name", "mentor_name", "batch",
        "session_start_time", "session_status", "lecture_recording_link",
        "mentor_join_time", "mentor_leave_time", "student_join_time",
        "student_leave_time", "over_lap_time_in_minute",
        "mentor_time_spent_in_minute", "student_time_spent_in_minute",
        "mentor_rating", "call_type", "communication_rating", "self_intro",
        "project_explanation", "excel", "sql", "power_bi", "pace_speed",
        "business_acumen", "hr_questions", "student_intent",
        "job_readiness", "pr_conversion_weeks", "fit_for_placements"
    ]

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/7577/query/json')
    df = pd.DataFrame(r.json())
    df = df.reindex(columns=EXPECTED_COLUMNS)

    write_sheet(SHEET_KEY, "Grooming", df)

# -------------------- SECTION 2: ASSIGNMENT UPDATED --------------------
def run_assignment_updated():
    print("\n📌 Running: Assignment Updated")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/7939/query/json')
    df = pd.DataFrame(r.json())
    df = df[df['batch_name'].str.startswith('DS', na=False)]
    df = df[[
        "course_id", "batch_name", "user_id", "student_name",
        "admin_unit_name", "module_name", "total_question", "open_q_count",
        "attempt_q_count", "completed_q_count", "completed_q_on_time",
        "users_attempt_rate", "users_completion_rate", "users_completion_rate_on_time"
    ]]

    write_sheet(SHEET_KEY, "Assignment updated", df)

# -------------------- SECTION 3: ATTENDANCE NEW --------------------
def run_attendance_new():
    print("\n📌 Running: Attendance New")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/3608/query/json')
    df = pd.DataFrame(r.json())
    df = df[df['batch_name'].str.startswith('DS', na=False)]
    df = df[[
        'course_id', 'user_id', 'student_name', 'batch_name',
        'lectures_conducted', 'overall_attendance', 'live_attendance',
        'recorded_attendance', 'live_60_per_watched_attendance',
        'recorded_40_per_watched_attendance', 'overall_70_per_watched_attendance',
        'avg_watch_live_mins', 'avg_watch_recorded_mins'
    ]]

    write_sheet(SHEET_KEY, "NEW", df)

# -------------------- SECTION 4: USER INFO 6045 OVERALL --------------------
def run_user_info_overall():
    print("\n📌 Running: User Info 6045 Overall")

    df = fetch_6045_df()
    df = df[df['Batch'].str.startswith('Professional Certificate Course In Data Science', na=False)]
    df = df[[
        "user_id", "username", "email", "student_name", "phone", "Batch", "status",
        "placement_status_updated_at", "label", "last_login",
        "number_of_days_since_last_login", "resume_approved", "number_of_projects",
        "resume_link", "linkedin_profile_link", "date_of_birth", "age_of_candidate",
        "Gender", "Bachelors Graduation", "10th Grade", "12th Grade", "Bachelors Grade",
        "Degree", "Field of Study", "job_titles", "companies", "location",
        "Experience Type", "Job_Description", "Time of Experience(Months)",
        "Is Tech Experienced?", "Technical Skills in experience", "Is Currently Working?",
        "domain_of_experience", "total_time_of_exp", "total_time_of_tech_exp",
        "total_time_of_non_tech_exp", "Current CTC", "notice_period", "Other Skills",
        "open_to_internship", "Preferred Job Role", "expected_max_ctc", "Bond Agreement",
        "preferred_location", "Current Location", "Current State",
        "course_user_mapping_status", "reason_for_marking_npr",
        "number_of_no_shows", "college_name"
    ]]

    write_sheet(SHEET_KEY, "user info 6045 overall", df)

# -------------------- SECTION 5: PROJECTS --------------------
def run_projects():
    print("\n📌 Running: Projects")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/6960/query/json')
    df = pd.DataFrame(r.json())
    df = df[df['Batch'].str.startswith('DS', na=False)]

    desired_columns = [
        'User ID', 'Name', 'Batch', 'Project', 'Module_name',
        'project_release_date', 'project_deadline_date', 'created_at',
        'Attempt Status', 'Attempt Start Time', 'Submission Status', 'Submission Time 1',
        'question_id', 'question_title', 'Code Link', 'Hosted Link', 'Upload_link',
        'File_Link', 'text_File_Link', 'Evaluation Status', 'marks_obtained',
        'number_of_submissions', 'first_submission', 'recent_submission',
        'first_feedback_given_time', 'latest_feedback_given_time',
        'feedback_received_count', 'Submission Time'
    ]
    existing_columns = [col for col in desired_columns if col in df.columns]
    df = df[existing_columns]

    write_sheet(SHEET_KEY, "Project", df)

# -------------------- SECTION 6: ACTIVITY --------------------
def run_activity():
    print("\n📌 Running: Activity")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/6616/query/json')
    df = pd.DataFrame(r.json())
    df = df[df['admin_unit_name'].str.startswith('Professional', na=False)]

    write_sheet(SHEET_KEY, "Activity", df)

# -------------------- SECTION 7: PICK AND PLAY --------------------
def run_pick_and_play():
    print("\n📌 Running: Pick and Play")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/8418/query/json')
    df = pd.DataFrame(r.json())

    write_sheet(SHEET_KEY, "pick and play", df)

# -------------------- SECTION 8: ONBOARDING DATA --------------------
def run_onboarding_data():
    print("\n📌 Running: Onboarding Data")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/8142/query/json')
    df = pd.DataFrame(r.json())

    write_sheet(SHEET_KEY, "Onboarding data", df)

# -------------------- SECTION 9: ASSESSMENT --------------------
def run_assessment():
    print("\n📌 Running: Assessment")

    r = mb_post('https://metabase-lierhfgoeiwhr.newtonschool.co/api/card/4332/query/json')
    df = pd.DataFrame(r.json())
    df = df[df['course_title'].str.startswith('DS', na=False)]
    df = df[[
        'course_id', 'course_title', 'Student ID', 'Student Name',
        'Number of Assessments Released', 'Number of Assessments Opened',
        'Number of Assessments Submitted', 'Average Attempted Score',
        'Average Overall Score'
    ]]

    write_sheet(SHEET_KEY, "Assesment", df)

# -------------------- SECTION 10: ONBOARDING SHAHID DUMP --------------------
def run_onboarding_shahid_dump():
    print("\n📌 Running: Onboarding Shahid Dump")

    EXCLUDE_BATCH = "Pre Course DS Certification and DS Spreadsheets - 2026"

    # Fetch 8218
    df_8218 = fetch_8218_df()
    df_8218 = df_8218[df_8218["au_batch_name"].str.contains("2026", na=False)]
    df_8218 = df_8218[df_8218["au_batch_name"] != EXCLUDE_BATCH]
    df_8218 = df_8218[[
        "user_id", "student_name", "au_batch_name", "lu_cum_status",
        "label_status", "current_email", "first_change_value",
        "second_change_value", "latest_change_value"
    ]]

    # Fetch 6045
    df_6045 = fetch_6045_df()
    df_6045 = df_6045[[
        "user_id", "username", "email", "phone", "Batch", "status",
        "placement_status_updated_at", "label", "last_login"
    ]]

    # Merge & fix email
    df_final = df_8218.merge(df_6045, how="left", on="user_id")
    df_final["email"] = df_final["current_email"].combine_first(df_final["email"])
    df_final.drop(columns=["current_email"], inplace=True)

    df_final = df_final[[
        "user_id", "student_name", "au_batch_name", "lu_cum_status",
        "label_status", "email", "phone", "Batch", "username", "status",
        "first_change_value", "second_change_value", "latest_change_value",
        "placement_status_updated_at", "label", "last_login"
    ]]

    write_sheet(SHEET_KEY, "Onboarding shahid dump", df_final)

# -------------------- SECTION 11: AUTOMATED ONBOARD DATA --------------------
def run_automated_onboard_data():
    print("\n📌 Running: Automated Onboard Data")

    df1 = fetch_8218_df()
    df2 = fetch_6045_df()

    # Raw sheets
    write_sheet(SHEET_KEY, "automated onboard data", df1)
    write_sheet(SHEET_KEY, "Ashrita onboard - 6045", df2)

    # Merged raw
    df_merged_raw = pd.merge(df1, df2, on='user_id', how='left')
    write_sheet(SHEET_KEY, "Merged onboarding raw", df_merged_raw)

    # Deduplicated & cleaned merged
    if 'last_login' in df1.columns:
        df1 = df1.sort_values('last_login', ascending=False)
    df1 = df1.drop_duplicates(subset='user_id', keep='first')

    if 'last_login' in df2.columns:
        df2 = df2.sort_values('last_login', ascending=False)
    df2 = df2.drop_duplicates(subset='user_id', keep='first')

    df3 = pd.merge(df1, df2, on='user_id', how='left', suffixes=('_df1', '_df2'))

    # Fix student_name
    if 'student_name_df1' in df3.columns:
        df3['student_name'] = df3['student_name_df1']
    elif 'student_name_df2' in df3.columns:
        df3['student_name'] = df3['student_name_df2']
    df3.drop(columns=[col for col in df3.columns if 'student_name_' in col], inplace=True, errors='ignore')

    # Fix email
    if 'current_email' in df3.columns and 'email' in df3.columns:
        df3['email'] = df3['current_email'].fillna(df3['email'])
        df3.drop(columns=['current_email'], inplace=True)

    final_columns = [
        'user_id', 'student_name', 'au_batch_name',
        'lu_cum_status', 'label_status', 'email', 'phone', 'last_login'
    ]
    df3 = df3[[col for col in final_columns if col in df3.columns]]
    df3 = df3.drop_duplicates(subset='user_id', keep='first')

    write_sheet(SHEET_KEY, "Merged onboarding", df3)

# -------------------- MAIN: RUN ALL --------------------
if __name__ == "__main__":
    print("🚀 Starting Automation...")

    tasks = [
        ("Grooming",                    run_grooming),
        ("Assignment Updated",          run_assignment_updated),
        ("Attendance New",              run_attendance_new),
        ("User Info 6045 Overall",      run_user_info_overall),
        ("Projects",                    run_projects),
        ("Activity",                    run_activity),
        ("Pick and Play",               run_pick_and_play),
        ("Onboarding Data",             run_onboarding_data),
        ("Assessment",                  run_assessment),
        ("Onboarding Shahid Dump",      run_onboarding_shahid_dump),
        ("Automated Onboard Data",      run_automated_onboard_data),
    ]

    for name, fn in tasks:
        try:
            fn()
        except Exception as e:
            print(f"❌ Error in {name}: {e}")

    # -------------------- TIMESTAMP --------------------
    current_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%b-%Y %H:%M:%S")
    print(f"\n✅ Timestamp: {current_time}")

    end_time = time.time()
    mins, secs = divmod(end_time - start_time, 60)
    print(f"⏱ Total time: {int(mins)}m {int(secs)}s")
    print("🎯 Automation completed successfully!")
