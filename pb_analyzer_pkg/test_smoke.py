"""
스모크 테스트: 핵심 흐름이 깨지지 않았는지 빠르게 확인.
실행: python test_smoke.py  (성공 시 'ALL PASSED' 출력)
네트워크/API 키 불필요(mock 사용).
"""

from mock_llm import make_mock_llm
from analyzer import analyze
from validators import validate
from customer_repository import ExcelCustomerRepository, resolve_customer, ResolveResult
from session_repository import ExcelSessionRepository
from analysis_schema import AnalysisResult
from models import SessionStatus, FactorStatus
import tempfile, os, json


def test_serialization_roundtrip():
    """7요인 결과 JSON 왕복이 손실 없는지."""
    r = AnalysisResult()
    r.goal_return.return_min, r.goal_return.return_max = 0.07, 0.09
    r.unique.excluded_sectors = ["tobacco"]
    restored = AnalysisResult.from_dict(json.loads(json.dumps(r.to_dict(), ensure_ascii=False)))
    assert restored.to_dict() == r.to_dict(), "JSON 왕복 불일치"


def test_duplicate_names():
    """동명이인이 다른 고유ID로 등록되고 검색 시 MULTIPLE인지."""
    tmp = tempfile.mkdtemp()
    repo = ExcelCustomerRepository(os.path.join(tmp, "c.xlsx"))
    a = repo.add_customer("홍길동", "1970-01-01", "PB1")
    b = repo.add_customer("홍길동", "1985-05-05", "PB2")
    assert a.customer_id != b.customer_id, "동명이인 ID 충돌"
    res = resolve_customer(repo, "홍길동")
    assert res.kind == ResolveResult.MULTIPLE and len(res.candidates) == 2


def test_full_pipeline_and_rules():
    """분석→검증→저장→불러오기, 핵심 규칙(A-1, B-3) 발동 확인."""
    llm = make_mock_llm({
        'tax': {'status':'inferred','evidence':'배당 연 3천','confidence':'중',
                'items':['배당소득 있음'],'annual_financial_income':30000000},
        'risk_tolerance': {'status':'explicit',
            'willingness':{'level':'낮음','evidence':'손실경험','confidence':'상'},
            'capacity':{'level':'높음','evidence':'여유자금','confidence':'중'},'binding':'willingness'},
        'liquidity': {'status':'explicit','evidence':'잔금','confidence':'상',
                      'events':[{'when':'1년 내','amount':200000000,'purpose':'잔금'}]},
        'horizon': {'status':'explicit','evidence':'5년','confidence':'상','years':5},
    })
    r = analyze("배당 연 3천, 손실경험 보수적이나 여유자금 많음, 1년내 잔금 2억, 5년 투자", llm).result
    r.total_investable = 1_000_000_000
    validate(r)
    rule_ids = {f.rule_id for f in r.flags}
    assert "A-1" in rule_ids, "A-1(종합과세) 미발동"
    assert "B-3" in rule_ids, "B-3(위험 격차) 미발동"
    # missing 요인(goal_return 등) → 추가질문 생성 확인
    assert len(r.follow_up_questions) > 0, "추가질문 미생성"

    tmp = tempfile.mkdtemp()
    srepo = ExcelSessionRepository(os.path.join(tmp, "s.xlsx"))
    sess = srepo.save("C0001", "홍길동", "PB1", "원문", r)
    reloaded = srepo.get(sess.session_id)
    assert reloaded.result.tax.annual_financial_income == 30000000, "저장/복원 불일치"
    srepo.update_status(sess.session_id, SessionStatus.CONFIRMED.value)
    assert srepo.get(sess.session_id).status == SessionStatus.CONFIRMED.value


if __name__ == "__main__":
    test_serialization_roundtrip()
    test_duplicate_names()
    test_full_pipeline_and_rules()
    print("ALL PASSED")
