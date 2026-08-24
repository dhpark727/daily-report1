import streamlit as st
import pandas as pd
from db_manager import (
    get_kst_date, get_kst_now, get_data, record_attendance,
    record_leave_range, manual_update_attendance, delete_attendance, time_to_minutes
)

def render_attendance_tab(user_name, user_dept):
    st.header(f"⏰ 근태 관리 포털")
    
    tab_live, tab_analysis = st.tabs([
        "📍 출퇴근 & 연차/출장 등록", 
        "📈 전사 근태 분석 및 통계"
    ])
    
    # --------------------------------
    # 서브탭 1: 실시간 출퇴근 & 연차/출장 등록
    # --------------------------------
    with tab_live:
        today_kst = get_kst_date()
        today_str = str(today_kst)
        now_time_display = get_kst_now().strftime("%H:%M:%S")
        st.caption(f"📅 오늘 날짜(KST): **{today_str}** | 🕒 현재 시각(한국): **{now_time_display}** | 접속자: **{user_name}**")
        
        live_df = get_data("live_attendance")
        my_status = None
        if not live_df.empty and 'date' in live_df.columns and 'name' in live_df.columns:
            live_df['date'] = live_df['date'].astype(str)
            live_df['name'] = live_df['name'].astype(str)
            row = live_df[(live_df['date'] == today_str) & (live_df['name'] == user_name)]
            if not row.empty:
                my_status = row.iloc[0]
                
        st.markdown("#### 📌 오늘 나의 출퇴근/근태 상태")
        c_st1, c_st2, c_st3, c_st4 = st.columns(4)
        c_st1.metric("근태 유형", my_status['type'] if my_status is not None else "미기록")
        c_st2.metric("출근 시간", my_status['check_in'] if my_status is not None else "-")
        c_st3.metric("퇴근 시간", my_status['check_out'] if my_status is not None else "-")
        c_st4.metric("메모/비고", my_status['note'] if my_status is not None and str(my_status['note']).strip() != "" else "-")
        
        st.markdown("---")
        sub_col1, sub_col2 = st.columns(2)
        
        with sub_col1:
            st.subheader("🏢 실시간 출퇴근 체크 (원클릭)")
            att_note = st.text_input("출퇴근 비고 (선택사항, 예: 외근 후 바로 출근)", key="att_note_input")
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if st.button("🟢 출근하기", use_container_width=True, type="primary"):
                    success, msg = record_attendance(user_name, user_dept, "출근", att_note)
                    if success: st.success(msg); st.rerun()
                    else: st.warning(msg)
            with btn_c2:
                if st.button("🔴 퇴근하기", use_container_width=True):
                    success, msg = record_attendance(user_name, user_dept, "퇴근", att_note)
                    if success: st.success(msg); st.rerun()
                    else: st.warning(msg)

        with sub_col2:
            st.subheader("🌴 연차 / 반차 / 휴가 / 출장 (기간 등록)")
            with st.form("leave_form"):
                leave_type = st.selectbox("근태 구분 선택", ["연차", "오전반차", "오후반차", "대체휴무", "경조휴가", "출장", "외근", "재택근무"])
                date_range = st.date_input("적용 날짜 또는 기간(시작일 ~ 종료일)", value=(today_kst, today_kst))
                leave_reason = st.text_input("사유 및 목적지 (예: 제주출장, 하계휴가)", placeholder="사유를 입력해 주세요")
                if st.form_submit_button("근태/휴가 신청하기", use_container_width=True, type="primary"):
                    if isinstance(date_range, tuple) or isinstance(date_range, list):
                        start_d = date_range[0] if len(date_range) >= 1 else today_kst
                        end_d = date_range[1] if len(date_range) == 2 else start_d
                    else: start_d = end_d = date_range
                    success, msg = record_leave_range(user_name, user_dept, leave_type, start_d, end_d, leave_reason)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)

        st.markdown("---")
        with st.expander("✏️ 출퇴근 시간 직접 수정 및 수동 등록 (시간 정정 필요 시)"):
            with st.form("manual_att_form"):
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1: man_date = st.date_input("수정할 날짜", value=today_kst, key="man_date_input")
                with m_col2: man_type = st.selectbox("근태 구분", ["근무", "연차", "오전반차", "오후반차", "출장", "외근", "재택근무"], key="man_type_input")
                with m_col3: man_note = st.text_input("비고/사유", placeholder="수정 사유", key="man_note_input")
                t_col1, t_col2 = st.columns(2)
                with t_col1: man_in = st.text_input("출근 시간", value=my_status['check_in'] if (my_status is not None and my_status['check_in'] != '-') else "09:00:00")
                with t_col2: man_out = st.text_input("퇴근 시간", value=my_status['check_out'] if (my_status is not None and my_status['check_out'] != '-') else "18:00:00")
                if st.form_submit_button("💾 출퇴근 기록 수동 수정 / 등록 완료", type="primary", use_container_width=True):
                    success, msg = manual_update_attendance(user_name, user_dept, man_date, man_type, man_in, man_out, man_note)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)
                        
        st.markdown("---")
        sub_tab_me, sub_tab_all = st.tabs(["📝 나의 최근 근태/휴가 신청 내역", "👥 오늘 전 직원 출근 & 근태 현황"])
        with sub_tab_me:
            if not live_df.empty and 'name' in live_df.columns:
                my_records = live_df[live_df['name'] == user_name].copy()
                if not my_records.empty:
                    my_records = my_records.sort_values(by='date', ascending=False)
                    show_my = my_records.rename(columns={'date': '날짜', 'type': '구분', 'check_in': '출근시간', 'check_out': '퇴근시간', 'note': '사유/비고'})
                    st.dataframe(show_my[['날짜', '구분', '출근시간', '퇴근시간', '사유/비고']], use_container_width=True, hide_index=True)
                    with st.expander("🗑️ 등록한 근태/휴가 일정 취소하기"):
                        options = {f"{r['date']} - {r['type']} ({r.get('note', '')})": r['id'] for _, r in my_records.iterrows() if 'id' in r}
                        target_cancel = st.selectbox("취소할 일정을 선택하세요", list(options.keys()))
                        if st.button("신청 취소하기"):
                            if target_cancel:
                                success, msg = delete_attendance(options[target_cancel])
                                if success: st.success(msg); st.rerun()
                else: st.info("등록된 나의 근태 기록이 없습니다.")
            else: st.info("근태 데이터가 없습니다.")
                
        with sub_tab_all:
            if not live_df.empty:
                today_all = live_df[live_df['date'] == today_str].copy()
                if not today_all.empty:
                    display_live = today_all.rename(columns={'name': '이름', 'department': '부서', 'type': '구분', 'check_in': '출근시간', 'check_out': '퇴근시간', 'note': '비고'})[['부서', '이름', '구분', '출근시간', '퇴근시간', '비고']]
                    st.dataframe(display_live, use_container_width=True, hide_index=True)
                else: st.info("오늘 아직 등록된 출퇴근/휴가 기록이 없습니다.")

    # --------------------------------
    # 서브탭 2: 전사 근태 분석 현황 (실시간 누적 + 엑셀 심층 분석)
    # --------------------------------
    with tab_analysis:
        sub_an1, sub_an2 = st.tabs(["⚡ 시스템 등록 누적 근태 데이터", "📁 월간 근태 엑셀 파일 심층 분석"])
        
        with sub_an1:
            st.subheader("시스템 등록 출퇴근 및 휴가/출장 전체 기록")
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
            st.caption("로커스솔루션 근태 엑셀 파일(.xlsx)을 업로드하면 지각/조퇴/연장근무/출장 등을 종합 분석합니다[cite: 1].")
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
                    else: st.error("엑셀 파일 양식이 맞지 않습니다. ('근무일자', '이름', '출근판정', '총근무시간' 컬럼 필요)[cite: 1]")
                except Exception as e: st.error(f"엑셀 파일 분석 오류: {e}")
