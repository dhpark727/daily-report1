import streamlit as st
import pandas as pd
from db_manager import (
    get_data, get_user_credentials, insert_approval_doc,
    approve_step1, approve_step2, approve_final,
    submit_expense_report, finalize_expense
)

def render_approval_tab(user_name, user_dept, user_role):
    # 세션 상태 안전 초기화
    if "expense_receipts" not in st.session_state:
        st.session_state["expense_receipts"] = {}

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
    # 서브탭 1: 신규 품의서 기안
    # --------------------------------
    with sub1:
        st.subheader("새로운 품의서 작성")
        
        # 기안 상신 성공 알림 메시지 노출 영역
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
                height=180
            )
            
            if st.form_submit_button("품의서 결재 상신", type="primary", use_container_width=True):
                if not title.strip() or not content.strip():
                    st.error("품의 제목과 내용을 모두 입력해 주세요.")
                else:
                    mgr2_val = "" if target_mgr2 == "선택 안 함" else target_mgr2
                    success, _ = insert_approval_doc(doc_type, title, user_name, user_dept, budget, target_mgr1, mgr2_val, cc_selected, content)
                    if success:
                        st.session_state["approval_submitted_msg"] = f"✅ [{title}] 품의가 정상 결재 상신 되었습니다. (1차 결재자: {target_mgr1})"
                        st.rerun()
                    else:
                        st.error("품의서 등록 중 오류가 발생했습니다.")

    # --------------------------------
    # 서브탭 2: 결재함 & 내 기안 문서 조회
    # --------------------------------
    with sub2:
        st.subheader("전자결재 승인 대기 목록 및 문서함")
        app_df = get_data("approvals")
        
        if not app_df.empty:
            for c in ['target_manager1', 'target_manager2', 'cc_users']:
                if c not in app_df.columns: 
                    app_df[c] = ''
                
            display_app = app_df.rename(columns={
                'created_at': '기안일시', 'doc_type': '구분', 'title': '제목',
                'drafter_name': '기안자', 'department': '부서', 'budget': '예산(원)',
                'status': '결재상태', 'target_manager1': '1차결재자', 'target_manager2': '2차결재자', 'cc_users': '참고자'
            })
            show_cols = ['기안일시', '구분', '제목', '기안자', '부서', '예산(원)', '결재상태', '1차결재자', '2차결재자', '참고자']
            valid_cols = [c for c in show_cols if c in display_app.columns]
            
            st.caption("💡 결재하거나 상세 내용을 검토할 문서를 표에서 클릭하세요.")
            selection = st.dataframe(
                display_app[valid_cols].reset_index(drop=True),
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row"
            )
            
            selected_rows = selection.selection.rows
            if selected_rows:
                doc = app_df.iloc[selected_rows[0]]
                doc_id = str(doc['id'])
                target_m1 = str(doc.get('target_manager1', ''))
                target_m2 = str(doc.get('target_manager2', ''))
                cc_list = str(doc.get('cc_users', ''))
                curr_status = str(doc.get('status', ''))
                
                st.markdown("---")
                st.subheader(f"📄 [{doc.get('doc_type')}] {doc.get('title')}")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"**기안자**: {doc.get('drafter_name')} ({doc.get('department')})")
                c2.write(f"**기안일시**: {doc.get('created_at')}")
                c3.write(f"**소요예산**: {doc.get('budget')} 원")
                c4.write(f"**결재선**: 1차({target_m1}) ➔ 2차({target_m2}) ➔ 최종(대표)")
                st.caption(f"👥 **참고자(CC)**: {cc_list}")
                
                st.text_area("품의 상세 내용", value=doc.get('content', ''), height=150, disabled=True)
                
                if doc.get('manager1_comment'):
                    st.info(f"🗣️ **1차 승인자({doc.get('manager1_name')}) 코멘트**: {doc.get('manager1_comment')}")
                if doc.get('manager2_comment'):
                    st.info(f"🗣️ **2차 승인자({doc.get('manager2_name')}) 코멘트**: {doc.get('manager2_comment')}")
                if doc.get('final_comment'):
                    st.success(f"👑 **최종 승인자({doc.get('final_approver')}) 코멘트**: {doc.get('final_comment')}")
                
                st.markdown("#### ✍️ 결재 처리")
                comment_input = st.text_input("결재 코멘트 / 심사의견", key=f"app_comment_{doc_id}")
                
                # 1차 결재
                if curr_status == '1차결재대기':
                    if user_name == target_m1 or user_role == "admin":
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("🔵 1차 승인", type="primary", use_container_width=True):
                                success, msg = approve_step1(doc_id, user_name, comment_input, is_reject=False)
                                st.success(msg)
                                st.rerun()
                        with b2:
                            if st.button("❌ 1차 반려", use_container_width=True):
                                success, msg = approve_step1(doc_id, user_name, comment_input, is_reject=True)
                                st.warning(msg)
                                st.rerun()
                    else:
                        st.warning(f"🔒 1차 결재자(**{target_m1}**)만 결재할 수 있습니다.")
                        
                # 2차 결재
                elif curr_status == '2차결재대기':
                    if user_name == target_m2 or user_role == "admin":
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("🔵 2차 승인 (최종결재로 상신)", type="primary", use_container_width=True):
                                success, msg = approve_step2(doc_id, user_name, comment_input, is_reject=False)
                                st.success(msg)
                                st.rerun()
                        with b2:
                            if st.button("❌ 2차 반려", use_container_width=True):
                                success, msg = approve_step2(doc_id, user_name, comment_input, is_reject=True)
                                st.warning(msg)
                                st.rerun()
                    else:
                        st.warning(f"🔒 2차 결재자(**{target_m2}**)만 결재할 수 있습니다.")
                        
                # 최종 결재
                elif curr_status == '최종결재대기':
                    if user_role == "admin":
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("👑 최종 승인 완료 (집행 허가)", type="primary", use_container_width=True):
                                success, msg = approve_final(doc_id, user_name, comment_input, is_reject=False)
                                st.success(msg)
                                st.rerun()
                        with b2:
                            if st.button("❌ 최종 반려", use_container_width=True):
                                success, msg = approve_final(doc_id, user_name, comment_input, is_reject=True)
                                st.warning(msg)
                                st.rerun()
                    else:
                        st.info("🔒 중간 결재가 완료되었습니다. 최종 승인은 대표님(관리자) 권한입니다.")
                else:
                    st.write(f"현재 문서는 `{curr_status}` 상태로 결재 처리가 완료되었습니다.")
        else:
            st.info("상신된 결재 문서가 없습니다.")

    # --------------------------------
    # 서브탭 3: 실행 후 지출 정산 등록 & 최종 마감
    # --------------------------------
    with sub3:
        st.subheader("💳 품의 실행 완료 건 지출 정산 & 증빙 관리")
        app_df = get_data("approvals")
        approved_docs = app_df[app_df['status'] == '승인완료(집행가능)'].copy() if not app_df.empty else pd.DataFrame()
        
        if not approved_docs.empty:
            st.write("**[정산 대상 품의서 목록]**")
            st.dataframe(
                approved_docs[['created_at', 'title', 'drafter_name', 'department', 'budget', 'spent_amount', 'expense_status']].rename(
                    columns={'created_at': '기안일', 'title': '품의명', 'drafter_name': '기안자', 'department': '부서', 'budget': '승인예산', 'spent_amount': '실집행액', 'expense_status': '정산상태'}
                ),
                use_container_width=True, hide_index=True
            )
            
            st.markdown("---")
            st.subheader("📝 실 지출내역 및 영수증 증빙 등록")
            
            doc_options = {f"[{r['id']}] {r['title']} (승인예산: {r['budget']}원)": r['id'] for _, r in approved_docs.iterrows()}
            sel_target = st.selectbox("지출 등록/검토할 품의서를 선택하세요", list(doc_options.keys()))
            
            if sel_target:
                t_id = doc_options[sel_target]
                t_row = approved_docs[approved_docs['id'] == t_id].iloc[0]
                
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
                    st.image(receipt_dict[t_id], caption="📄 첨부된 영수증 증빙 서류", width=400)
                
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
                            st.success(msg)
                            st.rerun()
                    with b_fin:
                        is_finance_manager = (user_role == "admin" or user_dept == "총무부")
                        if is_finance_manager:
                            if st.form_submit_button("👑 [총무부/관리자] 지출 정산 최종 승인 및 마감", use_container_width=True):
                                success, msg = finalize_expense(t_id)
                                st.success(msg)
                                st.rerun()
                        else:
                            st.caption("🔒 정산 최종 승인 및 마감은 **총무부** 및 **관리자**만 가능합니다.")
        else:
            st.info("현재 최종 승인되어 정산 가능한 품의서가 없습니다.")
