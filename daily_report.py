import streamlit as st
from db_manager import get_user_credentials, add_user, delete_user, get_data
from tab_approval import render_approval_tab
from tab_attendance import render_attendance_tab
from tab_reports import render_report_portal

st.set_page_config(page_title="로커스솔루션 통합 업무 포털", layout="wide")

# --------------------------------
# 메인 탭 글자 크기 적정화 및 위계 조절 CSS
# --------------------------------
st.markdown("""
<style>
    div[data-testid="stTabs"] > div:first-child button[data-baseweb="tab"] {
        font-size: 1.12rem !important;
        font-weight: 700 !important;
        padding: 10px 20px !important;
        color: #4A5568 !important;
        letter-spacing: -0.3px;
    }
    div[data-testid="stTabs"] > div:first-child button[aria-selected="true"] {
        color: #1E88E5 !important;
        border-bottom: 3px solid #1E88E5 !important;
    }
    div[data-testid="stTabs"] div[data-testid="stTabs"] > div:first-child button[data-baseweb="tab"] {
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        padding: 6px 14px !important;
        color: #718096 !important;
    }
    div[data-testid="stTabs"] div[data-testid="stTabs"] > div:first-child button[aria-selected="true"] {
        color: #2D3748 !important;
        border-bottom: 2px solid #2D3748 !important;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------
# 세션 초기화 및 F5 새로고침 자동 로그인 복구
# --------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

# URL 쿼리 파라미터에 user 정보가 있으면 F5 새로고침 시에도 로그인 유지
if not st.session_state.logged_in:
    saved_user_id = st.query_params.get("user", None)
    if saved_user_id:
        credentials = get_user_credentials()
        if saved_user_id in credentials:
            st.session_state.logged_in = True
            st.session_state.user_info = credentials[saved_user_id]
            st.session_state.user_info["username"] = saved_user_id

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
                # F5 새로고침 유지를 위해 URL 파라미터에 아이디 기록
                st.query_params["user"] = input_id
                st.success(f"{credentials[input_id]['name']}님, 환영합니다!")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    with tab_signup:
        st.write("신규 사용자를 등록합니다.")
        new_id = st.text_input("아이디 (ID)", key="dlg_reg_id")
        new_pw = st.text_input("비밀번호 (Password)", type="password", key="dlg_reg_pw")
        new_name = st.text_input("이름 (실명)", key="dlg_reg_name")
        new_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="dlg_reg_dept")
        if st.button("등록하기", type="primary", use_container_width=True, key="dlg_reg_btn"):
            if new_id.strip() and new_pw.strip() and new_name.strip():
                success, msg = add_user(new_id.strip(), new_pw.strip(), new_name.strip(), role="user", department=new_dept)
                if success:
                    st.success(msg + " [🔑 로그인] 탭에서 로그인해 주세요.")
                else:
                    st.error(msg)
            else:
                st.error("모든 항목을 입력해 주세요.")
    with tab_users:
        users_df = get_data("users")
        if not users_df.empty:
            st.dataframe(users_df[['username', 'name', 'department', 'role']].rename(columns={'username': '아이디', 'name': '이름', 'department': '소속 부서', 'role': '권한'}), use_container_width=True, hide_index=True)
        else:
            st.info("등록된 사용자 정보가 없습니다.")

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
    user_role_raw = st.session_state.user_info.get('role', 'user')
    user_role_label = "👑 총괄 관리자" if user_role_raw == "admin" else "💼 일반 임직원"
    st.write(f"**이름**: {user_name} | **부서**: {user_dept}")
    st.write(f"**권한**: {user_role_label}")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.query_params.clear()  # 로그아웃 시 URL 쿼리 파라미터 초기화
        st.rerun()
    if user_role_raw == "admin":
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

# 메인 3대 포털 탭
st.title("📋 로커스솔루션 통합 업무 포털")
main_tab1, main_tab2, main_tab3 = st.tabs([
    "📑 전자결재 & 지출품의",
    "⏰ 근태 관리 포털",
    "📋 업무보고 관리 포털"
])

with main_tab1:
    render_approval_tab(user_name, user_dept, user_role_raw)
with main_tab2:
    render_attendance_tab(user_name, user_dept)
with main_tab3:
    render_report_portal(user_name, user_dept)
