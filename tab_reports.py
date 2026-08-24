import streamlit as st
import pandas as pd
from db_manager import (
    get_kst_date, get_data, insert_report, update_report,
    delete_report, save_consolidated_report
)

def render_report_create_tab(user_name, user_dept):
    st.header("오늘의 업무를 기록해주세요")
    with st.form("report_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1: report_date = st.date_input("날짜", get_kst_date(), key="t1_date")
        with col2:
            dept_list = ["환경사업부", "시스템사업부", "총무부"]
            idx = dept_list.index(user_dept) if user_dept in dept_list else 0
            department = st.selectbox("소속 부서", dept_list, index=idx, key="t1_dept")
        with col3: name = st.text_input("이름", value=user_name if user_name != "기본관리자" else "", key="t1_name")
        st.markdown("---")
        today_result = st.text_area("1. 금일 업무 실적", placeholder="[프로젝트명] 세부 진행 내용 (진척도%)", height=150)
        tomorrow_plan = st.text_area("2. 명일 업무 계획", placeholder="[프로젝트명] 진행 예정 사항", height=100)
        issue = st.text_area("3. 특이사항 및 협조 요청", placeholder="이슈 및 타 부서 협조 사항", height=100)
        if st.form_submit_button("일일업무보고 제출하기", type="primary"):
            if not name.strip(): st.error("이름을 입력해주세요.")
            else:
                insert_report(report_date, department, name, today_result, tomorrow_plan, issue)
                st.success(f"{name}님의 업무보고가 성공적으로 제출되었습니다!")

def render_my_reports_tab(user_name):
    st.header("🔍 내 업무보고 조회 및 수정")
    col1, col2 = st.columns(2)
    with col1: search_dept = st.selectbox("소속 부서", ["환경사업부", "시스템사업부", "총무부"], key="search_dept")
    with col2: search_name = st.text_input("본인 이름 입력", value=user_name, key="search_name")
    if search_name.strip():
        df = get_data("reports")
        if not df.empty and 'department' in df.columns and 'name' in df.columns:
            my_df = df[(df['department'] == search_dept) & (df['name'] == search_name)].copy()
            if not my_df.empty:
                my_df = my_df.sort_values(by='report_date', ascending=False)
                st.subheader(f"{search_name}님의 과거 보고 내역")
                if 'status' not in my_df.columns: my_df['status'] = '제출완료'
                if 'comment' not in my_df.columns: my_df['comment'] = ''
                display_cols = {'report_date': '날짜', 'department': '부서', 'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항', 'status': '승인상태', 'comment': '피드백/코멘트'}
                display_df = my_df.rename(columns=display_cols)
                if 'id' in display_df.columns: display_df = display_df.drop(columns=['id'])
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
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.form_submit_button("내 보고서 수정하기", type="primary"):
                                update_report(selected_id, edit_today, edit_tomorrow, edit_issue)
                                st.success("수정 완료!"); st.rerun()
                        with b2:
                            if st.form_submit_button("이 보고서 삭제"):
                                delete_report(selected_id)
                                st.warning("삭제 완료!"); st.rerun()
            else: st.info(f"'{search_name}'님으로 등록된 업무보고가 없습니다.")

def render_consolidated_tab():
    st.header("부서 통합 업무보고 취합")
    col1, col2 = st.columns(2)
    with col1: m_date = st.date_input("확인할 날짜", get_kst_date(), key="m_date")
    with col2: m_dept = st.selectbox("관리 부서", ["환경사업부", "시스템사업부", "총무부"], key="m_dept")
    df = get_data("reports")
    m_df = pd.DataFrame()
    if not df.empty and 'report_date' in df.columns and 'department' in df.columns:
        df['report_date'] = df['report_date'].astype(str)
        m_df = df[(df['report_date'] == str(m_date)) & (df['department'] == m_dept)].copy()
    st.subheader(f"👥 {m_dept} 팀원 개별 보고 내역")
    if not m_df.empty:
        if 'status' not in m_df.columns: m_df['status'] = '제출완료'
        display_m_df = m_df.rename(columns={'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항', 'status': '승인상태'})
        show_cols = [c for c in ['이름', '금일 실적', '명일 계획', '특이사항', '승인상태'] if c in display_m_df.columns]
        st.dataframe(display_m_df[show_cols], use_container_width=True, hide_index=True)
    else: st.info("아직 해당 날짜에 제출된 팀원 보고서가 없습니다.")
    st.markdown("---")
    st.subheader("📝 부서 통합 보고서 작성")
    with st.form("consolidated_form", clear_on_submit=False):
        m_name = st.text_input("부서장 이름", key="m_name")
        c_today = st.text_area("1. 부서 통합 금일 실적", placeholder="팀원들의 실적을 요약하여 작성해주세요.", height=150)
        c_tomorrow = st.text_area("2. 부서 통합 명일 계획", height=100)
        c_issue = st.text_area("3. 특이사항 및 대표님 보고 사항", height=100)
        if st.form_submit_button("부서 통합 업무보고 제출", type="primary"):
            if not m_name.strip(): st.error("부서장 이름을 입력해주세요.")
            else:
                save_consolidated_report(m_date, m_dept, m_name, c_today, c_tomorrow, c_issue)
                st.success(f"{m_dept} 통합 보고서가 등록되었습니다.")
