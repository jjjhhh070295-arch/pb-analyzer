"""
1단계 시연 스크립트 (PB 고객 분석 시스템)

전체 흐름을 한 번에 보여준다:
  1) 고객 등록 (동명이인 처리)
  2) 고객 상담 원문 분석 (7요인 추출)
  3) 규칙 검증 (플래그·추가질문·optimizer 제약)
  4) 세션 저장 (엑셀)
  5) 다시 불러오기 (날짜/PB/고객 필터)
  6) PB 검수 화면 형태로 출력

실행: python demo.py
실제 사용 시: make_demo_llm() 대신 AnthropicLLMClient(api_key=...) 를 쓰면 된다.
"""

from __future__ import annotations

import os
import tempfile

from mock_llm import make_mock_llm
from analyzer import analyze
from validators import validate
from customer_repository import ExcelCustomerRepository, resolve_customer, ResolveResult
from session_repository import ExcelSessionRepository
from models import SessionStatus, Confidence, FactorStatus


# ---------------------------------------------------------------------------
# 데모용 가짜 LLM (실사용 시 AnthropicLLMClient로 교체)
# ---------------------------------------------------------------------------

def make_demo_llm():
    return make_mock_llm({
        'goal_return': {'status':'inferred','evidence':'은퇴 후에도 생활수준 유지','confidence':'중',
                        'return_min':0.07,'return_max':0.09,'raw_text':'연 7~9%'},
        'risk_tolerance': {'status':'explicit',
                           'willingness':{'level':'낮음','evidence':'2년 전 손실로 마음고생','confidence':'상'},
                           'capacity':{'level':'높음','evidence':'총자산 50억 중 10억 운용','confidence':'중'},
                           'binding':'willingness'},
        'horizon': {'status':'explicit','evidence':'5년 뒤 자녀 유학자금','confidence':'상','years':5},
        'tax': {'status':'inferred','evidence':'배당으로 연 3천만원 이상','confidence':'중',
                'items':['배당소득 있음'],'annual_financial_income':30000000},
        'liquidity': {'status':'explicit','evidence':'내년 봄 상가 잔금','confidence':'상',
                      'events':[{'when':'1년 내','amount':200000000,'purpose':'부동산 잔금'}]},
        'legal': {'status':'missing','evidence':None,'confidence':None,'items':[]},
        'unique': {'status':'explicit','evidence':'담배나 도박 회사엔 돈 넣기 싫다','confidence':'중',
                   'notes':['ESG 선호'],'excluded_sectors':['tobacco','gambling']},
    })


SAMPLE_TEXT = """은퇴가 한 10년 남았는데 그 뒤에도 지금 생활수준은 유지하고 싶어요. 연 7~9% 정도면 좋겠고.
2년 전에 주식으로 크게 물려서 마음고생을 좀 했어요. 막 공격적인 건 부담스럽습니다.
다만 전체 자산이 50억쯤 되는데 이번에 운용 맡기려는 건 10억 정도라 여유는 있어요.
5년 뒤에 애 유학 자금이 들어가야 하고, 내년 봄에는 상가 잔금 2억을 치러야 합니다.
배당으로 매년 3천만원 넘게 받고 있고요. 담배나 도박 같은 회사엔 돈 넣기 싫습니다."""


def hr(title=""):
    print("\n" + "═"*64)
    if title: print(f" {title}")
    if title: print("═"*64)


def print_pb_screen(session):
    """PB 검수 화면 형태 출력: 7요인(인라인 표시) + 검토 탭 + 추가질문 + 제약."""
    r = session.result
    conf = lambda c: c.value if c else "-"

    hr(f"[PB 화면] {session.customer_name} / 담당 {session.pb_name} / {session.consult_date} / 상태:{session.status}")

    # 인라인 플래그를 요인별로 모음
    inline = {}
    for f in r.flags:
        if f.inline_factor:
            inline.setdefault(f.inline_factor, []).append(f)

    def mark(attr, status, confidence):
        tags = []
        if status == FactorStatus.MISSING:
            tags.append("⚠정보없음")
        elif confidence == Confidence.LOW:
            tags.append("⚠신뢰도:하")
        for f in inline.get(attr, []):
            tags.append(f"🔎{f.rule_id}")
        return ("  " + " ".join(tags)) if tags else ""

    print("\n── 7요인 분석 ──")
    g = r.goal_return
    print(f"① 목표수익률 : {g.raw_text or '-'}  (신뢰도 {conf(g.meta.confidence)}, {g.meta.status.value}){mark('goal_return', g.meta.status, g.meta.confidence)}")
    print(f"   근거: {g.meta.evidence or '-'}")
    rt = r.risk_tolerance
    print(f"② 위험허용도 : 의향={rt.willingness.level or '-'} / 능력={rt.capacity.level or '-'} → 적용:{rt.binding or '-'}{mark('risk_tolerance', rt.status, None)}")
    print(f"   의향근거: {rt.willingness.evidence or '-'}")
    print(f"   능력근거: {rt.capacity.evidence or '-'}")
    h = r.horizon
    print(f"③ 투자기간   : {h.years if h.years is not None else '-'}년  (신뢰도 {conf(h.meta.confidence)}){mark('horizon', h.meta.status, h.meta.confidence)}")
    t = r.tax
    print(f"④ 세금요인   : {', '.join(t.items) or '-'}{mark('tax', t.meta.status, t.meta.confidence)}")
    if t.annual_financial_income:
        print(f"   연 금융소득: {t.annual_financial_income:,.0f}원")
    lq = r.liquidity
    evs = "; ".join(f"{e.when} {e.amount:,.0f}원({e.purpose})" if e.amount else f"{e.when}({e.purpose})" for e in lq.events) or "-"
    print(f"⑤ 유동성     : {evs}{mark('liquidity', lq.meta.status, lq.meta.confidence)}")
    lg = r.legal
    print(f"⑥ 법적제약   : {', '.join(lg.items) or '-'}{mark('legal', lg.meta.status, lg.meta.confidence)}")
    u = r.unique
    print(f"⑦ 고유상황   : {', '.join(u.notes) or '-'}  배제섹터:{u.excluded_sectors or '-'}{mark('unique', u.meta.status, u.meta.confidence)}")

    # 검토 탭 (인라인 아닌 횡단 플래그)
    tab = [f for f in r.flags if not f.inline_factor]
    print(f"\n── 검토 탭 ({len(tab)}건) ──")
    icon = {"red":"🔴","yellow":"🟡","gray":"⚪"}
    for f in tab:
        print(f"  {icon.get(f.severity,'•')} [{f.rule_id}] {f.message}")
    if not tab:
        print("  (없음)")

    # 추가질문
    print(f"\n── 고객에게 추가로 물어볼 질문 ({len(r.follow_up_questions)}건) ──")
    for q in r.follow_up_questions:
        print(f"  • {q}")

    # optimizer 제약 (포트폴리오 엔진 입력)
    oc = r.optimizer_constraints
    print(f"\n── 포트폴리오 엔진 입력 제약 {'(잠정)' if oc.provisional else ''} ──")
    print(f"  투자기간≤{oc.max_horizon_years}년 / 최소현금 {oc.min_cash_reserve:,.0f}원 / "
          f"위험등급:{oc.risk_level} / 배제:{oc.excluded_sectors}")


def main():
    tmp = tempfile.mkdtemp()
    cust_path = os.path.join(tmp, "customers.xlsx")
    sess_path = os.path.join(tmp, "sessions.xlsx")
    cust_repo = ExcelCustomerRepository(cust_path)
    sess_repo = ExcelSessionRepository(sess_path)
    llm = make_demo_llm()

    # 1) 고객 등록 (동명이인 시연)
    hr("STEP 1. 고객 등록")
    c1 = cust_repo.add_customer("김영수", "1968-03-12", "박상우")
    c2 = cust_repo.add_customer("김영수", "1981-07-25", "이지은")  # 동명이인
    print(f"등록: {c1.customer_id} {c1.display_label()}")
    print(f"등록: {c2.customer_id} {c2.display_label()}")
    res = resolve_customer(cust_repo, "김영수")
    print(f"\n'김영수' 검색 → {res.kind.upper()} (동명이인 {len(res.candidates)}명, PB가 선택 필요)")
    chosen = c1
    print(f"PB가 선택: {chosen.customer_id} {chosen.display_label()}")

    # 2~3) 분석 + 검증
    hr("STEP 2-3. 상담 원문 분석 + 규칙 검증")
    print("입력 원문:\n" + SAMPLE_TEXT)
    report = analyze(SAMPLE_TEXT, llm)
    result = report.result
    result.total_investable = 1_000_000_000
    validate(result, raw_text=SAMPLE_TEXT)
    print(f"\n분석 완료 (요인 오류: {report.errors or '없음'})")

    # 4) 저장
    hr("STEP 4. 세션 저장 (엑셀)")
    sess = sess_repo.save(chosen.customer_id, chosen.name, chosen.primary_pb,
                          SAMPLE_TEXT, result)
    print(f"저장됨: 세션 {sess.session_id} → {sess_path}")

    # 5) 다시 불러오기
    hr("STEP 5. 다시 불러오기 (담당 PB로 필터)")
    loaded = sess_repo.list_filtered(pb_name="박상우")
    for s in loaded:
        print(f"  {s.session_id} | {s.consult_date} | {s.customer_name} | 상태:{s.status}")

    # 6) PB 검수 화면
    reloaded = sess_repo.get(sess.session_id)
    print_pb_screen(reloaded)

    # PB 검수 확정 → 상태 변경 (고객 화면 노출 게이트)
    hr("STEP 6. PB 검수 확정 → 상태 변경")
    sess_repo.update_status(sess.session_id, SessionStatus.CONFIRMED.value)
    print(f"세션 {sess.session_id} 상태: {SessionStatus.DRAFT.value} → {SessionStatus.CONFIRMED.value}")
    print("(이제 확정본이 고객 화면으로 노출 가능)")

    hr("시연 완료")
    print(f"엑셀 파일 위치:\n  고객: {cust_path}\n  세션: {sess_path}")


if __name__ == "__main__":
    main()
