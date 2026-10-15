import streamlit as st
from db_manager import get_user_credentials, add_user, update_user_position, delete_user, get_data
from tab_approval import render_approval_tab
from tab_attendance import render_attendance_tab
from tab_reports import render_report_portal

st.set_page_config(page_title="로커스솔루션 통합 업무 포털", layout="wide")

POSITIONS_LIST = ["사원", "주임", "선임", "대리", "과장", "차장", "부장", "팀장", "부서장", "이사", "상무", "전무", "부사장", "대표이사"]

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
                st.query_params["user"] = input_id
                st.success(f"{credentials[input_id]['name']} ({credentials[input_id].get('position', '사원')})님, 환영합니다!")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    with tab_signup:
        st.write("신규 사용자를 등록합니다.")
        c1, c2 = st.columns(2)
        with c1:
            new_id = st.text_input("아이디 (ID)", key="dlg_reg_id")
            new_pw = st.text_input("비밀번호 (Password)", type="password", key="dlg_reg_pw")
            new_name = st.text_input("이름 (실명)", key="dlg_reg_name")
        with c2:
            new_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="dlg_reg_dept")
            new_pos = st.selectbox("직책", POSITIONS_LIST, key="dlg_reg_pos")
            
        if st.button("등록하기", type="primary", use_container_width=True, key="dlg_reg_btn"):
            if new_id.strip() and new_pw.strip() and new_name.strip():
                success, msg = add_user(new_id.strip(), new_pw.strip(), new_name.strip(), role="user", department=new_dept, position=new_pos)
                if success:
                    st.success(msg + " [🔑 로그인] 탭에서 로그인해 주세요.")
                else:
                    st.error(msg)
            else:
                st.error("모든 항목을 입력해 주세요.")
    with tab_users:
        users_df = get_data("users")
        if not users_df.empty:
            for col in ['username', 'name', 'position', 'department', 'role']:
                if col not in users_df.columns:
                    users_df[col] = "사원" if col == "position" else ""
            users_df['position'] = users_df['position'].apply(lambda x: x if str(x).strip() != "" else "사원")
            st.dataframe(
                users_df[['username', 'name', 'position', 'department', 'role']].rename(
                    columns={'username': '아이디', 'name': '이름', 'position': '직책', 'department': '소속 부서', 'role': '권한'}
                ),
                use_container_width=True, hide_index=True
            )
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
    user_id = st.session_state.user_info.get('username', '')
    user_name = st.session_state.user_info.get('name', '사용자')
    user_dept = st.session_state.user_info.get('department', '환경사업부')
    user_pos = st.session_state.user_info.get('position', '사원')
    user_role_raw = st.session_state.user_info.get('role', 'user')
    user_role_label = "👑 총괄 관리자" if user_role_raw == "admin" else "💼 일반 임직원"
    
    st.write(f"**이름**: {user_name} ({user_pos})")
    st.write(f"**부서**: {user_dept} | **권한**: {user_role_label}")
    
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.query_params.clear()
        st.rerun()

    # 내 직책/부서 변경 패널
    with st.expander("✏️ 내 직책 / 부서 정보 변경"):
        dept_opts = ["환경사업부", "시스템사업부", "총무부"]
        d_idx = dept_opts.index(user_dept) if user_dept in dept_opts else 0
        my_new_dept = st.selectbox("부서 변경", dept_opts, index=d_idx, key="side_my_dept")
        p_idx = POSITIONS_LIST.index(user_pos) if user_pos in POSITIONS_LIST else 0
        my_new_pos = st.selectbox("직책 변경", POSITIONS_LIST, index=p_idx, key="side_my_pos")
        if st.button("내 정보 저장", use_container_width=True, key="side_save_my_info"):
            ok, msg = update_user_position(user_id, my_new_dept, my_new_pos)
            if ok:
                st.session_state.user_info['department'] = my_new_dept
                st.session_state.user_info['position'] = my_new_pos
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    if user_role_raw == "admin":
        st.markdown("---")
        with st.expander("⚙️ 임직원 직책/계정 관리 (Admin)"):
            all_users = get_user_credentials()
            target_u = st.selectbox("대상 계정 선택", list(all_users.keys()), format_func=lambda k: f"{all_users[k]['name']} ({all_users[k].get('position', '사원')} | {k})")
            if target_u:
                u_info = all_users[target_u]
                dept_list = ["환경사업부", "시스템사업부", "총무부"]
                ud_idx = dept_list.index(u_info.get('department')) if u_info.get('department') in dept_list else 0
                adm_dept = st.selectbox("부서 지정", dept_list, index=ud_idx, key="adm_edit_dept")
                up_idx = POSITIONS_LIST.index(u_info.get('position')) if u_info.get('position') in POSITIONS_LIST else 0
                adm_pos = st.selectbox("직책 지정", POSITIONS_LIST, index=up_idx, key="adm_edit_pos")
                if st.button("직책/부서 수정 적용", type="primary", use_container_width=True):
                    ok, msg = update_user_position(target_u, adm_dept, adm_pos)
                    if ok:
                        st.success(msg); st.rerun()
                    else:
                        st.error(msg)
                if target_u != "admin":
                    if st.button("🗑️ 이 계정 삭제", use_container_width=True):
                        ok, msg = delete_user(target_u)
                        if ok:
                            st.warning(msg); st.rerun()
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
