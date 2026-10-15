import streamlit as st
import pandas as pd
from db_manager import (
    get_kst_date, get_data, insert_report, update_report,
    delete_report, save_consolidated_report, update_report_full
)

def render_readonly_report_card(title_prefix, row_data, key_prefix):
    """전일 / 전전일 보고서를 읽기 전용 카드로 깔끔하게 렌더링하는 헬퍼 함수"""
    if row_data is not None:
        r_date = str(row_data.get('report_date', '-'))
        r_status = str(row_data.get('status', '제출완료'))
        st.markdown(f"##### 📅 {title_prefix} ({r_date})")
        st.caption(f"승인상태: `{r_status}`")
        st.text_area(
            "1. 업무 실적",
            value=str(row_data.get('today_result', '')),
            height=130,
            disabled=True,
            key=f"{key_prefix}_res_{r_date}"
        )
        st.text_area(
            "2. 업무 계획",
            value=str(row_data.get('tomorrow_plan', '')),
            height=95,
            disabled=True,
            key=f"{key_prefix}_plan_{r_date}"
        )
        st.text_area(
            "3. 특이사항",
            value=str(row_data.get('issue', '')),
            height=85,
            disabled=True,
            key=f"{key_prefix}_iss_{r_date}"
        )
        if row_data.get('comment'):
            st.info(f"💬 **코멘트**: {row_data.get('comment')}")
    else:
        st.markdown(f"##### 📅 {title_prefix}")
        st.caption("기록 없음")
        st.info(f"이전 제출된 보고서 내역이 없습니다.")

def render_report_portal(user_name, user_dept):
    st.header("📋 업무보고 관리 포털")
    
    tab_write, tab_my, tab_dept, tab_dash = st.tabs([
        "✍️ 업무보고 작성", 
        "🔍 내 보고서 관리", 
        "👨‍💼 부서장 통합 보고", 
        "📊 업무 종합 대시보드"
    ])
    
    # --------------------------------
    # 서브탭 1: 업무보고 작성
    # --------------------------------
    with tab_write:
        st.subheader("오늘의 업무 기록")
        with st.form("report_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                report_date = st.date_input("날짜", get_kst_date(), key="t1_date")
            with col2:
                dept_list = ["환경사업부", "시스템사업부", "총무부"]
                idx = dept_list.index(user_dept) if user_dept in dept_list else 0
                department = st.selectbox("소속 부서", dept_list, index=idx, key="t1_dept")
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
    # 서브탭 2: 내 보고서 관리 (금일 보고 + 전일 보고 나란히 보기 & 수정)
    # --------------------------------
    with tab_my:
        st.subheader("🔍 내 업무보고 비교 조회 (금일 vs 전일) 및 수정")
        col1, col2 = st.columns(2)
        with col1:
            dept_list = ["환경사업부", "시스템사업부", "총무부"]
            d_idx = dept_list.index(user_dept) if user_dept in dept_list else 0
            search_dept = st.selectbox("소속 부서", dept_list, index=d_idx, key="search_dept")
        with col2:
            search_name = st.text_input("본인 이름 입력", value=user_name, key="search_name")

        if search_name.strip():
            df = get_data("reports")
            if not df.empty and 'department' in df.columns and 'name' in df.columns:
                my_df = df[(df['department'] == search_dept) & (df['name'] == search_name)].copy()
                if not my_df.empty:
                    if 'status' not in my_df.columns: my_df['status'] = '제출완료'
                    if 'comment' not in my_df.columns: my_df['comment'] = ''
                    
                    # 날짜 및 ID 최신순 정렬
                    my_df['num_id'] = pd.to_numeric(my_df['id'], errors='coerce').fillna(0)
                    my_df = my_df.sort_values(by=['report_date', 'num_id'], ascending=[False, False]).reset_index(drop=True)

                    report_options = {f"{row['report_date']} 업무보고 (#{row['id']})": idx for idx, row in my_df.iterrows()}
                    selected_label = st.selectbox(
                        "📌 기준 보고서 선택 (선택한 보고서와 그 직전 보고서를 나란히 비교합니다)",
                        list(report_options.keys()),
                        key="my_report_select"
                    )

                    if selected_label is not None:
                        sel_idx = report_options[selected_label]
                        curr_row = my_df.iloc[sel_idx]
                        prev_row = my_df.iloc[sel_idx + 1] if (sel_idx + 1) < len(my_df) else None
                        selected_id = str(curr_row['id'])

                        st.markdown("---")
                        # 좌측: 금일(선택일) 보고서 수정 폼 / 우측: 전일(직전) 보고서 읽기 전용 카드
                        col_today, col_prev = st.columns(2)
                        
                        with col_today:
                            st.markdown(f"##### ✍️ 금일(선택일) 보고 내용 수정 ({curr_row['report_date']})")
                            st.caption(f"승인상태: `{curr_status if (curr_status := str(curr_row.get('status', '제출완료'))) else '제출완료'}`")
                            with st.form(key=f"my_edit_form_{selected_id}"):
                                edit_today = st.text_area("1. 금일 업무 실적", value=str(curr_row.get('today_result', '')), height=130)
                                edit_tomorrow = st.text_area("2. 명일 업무 계획", value=str(curr_row.get('tomorrow_plan', '')), height=95)
                                edit_issue = st.text_area("3. 특이사항 및 협조 요청", value=str(curr_row.get('issue', '')), height=85)
                                
                                if curr_row.get('comment'):
                                    st.info(f"💬 **관리자/부서장 피드백**: {curr_row.get('comment')}")
                                    
                                b1, b2 = st.columns(2)
                                with b1:
                                    if st.form_submit_button("💾 내 보고서 수정 저장", type="primary", use_container_width=True):
                                        update_report(selected_id, edit_today, edit_tomorrow, edit_issue)
                                        st.success("수정 완료!"); st.rerun()
                                with b2:
                                    if st.form_submit_button("🗑️ 이 보고서 삭제", use_container_width=True):
                                        delete_report(selected_id)
                                        st.warning("삭제 완료!"); st.rerun()

                        with col_prev:
                            render_readonly_report_card("전일(직전) 보고 내용", prev_row, key_prefix=f"my_prev_{selected_id}")

                    st.markdown("---")
                    with st.expander("📋 나의 전체 과거 보고 내역 표로 보기", expanded=False):
                        display_cols = {
                            'report_date': '날짜', 'department': '부서', 'name': '이름',
                            'today_result': '금일 실적', 'tomorrow_plan': '명일 계획',
                            'issue': '특이사항', 'status': '승인상태', 'comment': '피드백/코멘트'
                        }
                        display_df = my_df.drop(columns=['id', 'num_id'], errors='ignore').rename(columns=display_cols)
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"'{search_name}'님으로 등록된 업무보고가 없습니다.")

    # --------------------------------
    # 서브탭 3: 부서장 통합 보고
    # --------------------------------
    with tab_dept:
        st.subheader(f"👨‍💼 [{user_dept}] 팀원 보고서 취합 및 부서 통합보고")
        
        c_filter1, c_filter2 = st.columns(2)
        with c_filter1: 
            m_date = st.date_input("확인할 날짜 선택", get_kst_date(), key="m_date")
        with c_filter2: 
            dept_list = ["환경사업부", "시스템사업부", "총무부"]
            idx = dept_list.index(user_dept) if user_dept in dept_list else 0
            m_dept = st.selectbox("관리 부서", dept_list, index=idx, key="m_dept")
            
        df = get_data("reports")
        m_df = pd.DataFrame()
        if not df.empty and 'report_date' in df.columns and 'department' in df.columns:
            df['report_date'] = df['report_date'].astype(str)
            m_df = df[(df['report_date'] == str(m_date)) & (df['department'] == m_dept)].copy()
            
        st.markdown("---")
        st.markdown(f"#### 👥 {m_date} {m_dept} 팀원 개별 제출 현황 (총 {len(m_df)}건)")
        
        if not m_df.empty:
            if 'status' not in m_df.columns: m_df['status'] = '제출완료'
            display_m_df = m_df.rename(columns={'name': '이름', 'today_result': '금일 실적', 'tomorrow_plan': '명일 계획', 'issue': '특이사항', 'status': '승인상태'})
            show_cols = [c for c in ['이름', '금일 실적', '명일 계획', '특이사항', '승인상태'] if c in display_m_df.columns]
            st.dataframe(display_m_df[show_cols], use_container_width=True, hide_index=True)
            
            with st.expander("🔍 팀원별 상세 보고 내용 펼쳐보기", expanded=True):
                for _, r in m_df.iterrows():
                    st.markdown(f"**👤 {r.get('name')}** (승인상태: `{r.get('status', '제출완료')}`)")
                    st.text(f"• 금일 실적: {r.get('today_result', '-')}")
                    st.text(f"• 명일 계획: {r.get('tomorrow_plan', '-')}")
                    st.text(f"• 특이사항: {r.get('issue', '-')}")
                    st.divider()
        else:
            st.info(f"{m_date} 일자에 {m_dept} 팀원이 제출한 업무보고서가 없습니다.")

        raw_c_df = get_data("consolidated_reports")
        saved_c_row = None
        if not raw_c_df.empty and 'report_date' in raw_c_df.columns and 'department' in raw_c_df.columns:
            raw_c_df['report_date'] = raw_c_df['report_date'].astype(str)
            existing_c = raw_c_df[(raw_c_df['report_date'] == str(m_date)) & (raw_c_df['department'] == m_dept)]
            if not existing_c.empty:
                saved_c_row = existing_c.iloc[0]

        st.markdown("---")
        st.markdown(f"#### 📝 {m_dept} 부서 통합 보고서 작성 및 부서장 멘트")
        
        with st.form("consolidated_form", clear_on_submit=False):
            m_name = st.text_input("부서장 이름", value=user_name, key="m_name")
            
            c_today_val = str(saved_c_row.get('today_result', '')) if saved_c_row is not None else ""
            c_tomorrow_val = str(saved_c_row.get('tomorrow_plan', '')) if saved_c_row is not None else ""
            c_issue_val = str(saved_c_row.get('issue', '')) if saved_c_row is not None else ""
            
            c_today = st.text_area("1. 부서 통합 금일 실적 요약", value=c_today_val, placeholder="팀원들의 금일 주요 실적을 요약하여 작성해주세요.", height=130)
            c_tomorrow = st.text_area("2. 부서 통합 명일 계획", value=c_tomorrow_val, placeholder="명일 부서 단위 주요 추진 계획을 입력해주세요.", height=100)
            c_issue = st.text_area("3. 부서장 총평 멘트 및 특이사항 (대표님 보고용)", value=c_issue_val, placeholder="부서장 총평 멘트, 애로사항 및 대표님 지시 요청 사항을 입력해주세요.", height=110)
            
            if st.form_submit_button("📤 부서 통합 업무보고 최종 제출", type="primary", use_container_width=True):
                if not m_name.strip():
                    st.error("부서장 이름을 입력해주세요.")
                else:
                    save_consolidated_report(m_date, m_dept, m_name, c_today, c_tomorrow, c_issue)
                    st.success(f"[{m_dept}] {m_date} 부서 통합 업무보고가 성공적으로 제출/갱신되었습니다!")
                    st.rerun()

    # --------------------------------
    # 서브탭 4: 업무 종합 대시보드 (금일 + 전일 + 전전일 3단 비교 및 금일 단독 승인)
    # --------------------------------
    with tab_dash:
        st.subheader("전사 업무 종합 대시보드 & 결재 검토")
        col1, col2 = st.columns(2)
        with col1:
            filter_date = st.date_input("조회할 기준 날짜 선택 (금일)", get_kst_date(), key="filter_date")
        with col2:
            filter_dept = st.selectbox("부서 필터링", ["전체", "환경사업부", "시스템사업부", "총무부"], key="filter_dept")

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
            else:
                st.info("해당 조건으로 등록된 부서장 통합 보고서가 없습니다.")

        with dash_tab2:
            st.subheader(f"👥 {filter_date} 팀원 개별 보고 목록")
            st.caption("💡 아래 표에서 직원의 행을 클릭하면 하단에 **[금일 / 전일 / 전전일]** 보고 내용이 나란히 표시되며, **금일 보고서에 대한 최종 승인**을 진행할 수 있습니다.")
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
                    emp_name = str(selected_row.get('name', ''))
                    emp_dept = str(selected_row.get('department', ''))
                    curr_date_str = str(selected_row.get('report_date', ''))

                    # 해당 직원의 기준일(filter_date) 이전 보고서 중 가장 최근 2건(전일, 전전일) 추출
                    emp_history = raw_i_df[
                        (raw_i_df['name'] == emp_name) &
                        (raw_i_df['department'] == emp_dept) &
                        (raw_i_df['report_date'] < curr_date_str)
                    ].copy()
                    if not emp_history.empty:
                        emp_history['num_id'] = pd.to_numeric(emp_history['id'], errors='coerce').fillna(0)
                        emp_history = emp_history.sort_values(by=['report_date', 'num_id'], ascending=[False, False]).reset_index(drop=True)
                    
                    prev_1_row = emp_history.iloc[0] if len(emp_history) >= 1 else None
                    prev_2_row = emp_history.iloc[1] if len(emp_history) >= 2 else None

                    st.markdown("---")
                    st.subheader(f"📄 [{emp_dept}] {emp_name}님의 업무보고 연속 비교 (금일 · 전일 · 전전일)")
                    
                    # 3단 컬럼 구성: 좌측(금일 보고 및 승인) | 중앙(전일 보고) | 우측(전전일 보고)
                    col_d0, col_d1, col_d2 = st.columns(3)
                    
                    with col_d0:
                        curr_status = str(selected_row.get('status', '제출완료'))
                        st.markdown(f"##### ✅ 금일 보고 ({curr_date_str}) - 검토/승인")
                        st.caption(f"현재 승인상태: `{curr_status}`")
                        
                        with st.form(key=f"approve_form_{target_id}"):
                            detail_today = st.text_area("1. 금일 업무 실적", value=str(selected_row.get('today_result', '')), height=130)
                            detail_tomorrow = st.text_area("2. 명일 업무 계획", value=str(selected_row.get('tomorrow_plan', '')), height=95)
                            detail_issue = st.text_area("3. 특이사항 및 협조 요청", value=str(selected_row.get('issue', '')), height=85)
                            admin_comment = st.text_area(
                                "💬 피드백 / 지시사항 (금일 보고서 전용)",
                                value=str(selected_row.get('comment', '')) if pd.notna(selected_row.get('comment')) else "",
                                placeholder="금일 보고에 대한 피드백이나 지시사항을 입력하세요.",
                                height=80
                            )
                            
                            if st.form_submit_button("✅ 금일 보고 최종 승인 완료", type="primary", use_container_width=True):
                                update_report_full(target_id, detail_today, detail_tomorrow, detail_issue, f"승인완료({user_name})", admin_comment)
                                st.success("금일 보고서가 최종 승인되었습니다!"); st.rerun()
                            if st.form_submit_button("💾 승인 없이 내용/Comment만 저장", use_container_width=True):
                                update_report_full(target_id, detail_today, detail_tomorrow, detail_issue, curr_status, admin_comment)
                                st.success("내용 및 코멘트가 저장되었습니다."); st.rerun()

                    with col_d1:
                        render_readonly_report_card("전일(직전) 보고", prev_1_row, key_prefix=f"dash_p1_{target_id}")

                    with col_d2:
                        render_readonly_report_card("전전일(2회전) 보고", prev_2_row, key_prefix=f"dash_p2_{target_id}")

                else:
                    st.info("👆 위 표에서 검토하거나 승인할 직원의 행(Row)을 클릭해 주세요.")
            else:
                st.info("해당 조건으로 제출된 개별 보고서가 없습니다.")
