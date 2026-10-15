import streamlit as st
import pandas as pd
from datetime import timedelta
from db_manager import (
    get_kst_date, get_data, get_user_credentials, insert_approval_doc,
    update_approval_doc, approve_step1, approve_step2, approve_final,
    submit_expense_report, finalize_expense
)

def render_file_preview(file_obj, key_prefix):
    """업로드된 첨부파일 미리보기 및 다운로드 버튼 제공"""
    file_name = file_obj.name
    lower_name = file_name.lower()
    if lower_name.endswith(('.png', '.jpg', '.jpeg', '.webp')):
        try:
            st.image(file_obj, caption=f"📎 첨부 이미지: {file_name}", width=400)
        except Exception:
            pass
    file_obj.seek(0)
    st.download_button(
        label=f"📥 첨부파일 다운로드 ({file_name})",
        data=file_obj.read(),
        file_name=file_name,
        key=f"{key_prefix}_{file_name}"
    )

def render_approval_tab(user_name, user_dept, user_role):
    # 세션 상태 안전 초기화
    if "expense_receipts" not in st.session_state:
        st.session_state["expense_receipts"] = {}
    if "approval_attachments" not in st.session_state:
        st.session_state["approval_attachments"] = {}

    st.header("📑 전자결재 & 품의 / 지출 정산 관리")
    
    sub1, sub2, sub3 = st.tabs([
        "✍️ 신규 품의서 기안", 
        "📬 결재함 & 내 기안 문서 조회", 
        "💰 실행 후 지출 정산 등록/마감"
    ])
    
    users_dict = get_user_credentials()
    all_emp_names = [info['name'] for info in users_dict.values() if info['name'] != user_name]
    if not all_emp_names: 
        all_emp_names = ["기본관리자"]

    # --------------------------------
    # 서브탭 1: 신규 품의서 기안 (파일 업로드 포함)
    # --------------------------------
    with sub1:
        st.subheader("새로운 품의서 작성")
        
        if st.session_state.get("approval_submitted_msg"):
            st.success(st.session_state["approval_submitted_msg"])
            st.session_state["approval_submitted_msg"] = None

        with st.form("new_approval_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                doc_type = st.selectbox("품의 구분", ["구매/지출 품의", "프로젝트 실행 품의", "출장/외근 품의", "일반 업무 품의"])
                title = st.text_input("품의 제목", placeholder="예: [환경사업부] 측정 장비 구매 건")
                budget = st.text_input("예상 소요 예산(원)", value="0", placeholder="숫자만 입력 (예: 1500000)")
            with col2:
                target_mgr1 = st.selectbox("🎯 1차 결재자 (중간관리자 / 필수)", all_emp_names)
                target_mgr2 = st.selectbox("🎯 2차 결재자 (선택 사항)", ["선택 안 함"] + [name for name in all_emp_names if name != target_mgr1])
                cc_selected = st.multiselect("👥 참고자 (열람 공유)", [name for name in all_emp_names if name not in [target_mgr1, target_mgr2]])
                
            st.caption(f"기안자: **{user_name}** ({user_dept}) | 1차: **{target_mgr1}** | 2차: **{target_mgr2}** | 참고: **{', '.join(cc_selected) if cc_selected else '없음'}**")
            content = st.text_area(
                "품의 내용 및 목적 (실행 계획)", 
                placeholder="1. 추진 목적:\n2. 세부 품목 및 단가:\n3. 기대 효과:\n4. 실행 예정일:", 
                height=160
            )
            
            attached_file = st.file_uploader(
                "📎 기안 첨부파일 업로드 (견적서, 시방서, 도면, PDF, 이미지 등)",
                type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "docx", "hwp", "zip"],
                key="new_doc_attachment"
            )
            
            if st.form_submit_button("품의서 결재 상신", type="primary", use_container_width=True):
                if not title.strip() or not content.strip():
                    st.error("품의 제목과 내용을 모두 입력해 주세요.")
                else:
                    mgr2_val = "" if target_mgr2 == "선택 안 함" else target_mgr2
                    att_name = attached_file.name if attached_file is not None else ""
                    success, new_doc_id = insert_approval_doc(
                        doc_type, title, user_name, user_dept, budget,
                        target_mgr1, mgr2_val, cc_selected, content, att_name
                    )
                    if success:
                        if attached_file is not None:
                            att_dict = st.session_state.get("approval_attachments", {})
                            att_dict[str(new_doc_id)] = attached_file
                            st.session_state["approval_attachments"] = att_dict
                        st.session_state["approval_submitted_msg"] = f"✅ [{title}] 품의가 정상 결재 상신 되었습니다. (1차 결재자: {target_mgr1})"
                        st.rerun()
                    else:
                        st.error("품의서 등록 중 오류가 발생했습니다.")

    # --------------------------------
    # 서브탭 2: 결재함 & 내 기안 문서 조회 (최근 기안일시순 정렬 적용)
    # --------------------------------
    with sub2:
        st.subheader("📬 결재함 & 내 관련 문서 조회")
        
        today_kst = get_kst_date()
        one_month_ago = today_kst - timedelta(days=30)
        
        # 상단 조회 필터 (기본 1개월)
        f_col1, f_col2, f_col3 = st.columns([2, 1.5, 1.5])
        with f_col1:
            date_filter = st.date_input(
                "📅 조회 기간 설정 (기본: 최근 1개월, 과거 기간 조정 가능)",
                value=(one_month_ago, today_kst),
                key="app_date_filter"
            )
        with f_col2:
            relation_filter = st.selectbox(
                "🔍 문서 구분 필터",
                ["전체 (내 관련 문서)", "내가 기안한 문서", "내가 결재할 문서(1/2차)", "내가 참고자인 문서"],
                key="app_rel_filter"
            )
        with f_col3:
            status_filter = st.selectbox(
                "📌 결재 상태 필터",
                ["전체", "미승인(결재대기/반려)", "승인완료(집행가능)"],
                key="app_status_filter"
            )

        app_df = get_data("approvals")
        
        if not app_df.empty:
            for c in ['target_manager1', 'target_manager2', 'cc_users', 'attachment_name']:
                if c not in app_df.columns: 
                    app_df[c] = ''
            
            # 1. 본인 관련 결재만 필터링
            def is_related_to_user(row):
                if user_role == "admin":
                    return True
                drafter = str(row.get('drafter_name', '')).strip()
                m1 = str(row.get('target_manager1', '')).strip()
                m2 = str(row.get('target_manager2', '')).strip()
                ccs = [x.strip() for x in str(row.get('cc_users', '')).split(',')]
                return (user_name in [drafter, m1, m2]) or (user_name in ccs)

            filtered_df = app_df[app_df.apply(is_related_to_user, axis=1)].copy()
            
            # 세부 구분 필터 적용
            if relation_filter == "내가 기안한 문서":
                filtered_df = filtered_df[filtered_df['drafter_name'] == user_name]
            elif relation_filter == "내가 결재할 문서(1/2차)":
                filtered_df = filtered_df[(filtered_df['target_manager1'] == user_name) | (filtered_df['target_manager2'] == user_name)]
            elif relation_filter == "내가 참고자인 문서":
                filtered_df = filtered_df[filtered_df['cc_users'].apply(lambda x: user_name in [i.strip() for i in str(x).split(',')])]

            # 결재 상태 필터 적용
            if status_filter == "미승인(결재대기/반려)":
                filtered_df = filtered_df[filtered_df['status'] != '승인완료(집행가능)']
            elif status_filter == "승인완료(집행가능)":
                filtered_df = filtered_df[filtered_df['status'] == '승인완료(집행가능)']

            # 2. 기간 필터링 (created_at 앞 10자리 YYYY-MM-DD 기준)
            if isinstance(date_filter, (tuple, list)) and len(date_filter) == 2:
                start_d, end_d = str(date_filter[0]), str(date_filter[1])
                filtered_df['doc_date'] = filtered_df['created_at'].astype(str).str.slice(0, 10)
                filtered_df = filtered_df[(filtered_df['doc_date'] >= start_d) & (filtered_df['doc_date'] <= end_d)]

            # 3. 최근 기안일시(created_at) 및 숫자형 ID 기준 최신순(내림차순) 정렬
            filtered_df['num_id'] = pd.to_numeric(filtered_df['id'], errors='coerce').fillna(0)
            filtered_df = filtered_df.sort_values(by=['created_at', 'num_id'], ascending=[False, False]).reset_index(drop=True)

            if not filtered_df.empty:
                display_app = filtered_df.rename(columns={
                    'created_at': '기안일시', 'doc_type': '구분', 'title': '제목',
                    'drafter_name': '기안자', 'department': '부서', 'budget': '예산(원)',
                    'status': '결재상태', 'target_manager1': '1차결재자', 'target_manager2': '2차결재자',
                    'cc_users': '참고자', 'attachment_name': '첨부파일'
                })
                show_cols = ['기안일시', '구분', '제목', '기안자', '부서', '예산(원)', '결재상태', '1차결재자', '2차결재자', '참고자', '첨부파일']
                valid_cols = [c for c in show_cols if c in display_app.columns]
                
                st.caption(f"💡 조회된 문서 총 **{len(filtered_df)}건** (최근 기안일시순 정렬) | 표에서 문서를 클릭하면 하단에 상정된 결재 상세 내용 및 수정/결재 창이 열립니다.")
                selection = st.dataframe(
                    display_app[valid_cols],
                    use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="single-row"
                )
                
                selected_rows = selection.selection.rows
                if selected_rows:
                    doc = filtered_df.iloc[selected_rows[0]]
                    doc_id = str(doc['id'])
                    drafter = str(doc.get('drafter_name', ''))
                    target_m1 = str(doc.get('target_manager1', ''))
                    target_m2 = str(doc.get('target_manager2', ''))
                    cc_list = str(doc.get('cc_users', ''))
                    curr_status = str(doc.get('status', ''))
                    att_name = str(doc.get('attachment_name', ''))
                    
                    st.markdown("---")
                    st.subheader(f"📄 [{doc.get('doc_type')}] {doc.get('title')}")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**기안자**: {drafter} ({doc.get('department')})")
                    c2.write(f"**기안일시**: {doc.get('created_at')}")
                    c3.write(f"**소요예산**: {doc.get('budget')} 원")
                    c4.write(f"**결재상태**: `{curr_status}`")
                    st.caption(f"🎯 **결재선**: 1차({target_m1}) ➔ 2차({target_m2}) ➔ 최종(대표) | 👥 **참고자(CC)**: {cc_list}")
                    
                    # 첨부파일 표시 및 다운로드
                    att_dict = st.session_state.get("approval_attachments", {})
                    if doc_id in att_dict:
                        render_file_preview(att_dict[doc_id], f"view_att_{doc_id}")
                    elif att_name and att_name.strip() != "":
                        st.info(f"📎 등록된 첨부파일명: **{att_name}**")

                    # 결재 코멘트 내역 표시
                    if doc.get('manager1_comment'):
                        st.info(f"🗣️ **1차 결재자({doc.get('manager1_name')}) 의견**: {doc.get('manager1_comment')}")
                    if doc.get('manager2_comment'):
                        st.info(f"🗣️ **2차 결재자({doc.get('manager2_name')}) 의견**: {doc.get('manager2_comment')}")
                    if doc.get('final_comment'):
                        st.success(f"👑 **최종 결재자({doc.get('final_approver')}) 의견**: {doc.get('final_comment')}")

                    # ------------------------------------------------
                    # A. 기안자 본인 & 아직 최종 승인 전인 경우 -> [내용 수정 가능]
                    # ------------------------------------------------
                    is_unapproved = curr_status != '승인완료(집행가능)'
                    if user_name == drafter and is_unapproved:
                        st.markdown("#### ✏️ 내 기안 문서 수정 (미승인 상태)")
                        st.caption("아직 최종 승인이 나지 않은 상태이므로 기안 내용을 수정할 수 있습니다.")
                        
                        all_mgr_candidates = [info['name'] for info in users_dict.values() if info['name'] != user_name]
                        if not all_mgr_candidates:
                            all_mgr_candidates = ["기본관리자"]
                            
                        with st.form(key=f"edit_approval_form_{doc_id}"):
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                doc_types = ["구매/지출 품의", "프로젝트 실행 품의", "출장/외근 품의", "일반 업무 품의"]
                                d_idx = doc_types.index(doc.get('doc_type')) if doc.get('doc_type') in doc_types else 0
                                edit_type = st.selectbox("품의 구분", doc_types, index=d_idx)
                                edit_title = st.text_input("품의 제목", value=str(doc.get('title', '')))
                                edit_budget = st.text_input("예상 소요 예산(원)", value=str(doc.get('budget', '0')))
                            with ec2:
                                m1_idx = all_mgr_candidates.index(target_m1) if target_m1 in all_mgr_candidates else 0
                                edit_m1 = st.selectbox("🎯 1차 결재자", all_mgr_candidates, index=m1_idx)
                                
                                m2_options = ["선택 안 함"] + [n for n in all_mgr_candidates if n != edit_m1]
                                m2_idx = m2_options.index(target_m2) if target_m2 in m2_options else 0
                                edit_m2 = st.selectbox("🎯 2차 결재자", m2_options, index=m2_idx)
                                
                                cc_options = [n for n in all_mgr_candidates if n not in [edit_m1, edit_m2]]
                                default_ccs = [c.strip() for c in cc_list.split(',') if c.strip() in cc_options]
                                edit_cc = st.multiselect("👥 참고자", cc_options, default=default_ccs)

                            edit_content = st.text_area("품의 상세 내용", value=str(doc.get('content', '')), height=160)
                            new_att = st.file_uploader(
                                "📎 첨부파일 변경/추가 (선택사항)",
                                type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "docx", "hwp", "zip"],
                                key=f"edit_att_{doc_id}"
                            )
                            
                            if st.form_submit_button("💾 기안 내용 수정 저장", type="primary", use_container_width=True):
                                m2_clean = "" if edit_m2 == "선택 안 함" else edit_m2
                                new_att_name = new_att.name if new_att is not None else None
                                ok, msg = update_approval_doc(
                                    doc_id, edit_type, edit_title, edit_budget,
                                    edit_m1, m2_clean, edit_cc, edit_content, new_att_name
                                )
                                if ok:
                                    if new_att is not None:
                                        att_dict[doc_id] = new_att
                                        st.session_state["approval_attachments"] = att_dict
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        # 기안자가 아니거나 이미 승인된 경우 읽기 전용으로 품의 내용 표시
                        st.text_area("품의 상세 내용", value=doc.get('content', ''), height=150, disabled=True)

                    # ------------------------------------------------
                    # B. 결재권자 심사 및 승인/반려 처리 영역
                    # ------------------------------------------------
                    st.markdown("#### ✍️ 결재 심사 처리")
                    comment_input = st.text_input("결재 코멘트 / 심사의견", key=f"app_comment_{doc_id}")
                    
                    if curr_status == '1차결재대기':
                        if user_name == target_m1 or user_role == "admin":
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button("🔵 1차 승인", type="primary", use_container_width=True):
                                    success, msg = approve_step1(doc_id, user_name, comment_input, is_reject=False)
                                    st.success(msg); st.rerun()
                            with b2:
                                if st.button("❌ 1차 반려", use_container_width=True):
                                    success, msg = approve_step1(doc_id, user_name, comment_input, is_reject=True)
                                    st.warning(msg); st.rerun()
                        else:
                            st.warning(f"🔒 1차 결재자(**{target_m1}**) 승인 대기 중입니다.")
                            
                    elif curr_status == '2차결재대기':
                        if user_name == target_m2 or user_role == "admin":
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button("🔵 2차 승인 (최종결재로 상신)", type="primary", use_container_width=True):
                                    success, msg = approve_step2(doc_id, user_name, comment_input, is_reject=False)
                                    st.success(msg); st.rerun()
                            with b2:
                                if st.button("❌ 2차 반려", use_container_width=True):
                                    success, msg = approve_step2(doc_id, user_name, comment_input, is_reject=True)
                                    st.warning(msg); st.rerun()
                        else:
                            st.warning(f"🔒 2차 결재자(**{target_m2}**) 승인 대기 중입니다.")
                            
                    elif curr_status == '최종결재대기':
                        if user_role == "admin":
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button("👑 최종 승인 완료 (집행 허가)", type="primary", use_container_width=True):
                                    success, msg = approve_final(doc_id, user_name, comment_input, is_reject=False)
                                    st.success(msg); st.rerun()
                            with b2:
                                if st.button("❌ 최종 반려", use_container_width=True):
                                    success, msg = approve_final(doc_id, user_name, comment_input, is_reject=True)
                                    st.warning(msg); st.rerun()
                        else:
                            st.info("🔒 중간 결재가 완료되었습니다. 최종 승인은 대표님(관리자) 권한입니다.")
                    else:
                        st.write(f"현재 문서는 `{curr_status}` 상태입니다.")
            else:
                st.info("선택한 기간 및 조건에 해당하는 본인 관련 결재 문서가 없습니다.")
        else:
            st.info("상신된 결재 문서가 없습니다.")

    # --------------------------------
    # 서브탭 3: 실행 후 지출 정산 등록 & 최종 마감 (최근 기안일시순 정렬 적용)
    # --------------------------------
    with sub3:
        st.subheader("💳 품의 실행 완료 건 지출 정산 & 증빙 관리")
        app_df = get_data("approvals")
        approved_docs = app_df[app_df['status'] == '승인완료(집행가능)'].copy() if not app_df.empty else pd.DataFrame()
        
        if not approved_docs.empty:
            # 정산 목록도 최근 기안일시 및 숫자형 ID 기준 내림차순 정렬
            approved_docs['num_id'] = pd.to_numeric(approved_docs['id'], errors='coerce').fillna(0)
            approved_docs = approved_docs.sort_values(by=['created_at', 'num_id'], ascending=[False, False]).reset_index(drop=True)

            st.markdown("#### 📋 [정산 대상 품의서 목록]")
            st.caption("💡 표에서 정산할 품의서 행(Row)을 마우스로 클릭하면 하단 폼이 해당 품의서로 자동 변경됩니다. (최근 기안일시순)")
            
            display_approved = approved_docs[['created_at', 'title', 'drafter_name', 'department', 'budget', 'spent_amount', 'expense_status']].rename(
                columns={
                    'created_at': '기안일시', 'title': '품의명', 'drafter_name': '기안자',
                    'department': '부서', 'budget': '승인예산(원)', 'spent_amount': '실집행액(원)', 'expense_status': '정산상태'
                }
            )
            
            selection = st.dataframe(
                display_approved,
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row"
            )
            
            selected_rows = selection.selection.rows
            t_row = approved_docs.iloc[selected_rows[0]] if selected_rows else approved_docs.iloc[0]
            t_id = str(t_row['id'])
            
            st.markdown("---")
            st.subheader(f"📝 [{t_row.get('title')}] 실 지출내역 및 증빙 관리")
            
            c_info1, c_info2, c_info3 = st.columns(3)
            c_info1.info(f"**기안자**: {t_row.get('drafter_name')} ({t_row.get('department')})")
            c_info2.info(f"**승인 예산**: {t_row.get('budget')} 원")
            c_info3.info(f"**정산 진행상태**: `{t_row.get('expense_status', '정산대기')}`")
            
            uploaded_receipt = st.file_uploader(
                "📎 영수증 / 카드전표 / 세금계산서 증빙 파일 업로드", 
                type=["png", "jpg", "jpeg", "pdf"], 
                key=f"receipt_upload_{t_id}"
            )
            
            receipt_dict = st.session_state.get("expense_receipts", {})
            if uploaded_receipt is not None:
                receipt_dict[t_id] = uploaded_receipt
                st.session_state["expense_receipts"] = receipt_dict
                
            if t_id in receipt_dict:
                render_file_preview(receipt_dict[t_id], f"receipt_dl_{t_id}")
            
            with st.form(key=f"expense_form_{t_id}"):
                actual_spent = st.text_input("실제 사용 금액 (원)", value=str(t_row.get('spent_amount', '0')))
                spent_desc = st.text_area(
                    "지출 세부 내역 (품목, 수량, 거래처, 계좌번호 등)", 
                    value=str(t_row.get('expense_details', '')),
                    placeholder="예: 영수증 번호 2026-08 / 우리카드 법인결제 / 세금계산서 발행 완료"
                )
                
                b_sub, b_fin = st.columns(2)
                with b_sub:
                    if st.form_submit_button("📤 지출 내역 상신 (정산 요청)", type="primary", use_container_width=True):
                        success, msg = submit_expense_report(t_id, actual_spent, spent_desc)
                        st.success(msg); st.rerun()
                with b_fin:
                    is_finance_manager = (user_role == "admin" or user_dept == "총무부")
                    if is_finance_manager:
                        if st.form_submit_button("👑 [총무부/관리자] 지출 정산 최종 승인 및 마감", use_container_width=True):
                            success, msg = finalize_expense(t_id)
                            st.success(msg); st.rerun()
                    else:
                        st.caption("🔒 정산 최종 승인 및 마감은 **총무부** 및 **관리자**만 가능합니다.")
        else:
            st.info("현재 최종 승인되어 정산 가능한 품의서가 없습니다.")
