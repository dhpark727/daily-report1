import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from streamlit_gsheets import GSheetsConnection

# --------------------------------
# 한국 표준시 (KST) 설정
# --------------------------------
KST = timezone(timedelta(hours=9))

def get_kst_now():
    return datetime.now(KST)

def get_kst_date():
    return get_kst_now().date()

# --------------------------------
# 1. 구글 스프레드시트 연동 및 캐싱
# --------------------------------
APPROVAL_COLS = [
    'id', 'created_at', 'doc_type', 'title', 'drafter_name', 'department',
    'budget', 'content', 'status', 'target_manager1', 'target_manager2',
    'cc_users', 'attachment_name', 'related_doc_id', 'manager1_name', 'manager1_comment',
    'manager2_name', 'manager2_comment', 'final_approver', 'final_comment',
    'spent_amount', 'expense_details', 'expense_status'
]

@st.cache_data(ttl=60, show_spinner=False)
def fetch_sheet_data(worksheet_name):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet=worksheet_name, ttl=60)
        df = df.dropna(how="all")
        if df.empty:
            if worksheet_name == "reports":
                df = pd.DataFrame(columns=['id', 'report_date', 'department', 'name', 'today_result', 'tomorrow_plan', 'issue', 'status', 'comment'])
            elif worksheet_name == "consolidated_reports":
                df = pd.DataFrame(columns=['id', 'report_date', 'department', 'manager_name', 'today_result', 'tomorrow_plan', 'issue'])
            elif worksheet_name == "users":
                df = pd.DataFrame(columns=['username', 'password', 'name', 'role', 'department'])
            elif worksheet_name == "live_attendance":
                df = pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
            elif worksheet_name == "approvals":
                df = pd.DataFrame(columns=APPROVAL_COLS)
        else:
            df = df.fillna("")
            for col in df.columns:
                df[col] = df[col].astype(str)
        return df
    except Exception:
        return pd.DataFrame()

def get_data(worksheet_name):
    df = fetch_sheet_data(worksheet_name)
    if df.empty:
        if worksheet_name == "reports":
            return pd.DataFrame(columns=['id', 'report_date', 'department', 'name', 'today_result', 'tomorrow_plan', 'issue', 'status', 'comment'])
        elif worksheet_name == "consolidated_reports":
            return pd.DataFrame(columns=['id', 'report_date', 'department', 'manager_name', 'today_result', 'tomorrow_plan', 'issue'])
        elif worksheet_name == "users":
            return pd.DataFrame(columns=['username', 'password', 'name', 'role', 'department'])
        elif worksheet_name == "live_attendance":
            return pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
        elif worksheet_name == "approvals":
            return pd.DataFrame(columns=APPROVAL_COLS)
    return df.copy()

def save_data(worksheet_name, df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = df.fillna("")
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

def generate_new_id(df):
    if df.empty or 'id' not in df.columns:
        return "1"
    max_id = pd.to_numeric(df['id'], errors='coerce').max()
    return str(int(max_id) + 1 if pd.notna(max_id) else 1)

# --------------------------------
# 2. 사용자 계정 관리
# --------------------------------
def get_user_credentials():
    users_df = get_data("users")
    credentials = {"admin": {"password": "admin1234", "name": "기본관리자", "role": "admin", "department": "총무부"}}
    if not users_df.empty and 'username' in users_df.columns:
        for _, row in users_df.iterrows():
            if pd.isna(row.get('username')): 
                continue
            u_id = str(row['username']).strip()
            if u_id:
                credentials[u_id] = {
                    "password": str(row.get('password', '')).strip(),
                    "name": str(row.get('name', u_id)).strip(),
                    "role": str(row.get('role', 'user')).strip(),
                    "department": str(row.get('department', '환경사업부')).strip()
                }
    return credentials

def add_user(username, password, name, role="user", department="환경사업부"):
    users_df = get_data("users")
    if not users_df.empty and 'username' in users_df.columns:
        if username in users_df['username'].astype(str).values:
            return False, "이미 존재하는 아이디입니다."
    new_user = pd.DataFrame([{'username': str(username), 'password': str(password), 'name': str(name), 'role': str(role), 'department': str(department)}])
    save_data("users", pd.concat([users_df, new_user], ignore_index=True))
    return True, f"'{name}' 사용자가 성공적으로 등록되었습니다."

def delete_user(username):
    users_df = get_data("users")
    if not users_df.empty and 'username' in users_df.columns:
        if username == "admin":
            return False, "기본 관리자(admin) 계정은 삭제할 수 없습니다."
        save_data("users", users_df[users_df['username'].astype(str) != str(username)])
        return True, f"'{username}' 계정이 삭제되었습니다."
    return False, "계정 정보를 찾을 수 없습니다."

# --------------------------------
# 3. 실시간 근태 및 출퇴근
# --------------------------------
def record_attendance(name, department, att_type, note=""):
    df = get_data("live_attendance")
    today_str = str(get_kst_date())
    now_time_str = get_kst_now().strftime("%H:%M:%S")
    df['date'] = df['date'].astype(str)
    df['name'] = df['name'].astype(str)
    user_today = df[(df['date'] == today_str) & (df['name'] == str(name))]
    
    if att_type == "출근":
        if not user_today.empty and user_today.iloc[0]['check_in'] != "-" and str(user_today.iloc[0]['check_in']).strip() != "":
            return False, f"이미 오늘 출근 체크({user_today.iloc[0]['check_in']})가 완료되었습니다."
        if not user_today.empty:
            idx = user_today.index[0]
            df.loc[idx, 'check_in'] = now_time_str
            df.loc[idx, 'type'] = "근무"
            if note: df.loc[idx, 'note'] = str(note)
        else:
            new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'date': today_str, 'name': str(name), 'department': str(department), 'type': '근무', 'check_in': now_time_str, 'check_out': '-', 'note': str(note)}])
            df = pd.concat([df, new_row], ignore_index=True)
        save_data("live_attendance", df)
        return True, f"[{now_time_str}] 출근 체크 완료!"

    elif att_type == "퇴근":
        if user_today.empty or user_today.iloc[0]['check_in'] == "-" or str(user_today.iloc[0]['check_in']).strip() == "":
            return False, "출근 기록이 먼저 확인되어야 퇴근을 기록할 수 있습니다."
        idx = user_today.index[0]
        df.loc[idx, 'check_out'] = now_time_str
        if note:
            df.loc[idx, 'note'] = (str(df.loc[idx, 'note']) + f" / 퇴근: {note}").strip(" /")
        save_data("live_attendance", df)
        return True, f"[{now_time_str}] 퇴근 체크 완료! 수고하셨습니다."

def manual_update_attendance(name, department, target_date, att_type, check_in_val, check_out_val, note_val):
    df = get_data("live_attendance")
    df['date'] = df['date'].astype(str)
    df['name'] = df['name'].astype(str)
    d_str = str(target_date)
    existing = df[(df['date'] == d_str) & (df['name'] == str(name))]
    if not existing.empty:
        idx = existing.index[0]
        df.loc[idx, 'type'] = str(att_type)
        df.loc[idx, 'check_in'] = str(check_in_val) if str(check_in_val).strip() else "-"
        df.loc[idx, 'check_out'] = str(check_out_val) if str(check_out_val).strip() else "-"
        df.loc[idx, 'note'] = str(note_val)
    else:
        new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'date': d_str, 'name': str(name), 'department': str(department), 'type': str(att_type), 'check_in': str(check_in_val) if str(check_in_val).strip() else "-", 'check_out': str(check_out_val) if str(check_out_val).strip() else "-", 'note': str(note_val)}])
        df = pd.concat([df, new_row], ignore_index=True)
    save_data("live_attendance", df)
    return True, f"{d_str} 근태 기록이 성공적으로 수정/등록되었습니다."

def record_leave_range(name, department, leave_type, start_d, end_d, note=""):
    df = get_data("live_attendance")
    df['date'] = df['date'].astype(str)
    df['name'] = df['name'].astype(str)
    curr = start_d
    added_count = 0
    while curr <= end_d:
        d_str = str(curr)
        existing = df[(df['date'] == d_str) & (df['name'] == str(name))]
        if not existing.empty:
            idx = existing.index[0]
            df.loc[idx, 'type'] = str(leave_type)
            df.loc[idx, 'note'] = str(note)
            df.loc[idx, 'check_in'] = '-'
            df.loc[idx, 'check_out'] = '-'
        else:
            new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'date': d_str, 'name':
