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
            return False, "
