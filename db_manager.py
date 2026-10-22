import streamlit as st
import pandas as pd
import json
from datetime import date, datetime, timedelta, timezone
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --------------------------------
# 한국 표준시 (KST) 설정
# --------------------------------
KST = timezone(timedelta(hours=9))

def get_kst_now():
    return datetime.now(KST)

def get_kst_date():
    return get_kst_now().date()

# --------------------------------
# 0. 구글 드라이브 파일 업로드 함수
# --------------------------------
def upload_file_to_drive(uploaded_file, prefix="DOC"):
    if uploaded_file is None:
        return "", ""
    try:
        gsheets_secret = dict(st.secrets["connections"]["gsheets"])
        folder_id = gsheets_secret.get("drive_folder_id", "").strip()
        
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(gsheets_secret, scopes=scopes)
        drive_service = build('drive', 'v3', credentials=creds)
        
        now_stamp = get_kst_now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"[{prefix}_{now_stamp}] {uploaded_file.name}"
        
        file_metadata = {'name': safe_filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        uploaded_file.seek(0)
        media = MediaIoBaseUpload(
            uploaded_file,
            mimetype=uploaded_file.type if uploaded_file.type else 'application/octet-stream',
            resumable=True
        )
        
        created_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        file_id = created_file.get('id')
        web_link = created_file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
        
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                supportsAllDrives=True
            ).execute()
        except Exception:
            pass
            
        return uploaded_file.name, web_link
    except Exception as e:
        st.error(f"구글 드라이브 파일 업로드 오류: {e}")
        return uploaded_file.name, ""

# --------------------------------
# 1. 구글 스프레드시트 연동 및 캐싱
# --------------------------------
APPROVAL_COLS = [
    'id', 'created_at', 'doc_type', 'title', 'drafter_name', 'department',
    'budget', 'content', 'status', 'target_manager1', 'target_manager2',
    'final_approval_req', 'cc_users', 'attachment_name', 'attachment_url',
    'related_doc_id', 'manager1_name', 'manager1_comment', 'manager2_name',
    'manager2_comment', 'final_approver', 'final_comment', 'spent_amount',
    'expense_details', 'expense_status', 'receipt_name', 'receipt_url'
]

USER_COLS = ['username', 'password', 'name', 'role', 'department', 'position']
ARCHIVE_COLS = ['id', 'month_label', 'saved_at', 'saved_by', 'summary_json', 'raw_json']

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
                df = pd.DataFrame(columns=USER_COLS)
            elif worksheet_name == "live_attendance":
                df = pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
            elif worksheet_name == "approvals":
                df = pd.DataFrame(columns=APPROVAL_COLS)
            elif worksheet_name == "monthly_att_archive":
                df = pd.DataFrame(columns=ARCHIVE_COLS)
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
            return pd.DataFrame(columns=USER_COLS)
        elif worksheet_name == "live_attendance":
            return pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
        elif worksheet_name == "approvals":
            return pd.DataFrame(columns=APPROVAL_COLS)
        elif worksheet_name == "monthly_att_archive":
            return pd.DataFrame(columns=ARCHIVE_COLS)
    return df.copy()

def save_data(worksheet_name, df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = df.fillna("")
    try:
        conn.update(worksheet=worksheet_name, data=df)
    except Exception:
        # 시트(탭)가 존재하지 않을 경우 자동으로 시트를 새로 생성한 뒤 데이터 저장
        try:
            conn.create(worksheet=worksheet_name, data=df)
        except Exception as e:
            st.error(f"구글 시트 저장 오류 ({worksheet_name}): {e}")
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
    credentials = {
        "admin": {
            "password": "admin1234",
            "name": "기본관리자",
            "role": "admin",
            "department": "총무부",
            "position": "대표이사"
        }
    }
    if not users_df.empty and 'username' in users_df.columns:
        for _, row in users_df.iterrows():
            if pd.isna(row.get('username')): 
                continue
            u_id = str(row['username']).strip()
            if u_id:
                pos_val = str(row.get('position', '')).strip()
                if not pos_val:
                    pos_val = "대표이사" if str(row.get('role', '')).strip() == "admin" else "사원"
                credentials[u_id] = {
                    "password": str(row.get('password', '')).strip(),
                    "name": str(row.get('name', u_id)).strip(),
                    "role": str(row.get('role', 'user')).strip(),
                    "department": str(row.get('department', '환경사업부')).strip(),
                    "position": pos_val
                }
    return credentials

def add_user(username, password, name, role="user", department="환경사업부", position="사원"):
    users_df = get_data("users")
    for col in USER_COLS:
        if col not in users_df.columns:
            users_df[col] = ""
    if not users_df.empty and 'username' in users_df.columns:
        if username in users_df['username'].astype(str).values:
            return False, "이미 존재하는 아이디입니다."
    new_user = pd.DataFrame([{
        'username': str(username),
        'password': str(password),
        'name': str(name),
        'role': str(role),
        'department': str(department),
        'position': str(position)
    }])
    save_data("users", pd.concat([users_df, new_user], ignore_index=True))
    return True, f"'{name} ({position})' 사용자가 성공적으로 등록되었습니다."

def update_user_position(username, new_dept, new_pos):
    users_df = get_data("users")
    if not users_df.empty and 'username' in users_df.columns:
        for col in USER_COLS:
            if col not in users_df.columns:
                users_df[col] = ""
            users_df[col] = users_df[col].astype(object)
        idx = users_df[users_df['username'].astype(str) == str(username)].index
        if len(idx) > 0:
            t_idx = idx[0]
            users_df.at[t_idx, 'department'] = str(new_dept)
            users_df.at[t_idx, 'position'] = str(new_pos)
            save_data("users", users_df)
            return True, f"'{username}' 계정의 직책/부서 정보가 수정되었습니다."
    return False, "사용자 정보를 찾을 수 없습니다."

def delete_user(username):
    users_df = get_data("users")
    if not users_df.empty and 'username' in users_df.columns:
        if username == "admin":
            return False, "기본 관리자(admin) 계정은 삭제할 수 없습니다."
        save_data("users", users_df[users_df['username'].astype(str) != str(username)])
        return True, f"'{username}' 계정이 삭제되었습니다."
    return False, "계정 정보를 찾을 수 없습니다."

# --------------------------------
# 3. 실시간 근태 및 월간 분석 아카이브 관리
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

def save_monthly_att_archive(month_label, saved_by, summary_dict, raw_df):
    """월간 심층 분석 결과를 구글 시트(monthly_att_archive)에 영구 저장"""
    df = get_data("monthly_att_archive")
    for col in ARCHIVE_COLS:
        if col not in df.columns:
            df[col] = ""
    
    if not df.empty:
        df = df[df['month_label'].astype(str) != str(month_label)]
        
    new_id = generate_new_id(df)
    now_str = get_kst_now().strftime("%Y-%m-%d %H:%M")
    
    keep_cols = ['근무일자', '이름', '출근시간', '퇴근시간', '출근판정', '퇴근판정', '총근무시간', '연장근무시간']
    valid_cols = [c for c in keep_cols if c in raw_df.columns]
    compact_df = raw_df[valid_cols].copy()
    for c in compact_df.columns:
        compact_df[c] = compact_df[c].astype(str)
        
    summary_json_str = json.dumps(summary_dict, ensure_ascii=False)
    raw_json_str = compact_df.to_json(orient="records", force_ascii=False)
    
    if len(raw_json_str) > 48000:
        raw_json_str = compact_df.head(350).to_json(orient="records", force_ascii=False)
        
    new_row = pd.DataFrame([{
        'id': str(new_id),
        'month_label': str(month_label),
        'saved_at': now_str,
        'saved_by': str(saved_by),
        'summary_json': summary_json_str,
        'raw_json': raw_json_str
    }])
    save_data("monthly_att_archive", pd.concat([df, new_row], ignore_index=True))
    return True, f"[{month_label}] 월간 근태 심층 분석 결과가 아카이브에 저장되었습니다."

def delete_monthly_att_archive(archive_id):
    df = get_data("monthly_att_archive")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        save_data("monthly_att_archive", df[df['id'] != str(archive_id)])
        return True, "저장된 분석 기록이 삭제되었습니다."
    return False, "삭제할 기록을 찾을 수 없습니다."

# --------------------------------
# 4. 업무보고 관리
# --------------------------------
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
            if col not in df.columns: 
                df[col] = ""
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
            if col not in df.columns: 
                df[col] = ""
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
    if pd.isna(t): 
        return 0
    try:
        t_str = str(t).strip()
        if ':' in t_str:
            parts = t_str.split(':')
            if len(parts) >= 2: 
                return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0

# --------------------------------
# 5. 전자결재 & 지출정산 관리
# --------------------------------
def _determine_initial_status(mgr1, mgr2, final_req):
    m1_clean = str(mgr1).strip()
    m2_clean = str(mgr2).strip()
    if m1_clean not in ["", "없음", "선택 안 함"]:
        return "1차결재대기"
    elif m2_clean not in ["", "없음", "선택 안 함"]:
        return "2차결재대기"
    elif str(final_req).strip() == "대표승인 요":
        return "최종결재대기"
    return "승인완료(집행가능)"

def insert_approval_doc(doc_type, title, drafter_name, department, budget, target_mgr1, target_mgr2, final_req, cc_users, content, attachment_name="", attachment_url="", related_doc_id=""):
    df = get_data("approvals")
    for col in APPROVAL_COLS:
        if col not in df.columns:
            df[col] = ""
    new_id = generate_new_id(df)
    now_str = get_kst_now().strftime("%Y-%m-%d %H:%M")
    
    m1_val = str(target_mgr1).strip() if str(target_mgr1).strip() not in ["", "선택 안 함"] else "없음"
    m2_val = str(target_mgr2).strip() if str(target_mgr2).strip() not in ["", "선택 안 함"] else "없음"
    init_status = _determine_initial_status(m1_val, m2_val, final_req)
    exp_status = "정산대기" if init_status == "승인완료(집행가능)" else "미집행"

    new_row = pd.DataFrame([{
        'id': str(new_id), 'created_at': now_str, 'doc_type': str(doc_type),
        'title': str(title), 'drafter_name': str(drafter_name), 'department': str(department),
        'budget': str(budget), 'content': str(content), 'status': init_status,
        'target_manager1': m1_val,
        'target_manager2': m2_val,
        'final_approval_req': str(final_req),
        'cc_users': str(", ".join(cc_users)) if cc_users else "없음",
        'attachment_name': str(attachment_name),
        'attachment_url': str(attachment_url),
        'related_doc_id': str(related_doc_id) if related_doc_id else "",
        'manager1_name': '', 'manager1_comment': '',
        'manager2_name': '', 'manager2_comment': '',
        'final_approver': '', 'final_comment': '',
        'spent_amount': '0', 'expense_details': '', 'expense_status': exp_status,
        'receipt_name': '', 'receipt_url': ''
    }])
    save_data("approvals", pd.concat([df, new_row], ignore_index=True))
    return True, new_id

def update_approval_doc(doc_id, doc_type, title, budget, target_mgr1, target_mgr2, final_req, cc_users, content, attachment_name=None, attachment_url=None, related_doc_id=None):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        for col in APPROVAL_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            m1_val = str(target_mgr1).strip() if str(target_mgr1).strip() not in ["", "선택 안 함"] else "없음"
            m2_val = str(target_mgr2).strip() if str(target_mgr2).strip() not in ["", "선택 안 함"] else "없음"
            
            df.at[t_idx, 'doc_type'] = str(doc_type)
            df.at[t_idx, 'title'] = str(title)
            df.at[t_idx, 'budget'] = str(budget)
            df.at[t_idx, 'target_manager1'] = m1_val
            df.at[t_idx, 'target_manager2'] = m2_val
            df.at[t_idx, 'final_approval_req'] = str(final_req)
            df.at[t_idx, 'cc_users'] = str(", ".join(cc_users)) if cc_users else "없음"
            df.at[t_idx, 'content'] = str(content)
            if attachment_name is not None:
                df.at[t_idx, 'attachment_name'] = str(attachment_name)
            if attachment_url is not None:
                df.at[t_idx, 'attachment_url'] = str(attachment_url)
            if related_doc_id is not None:
                df.at[t_idx, 'related_doc_id'] = str(related_doc_id)
                
            df.at[t_idx, 'status'] = _determine_initial_status(m1_val, m2_val, final_req)
            save_data("approvals", df)
            return True, "품의서 내용 및 첨부파일이 수정되었습니다."
    return False, "문서를 찾을 수 없습니다."

def approve_step1(doc_id, manager_name, comment, is_reject=False):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        for col in APPROVAL_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'manager1_name'] = str(manager_name)
            df.at[t_idx, 'manager1_comment'] = str(comment)
            if is_reject:
                df.at[t_idx, 'status'] = '1차반려'
                msg = "1차 반려 처리되었습니다."
            else:
                has_mgr2 = str(df.at[t_idx, 'target_manager2']).strip() not in ["", "없음", "선택 안 함"]
                final_req = str(df.at[t_idx, 'final_approval_req']).strip()
                if has_mgr2:
                    df.at[t_idx, 'status'] = '2차결재대기'
                    msg = "1차 승인 완료! 2차 결재로 넘어갔습니다."
                elif final_req == "대표 승인 불요":
                    df.at[t_idx, 'status'] = '승인완료(집행가능)'
                    df.at[t_idx, 'expense_status'] = '정산대기'
                    msg = "1차 승인 완료! (대표 승인 불요 건으로 최종 승인 및 집행 가능 처리되었습니다.)"
                else:
                    df.at[t_idx, 'status'] = '최종결재대기'
                    msg = "1차 승인 완료! 최종 결재(대표 승인) 대기 상태로 넘어갔습니다."
            save_data("approvals", df)
            return True, msg
    return False, "문서를 찾을 수 없습니다."

def approve_step2(doc_id, manager_name, comment, is_reject=False):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        for col in APPROVAL_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'manager2_name'] = str(manager_name)
            df.at[t_idx, 'manager2_comment'] = str(comment)
            if is_reject:
                df.at[t_idx, 'status'] = '2차반려'
                msg = "2차 반려 처리되었습니다."
            else:
                final_req = str(df.at[t_idx, 'final_approval_req']).strip()
                if final_req == "대표 승인 불요":
                    df.at[t_idx, 'status'] = '승인완료(집행가능)'
                    df.at[t_idx, 'expense_status'] = '정산대기'
                    msg = "2차 승인 완료! (대표 승인 불요 건으로 최종 승인 및 집행 가능 처리되었습니다.)"
                else:
                    df.at[t_idx, 'status'] = '최종결재대기'
                    msg = "2차 승인 완료! 최종 결재(대표 승인)로 상신되었습니다."
            save_data("approvals", df)
            return True, msg
    return False, "문서를 찾을 수 없습니다."

def approve_final(doc_id, final_approver, comment, is_reject=False):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        for col in APPROVAL_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].astype(object)
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
            return True, "최종 반려되었습니다." if is_reject else "최종 결재 완료! 집행 및 지출 정산이 가능합니다."
    return False, "문서를 찾을 수 없습니다."

def submit_expense_report(doc_id, spent_amount, expense_details, receipt_name=None, receipt_url=None):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        for col in APPROVAL_COLS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].astype(object)
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            t_idx = idx[0]
            df.at[t_idx, 'spent_amount'] = str(spent_amount)
            df.at[t_idx, 'expense_details'] = str(expense_details)
            df.at[t_idx, 'expense_status'] = '정산검토중'
            if receipt_name:
                df.at[t_idx, 'receipt_name'] = str(receipt_name)
            if receipt_url:
                df.at[t_idx, 'receipt_url'] = str(receipt_url)
            save_data("approvals", df)
            return True, "지출 정산 내역 및 증빙 파일이 상신되었습니다."
    return False, "문서를 찾을 수 없습니다."

def finalize_expense(doc_id):
    df = get_data("approvals")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(doc_id)].index
        if len(idx) > 0:
            df.at[idx[0], 'expense_status'] = '정산완료'
            save_data("approvals", df)
            return True, "지출 정산이 최종 마감/승인되었습니다."
    return False, "문서를 찾을 수 없습니다."
