import streamlit as st
import pandas as pd
import json
from db_manager import (
    get_kst_date, get_kst_now, get_data, record_attendance,
    record_leave_range, manual_update_attendance, delete_attendance,
    time_to_minutes, save_monthly_att_archive, delete_monthly_att_archive
)

def render_deep_analysis_dashboard(att_df, title_label, key_suffix="live"):
    """근태 데이터프레임을 받아 기본 요약 + 심층 분석 + 타임라인을 렌더링하는 통합 함수"""
    att_df = att_df.copy()
    att_df['총근무_분'] = att_df['총근무시간'].apply(time_to_minutes)
    att_df['연장근무_분'] = att_df['연장근무시간'].apply(time_to_minutes)
    att_df['지각여부'] = att_df['출근판정'] == '지각'
    att_df['결근여부'] = att_df['출근판정'] == '결근'
    att_df['조퇴여부'] = att_df['퇴근판정'] == '조퇴'
    att_df['정상출근여부'] = att_df['출근판정'] == '정상출근'

    # 요일 계산
    parsed_dates = pd.to_datetime(att_df['근무일자'].astype(str).str.slice(0, 10), errors='coerce')
    weekday_map = {0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'}
    att_df['요일'] = parsed_dates.dt.dayofweek.map(weekday_map).fillna('기타')

    total_emps = att_df['이름'].nunique()
    total_work_hours = att_df['총근무_분'].sum() / 60
    total_over_hours = att_df['연장근무_분'].sum() / 60
    total_late_cnt = int(att_df['지각여부'].sum())
    total_early_cnt = int(att_df['조퇴여부'].sum())
    avg_work_per_emp = total_work_hours / total_emps if total_emps > 0 else 0

    st.markdown(f"### 📊 [{title_label}] 전사 근태 종합 요약")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("총 대상 인원", f"{total_emps}명")
    k2.metric("총 근무 시간", f"{total_work_hours:,.1f}시간")
    k3.metric("인당 평균 근무", f"{avg_work_per_emp:,.1f}시간")
    k4.metric("총 연장근무", f"{total_over_hours:,.1f}시간")
    k5.metric("총 지각 발생", f"{total_late_cnt}건")
    k6.metric("총 조퇴 발생", f"{total_early_cnt}건")

    st.markdown("---")

    # 직원별 집계 및 심층 지표 산출
    emp_summary = att_df.groupby('이름').agg(
        근무일수=('근무일자', 'count'),
        정상출근일수=('정상출근여부', 'sum'),
        지각횟수=('지각여부', 'sum'),
        조퇴횟수=('조퇴여부', 'sum'),
        출장휴가등_결근=('결근여부', 'sum'),
        총근무시간=('총근무_분', lambda x: round(sum(x) / 60, 1)),
        총연장근무=('연장근무_분', lambda x: round(sum(x) / 60, 1))
    ).reset_index()

    # 실출근일수 (정상출근 + 지각)
    emp_summary['실출근일수'] = emp_summary['정상출근일수'] + emp_summary['지각횟수']
    emp_summary['일평균근무시간'] = emp_summary.apply(
        lambda r: round(r['총근무시간'] / r['실출근일수'], 1) if r['실출근일수'] > 0 else 0.0, axis=1
    )
    emp_summary['정시출근율(%)'] = emp_summary.apply(
        lambda r: round((r['정상출근일수'] / r['실출근일수']) * 100, 1) if r['실출근일수'] > 0 else 100.0, axis=1
    )
    emp_summary['연장근무비중(%)'] = emp_summary.apply(
        lambda r: round((r['총연장근무'] / r['총근무시간']) * 100, 1) if r['총근무시간'] > 0 else 0.0, axis=1
    )

    def evaluate_status(r):
        if r['총연장근무'] >= 30 or r['일평균근무시간'] >= 9.5:
            return "🚨 과로/번아웃 주의"
        elif r['지각횟수'] >= 3 or r['조퇴횟수'] >= 3:
            return "⚠️ 근태관리 필요"
        elif r['정시출근율(%)'] == 100.0 and r['실출근일수'] >= 10:
            return "🌟 우수(정시출근)"
        return "✅ 정상"

    emp_summary['종합진단'] = emp_summary.apply(evaluate_status, axis=1)
    emp_summary = emp_summary.sort_values(by='총근무시간', ascending=False).reset_index(drop=True)

    e_tab1, e_tab2, e_tab3 = st.tabs([
        "🏆 직원별 근태 순위 & 진단",
        "🔬 다각도 심층 분석 리포트 (패턴/워라밸/성실도)",
        "🔍 개인별 상세 출퇴근 타임라인"
    ])

    # 탭 1: 직원별 순위 요약
    with e_tab1:
        st.subheader("직원별 근태 통계 및 종합 진단")
        display_summary = emp_summary[[
            '이름', '종합진단', '근무일수', '정상출근일수', '지각횟수', '조퇴횟수',
            '출장휴가등_결근', '총근무시간', '총연장근무', '일평균근무시간', '정시출근율(%)'
        ]].rename(columns={
            '이름': '직원명', '종합진단': 'AI 근태진단', '근무일수': '기록일수',
            '정상출근일수': '정상출근', '지각횟수': '지각(회)', '조퇴횟수': '조퇴(회)',
            '출장휴가등_결근': '출장/휴가(결근)', '총근무시간': '총 근무(h)',
            '총연장근무': '연장근무(h)', '일평균근무시간': '일평균(h)', '정시출근율(%)': '정시출근율(%)'
        })
        st.dataframe(display_summary, use_container_width=True, hide_index=True)

        c_warn1, c_warn2 = st.columns(2)
        with c_warn1:
            over_top = emp_summary.sort_values(by='총연장근무', ascending=False).head(3)
            st.info("🔥 **연장근무 상위 Top 3**: " + ", ".join([f"{r['이름']} ({r['총연장근무']}h)" for _, r in over_top.iterrows()]))
        with c_warn2:
            late_top = emp_summary[emp_summary['지각횟수'] > 0].sort_values(by='지각횟수', ascending=False)
            if not late_top.empty:
                st.warning("⚠️ **지각 발생 인원**: " + ", ".join([f"{r['이름']} ({r['지각횟수']}회)" for _, r in late_top.iterrows()]))
            else:
                st.success("✅ 해당 기간 지각자가 없습니다.")

    # 탭 2: 심층 분석 리포트
    with e_tab2:
        st.subheader("🔬 심층 분석 1: 워라밸(Work-Life Balance) 및 과로 위험도 분석")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            st.markdown("**📊 직원별 총 근무시간 vs 연장근무 시간 비교**")
            chart_df = emp_summary.set_index('이름')[['총근무시간', '총연장근무']]
            st.bar_chart(chart_df)
        with d_col2:
            st.markdown("**🚨 집중 케어 및 근태 관리 대상자 자동 추출**")
            overwork_emps = emp_summary[emp_summary['종합진단'] == "🚨 과로/번아웃 주의"]
            if not overwork_emps.empty:
                for _, r in overwork_emps.iterrows():
                    st.error(f"**[과로 주의] {r['이름']}**: 총 연장근무 **{r['총연장근무']}시간** (일평균 **{r['일평균근무시간']}시간** 근무, 연장비중 {r['연장근무비중(%)']}%) ➔ 업무량 조절 및 휴식 권고")
            else:
                st.success("✅ 과로/번아웃 위험 기준(월 연장 30h 이상 또는 일평균 9.5h 이상)에 해당하는 직원이 없습니다.")

            care_emps = emp_summary[emp_summary['종합진단'] == "⚠️ 근태관리 필요"]
            if not care_emps.empty:
                for _, r in care_emps.iterrows():
                    st.warning(f"**[근태 주의] {r['이름']}**: 지각 **{r['지각횟수']}회**, 조퇴 **{r['조퇴횟수']}회** (정시출근율 {r['정시출근율(%)']}%) ➔ 출퇴근 시간 엄수 안내 필요")

            best_emps = emp_summary[emp_summary['종합진단'] == "🌟 우수(정시출근)"]
            if not best_emps.empty:
                names_str = ", ".join(best_emps['이름'].tolist())
                st.info(f"🌟 **이달의 정시출근 우수 직원 (지각 0회)**: {names_str}")

        st.markdown("---")
        st.subheader("🔬 심층 분석 2: 요일별 근무 & 지각 패턴 분석")
        weekday_order = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        day_summary = att_df.groupby('요일').agg(
            출근기록수=('근무일자', 'count'),
            평균근무시간=('총근무_분', lambda x: round((sum(x) / len(x)) / 60, 1) if len(x) > 0 else 0),
            총연장근무시간=('연장근무_분', lambda x: round(sum(x) / 60, 1)),
            지각발생건수=('지각여부', 'sum'),
            조퇴발생건수=('조퇴여부', 'sum')
        ).reindex([d for d in weekday_order if d in att_df['요일'].unique()]).reset_index()

        w_col1, w_col2 = st.columns([1.3, 1])
        with w_col1:
            st.dataframe(
                day_summary.rename(columns={
                    '요일': '요일', '출근기록수': '총 기록(건)', '평균근무시간': '일평균 근무(h)',
                    '총연장근무시간': '누적 연장근무(h)', '지각발생건수': '지각(건)', '조퇴발생건수': '조퇴(건)'
                }),
                use_container_width=True, hide_index=True
            )
        with w_col2:
            if not day_summary.empty:
                max_over_day = day_summary.sort_values(by='총연장근무시간', ascending=False).iloc[0]
                max_late_day = day_summary.sort_values(by='지각발생건수', ascending=False).iloc[0]
                st.write("**💡 요일별 인사이트 요약**")
                st.write(f"• 야근/연장근무가 가장 많은 요일: **{max_over_day['요일']}** (누적 {max_over_day['총연장근무시간']}h)")
                if max_late_day['지각발생건수'] > 0:
                    st.write(f"• 지각이 가장 빈번한 요일: **{max_late_day['요일']}** ({int(max_late_day['지각발생건수'])}건 발생)")
                else:
                    st.write("• 모든 요일에서 지각 발생 없음")

    # 탭 3: 개인별 상세 타임라인
    with e_tab3:
        st.subheader("개인별 상세 출퇴근 기록 조회")
        selected_emp = st.selectbox(
            "조회할 직원을 선택하세요",
            emp_summary['이름'].tolist(),
            key=f"att_emp_select_{key_suffix}"
        )
        if selected_emp:
            user_att = att_df[att_df['이름'] == selected_emp].copy()
            user_att['근무일자'] = user_att['근무일자'].astype(str)
            show_cols = ['근무일자', '요일', '출근시간', '퇴근시간', '출근판정', '퇴근판정', '총근무시간', '연장근무시간']
            present_cols = [c for c in show_cols if c in user_att.columns]
            st.dataframe(user_att[present_cols], use_container_width=True, hide_index=True)

    return {
        "total_emps": int(total_emps),
        "total_work_hours": round(total_work_hours, 1),
        "total_over_hours": round(total_over_hours, 1),
        "total_late_cnt": int(total_late_cnt),
        "total_early_cnt": int(total_early_cnt)
    }


def render_attendance_tab(user_name, user_dept):
    st.header("⏰ 근태 관리 포털")
    
    tab_live, tab_analysis = st.tabs([
        "📍 출퇴근 & 연차/출장 등록", 
        "📈 전사 근태 분석 및 월간 아카이브"
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
    # 서브탭 2: 전사 근태 분석 현황 & 월간 심층 분석 아카이브
    # --------------------------------
    with tab_analysis:
        sub_an1, sub_an2 = st.tabs([
            "📁 월간 근태 엑셀 파일 심층 분석 & 아카이브",
            "⚡ 시스템 등록 실시간 누적 근태 현황"
        ])
        
        with sub_an1:
            st.subheader("📁 월간 근태 엑셀 심층 분석 및 보관함")
            
            # 1. 저장된 아카이브 목록 불러오기 섹션
            archive_df = get_data("monthly_att_archive")
            archive_options = {"➕ 새 엑셀 파일 직접 업로드하여 분석하기": "NEW"}
            if not archive_df.empty and 'month_label' in archive_df.columns:
                archive_df['num_id'] = pd.to_numeric(archive_df['id'], errors='coerce').fillna(0)
                archive_df = archive_df.sort_values(by='num_id', ascending=False).reset_index(drop=True)
                for _, r in archive_df.iterrows():
                    lbl = f"📌 {r['month_label']} (저장일: {r.get('saved_at', '-')} | 작성자: {r.get('saved_by', '-')})"
                    archive_options[lbl] = str(r['id'])

            selected_mode_label = st.selectbox(
                "📂 분석 모드 선택 (과거 저장된 월간 심층 분석 결과를 선택하거나 새 엑셀 파일을 업로드하세요)",
                options=list(archive_options.keys()),
                key="archive_mode_select"
            )
            selected_mode_id = archive_options[selected_mode_label]

            st.markdown("---")

            # A. 신규 엑셀 파일 업로드 모드
            if selected_mode_id == "NEW":
                st.caption("로커스솔루션 근태 엑셀 파일(.xlsx)을 업로드하면 기본 통계 + 심층 분석 리포트를 생성하고 저장할 수 있습니다.")
                uploaded_file = st.file_uploader("월간 근태기록 엑셀 파일 업로드", type=["xlsx", "xls"], key="attendance_uploader")
                
                if uploaded_file is not None:
                    try:
                        att_df = pd.read_excel(uploaded_file, sheet_name=0)
                        req_cols = ['근무일자', '이름', '출근판정', '퇴근판정', '총근무시간', '연장근무시간']
                        if all(col in att_df.columns for col in req_cols):
                            default_title = uploaded_file.name.replace(".xlsx", "").replace(".xls", "")
                            
                            # 심층 분석 렌더링
                            summary_dict = render_deep_analysis_dashboard(att_df, default_title, key_suffix="upload")
                            
                            st.markdown("---")
                            st.markdown("#### 💾 이 월간 심층 분석 결과를 아카이브에 저장하기")
                            st.caption("저장해 두면 다음부터 엑셀 파일을 다시 올리지 않아도 상단 목록에서 선택해 언제든 다시 볼 수 있습니다.")
                            with st.form("save_archive_form"):
                                col_s1, col_s2 = st.columns([3, 1])
                                with col_s1:
                                    save_label = st.text_input("저장할 월간 분석 제목", value=f"{default_title} 근태 심층분석")
                                with col_s2:
                                    st.write("")
                                    if st.form_submit_button("💾 분석 결과 영구 저장", type="primary", use_container_width=True):
                                        if save_label.strip():
                                            ok, msg = save_monthly_att_archive(save_label.strip(), user_name, summary_dict, att_df)
                                            if ok:
                                                st.success(msg)
                                                st.rerun()
                                        else:
                                            st.error("저장할 제목을 입력해 주세요.")
                        else:
                            st.error("엑셀 파일 양식이 맞지 않습니다. ('근무일자', '이름', '출근판정', '퇴근판정', '총근무시간', '연장근무시간' 컬럼 필요)")
                    except Exception as e:
                        st.error(f"엑셀 파일 분석 오류: {e}")
                else:
                    st.info("👆 위 파일 업로더에 월간 근태 엑셀 파일을 업로드하거나, 상단 드롭다운에서 저장된 과거 분석 기록을 선택해 주세요.")

            # B. 저장된 과거 월간 심층 분석 아카이브 열람 모드
            else:
                matched_arch = archive_df[archive_df['id'].astype(str) == selected_mode_id]
                if not matched_arch.empty:
                    arch_row = matched_arch.iloc[0]
                    m_label = arch_row.get('month_label', '저장된 분석')
                    raw_json_str = arch_row.get('raw_json', '')
                    
                    top_c1, top_c2 = st.columns([4, 1])
                    with top_c1:
                        st.info(f"📂 **아카이브 열람 중**: `{m_label}` (저장일시: {arch_row.get('saved_at')} | 저장자: {arch_row.get('saved_by')})")
                    with top_c2:
                        if st.button("🗑️ 이 아카이브 삭제", key=f"del_arch_{selected_mode_id}", use_container_width=True):
                            ok, msg = delete_monthly_att_archive(selected_mode_id)
                            if ok:
                                st.warning(msg)
                                st.rerun()

                    if raw_json_str:
                        try:
                            restored_df = pd.DataFrame(json.loads(raw_json_str))
                            render_deep_analysis_dashboard(restored_df, m_label, key_suffix=f"arch_{selected_mode_id}")
                        except Exception as e:
                            st.error(f"저장된 데이터를 복원하는 중 오류가 발생했습니다: {e}")
                    else:
                        st.warning("저장된 상세 데이터가 비어 있습니다.")

        with sub_an2:
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
            else:
                st.info("현재 시스템에 누적된 출퇴근/휴가 기록이 없습니다.")
