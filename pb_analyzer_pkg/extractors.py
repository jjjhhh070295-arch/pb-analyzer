"""
요인별 추출기 (Extractors)

설계:
  - 요인마다 전용 프롬프트. 단, '전체 고객 원문'은 항상 통째로 제공하여
    요인 간 맥락(예: 자산 규모 언급)이 끊기지 않게 한다.
  - LLM에는 "지정한 JSON 스키마로만, 설명 없이" 출력하도록 강하게 지시.
  - 정보가 없으면 추측하지 말고 status="missing" + 신뢰도 null 로 반환하도록 지시.
  - 각 추출기는 (전체텍스트, llm) -> 스키마객체 를 반환한다.

신뢰도는 상/중/하 문자열로 받는다.
"""

from __future__ import annotations

from typing import Optional

from llm_client import LLMClient, extract_json
from models import Confidence, FactorStatus
from analysis_schema import (
    FactorMeta, GoalReturn, RiskTolerance, RiskAxis, InvestmentHorizon,
    TaxFactors, LiquidityNeeds, LiquidityEvent, LegalConstraints, UniqueSituation,
)

# 모든 추출기 프롬프트에 공통으로 박는 규칙
_COMMON_RULES = """\
너는 한국 증권사 PB를 돕는 고객 상황 분석기다. 아래 고객 상담 원문을 읽고, 지정된 한 가지 요인만 분석한다.
반드시 지켜라:
- 원문에 근거가 없으면 추측하지 마라. 그 경우 status는 "missing", confidence는 null로 둔다.
- 추출한 값에는 반드시 원문에서 그 판단의 근거가 된 부분을 evidence로 짧게 인용하라.
- confidence는 "상", "중", "하" 중 하나. 근거가 명확하고 직접적이면 "상", 정황 추론이면 "중" 또는 "하".
- status는 "explicit"(고객이 명시), "inferred"(정황 추론), "missing"(정보 없음) 중 하나.
- 출력은 지정한 JSON 객체 하나만. 코드펜스나 설명 문장을 붙이지 마라.
"""


def _conf(v) -> Optional[Confidence]:
    if v in ("상", "중", "하"):
        return Confidence(v)
    return None


def _status(v) -> FactorStatus:
    try:
        return FactorStatus(v)
    except ValueError:
        return FactorStatus.MISSING


# ---------------------------------------------------------------------------
# 1. 목표수익률
# ---------------------------------------------------------------------------

_GOAL_PROMPT = _COMMON_RULES + """
[분석 요인] 목표수익률 (연 단위 기대수익률)
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "원문 근거 인용 또는 null",
  "confidence": "상|중|하 또는 null",
  "return_min": 0.07,   // 연 수익률 하한(소수). 모르면 null
  "return_max": 0.09,   // 연 수익률 상한(소수). 단일값이면 min=max. 모르면 null
  "raw_text": "연 7~9%"  // 고객이 표현한 원래 문구. 없으면 null
}
"""


def extract_goal_return(text: str, llm: LLMClient) -> GoalReturn:
    raw = llm.complete(_GOAL_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    return GoalReturn(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        return_min=d.get("return_min"), return_max=d.get("return_max"),
        raw_text=d.get("raw_text"),
    )


# ---------------------------------------------------------------------------
# 2. 위험허용도 (의향/능력 이중 축)
# ---------------------------------------------------------------------------

_RISK_PROMPT = _COMMON_RULES + """
[분석 요인] 위험허용도. 반드시 두 축으로 분리한다.
- willingness(감수 의향): 심리·경험·성향 기반. 예) 과거 손실 경험, 변동성에 대한 태도.
- capacity(감수 능력): 재무 여력 기반. 예) 총자산 대비 운용액 비중, 소득, 부양 부담.
두 축은 다를 수 있다(의향은 낮지만 능력은 높은 경우 등). 각 축의 level은 "높음|중립|낮음".
binding은 더 보수적인(낮은) 축의 이름("willingness" 또는 "capacity"). 둘 다 없으면 null.
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "willingness": {"level": "높음|중립|낮음 또는 null", "evidence": "근거 또는 null", "confidence": "상|중|하 또는 null"},
  "capacity":    {"level": "높음|중립|낮음 또는 null", "evidence": "근거 또는 null", "confidence": "상|중|하 또는 null"},
  "binding": "willingness|capacity 또는 null"
}
"""


def extract_risk_tolerance(text: str, llm: LLMClient) -> RiskTolerance:
    raw = llm.complete(_RISK_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    w = d.get("willingness", {}) or {}
    c = d.get("capacity", {}) or {}
    return RiskTolerance(
        status=_status(d.get("status")),
        willingness=RiskAxis(w.get("level"), w.get("evidence"), _conf(w.get("confidence"))),
        capacity=RiskAxis(c.get("level"), c.get("evidence"), _conf(c.get("confidence"))),
        binding=d.get("binding"),
    )


# ---------------------------------------------------------------------------
# 3. 투자 기간
# ---------------------------------------------------------------------------

_HORIZON_PROMPT = _COMMON_RULES + """
[분석 요인] 투자 기간 (자금을 묶어둘 수 있는 기간, 연 단위)
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "근거 또는 null",
  "confidence": "상|중|하 또는 null",
  "years": 5   // 투자 기간(년). 모르면 null
}
"""


def extract_horizon(text: str, llm: LLMClient) -> InvestmentHorizon:
    raw = llm.complete(_HORIZON_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    return InvestmentHorizon(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        years=d.get("years"),
    )


# ---------------------------------------------------------------------------
# 4. 세금 요인
# ---------------------------------------------------------------------------

_TAX_PROMPT = _COMMON_RULES + """
[분석 요인] 세금 요인. 한국 세제 관점에서 고려할 사항을 뽑는다.
- 연간 금융소득(이자+배당)이 언급되면 원 단위 숫자로 annual_financial_income에 넣어라(예: 3천만원 -> 30000000).
- 종합과세/양도세/증여 등 고객이 언급했거나 명확히 추론되는 항목을 items에 넣어라.
- 세금 판정(예: 종합과세 대상 여부)은 시스템 규칙이 따로 한다. 여기서는 단정하지 말고 사실만 추출.
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "근거 또는 null",
  "confidence": "상|중|하 또는 null",
  "items": ["배당소득 있음"],          // 없으면 []
  "annual_financial_income": 30000000  // 모르면 null
}
"""


def extract_tax(text: str, llm: LLMClient) -> TaxFactors:
    raw = llm.complete(_TAX_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    return TaxFactors(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        items=d.get("items", []) or [],
        annual_financial_income=d.get("annual_financial_income"),
    )


# ---------------------------------------------------------------------------
# 5. 유동성 필요시기
# ---------------------------------------------------------------------------

_LIQUIDITY_PROMPT = _COMMON_RULES + """
[분석 요인] 유동성 필요시기. 가까운 장래에 현금이 필요한 사건들을 뽑는다.
각 사건은 시점(when), 금액(amount, 원 단위), 용도(purpose)로 구성. 금액 미상이면 null.
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "근거 또는 null",
  "confidence": "상|중|하 또는 null",
  "events": [
    {"when": "1년 내", "amount": 200000000, "purpose": "부동산 잔금"}
  ]   // 없으면 []
}
"""


def extract_liquidity(text: str, llm: LLMClient) -> LiquidityNeeds:
    raw = llm.complete(_LIQUIDITY_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    events = [LiquidityEvent(e.get("when"), e.get("amount"), e.get("purpose"))
              for e in (d.get("events", []) or [])]
    return LiquidityNeeds(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        events=events,
    )


# ---------------------------------------------------------------------------
# 6. 법적 제약
# ---------------------------------------------------------------------------

_LEGAL_PROMPT = _COMMON_RULES + """
[분석 요인] 법적 제약. 투자에 영향을 주는 법적·제도적 제약을 뽑는다.
예) 신탁 설정, 증여/상속 진행, 미성년 계좌, 해외 거주 신분, 직무상 거래제한 등.
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "근거 또는 null",
  "confidence": "상|중|하 또는 null",
  "items": ["신탁 진행 중"]   // 없으면 []
}
"""


def extract_legal(text: str, llm: LLMClient) -> LegalConstraints:
    raw = llm.complete(_LEGAL_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    return LegalConstraints(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        items=d.get("items", []) or [],
    )


# ---------------------------------------------------------------------------
# 7. 고객 고유 상황
# ---------------------------------------------------------------------------

_UNIQUE_PROMPT = _COMMON_RULES + """
[분석 요인] 고객 고유 상황. 앞의 6개 요인(목표수익률/위험/기간/세금/유동성/법적제약)으로
분류되지 않는 특이사항을 뽑는다. 예) ESG·종교적 신념에 따른 특정 업종 기피, 특정 자산 선호 등.
- 특정 업종을 투자에서 배제하려는 의사가 있으면 excluded_sectors에 영문 키워드로 넣어라
  (예: 담배 -> "tobacco", 도박 -> "gambling", 주류 -> "alcohol", 무기 -> "weapons").
[출력 JSON 스키마]
{
  "status": "explicit|inferred|missing",
  "evidence": "근거 또는 null",
  "confidence": "상|중|하 또는 null",
  "notes": ["ESG 선호"],              // 없으면 []
  "excluded_sectors": ["tobacco"]      // 없으면 []
}
"""


def extract_unique(text: str, llm: LLMClient) -> UniqueSituation:
    raw = llm.complete(_UNIQUE_PROMPT, f"[고객 상담 원문]\n{text}")
    d = extract_json(raw)
    return UniqueSituation(
        meta=FactorMeta(_status(d.get("status")), d.get("evidence"), _conf(d.get("confidence"))),
        notes=d.get("notes", []) or [],
        excluded_sectors=d.get("excluded_sectors", []) or [],
    )
