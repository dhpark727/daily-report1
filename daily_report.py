import streamlit as st
import pandas as pd
from datetime import date
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
                df = pd.DataFrame(
                    columns=['id', 'report_date', 'department', 'name', 'today_result', 'tomorrow_plan', 'issue'])
            else:
                df = pd.DataFrame(
                    columns=['id', 'report_date', 'department', 'manager_name', 'today_result', 'tomorrow_plan',
                             'issue'])
        return df
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
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
    if not df.empty:
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
    if not df.empty:
        df['id'] = df['id'].astype(str)
        idx = df[df['id'] == str(report_id)].index
        if len(idx) > 0:
            df.loc[idx, 'today_result'] = today_result
            df.loc[idx, 'tomorrow_plan'] = tomorrow_plan
            df.loc[idx, 'issue'] = issue
            save_data("reports", df)


def delete_report(report_id):
    df = get_data("reports")
    if not df.empty:
        df['id'] = df['id'].astype(str)
        updated_df = df[df['id'] != str(report_id)]
        save_data("reports", updated_df)


# --------------------------------
# 2. 웹 인터페이스 (UI) 설정
# --------------------------------
st.set_page_config(page_title="일일 업무보고 시스템", layout="wide")
st.title("📋 일일 업무보고 시스템")

tab1, tab2, tab3, tab4 = st.tabs(["✍️ 보고서 작성", "🔍 내 보고서 관리", "👨‍💼 부서장 통합 보고", "📊 종합 대시보드"])

# 탭 1: 보고서 작성
with tab1:
    st.header("오늘의 업무를 기록해주세요")
    with st.form("report_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            report_date = st.date_input("날짜", date.today(), key="t1_date")
        with col2:
            department = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="t1_dept")
        with col3:
            name = st.text_input("이름", key="t1_name")

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

# 탭 2: 내 보고서 관리
with tab2:
    st.header("🔍 내 업무보고 조회 및 수정")
    col1, col2 = st.columns(2)
    with col1:
        search_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="search_dept")
    with col2:
        search_name = st.text_input("본인 이름 입력", key="search_name", placeholder="조회할 이름을 입력하고 엔터를 누르세요")

    if search_name.strip():
        df = get_data("reports")
        if not df.empty:
            my_df = df[(df['department'] == search_dept) & (df['name'] == search_name)].copy()
            if not my_df.empty:
                my_df = my_df.sort_values(by='report_date', ascending=False)
                st.subheader(f"{search_name}님의 과거 보고 내역")
                display_df = my_df.rename(columns={
                    'report_date': '날짜', 'department': '부서', 'name': '이름',
                    'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
                }).drop(columns=['id'])
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.subheader("📝 내 보고서 수정")
                report_options = {f"{row['report_date']} 업무보고": row['id'] for _, row in my_df.iterrows()}
                selected_label = st.selectbox("수정/삭제할 보고서 날짜를 선택하세요", list(report_options.keys()),
                                              key="my_report_select")

                if selected_label:
                    selected_id = str(report_options[selected_label])
                    selected_row = my_df[my_df['id'].astype(str) == selected_id].iloc[0]
                    with st.form(key=f"my_edit_form_{selected_id}"):
                        edit_today = st.text_area("1. 금일 업무 실적", value=selected_row['today_result'], height=150)
                        edit_tomorrow = st.text_area("2. 명일 업무 계획", value=selected_row['tomorrow_plan'], height=100)
                        edit_issue = st.text_area("3. 특이사항 및 협조 요청", value=selected_row['issue'], height=100)

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

# 탭 3: 부서장 통합 보고
with tab3:
    st.header("부서 통합 업무보고 취합")
    col1, col2 = st.columns(2)
    with col1:
        m_date = st.date_input("확인할 날짜", date.today(), key="m_date")
    with col2:
        m_dept = st.selectbox("관리 부서", ["환경사업부", "시스템사업부", "총무부"], key="m_dept")

    df = get_data("reports")
    m_df = pd.DataFrame()
    if not df.empty:
        df['report_date'] = df['report_date'].astype(str)
        m_df = df[(df['report_date'] == str(m_date)) & (df['department'] == m_dept)].copy()

    st.subheader(f"👥 {m_dept} 팀원 개별 보고 내역")
    if not m_df.empty:
        display_m_df = m_df.rename(columns={
            'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
        })[['이름', '금일 실적', '명일 계획', '특이사항']]
        st.dataframe(display_m_df, use_container_width=True, hide_index=True)
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

# 탭 4: 종합 대시보드
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
    if not raw_c_df.empty:
        raw_c_df['report_date'] = raw_c_df['report_date'].astype(str)
        c_df = raw_c_df[raw_c_df['report_date'] == str(filter_date)].copy() if filter_dept == "전체" else raw_c_df[
            (raw_c_df['report_date'] == str(filter_date)) & (raw_c_df['department'] == filter_dept)].copy()

    if not raw_i_df.empty:
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
            })[['부서', '부서장', '금일 실적', '명일 계획', '특이사항']]
            st.dataframe(display_c_df, use_container_width=True, hide_index=True)
        else:
            st.info("해당 조건으로 등록된 부서장 통합 보고서가 없습니다.")

    with dash_tab2:
        st.subheader("모든 팀원 개별 상세 내역" if filter_dept == "전체" else f"{filter_dept} 팀원 개별 상세 내역")
        if not i_df.empty:
            display_i_df = i_df.rename(columns={
                'department': '부서', 'name': '이름',
                'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'
            })[['부서', '이름', '금일 실적', '명일 계획', '특이사항']]
            st.dataframe(display_i_df, use_container_width=True, hide_index=True)

            with st.expander("관리자 전용 개별 보고서 강제 수정/삭제"):
                report_options = {f"{row['name']} ({row['department']})": row['id'] for _, row in i_df.iterrows()}
                selected_label = st.selectbox("조치할 직원의 보고서를 선택하세요", list(report_options.keys()))
                if selected_label:
                    selected_id = str(report_options[selected_label])
                    selected_row = i_df[i_df['id'].astype(str) == selected_id].iloc[0]
                    with st.form(key=f"admin_edit_form_{selected_id}"):
                        edit_today = st.text_area("1. 금일 업무 실적", value=selected_row['today_result'], height=150)
                        edit_tomorrow = st.text_area("2. 명일 업무 계획", value=selected_row['tomorrow_plan'], height=100)
                        edit_issue = st.text_area("3. 특이사항 및 협조 요청", value=selected_row['issue'], height=100)
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