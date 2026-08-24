import streamlit as st
import pandas as pd
from db_manager import get_kst_date, get_data, update_report_full, time_to_minutes

def render_work_dashboard_tab(user_name):
    st.header("부서별 업무보고 종합 대시보드")
    col1, col2 = st.columns(2)
    with col1: filter_date = st.date_input("조회할 날짜 선택", get_kst_date(), key="filter_date")
    with col2: filter_dept = st.selectbox("부서 필터링", ["전체", "환경사업부", "시스템사업부", "총무부"], key="filter_dept")

    raw_c_df = get_data("consolidated_reports")
    raw_i_df = get_data("reports")
    c_df, i_df = pd.DataFrame(), pd.DataFrame()
    if not raw_c_df.empty and 'report_date' in raw_c_df.columns:
        raw_c_df['report_date'] = raw_c_df['report_date'].astype(str)
        c_df = raw_c_df[raw_c_df['report_date'] == str(filter_date)].copy() if filter_dept == "전체" else raw_c_df[(raw_c_df['report_date'] == str(filter_date)) & (raw_c_df['department'] == filter_dept)].copy()

    if not raw_i_df.empty and 'report_date' in raw_i_df.columns:
        raw_i_df['report_date'] = raw_i_df['report_date'].astype(str)
        i_df = raw_i_df[raw_i_df['report_date'] == str(filter_date)].copy() if filter_dept == "전체" else raw_i_df[(raw_i_df['report_date'] == str(filter_date)) & (raw_i_df['department'] == filter_dept)].copy()

    dash_tab1, dash_tab2 = st.tabs(["🌟 부서별 전체보기 (부서장 통합보고)", "👥 팀원 개별 보고 상세 & 최종 승인"])
    with dash_tab1:
        st.subheader("전체 부서 통합 요약" if filter_dept == "전체" else f"{filter_dept} 통합 요약")
        if not c_df.empty:
            display_c_df = c_df.rename(columns={'department': '부서', 'manager_name': '부서장', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항'})
            show_cols = [c for c in ['부서', '부서장', '금일 실적', '명일 계획', '특이사항'] if c in display_c_df.columns]
            st.dataframe(display_c_df[show_cols], use_container_width=True, hide_index=True)
        else: st.info("해당 조건으로 등록된 부서장 통합 보고서가 없습니다.")

    with dash_tab2:
        st.subheader("모든 팀원 개별 상세 내역")
        st.caption("💡 아래 표에서 직원의 행을 클릭하면 하단에 상세 내용이 활성화되며, Comment 작성 및 **최종 승인** 처리가 가능합니다.")
        if not i_df.empty:
            if 'status' not in i_df.columns: i_df['status'] = '제출완료'
            if 'comment' not in i_df.columns: i_df['comment'] = ''
            display_i_df = i_df.rename(columns={'department': '부서', 'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항', 'status': '승인상태', 'comment': '피드백'})
            show_cols = [c for c in ['부서', '이름', '승인상태', '금일 실적', '명일 계획', '특이사항', '피드백'] if c in display_i_df.columns]
            selection = st.dataframe(display_i_df[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            selected_rows = selection.selection.rows
            if selected_rows:
                selected_row = i_df.iloc[selected_rows[0]]
                target_id = str(selected_row['id'])
                st.markdown("---")
                st.subheader(f"📄 [{selected_row.get('department', '')}] {selected_row.get('name', '')}님의 업무보고 검토 & 승인")
                with st.form(key=f"approve_form_{target_id}"):
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: st.text_input("날짜", value=str(selected_row.get('report_date', '')), disabled=True)
                    with c2: st.text_input("소속 부서", value=str(selected_row.get('department', '')), disabled=True)
                    with c3: st.text_input("이름", value=str(selected_row.get('name', '')), disabled=True)
                    with c4: st.text_input("현재 승인 상태", value=str(selected_row.get('status', '제출완료')), disabled=True)
                    detail_today = st.text_area("1. 금일 업무 실적", value=str(selected_row.get('today_result', '')), height=140)
                    detail_tomorrow = st.text_area("2. 명일 업무 계획", value=str(selected_row.get('tomorrow_plan', '')), height=100)
                    detail_issue = st.text_area("3. 특이사항 및 협조 요청", value=str(selected_row.get('issue', '')), height=100)
                    admin_comment = st.text_area("피드백 / 지시사항 (Comment)", value=str(selected_row.get('comment', '')) if pd.notna(selected_row.get('comment')) else "", height=90)
                    btn_c1, btn_c2 = st.columns([1, 1])
                    with btn_c1:
                        if st.form_submit_button("✅ 최종 승인 완료 (Comment 포함)", type="primary", use_container_width=True):
                            update_report_full(target_id, detail_today, detail_tomorrow, detail_issue, f"승인완료({user_name})", admin_comment)
                            st.success("성공적으로 최종 승인되었습니다!"); st.rerun()
                    with btn_c2:
                        if st.form_submit_button("💾 승인 없이 내용/Comment만 저장", use_container_width=True):
                            update_report_full(target_id, detail_today, detail_tomorrow, detail_issue, str(selected_row.get('status', '제출완료')), admin_comment)
                            st.success("내용 및 코멘트가 저장되었습니다."); st.rerun()
            else: st.info("👆 위 표에서 검토하거나 승인할 직원의 행(Row)을 클릭해 주세요.")
        else: st.info("해당 조건으로 제출된 개별 보고서가 없습니다.")

def render_attendance_analysis_tab():
    st.header("📈 전사 근태 분석 & 관리")
    sub_an1, sub_an2 = st.tabs(["⚡ 시스템 등록 실시간 근태 현황", "📁 월간 근태기록 엑셀 심층 분석"])
    with sub_an1:
        st.subheader("시스템 등록 출퇴근 및 휴가/출장 누적 기록")
        raw_att = get_data("live_attendance")
        if not raw_att.empty:
            f1, f2 = st.columns(2)
            with f1: sel_dept = st.selectbox("부서 필터", ["전체", "환경사업부", "시스템사업부", "총무부"], key="att_dash_dept")
            with f2: sel_type = st.selectbox("근태 유형 필터", ["전체", "근무", "연차", "오전반차", "오후반차", "출장", "대체휴무", "경조휴가", "외근", "재택근무"], key="att_dash_type")
            filtered_att = raw_att.copy()
            if sel_dept != "전체" and 'department' in filtered_att.columns: filtered_att = filtered_att[filtered_att['department'] == sel_dept]
            if sel_type != "전체" and 'type' in filtered_att.columns: filtered_att = filtered_att[filtered_att['type'] == sel_type]
            filtered_att = filtered_att.sort_values(by='date', ascending=False)
            show_df = filtered_att.rename(columns={'date': '날짜', 'name': '이름', 'department': '부서', 'type': '구분', 'check_in': '출근시간', 'check_out': '퇴근시간', 'note': '사유/비고'})
            valid_cols = [c for c in ['날짜', '부서', '이름', '구분', '출근시간', '퇴근시간', '사유/비고'] if c in show_df.columns]
            st.dataframe(show_df[valid_cols], use_container_width=True, hide_index=True)
        else: st.info("현재 시스템에 누적된 출퇴근/휴가 기록이 없습니다.")
    with sub_an2:
        st.caption("로커스솔루션 근태 엑셀 파일(.xlsx)을 업로드하면 지각/조퇴/연장근무/출장 등을 종합 분석합니다[cite: 3].")
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
                    st.markdown("### 📊 전체 근태 종합 요약")
                    k1, k2, k3, k4, k5 = st.columns(5)
                    k1.metric("총 대상 인원", f"{att_df['이름'].nunique()}명")
                    k2.metric("총 근무 시간", f"{att_df['총근무_분'].sum() / 60:,.1f}시간")
                    k3.metric("총 연장근무", f"{att_df['연장근무_분'].sum() / 60:,.1f}시간")
                    k4.metric("총 지각 발생", f"{att_df['지각여부'].sum()}건")
                    k5.metric("총 조퇴 발생", f"{att_df['조퇴여부'].sum()}건")
                    st.markdown("---")
                    emp_summary = att_df.groupby('이름').agg(
                        근무일수=('근무일자', 'count'), 정상출근일수=('출근판정', lambda x: (x == '정상출근').sum()),
                        지각횟수=('지각여부', 'sum'), 조퇴횟수=('조퇴여부', 'sum'), 출장휴가등_결근=('결근여부', 'sum'),
                        총근무시간=('총근무_분', lambda x: round(sum(x) / 60, 1)), 총연장근무=('연장근무_분', lambda x: round(sum(x) / 60, 1))
                    ).reset_index().sort_values(by='총근무시간', ascending=False).reset_index(drop=True)
                    e_tab1, e_tab2 = st.tabs(["🏆 직원별 근태 순위 요약", "🔍 개인별 상세 출퇴근 타임라인"])
                    with e_tab1:
                        st.dataframe(emp_summary.rename(columns={'이름': '직원명', '근무일수': '기록일수', '정상출근일수': '정상 출근', '지각횟수': '지각(회)', '조퇴횟수': '조퇴(회)', '출장휴가등_결근': '출장/휴가(결근)', '총근무시간': '총 근무(시간)', '총연장근무': '연장근무(시간)'}), use_container_width=True, hide_index=True)
                    with e_tab2:
                        selected_emp = st.selectbox("조회할 직원을 선택하세요", emp_summary['이름'].tolist(), key="att_emp_select")
                        if selected_emp:
                            user_att = att_df[att_df['이름'] == selected_emp].copy()
                            user_att['근무일자'] = user_att['근무일자'].astype(str)
                            present_cols = [c for c in ['근무일자', '출근시간', '퇴근시간', '출근판정', '퇴근판정', '총근무시간', '연장근무시간'] if c in user_att.columns]
                            st.dataframe(user_att[present_cols], use_container_width=True, hide_index=True)
                else: st.error("엑셀 파일 양식이 맞지 않습니다. ('근무일자', '이름', '출근판정', '총근무시간' 컬럼 필요)[cite: 3]")
            except Exception as e: st.error(f"엑셀 파일 분석 오류: {e}")
