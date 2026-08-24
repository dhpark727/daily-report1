import streamlit as st
import pandas as pd
from datetime import date, datetime
from streamlit_gsheets import GSheetsConnection

# --------------------------------
# 1. 구글 스프레드시트 연동 및 데이터 관리 함수
# --------------------------------
def get_data(worksheet_name):
    """구글 시트에서 데이터를 불러옵니다."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df = df.dropna(how="all")
        if df.empty:
            if worksheet_name == "reports":
                df = pd.DataFrame(columns=['id', 'report_date', 'department', 'name', 'today_result', 'tomorrow_plan', 'issue'])
            elif worksheet_name == "consolidated_reports":
                df = pd.DataFrame(columns=['id', 'report_date', 'department', 'manager_name', 'today_result', 'tomorrow_plan', 'issue'])
            elif worksheet_name == "users":
                df = pd.DataFrame(columns=['username', 'password', 'name', 'role', 'department'])
            elif worksheet_name == "live_attendance":
                df = pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
        return df
    except Exception as e:
        st.error(f"구글 시트 연결 오류 ({worksheet_name}): {e}")
        return pd.DataFrame()


def save_data(worksheet_name, df):
    """구글 시트에 데이터를 저장합니다."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()


def generate_new_id(df):
    if df.empty or 'id' not in df.columns:
        return "1"
    else:
        max_id = pd.to_numeric(df['id'], errors='coerce').max()
        return str(int(max_id) + 1 if pd.notna(max_id) else 1)


# --- 사용자 계정 관리 함수 ---
def get_user_credentials():
    users_df = get_data("users")
    credentials = {
        "admin": {"password": "admin1234", "name": "기본관리자", "role": "admin", "department": "총무부"}
    }
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
    
    new_user = pd.DataFrame([{
        'username': username,
        'password': password,
        'name': name,
        'role': role,
        'department': department
    }])
    updated_df = pd.concat([users_df, new_user], ignore_index=True)
    save_data("users", updated_df)
    return True, f"'{name}' 사용자가 성공적으로 등록되었습니다."

def delete_user(username):
    users_df = get_data("users")
    if not users_df.empty and 'username' in users_df.columns:
        if username == "admin":
            return False, "기본 관리자(admin) 계정은 삭제할 수 없습니다."
        updated_df = users_df[users_df['username'].astype(str) != str(username)]
        save_data("users", updated_df)
        return True, f"'{username}' 계정이 삭제되었습니다."
    return False, "계정 정보를 찾을 수 없습니다."


# --- 실시간 근태(출퇴근/휴가) 관리 함수 ---
def record_attendance(name, department, att_type, note=""):
    """출근, 퇴근, 연차, 반차 등을 기록합니다."""
    df = get_data("live_attendance")
    today_str = str(date.today())
    now_time_str = datetime.now().strftime("%H:%M:%S")
    
    if df.empty or 'name' not in df.columns:
        df = pd.DataFrame(columns=['id', 'date', 'name', 'department', 'type', 'check_in', 'check_out', 'note'])
        
    df['date'] = df['date'].astype(str)
    df['name'] = df['name'].astype(str)
    
    user_today = df[(df['date'] == today_str) & (df['name'] == str(name))]
    
    if att_type == "출근":
        if not user_today.empty and user_today.iloc[0]['check_in'] != "-" and pd.notna(user_today.iloc[0]['check_in']):
            return False, f"이미 오늘 출근 체크({user_today.iloc[0]['check_in']})가 완료되었습니다."
        if not user_today.empty:
            idx = user_today.index[0]
            df.loc[idx, 'check_in'] = now_time_str
            df.loc[idx, 'type'] = "근무"
            if note: df.loc[idx, 'note'] = note
        else:
            new_id = generate_new_id(df)
            new_row = pd.DataFrame([{
                'id': new_id, 'date': today_str, 'name': name, 'department': department,
                'type': '근무', 'check_in': now_time_str, 'check_out': '-', 'note': note
            }])
            df = pd.concat([df, new_row], ignore_index=True)
        save_data("live_attendance", df)
        return True, f"[{now_time_str}] 출근 체크 완료!"

    elif att_type == "퇴근":
        if user_today.empty or user_today.iloc[0]['check_in'] == "-" or pd.isna(user_today.iloc[0]['check_in']):
            return False, "출근 기록이 먼저 확인되어야 퇴근을 기록할 수 있습니다."
        idx = user_today.index[0]
        df.loc[idx, 'check_out'] = now_time_str
        if note:
            df.loc[idx, 'note'] = (str(df.loc[idx, 'note']) + f" / 퇴근: {note}").strip(" /")
        save_data("live_attendance", df)
        return True, f"[{now_time_str}] 퇴근 체크 완료! 수고하셨습니다."

    else: # 연차, 오전반차, 오후반차, 출장 등
        if not user_today.empty:
            idx = user_today.index[0]
            df.loc[idx, 'type'] = att_type
            df.loc[idx, 'note'] = note
        else:
            new_id = generate_new_id(df)
            new_row = pd.DataFrame([{
                'id': new_id, 'date': today_str, 'name': name, 'department': department,
                'type': att_type, 'check_in': '-', 'check_out': '-', 'note': note
            }])
            df = pd.concat([df, new_row], ignore_index=True)
        save_data("live_attendance", df)
        return True, f"오늘 일정이 [{att_type}]로 등록되었습니다."


# --- 보고서 데이터 관리 함수 ---
def insert_report(report_date, department, name, today_result, tomorrow_plan, issue):
    df = get_data("reports")
    new_id = generate_new_id(df)
    new_row = pd.DataFrame([{
        'id': new_id, 'report_date': str(report_date), 'department': department,
        'name': name, 'today_result': today_result, 'tomorrow_plan': tomorrow_plan, 'issue': issue
    }])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    save_data("reports", updated_df)


def save_consolidated_report(report_date, department, manager_name, today_result, tomorrow_plan, issue):
    df = get_data("consolidated_reports")
    if not df.empty and 'report_date' in df.columns and 'department' in df.columns:
        df['report_date'] = df['report_date'].astype(str)
        condition = (df['report_date'] == str(report_date)) & (df['department'] == department)
        df = df[~condition]
    new_id = generate_new_id(df)
    new_row = pd.DataFrame([{
        'id': new_id, 'report_date': str(report_date), 'department': department,
        'manager_name': manager_name, 'today_result': today_result, 'tomorrow_plan': tomorrow_plan, 'issue': issue
    }])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    save_data("consolidated_reports", updated_df)


def update_report(report_id, today_result, tomorrow_plan, issue):
    df = get_data("reports")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(report_id)].index
        if len(idx) > 0:
            df.loc[idx, 'today_result'] = today_result
            df.loc[idx, 'tomorrow_plan'] = tomorrow_plan
            df.loc[idx, 'issue'] = issue
            save_data("reports", df)


def delete_report(report_id):
    df = get_data("reports")
    if not df.empty and 'id' in df.columns:
        df['id'] = df['id'].astype(str)
        updated_df = df[df['id'] != str(report_id)]
        save_data("reports", updated_df)


def time_to_minutes(t):
    if pd.isna(t): return 0
    try:
        if isinstance(t, str) and ':' in t:
            parts = t.split(':')
            if len(parts) >= 2:
                return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0


# --------------------------------
# 2. 웹 페이지 기본 구성 & 로그인 검증
# --------------------------------
st.set_page_config(page_title="로커스솔루션 업무 & 근태 관리", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

@st.dialog("📋 로커스솔루션 포털 - 사용자 인증", width="large")
def login_dialog():
    tab_login, tab_signup, tab_users = st.tabs(["🔑 로그인", "➕ 사용자 등록", "🔍 사용자 목록"])
    
    with tab_login:
        st.write("아이디와 비밀번호를 입력해 주세요.")
        input_id = st.text_input("아이디 (ID)", key="dlg_login_id")
        input_pw = st.text_input("비밀번호 (Password)", type="password", key="dlg_login_pw")
        
        if st.button("로그인", type="primary", use_container_width=True, key="dlg_login_btn"):
            credentials = get_user_credentials()
            if input_id in credentials and credentials[input_id]["password"] == input_pw:
                st.session_state.logged_in = True
                st.session_state.user_info = credentials[input_id]
                st.session_state.user_info["username"] = input_id
                st.success(f"{credentials[input_id]['name']}님, 환영합니다!")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with tab_signup:
        st.write("신규 사용자를 등록합니다.")
        new_id = st.text_input("아이디 (ID)", key="dlg_reg_id", placeholder="영문/숫자 조합")
        new_pw = st.text_input("비밀번호 (Password)", type="password", key="dlg_reg_pw")
        new_name = st.text_input("이름 (실명)", key="dlg_reg_name", placeholder="홍길동")
        new_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="dlg_reg_dept")
        
        if st.button("등록하기", type="primary", use_container_width=True, key="dlg_reg_btn"):
            if new_id.strip() and new_pw.strip() and new_name.strip():
                success, msg = add_user(new_id.strip(), new_pw.strip(), new_name.strip(), role="user", department=new_dept)
                if success:
                    st.success(msg + " 이제 [🔑 로그인] 탭에서 로그인해 주세요.")
                else:
                    st.error(msg)
            else:
                st.error("모든 항목을 입력해 주세요.")

    with tab_users:
        st.write("현재 등록된 임직원 목록입니다.")
        users_df = get_data("users")
        if not users_df.empty:
            display_users = users_df.copy()
            for col in ['username', 'name', 'department', 'role']:
                if col not in display_users.columns:
                    display_users[col] = ""
            display_users = display_users.rename(columns={'username': '아이디', 'name': '이름', 'department': '소속 부서', 'role': '권한'})
            st.dataframe(display_users[['아이디', '이름', '소속 부서', '권한']], use_container_width=True, hide_index=True)
        else:
            st.info("등록된 사용자 정보가 없습니다.")

if not st.session_state.logged_in:
    st.title("📋 로커스솔루션 통합 업무 관리 포털")
    st.info("서비스를 이용하시려면 먼저 로그인을 완료해 주세요.")
    login_dialog()
    st.stop()

# --- 로그인 완료 후 메인 시스템 ---

with st.sidebar:
    st.markdown("### 👤 접속 정보")
    user_name = st.session_state.user_info.get('name', '사용자')
    user_role = "👑 총괄 관리자" if st.session_state.user_info.get('role') == "admin" else "💼 일반 임직원"
    st.write(f"**이름**: {user_name}")
    st.write(f"**권한**: {user_role}")
    
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.rerun()
        
    if st.session_state.user_info.get("role") == "admin":
        st.markdown("---")
        with st.expander("⚙️ 계정 삭제 관리 (Admin)"):
            all_users = get_user_credentials()
            del_target = st.selectbox("삭제할 계정 선택", [u for u in all_users.keys() if u != "admin"])
            if st.button("선택 계정 삭제", key="sidebar_del_btn"):
                if del_target:
                    success, msg = delete_user(del_target)
                    if success:
                        st.warning(msg)
                        st.rerun()
                    else:
                        st.error(msg)

st.title("📋 로커스솔루션 통합 업무 포털")

tab_att, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⏰ 출퇴근 & 연차 등록",
    "✍️ 보고서 작성", 
    "🔍 내 보고서 관리", 
    "👨‍💼 부서장 통합 보고", 
    "📊 종합 대시보드",
    "📈 월간 근태 분석"
])

# --------------------------------
# 탭 0: 실시간 출퇴근 및 연차/휴가 등록 (신규 기능)
# --------------------------------
with tab_att:
    st.header(f"⏰ {user_name}님의 출퇴근 및 근태 관리")
    today_str = str(date.today())
    now_time_display = datetime.now().strftime("%H:%M")
    st.caption(f"📅 오늘 날짜: **{today_str}** | 🕒 현재 시간: **{now_time_display}**")
    
    # 오늘 나의 근태 현황 불러오기
    live_df = get_data("live_attendance")
    my_status = None
    if not live_df.empty and 'date' in live_df.columns and 'name' in live_df.columns:
        live_df['date'] = live_df['date'].astype(str)
        live_df['name'] = live_df['name'].astype(str)
        row = live_df[(live_df['date'] == today_str) & (live_df['name'] == user_name)]
        if not row.empty:
            my_status = row.iloc[0]
            
    # 상단 요약 카드
    st.markdown("#### 📌 오늘 나의 출퇴근 상태")
    c_st1, c_st2, c_st3, c_st4 = st.columns(4)
    c_st1.metric("근태 유형", my_status['type'] if my_status is not None else "미기록")
    c_st2.metric("출근 시간", my_status['check_in'] if my_status is not None else "-")
    c_st3.metric("퇴근 시간", my_status['check_out'] if my_status is not None else "-")
    c_st4.metric("메모/비고", my_status['note'] if my_status is not None and pd.notna(my_status['note']) else "-")
    
    st.markdown("---")
    
    col_inout, col_leave = st.columns(2)
    
    # 1. 원클릭 출퇴근 체크
    with col_inout:
        st.subheader("🏢 출퇴근 체크")
        att_note = st.text_input("출퇴근 비고 (선택사항, 예: 외근 후 바로 출근)", key="att_note_input")
        
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🟢 출근하기", use_container_width=True, type="primary"):
                dept = st.session_state.user_info.get("department", "환경사업부")
                success, msg = record_attendance(user_name, dept, "출근", att_note)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
        with btn_c2:
            if st.button("🔴 퇴근하기", use_container_width=True):
                dept = st.session_state.user_info.get("department", "환경사업부")
                success, msg = record_attendance(user_name, dept, "퇴근", att_note)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)

    # 2. 연차 / 반차 / 출장 신청
    with col_leave:
        st.subheader("🌴 연차 / 반차 / 휴가 / 출장 등록")
        with st.form("leave_form"):
            leave_type = st.selectbox("근태 유형 선택", ["연차", "오전반차", "오후반차", "대체휴무", "경조휴가", "출장", "재택근무"])
            leave_reason = st.text_input("사유 및 목적지 (예: 제주출장, 개인연차)", placeholder="사유를 입력해 주세요")
            
            if st.form_submit_button("근태 등록하기", use_container_width=True, type="primary"):
                dept = st.session_state.user_info.get("department", "환경사업부")
                success, msg = record_attendance(user_name, dept, leave_type, leave_reason)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
                    
    st.markdown("---")
    st.subheader("📋 오늘의 전 직원 근태 현황")
    if not live_df.empty:
        today_all = live_df[live_df['date'] == today_str].copy()
        if not today_all.empty:
            display_live = today_all.rename(columns={
                'name': '이름', 'department': '부서', 'type': '구분', 
                'check_in': '출근시간', 'check_out': '퇴근시간', 'note': '비고'
            })[['부서', '이름', '구분', '출근시간', '퇴근시간', '비고']]
            st.dataframe(display_live, use_container_width=True, hide_index=True)
        else:
            st.info("오늘 아직 등록된 출퇴근/휴가 기록이 없습니다.")
    else:
        st.info("근태 기록 데이터가 없습니다.")

# --------------------------------
# 탭 1: 보고서 작성
# --------------------------------
with tab1:
    st.header("오늘의 업무를 기록해주세요")
    with st.form("report_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            report_date = st.date_input("날짜", date.today(), key="t1_date")
        with col2:
            default_dept = st.session_state.user_info.get("department", "환경사업부")
            dept_list = ["환경사업부", "시스템사업부", "총무부"]
            dept_index = dept_list.index(default_dept) if default_dept in dept_list else 0
            department = st.selectbox("소속 부서", dept_list, index=dept_index, key="t1_dept")
        with col3:
            name = st.text_input("이름", value=user_name if user_name != "기본관리자" else "", key="t1_name")

        st.markdown("---")
        today_result = st.text_area("1. 금일 업무 실적", placeholder="[프로젝트명] 세부 진행 내용 (진척도%)", height=150)
        tomorrow_plan = st.text_area("2. 명일 업무 계획", placeholder="[프로젝트명] 진행 예정 사항", height=100)
        issue = st.text_area("3. 특이사항 및 협조 요청", placeholder="이슈 및 타 부서 협조 사항", height=100)

        if st.form_submit_button("일일업무보고 제출하기", type="primary"):
            if not name.strip():
                st.error("이름을 입력해주세요.")
            else:
                insert_report(report_date, department, name, today_result, tomorrow_plan, issue)
                st.success(f"{name}님의 업무보고가 성공적으로 제출되었습니다!")

# --------------------------------
# 탭 2: 내 보고서 관리
# --------------------------------
with tab2:
    st.header("🔍 내 업무보고 조회 및 수정")
    col1, col2 = st.columns(2)
    with col1:
        search_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="search_dept")
    with col2:
        search_name = st.text_input("본인 이름 입력", value=user_name, key="search_name")

    if search_name.strip():
        df = get_data("reports")
        if not df.empty and 'department' in df.columns and 'name' in df.columns:
            my_df = df[(df['department'] == search_dept) & (df['name'] == search_name)].copy()
            if not my_df.empty:
                my_df = my_df.sort_values(by='report_date', ascending=False)
                st.subheader(f"{search_name}님의 과거 보고 내역")
                display_cols = {'report_date': '날짜', 'department': '부서', 'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'}
                display_df = my_df.rename(columns=display_cols)
                if 'id' in display_df.columns:
                    display_df = display_df.drop(columns=['id'])
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.subheader("📝 내 보고서 수정")
                report_options = {f"{row['report_date']} 업무보고": row['id'] for _, row in my_df.iterrows() if 'id' in row}
                selected_label = st.selectbox("수정/삭제할 보고서 날짜를 선택하세요", list(report_options.keys()), key="my_report_select")

                if selected_label:
                    selected_id = str(report_options[selected_label])
                    selected_row = my_df[my_df['id'].astype(str) == selected_id].iloc[0]
                    with st.form(key=f"my_edit_form_{selected_id}"):
                        edit_today = st.text_area("1. 금일 업무 실적", value=selected_row.get('today_result', ''), height=150)
                        edit_tomorrow = st.text_area("2. 명일 업무 계획", value=selected_row.get('tomorrow_plan', ''), height=100)
                        edit_issue = st.text_area("3. 특이사항 및 협조 요청", value=selected_row.get('issue', ''), height=100)

                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.form_submit_button("내 보고서 수정하기", type="primary"):
                                update_report(selected_id, edit_today, edit_tomorrow, edit_issue)
                                st.success("수정 완료! 화면을 새로고침합니다.")
                                st.rerun()
                        with btn_col2:
                            if st.form_submit_button("이 보고서 삭제"):
                                delete_report(selected_id)
                                st.warning("삭제 완료! 화면을 새로고침합니다.")
                                st.rerun()
            else:
                st.info(f"'{search_name}'님으로 등록된 업무보고가 없습니다.")

# --------------------------------
# 탭 3: 부서장 통합 보고
# --------------------------------
with tab3:
    st.header("부서 통합 업무보고 취합")
    col1, col2 = st.columns(2)
    with col1:
        m_date = st.date_input("확인할 날짜", date.today(), key="m_date")
    with col2:
        m_dept = st.selectbox("관리 부서", ["환경사업부", "시스템사업부", "총무부"], key="m_dept")

    df = get_data("reports")
    m_df = pd.DataFrame()
    if not df.empty and 'report_date' in df.columns and 'department' in df.columns:
        df['report_date'] = df['report_date'].astype(str)
        m_df = df[(df['report_date'] == str(m_date)) & (df['department'] == m_dept)].copy()

    st.subheader(f"👥 {m_dept} 팀원 개별 보고 내역")
    if not m_df.empty:
        display_m_df = m_df.rename(columns={
            'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
        })
        show_cols = [c for c in ['이름', '금일 실적', '명일 계획', '특이사항'] if c in display_m_df.columns]
        st.dataframe(display_m_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("아직 해당 날짜에 제출된 팀원 보고서가 없습니다.")

    st.markdown("---")
    st.subheader("📝 부서 통합 보고서 작성")
    with st.form("consolidated_form", clear_on_submit=False):
        m_name = st.text_input("부서장 이름", key="m_name")
        c_today = st.text_area("1. 부서 통합 금일 실적", placeholder="팀원들의 실적을 요약하여 작성해주세요.", height=150)
        c_tomorrow = st.text_area("2. 부서 통합 명일 계획", height=100)
        c_issue = st.text_area("3. 특이사항 및 대표님 보고 사항", height=100)

        if st.form_submit_button("부서 통합 업무보고 제출", type="primary"):
            if not m_name.strip():
                st.error("부서장 이름을 입력해주세요.")
            else:
                save_consolidated_report(m_date, m_dept, m_name, c_today, c_tomorrow, c_issue)
                st.success(f"{m_dept} 통합 보고서가 등록되었습니다.")

# --------------------------------
# 탭 4: 종합 대시보드
# --------------------------------
with tab4:
    st.header("부서별 업무보고 종합 대시보드")
    col1, col2 = st.columns(2)
    with col1:
        filter_date = st.date_input("조회할 날짜 선택", date.today(), key="filter_date")
    with col2:
        filter_dept = st.selectbox("부서 필터링", ["전체", "환경사업부", "시스템사업부", "총무부"], key="filter_dept")

    raw_c_df = get_data("consolidated_reports")
    raw_i_df = get_data("reports")

    c_df, i_df = pd.DataFrame(), pd.DataFrame()
    if not raw_c_df.empty and 'report_date' in raw_c_df.columns:
        raw_c_df['report_date'] = raw_c_df['report_date'].astype(str)
        c_df = raw_c_df[raw_c_df['report_date'] == str(filter_date)].copy() if filter_dept == "전체" else raw_c_df[
            (raw_c_df['report_date'] == str(filter_date)) & (raw_c_df['department'] == filter_dept)].copy()

    if not raw_i_df.empty and 'report_date' in raw_i_df.columns:
        raw_i_df['report_date'] = raw_i_df['report_date'].astype(str)
        i_df = raw_i_df[raw_i_df['report_date'] == str(filter_date)].copy() if filter_dept == "전체" else raw_i_df[
            (raw_i_df['report_date'] == str(filter_date)) & (raw_i_df['department'] == filter_dept)].copy()

    dash_tab1, dash_tab2 = st.tabs(["🌟 부서별 전체보기 (부서장 통합보고)", "👥 팀원 개별 보고 상세"])

    with dash_tab1:
        st.subheader("전체 부서 통합 요약" if filter_dept == "전체" else f"{filter_dept} 통합 요약")
        if not c_df.empty:
            display_c_df = c_df.rename(columns={
                'department': '부서', 'manager_name': '부서장',
                'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
            })
            show_cols = [c for c in ['부서', '부서장', '금일 실적', '명일 계획', '특이사항'] if c in display_c_df.columns]
            st.dataframe(display_c_df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.info("해당 조건으로 등록된 부서장 통합 보고서가 없습니다.")

    with dash_tab2:
        st.subheader("모든 팀원 개별 상세 내역" if filter_dept == "전체" else f"{filter_dept} 팀원 개별 상세 내역")
        st.caption("💡 아래 표에서 직원의 행/셀을 마우스로 클릭하시면 하단에 [보고서 작성 양식] 형태로 상세 내용이 표시됩니다.")
        
        if not i_df.empty:
            display_i_df = i_df.rename(columns={
                'department': '부서', 'name': '이름',
                'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
            })
            show_cols = [c for c in ['부서', '이름', '금일 실적', '명일 계획', '특이사항'] if c in display_i_df.columns]
            display_i_df = display_i_df[show_cols].reset_index(drop=True)

            selection = st.dataframe(
                display_i_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            selected_rows = selection.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                selected_row = i_df.iloc[selected_idx]

                st.markdown("---")
                st.subheader(f"📄 [{selected_row.get('department', '')}] {selected_row.get('name', '')}님의 업무보고 상세")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.text_input("날짜", value=str(selected_row.get('report_date', '')), disabled=True, key="view_date")
                with c2:
                    st.text_input("소속 부서", value=str(selected_row.get('department', '')), disabled=True, key="view_dept")
                with c3:
                    st.text_input("이름", value=str(selected_row.get('name', '')), disabled=True, key="view_name")

                st.text_area("1. 금일 업무 실적", value=str(selected_row.get('today_result', '')), height=150, disabled=True, key="view_today")
                st.text_area("2. 명일 업무 계획", value=str(selected_row.get('tomorrow_plan', '')), height=100, disabled=True, key="view_tomorrow")
                st.text_area("3. 특이사항 및 협조 요청", value=str(selected_row.get('issue', '')), height=100, disabled=True, key="view_issue")

            if st.session_state.user_info.get("role") == "admin":
                with st.expander("👑 관리자 전용 개별 보고서 강제 수정/삭제"):
                    report_options = {f"{row.get('name', '')} ({row.get('department', '')})": row['id'] for _, row in i_df.iterrows() if 'id' in row}
                    if report_options:
                        selected_label = st.selectbox("조치할 직원의 보고서를 선택하세요", list(report_options.keys()))
                        if selected_label:
                            selected_id = str(report_options[selected_label])
                            selected_row = i_df[i_df['id'].astype(str) == selected_id].iloc[0]
                            with st.form(key=f"admin_edit_form_{selected_id}"):
                                edit_today = st.text_area("1. 금일 업무 실적", value=selected_row.get('today_result', ''), height=150)
                                edit_tomorrow = st.text_area("2. 명일 업무 계획", value=selected_row.get('tomorrow_plan', ''), height=100)
                                edit_issue = st.text_area("3. 특이사항 및 협조 요청", value=selected_row.get('issue', ''), height=100)
                                btn_col1, btn_col2 = st.columns(2)
                                with btn_col1:
                                    if st.form_submit_button("강제 수정", type="primary"):
                                        update_report(selected_id, edit_today, edit_tomorrow, edit_issue)
                                        st.success("수정되었습니다.")
                                        st.rerun()
                                with btn_col2:
                                    if st.form_submit_button("강제 삭제"):
                                        delete_report(selected_id)
                                        st.warning("삭제되었습니다.")
                                        st.rerun()
        else:
            st.info("해당 조건으로 제출된 개별 보고서가 없습니다.")

# --------------------------------
# 탭 5: 월간 근태 분석 (엑셀 업로드 분석)
# --------------------------------
with tab5:
    st.header("📈 임직원 월간 근태 분석 & 관리")
    st.caption("로커스솔루션 근태기록 엑셀 파일(.xlsx)을 업로드하면 자동으로 통계 및 이상 근태를 분석합니다.")
    
    uploaded_file = st.file_uploader("월간 근태기록 엑셀 파일 업로드", type=["xlsx", "xls"], key="attendance_uploader")
    
    if uploaded_file is not None:
        try:
            att_df = pd.read_excel(uploaded_file, sheet_name=0)
            req_cols = ['근무일자', '이름', '출근판정', '퇴근판정', '총근무시간', '연장근무시간']
            if all(col in att_df.columns for col in req_cols):
                
                att_df['총근무_분'] = att_df['총근무시간'].apply(time_to_minutes)
                att_df['연장근무_분'] = att_df['연장근무시간'].apply(time_to_minutes)
                att_df['지각여부'] = att_df['출근판정'] == '지각'
                att_df['결근여부'] = att_df['출근판정'] == '결근'
                att_df['조퇴여부'] = att_df['퇴근판정'] == '조퇴'
                
                total_emps = att_df['이름'].nunique()
                total_work_hours = att_df['총근무_분'].sum() / 60
                total_over_hours = att_df['연장근무_분'].sum() / 60
                total_late_cnt = att_df['지각여부'].sum()
                total_early_cnt = att_df['조퇴여부'].sum()
                
                st.markdown("### 📊 전체 근태 종합 요약")
                kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
                kpi1.metric("총 대상 인원", f"{total_emps}명")
                kpi2.metric("총 근무 시간", f"{total_work_hours:,.1f}시간")
                kpi3.metric("총 연장근무", f"{total_over_hours:,.1f}시간")
                kpi4.metric("총 지각 발생", f"{total_late_cnt}건")
                kpi5.metric("총 조퇴 발생", f"{total_early_cnt}건")
                
                st.markdown("---")
                
                emp_summary = att_df.groupby('이름').agg(
                    근무일수=('근무일자', 'count'),
                    정상출근일수=('출근판정', lambda x: (x == '정상출근').sum()),
                    지각횟수=('지각여부', 'sum'),
                    조퇴횟수=('조퇴여부', 'sum'),
                    출장휴가등_결근=('결근여부', 'sum'),
                    총근무시간=('총근무_분', lambda x: round(sum(x) / 60, 1)),
                    총연장근무=('연장근무_분', lambda x: round(sum(x) / 60, 1))
                ).reset_index()
                
                emp_summary = emp_summary.sort_values(by='총근무시간', ascending=False).reset_index(drop=True)
                
                sub_tab1, sub_tab2 = st.tabs(["🏆 직원별 근태 순위 요약", "🔍 개인별 상세 출퇴근 타임라인"])
                
                with sub_tab1:
                    st.subheader("직원별 근태 통계 순위")
                    display_summary = emp_summary.rename(columns={
                        '이름': '직원명', '근무일수': '기록일수', '정상출근일수': '정상 출근',
                        '지각횟수': '지각(회)', '조퇴횟수': '조퇴(회)', '출장휴가등_결근': '출장/휴가(결근)',
                        '총근무시간': '총 근무(시간)', '총연장근무': '연장근무(시간)'
                    })
                    st.dataframe(display_summary, use_container_width=True, hide_index=True)
                    
                    st.markdown("#### 💡 관리자 점검 체크포인트")
                    c_warn1, c_warn2 = st.columns(2)
                    with c_warn1:
                        over_top = emp_summary.sort_values(by='총연장근무', ascending=False).head(3)
                        st.info(f"🔥 **연장근무 상위자 Top 3**: " + ", ".join([f"{r['이름']} ({r['총연장근무']}h)" for _, r in over_top.iterrows()]))
                    with c_warn2:
                        late_top = emp_summary[emp_summary['지각횟수'] > 0].sort_values(by='지각횟수', ascending=False)
                        if not late_top.empty:
                            st.warning(f"⚠️ **지각 발생 인원**: " + ", ".join([f"{r['이름']} ({r['지각횟수']}회)" for _, r in late_top.iterrows()]))
                        else:
                            st.success("✅ 지각자가 없습니다.")
                            
                with sub_tab2:
                    st.subheader("개인별 상세 출퇴근 기록")
                    selected_emp = st.selectbox("조회할 직원을 선택하세요", emp_summary['이름'].tolist(), key="att_emp_select")
                    
                    if selected_emp:
                        user_att = att_df[att_df['이름'] == selected_emp].copy()
                        user_att['근무일자'] = user_att['근무일자'].astype(str)
                        show_cols = ['근무일자', '출근시간', '퇴근시간', '출근판정', '퇴근판정', '총근무시간', '연장근무시간']
                        present_cols = [c for c in show_cols if c in user_att.columns]
                        st.dataframe(user_att[present_cols], use_container_width=True, hide_index=True)
            else:
                st.error("엑셀 파일 양식이 맞지 않습니다. ('근무일자', '이름', '출근판정', '총근무시간' 컬럼이 포함되어야 합니다.)")
        except Exception as e:
            st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
    else:
        st.info("👆 위 파일 업로더에 근태 엑셀 파일(예: 2026년 7월.xlsx)을 업로드해 주세요.")
