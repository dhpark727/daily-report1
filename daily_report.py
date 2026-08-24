import streamlit as st
from db_manager import get_user_credentials, add_user, delete_user, get_data
from tab_attendance import render_attendance_tab
from tab_reports import render_report_create_tab, render_my_reports_tab, render_consolidated_tab
from tab_dashboard import render_work_dashboard_tab, render_attendance_analysis_tab

st.set_page_config(page_title="로커스솔루션 업무 & 근태 관리", layout="wide")

# 세션 초기화
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = None

# 로그인 팝업
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
                st.success(f"{credentials[input_id]['name']}님, 환영합니다!"); st.rerun()
            else: st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    with tab_signup:
        st.write("신규 사용자를 등록합니다.")
        new_id = st.text_input("아이디 (ID)", key="dlg_reg_id")
        new_pw = st.text_input("비밀번호 (Password)", type="password", key="dlg_reg_pw")
        new_name = st.text_input("이름 (실명)", key="dlg_reg_name")
        new_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="dlg_reg_dept")
        if st.button("등록하기", type="primary", use_container_width=True, key="dlg_reg_btn"):
            if new_id.strip() and new_pw.strip() and new_name.strip():
                success, msg = add_user(new_id.strip(), new_pw.strip(), new_name.strip(), role="user", department=new_dept)
                if success: st.success(msg + " [🔑 로그인] 탭에서 로그인해 주세요.")
                else: st.error(msg)
            else: st.error("모든 항목을 입력해 주세요.")
    with tab_users:
        users_df = get_data("users")
        if not users_df.empty:
            st.dataframe(users_df[['username', 'name', 'department', 'role']].rename(columns={'username': '아이디', 'name': '이름', 'department': '소속 부서', 'role': '권한'}), use_container_width=True, hide_index=True)
        else: st.info("등록된 사용자 정보가 없습니다.")

if not st.session_state.logged_in:
    st.title("📋 로커스솔루션 통합 업무 관리 포털")
    st.info("서비스를 이용하시려면 먼저 로그인을 완료해 주세요.")
    login_dialog()
    st.stop()

# 사이드바
with st.sidebar:
    st.markdown("### 👤 접속 정보")
    user_name = st.session_state.user_info.get('name', '사용자')
    user_dept = st.session_state.user_info.get('department', '환경사업부')
    user_role = "👑 총괄 관리자" if st.session_state.user_info.get('role') == "admin" else "💼 일반 임직원"
    st.write(f"**이름**: {user_name} | **권한**: {user_role}")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False; st.session_state.user_info = None; st.rerun()
    if st.session_state.user_info.get("role") == "admin":
        st.markdown("---")
        with st.expander("⚙️ 계정 삭제 관리 (Admin)"):
            all_users = get_user_credentials()
            del_target = st.selectbox("삭제할 계정 선택", [u for u in all_users.keys() if u != "admin"])
            if st.button("선택 계정 삭제", key="sidebar_del_btn"):
                if del_target:
                    success, msg = delete_user(del_target)
                    if success: st.warning(msg); st.rerun()
                    else: st.error(msg)

# 메인 탭 렌더링
st.title("📋 로커스솔루션 통합 업무 포털")
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⏰ 출퇴근 & 연차/출장 등록", "✍️ 업무보고 작성", "🔍 내 보고서 관리",
    "👨‍💼 부서장 통합 보고", "📊 업무 종합 대시보드", "📈 전사 근태 분석 현황"
])

with tab0: render_attendance_tab(user_name, user_dept)
with tab1: render_report_create_tab(user_name, user_dept)
with tab2: render_my_reports_tab(user_name)
with tab3: render_consolidated_tab()
with tab4: render_work_dashboard_tab(user_name)
with tab5: render_attendance_analysis_tab()
