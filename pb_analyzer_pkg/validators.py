"""
규칙 검증 레이어 (Validators)

분석 엔진이 만든 AnalysisResult를 받아:
  1) A/B/C/D 규칙을 적용해 Flag를 단다 (인라인 or 검토 탭, 심각도별).
  2) missing 요인에 대응하는 추가질문을 생성한다 (C-4).
  3) optimizer 제약을 요인에서 번역해 채운다 (+ D-3 신뢰도 전파).

설계: 각 규칙은 (result) -> list[Flag] 형태의 독립 함수.
       토글로 켜고 끌 수 있다. validate()가 전체를 묶어 실행한다.
"""

from __future__ import annotations

import re

from models import Confidence, FactorStatus, Severity
from analysis_schema import AnalysisResult, Flag, OptimizerConstraints
import rules_config as cfg


# ===========================================================================
# A. 세법 기준 규칙
# ===========================================================================

def rule_A1(r: AnalysisResult) -> list[Flag]:
    """금융소득종합과세 판정. 2천만 원 초과 시 세금 항목에 확정 추가."""
    inc = r.tax.annual_financial_income
    if inc is None:
        return []
    if inc > cfg.FINANCIAL_INCOME_THRESHOLD:
        label = "금융소득종합과세 대상"
        if label not in r.tax.items:
            r.tax.items.append(label)
        # 합산 근거가 불완전(inferred)하면 신뢰도 중 + 추가질문
        flags = [Flag("A-1", Severity.YELLOW.value,
                      f"연 금융소득 {inc:,.0f}원 → 종합과세 대상(기준 {cfg.FINANCIAL_INCOME_THRESHOLD:,}원 초과)",
                      inline_factor="tax")]
        if r.tax.meta.status == FactorStatus.INFERRED:
            q = "이자·배당을 합한 연간 금융소득이 정확히 얼마인지 확인 가능할까요?"
            if q not in r.follow_up_questions:
                r.follow_up_questions.append(q)
        return flags
    return []


def rule_A2(r: AnalysisResult) -> list[Flag]:
    """건강보험료 영향 플래그(검토 필요만)."""
    inc = r.tax.annual_financial_income
    if inc is not None and inc > cfg.FINANCIAL_INCOME_THRESHOLD:
        return [Flag("A-2", Severity.YELLOW.value,
                     "금융소득 증가에 따른 건강보험 피부양자 자격·보험료 영향 검토 필요",
                     inline_factor=None)]
    return []


def rule_A3(r: AnalysisResult) -> list[Flag]:
    """고배당주 보유 시 분리과세 특례 검토 플래그(PB 검토 필요)."""
    blob = " ".join(r.tax.items + r.unique.notes + [r.tax.meta.evidence or ""])
    if any(k in blob for k in cfg.HIGH_DIVIDEND_KEYWORDS):
        return [Flag("A-3", Severity.GRAY.value,
                     "고배당 관련 언급 → 배당소득 분리과세 특례 적용 가능 여부 PB 검토 필요",
                     inline_factor=None)]
    return []


def rule_A4(r: AnalysisResult) -> list[Flag]:
    """증여·상속 언급 시 증여공제 한도 인지 플래그(정보 표시만, 권유 아님)."""
    blob = " ".join(
        r.legal.items + r.unique.notes +
        [r.legal.meta.evidence or "", r.unique.meta.evidence or ""]
    )
    if any(k in blob for k in cfg.GIFT_KEYWORDS):
        return [Flag("A-4", Severity.GRAY.value,
                     "증여·상속 관련 언급 → 증여공제 한도 등 세무 검토 필요(권유 아님, 정보 확인용)",
                     inline_factor=None)]
    return []


def rule_A5(r: AnalysisResult) -> list[Flag]:
    """비현실적 목표수익률 경고(차단 아님). 신뢰도 하향 + 원인 확인."""
    hi = r.goal_return.return_max
    lo = r.goal_return.return_min
    flags = []
    check = hi if hi is not None else lo
    if check is None:
        return []
    if check > cfg.GOAL_RETURN_UPPER:
        r.goal_return.meta.confidence = Confidence.LOW
        flags.append(Flag("A-5", Severity.GRAY.value,
                          f"목표수익률 연 {check*100:.0f}%가 비현실적으로 높음 → 추출 오류인지 고객 기대 자체인지 확인 요망",
                          inline_factor="goal_return"))
    elif lo is not None and lo < cfg.GOAL_RETURN_LOWER:
        r.goal_return.meta.confidence = Confidence.LOW
        flags.append(Flag("A-5", Severity.GRAY.value,
                          "목표수익률이 음수로 추출됨 → 추출 오류 가능성 확인 요망",
                          inline_factor="goal_return"))
    return flags


# ===========================================================================
# B. 정합성 규칙
# ===========================================================================

def rule_B1(r: AnalysisResult) -> list[Flag]:
    """유동성 필요금액 합계 > 운용 총액 모순."""
    total_need = sum(e.amount for e in r.liquidity.events if e.amount)
    if total_need <= 0:
        return []
    if r.total_investable is None:
        q = "이번에 운용하실 총 금액(원)이 어느 정도인가요?"
        if q not in r.follow_up_questions:
            r.follow_up_questions.append(q)
        return []
    if total_need > r.total_investable:
        return [Flag("B-1", Severity.RED.value,
                     f"유동성 필요액 {total_need:,.0f}원이 운용총액 {r.total_investable:,.0f}원을 초과(논리 모순)",
                     inline_factor=None)]
    return []


def rule_B2(r: AnalysisResult) -> list[Flag]:
    """유동성 이벤트 시점이 투자기간보다 늦은 모순(연 단위로 추정 비교)."""
    yrs = r.horizon.years
    if yrs is None:
        return []
    # when 텍스트에서 'N년' 패턴을 보수적으로 추출
    flags = []
    for e in r.liquidity.events:
        if not e.when:
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*년", e.when)
        if m and float(m.group(1)) > yrs:
            flags.append(Flag("B-2", Severity.YELLOW.value,
                              f"유동성 시점({e.when})이 투자기간({yrs}년)보다 늦음 → 둘 중 하나 재확인",
                              inline_factor=None))
    return flags


def rule_B3(r: AnalysisResult) -> list[Flag]:
    """위험 의향/능력 격차 2단계 이상."""
    w = r.risk_tolerance.willingness.level
    c = r.risk_tolerance.capacity.level
    order = cfg.RISK_LEVEL_ORDER
    if w in order and c in order:
        gap = abs(order[w] - order[c])
        if gap >= cfg.RISK_GAP_THRESHOLD:
            # binding을 보수적(낮은) 쪽으로 자동 설정
            r.risk_tolerance.binding = "willingness" if order[w] <= order[c] else "capacity"
            return [Flag("B-3", Severity.YELLOW.value,
                         f"위험 의향({w})과 능력({c}) 격차 큼 → PB가 반드시 짚어야 할 지점. 보수적 축({r.risk_tolerance.binding}) 적용",
                         inline_factor="risk_tolerance")]
    return []


def rule_B4(r: AnalysisResult) -> list[Flag]:
    """목표수익률 높은데 위험허용도 낮음."""
    target = r.goal_return.return_max or r.goal_return.return_min
    binding_level = _binding_level(r)
    if target is not None and binding_level == "낮음" and target > cfg.HIGH_RETURN_FOR_LOW_RISK:
        return [Flag("B-4", Severity.YELLOW.value,
                     f"목표수익률(연 {target*100:.0f}%)은 높은데 위험허용도가 '낮음' → 달성 가능성 한계, 기대 조정 상담 필요",
                     inline_factor=None)]
    return []


def rule_B5(r: AnalysisResult) -> list[Flag]:
    """단기 투자기간인데 고수익 목표."""
    target = r.goal_return.return_max or r.goal_return.return_min
    yrs = r.horizon.years
    if target is not None and yrs is not None and yrs <= cfg.SHORT_HORIZON_YEARS \
            and target > cfg.SHORT_HORIZON_HIGH_RETURN:
        return [Flag("B-5", Severity.YELLOW.value,
                     f"투자기간이 짧은데({yrs}년) 목표수익률(연 {target*100:.0f}%)이 높음 → 위험 과다 우려",
                     inline_factor=None)]
    return []


def _binding_level(r: AnalysisResult) -> str | None:
    b = r.risk_tolerance.binding
    if b == "willingness":
        return r.risk_tolerance.willingness.level
    if b == "capacity":
        return r.risk_tolerance.capacity.level
    # binding 미설정이면 더 보수적인 쪽
    order = cfg.RISK_LEVEL_ORDER
    levels = [x for x in (r.risk_tolerance.willingness.level, r.risk_tolerance.capacity.level) if x in order]
    return min(levels, key=lambda x: order[x]) if levels else None


# ===========================================================================
# C. 형식·완결성 규칙
# ===========================================================================

_FACTOR_ATTRS = ["goal_return", "risk_tolerance", "horizon", "tax", "liquidity", "legal", "unique"]


def rule_C1(r: AnalysisResult) -> list[Flag]:
    """필수 7요인 객체 존재 확인."""
    missing = [a for a in _FACTOR_ATTRS if getattr(r, a, None) is None]
    if missing:
        return [Flag("C-1", Severity.RED.value,
                     f"필수 요인 누락: {', '.join(missing)}", inline_factor=None)]
    return []


def rule_C2(r: AnalysisResult) -> list[Flag]:
    """status 값 유효성(이미 Enum이라 타입상 보장되나, 방어적 확인)."""
    flags = []
    for a in _FACTOR_ATTRS:
        obj = getattr(r, a)
        status = obj.status if a == "risk_tolerance" else obj.meta.status
        if not isinstance(status, FactorStatus):
            flags.append(Flag("C-2", Severity.RED.value,
                              f"{a} status 값이 유효하지 않음", inline_factor=None))
    return flags


def rule_C3(r: AnalysisResult) -> list[Flag]:
    """값 범위 검사: 투자기간 양수 등."""
    flags = []
    if r.horizon.years is not None and r.horizon.years <= 0:
        flags.append(Flag("C-3", Severity.YELLOW.value,
                          f"투자기간이 0 이하({r.horizon.years})로 추출됨 → 재확인",
                          inline_factor="horizon"))
    return flags


def rule_C4(r: AnalysisResult) -> list[Flag]:
    """missing 요인에 대응 추가질문이 없으면 자동 생성."""
    q_map = {
        "goal_return": "목표로 하시는 연 수익률 수준이 있으신가요?",
        "risk_tolerance": "투자 손실에 대해 어느 정도까지 감내 가능하신가요?",
        "horizon": "이 자금을 어느 정도 기간 동안 묶어두실 수 있나요?",
        "tax": "현재 이자·배당 등 금융소득 규모가 어느 정도인가요?",
        "liquidity": "가까운 시일 내에 목돈이 필요한 일정이 있으신가요?",
        "legal": "투자에 영향을 줄 법적 사항(신탁·증여·거래제한 등)이 있나요?",
    }
    for a in _FACTOR_ATTRS:
        obj = getattr(r, a)
        status = obj.status if a == "risk_tolerance" else obj.meta.status
        if status == FactorStatus.MISSING and a in q_map:
            if q_map[a] not in r.follow_up_questions:
                r.follow_up_questions.append(q_map[a])
    return []  # 플래그가 아닌 추가질문 보강이므로 빈 리스트


# ===========================================================================
# D. 안전·컴플라이언스 규칙
# ===========================================================================

def rule_D1(r: AnalysisResult, raw_text: str | None) -> list[Flag]:
    """민감정보 탐지(원문 기준). 탐지 시 경고.
    중복 탐지 방지: 더 구체적인 패턴(주민번호·연락처)을 먼저 검사하고,
    이미 매칭된 구간은 가려서 계좌번호 패턴의 과탐을 막는다."""
    if not raw_text:
        return []
    flags = []
    masked = raw_text
    # 구체적 패턴 우선순위 순서
    priority = ["주민등록번호", "연락처", "계좌번호 추정"]
    for label in priority:
        pat = cfg.SENSITIVE_PATTERNS.get(label)
        if pat and re.search(pat, masked):
            flags.append(Flag("D-1", Severity.RED.value,
                              f"원문에 {label}로 보이는 정보 포함 → 마스킹·삭제 검토 필요",
                              inline_factor=None))
            # 매칭 구간을 가려 다음(덜 구체적인) 패턴의 중복 탐지 방지
            masked = re.sub(pat, " ", masked)
    return flags


def rule_D3(r: AnalysisResult) -> list[Flag]:
    """핵심 요인 신뢰도 '하'면 optimizer 제약을 잠정(provisional)으로 표시."""
    low = []
    for a in cfg.CRITICAL_FACTORS:
        obj = getattr(r, a)
        if a == "risk_tolerance":
            confs = [obj.willingness.confidence, obj.capacity.confidence]
            if Confidence.LOW in confs:
                low.append(a)
        else:
            if obj.meta.confidence == Confidence.LOW:
                low.append(a)
    if low:
        r.optimizer_constraints.provisional = True
        r.optimizer_constraints.notes.append(f"핵심 요인 신뢰도 낮음({', '.join(low)}) → 제약 잠정")
        return [Flag("D-3", Severity.YELLOW.value,
                     f"핵심 요인({', '.join(low)}) 신뢰도 '하' → 포트폴리오 제약을 잠정 처리",
                     inline_factor=None)]
    return []


# ===========================================================================
# optimizer 제약 번역 (요인 -> 정량 제약)
# ===========================================================================

def build_optimizer_constraints(r: AnalysisResult) -> None:
    oc = r.optimizer_constraints
    oc.max_horizon_years = r.horizon.years
    oc.min_cash_reserve = sum(e.amount for e in r.liquidity.events if e.amount) or None
    oc.target_return_min = r.goal_return.return_min
    oc.target_return_max = r.goal_return.return_max
    oc.risk_level = _binding_level(r)
    oc.excluded_sectors = list(r.unique.excluded_sectors)


# ===========================================================================
# 전체 실행
# ===========================================================================

def validate(r: AnalysisResult, raw_text: str | None = None) -> AnalysisResult:
    """모든 규칙을 토글에 따라 실행하고 결과(r)에 플래그·추가질문·제약을 채운다."""
    # 1) optimizer 제약 먼저 번역(이후 D-3가 provisional 표시)
    build_optimizer_constraints(r)

    simple_rules = {
        "A-1": rule_A1, "A-2": rule_A2, "A-3": rule_A3, "A-4": rule_A4, "A-5": rule_A5,
        "B-1": rule_B1, "B-2": rule_B2, "B-3": rule_B3, "B-4": rule_B4, "B-5": rule_B5,
        "C-1": rule_C1, "C-2": rule_C2, "C-3": rule_C3, "C-4": rule_C4, "D-3": rule_D3,
    }
    for rid, fn in simple_rules.items():
        if cfg.RULE_TOGGLES.get(rid):
            r.flags.extend(fn(r))

    if cfg.RULE_TOGGLES.get("D-1"):
        r.flags.extend(rule_D1(r, raw_text))

    # 심각도 정렬: red > yellow > gray
    sev_order = {Severity.RED.value: 0, Severity.YELLOW.value: 1, Severity.GRAY.value: 2}
    r.flags.sort(key=lambda f: sev_order.get(f.severity, 9))
    return r
