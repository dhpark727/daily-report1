import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from streamlit_gsheets import GSheetsConnection

# 한국 표준시 (KST) 설정
KST = timezone(timedelta(hours=9))

def get_kst_now():
    return datetime.now(KST)

def get_kst_date():
    return get_kst_now().date()

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

# 사용자 계정 관리
def get_user_credentials():
    users_df = get_data("users")
    credentials = {"admin": {"password": "admin1234", "name": "기본관리자", "role": "admin", "department": "총무부"}}
    if not users_df.empty and 'username' in users_df.columns:
        for _, row in users_df.iterrows():
            if pd.isna(row.get('username')): continue
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

# 근태 관련 함수
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
            new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'date': d_str, 'name': str(name), 'department': str(department), 'type': str(leave_type), 'check_in': '-', 'check_out': '-', 'note': str(note)}])
            df = pd.concat([df, new_row], ignore_index=True)
        added_count += 1
        curr += timedelta(days=1)
    save_data("live_attendance", df)
    return True, f"{start_d} ~ {end_d} 기간({added_count}일간) 동안 [{leave_type}] 일정이 등록되었습니다."

def delete_attendance(att_id):
    df = get_data("live_attendance")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        save_data("live_attendance", df[df['id'] != str(att_id)])
        return True, "신청 내역이 정상적으로 취소되었습니다."
    return False, "기록을 찾을 수 없습니다."

# 보고서 CRUD 함수
def insert_report(report_date, department, name, today_result, tomorrow_plan, issue):
    df = get_data("reports")
    new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'report_date': str(report_date), 'department': str(department), 'name': str(name), 'today_result': str(today_result), 'tomorrow_plan': str(tomorrow_plan), 'issue': str(issue), 'status': '제출완료', 'comment': ''}])
    save_data("reports", pd.concat([df, new_row], ignore_index=True))

def save_consolidated_report(report_date, department, manager_name, today_result, tomorrow_plan, issue):
    df = get_data("consolidated_reports")
    if not df.empty and 'report_date' in df.columns and 'department' in df.columns:
        df['report_date'] = df['report_date'].astype(str)
        df = df[~((df['report_date'] == str(report_date)) & (df['department'] == department))]
    new_row = pd.DataFrame([{'id': str(generate_new_id(df)), 'report_date': str(report_date), 'department': str(department), 'manager_name': str(manager_name), 'today_result': str(today_result), 'tomorrow_plan': str(tomorrow_plan), 'issue': str(issue)}])
    save_data("consolidated_reports", pd.concat([df, new_row], ignore_index=True))

def update_report_full(report_id, today_result, tomorrow_plan, issue, status, comment):
    df = get_data("reports")
    if not df.empty and 'id' in df.columns:
        for col in ['status', 'comment', 'today_result', 'tomorrow_plan', 'issue']:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(report_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'today_result'] = str(today_result)
            df.at[t_idx, 'tomorrow_plan'] = str(tomorrow_plan)
            df.at[t_idx, 'issue'] = str(issue)
            df.at[t_idx, 'status'] = str(status)
            df.at[t_idx, 'comment'] = str(comment)
            save_data("reports", df)

def update_report(report_id, today_result, tomorrow_plan, issue):
    df = get_data("reports")
    if not df.empty and 'id' in df.columns:
        for col in ['today_result', 'tomorrow_plan', 'issue']:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(report_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'today_result'] = str(today_result)
            df.at[t_idx, 'tomorrow_plan'] = str(tomorrow_plan)
            df.at[t_idx, 'issue'] = str(issue)
            save_data("reports", df)

def delete_report(report_id):
    df = get_data("reports")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        save_data("reports", df[df['id'] != str(report_id)])

def time_to_minutes(t):
    if pd.isna(t): return 0
    try:
        if isinstance(t, str) and ':' in t:
            parts = t.split(':')
            if len(parts) >= 2: return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0
# --- 전자결재 (품의 및 지출정산) 관련 함수 ---
def insert_approval_doc(doc_type, title, drafter_name, department, budget, content):
    df = get_data("approvals")
    new_id = generate_new_id(df)
    now_str = get_kst_now().strftime("%Y-%m-%d %H:%M")
    new_row = pd.DataFrame([{
        'id': str(new_id), 'created_at': now_str, 'doc_type': str(doc_type),
        'title': str(title), 'drafter_name': str(drafter_name), 'department': str(department),
        'budget': str(budget), 'content': str(content), 'status': '1차결재대기',
        'manager_name': '', 'manager_comment': '', 'final_approver': '', 'final_comment': '',
        'spent_amount': '0', 'expense_details': '', 'expense_status': '미집행'
    }])
    save_data("approvals", pd.concat([df, new_row], ignore_index=True))
    return True, f"[{title}] 품의서가 상신되었습니다. (1차 결재 대기)"

def approve_step1(doc_id, manager_name, comment, is_reject=False):
    """1차 중간관리자 승인/반려"""
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'manager_name'] = str(manager_name)
            df.at[t_idx, 'manager_comment'] = str(comment)
            df.at[t_idx, 'status'] = '1차반려' if is_reject else '최종결재대기'
            save_data("approvals", df)
            return True, "1차 반려 처리되었습니다." if is_reject else "1차 승인 완료! 최종 결재로 상신되었습니다."
    return False, "문서를 찾을 수 없습니다."

def approve_step2(doc_id, final_approver, comment, is_reject=False):
    """2차 최종 결재자 승인/반려"""
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'final_approver'] = str(final_approver)
            df.at[t_idx, 'final_comment'] = str(comment)
            df.at[t_idx, 'status'] = '최종반려' if is_reject else '승인완료(집행가능)'
            if not is_reject:
                df.at[t_idx, 'expense_status'] = '정산대기'
            save_data("approvals", df)
            return True, "최종 반려 처리되었습니다." if is_reject else "최종 결재 승인이 완료되었습니다. 이제 실행 및 지출 등록이 가능합니다."
    return False, "문서를 찾을 수 없습니다."

def submit_expense_report(doc_id, spent_amount, expense_details):
    """실행 후 지출 내역 및 영수증 증빙 등록"""
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'spent_amount'] = str(spent_amount)
            df.at[t_idx, 'expense_details'] = str(expense_details)
            df.at[t_idx, 'expense_status'] = '정산검토중'
            save_data("approvals", df)
            return True, "지출 정산 내역이 상신되었습니다."
    return False, "문서를 찾을 수 없습니다."

def finalize_expense(doc_id):
    """지출 정산 최종 완료 처리"""
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            df.at[idx[0], 'expense_status'] = '정산완료'
            save_data("approvals", df)
            return True, "지출 정산이 최종 마감/승인되었습니다."
    return False, "문서를 찾을 수 없습니다."
