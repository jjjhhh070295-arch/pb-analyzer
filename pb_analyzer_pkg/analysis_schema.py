"""
7요인 분석 결과 스키마 (시스템의 중심 데이터)

고객 자유 텍스트 -> LLM 분석 -> 이 구조 -> 규칙 검증 -> PB 검수 -> 포트폴리오 엔진

설계 원칙:
  1) 근거 추적: 모든 추출값에 원문 인용(evidence)을 붙여 PB가 검수 가능하게.
  2) 빈 항목 명시: 정보 없으면 임의로 채우지 않고 status=MISSING + 추가질문 생성.
  3) 위험허용도 이중 축: 감수 의향(willingness)과 능력(capacity)을 분리.
  4) optimizer 제약: 정성 분석을 포트폴리오 엔진이 먹을 정량 제약으로 번역.

직렬화: 모든 dataclass는 to_dict / from_dict 를 제공해 JSON 한 칸 저장을 지원한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Any

from models import Confidence, FactorStatus


# ---------------------------------------------------------------------------
# 공통: 한 요인의 기본 메타 (근거 + 신뢰도 + status)
# ---------------------------------------------------------------------------

@dataclass
class FactorMeta:
    """모든 요인이 공통으로 갖는 메타데이터."""
    status: FactorStatus = FactorStatus.MISSING
    evidence: Optional[str] = None          # 원문 인용 (PB 검수용)
    confidence: Optional[Confidence] = None  # 상/중/하 (MISSING이면 None)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "evidence": self.evidence,
            "confidence": self.confidence.value if self.confidence else None,
        }

    @staticmethod
    def from_dict(d: dict) -> "FactorMeta":
        return FactorMeta(
            status=FactorStatus(d.get("status", "missing")),
            evidence=d.get("evidence"),
            confidence=Confidence(d["confidence"]) if d.get("confidence") else None,
        )


# ---------------------------------------------------------------------------
# 1. 목표수익률
# ---------------------------------------------------------------------------

@dataclass
class GoalReturn:
    meta: FactorMeta = field(default_factory=FactorMeta)
    return_min: Optional[float] = None   # 연 수익률 하한 (예: 0.07 = 7%)
    return_max: Optional[float] = None   # 연 수익률 상한
    raw_text: Optional[str] = None       # "연 7~9%" 같은 원래 표현

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "return_min": self.return_min,
                "return_max": self.return_max, "raw_text": self.raw_text}

    @staticmethod
    def from_dict(d: dict) -> "GoalReturn":
        return GoalReturn(meta=FactorMeta.from_dict(d.get("meta", {})),
                          return_min=d.get("return_min"), return_max=d.get("return_max"),
                          raw_text=d.get("raw_text"))


# ---------------------------------------------------------------------------
# 2. 위험허용도 (이중 축: 의향 / 능력)
# ---------------------------------------------------------------------------

@dataclass
class RiskAxis:
    """위험허용도의 한 축. level은 '높음'/'중립'/'낮음' 등 자유 등급."""
    level: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[Confidence] = None

    def to_dict(self) -> dict:
        return {"level": self.level, "evidence": self.evidence,
                "confidence": self.confidence.value if self.confidence else None}

    @staticmethod
    def from_dict(d: dict) -> "RiskAxis":
        return RiskAxis(level=d.get("level"), evidence=d.get("evidence"),
                        confidence=Confidence(d["confidence"]) if d.get("confidence") else None)


@dataclass
class RiskTolerance:
    """
    willingness: 위험을 감수할 '의향' (심리·경험 기반)
    capacity:    위험을 감수할 '능력' (자산 규모·여유자금 기반)
    binding:     실제 적용할 더 보수적인 축 ('willingness' | 'capacity')
    """
    status: FactorStatus = FactorStatus.MISSING
    willingness: RiskAxis = field(default_factory=RiskAxis)
    capacity: RiskAxis = field(default_factory=RiskAxis)
    binding: Optional[str] = None

    def to_dict(self) -> dict:
        return {"status": self.status.value,
                "willingness": self.willingness.to_dict(),
                "capacity": self.capacity.to_dict(),
                "binding": self.binding}

    @staticmethod
    def from_dict(d: dict) -> "RiskTolerance":
        return RiskTolerance(
            status=FactorStatus(d.get("status", "missing")),
            willingness=RiskAxis.from_dict(d.get("willingness", {})),
            capacity=RiskAxis.from_dict(d.get("capacity", {})),
            binding=d.get("binding"),
        )


# ---------------------------------------------------------------------------
# 3. 투자 기간
# ---------------------------------------------------------------------------

@dataclass
class InvestmentHorizon:
    meta: FactorMeta = field(default_factory=FactorMeta)
    years: Optional[float] = None    # 투자 기간(년)

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "years": self.years}

    @staticmethod
    def from_dict(d: dict) -> "InvestmentHorizon":
        return InvestmentHorizon(meta=FactorMeta.from_dict(d.get("meta", {})),
                                 years=d.get("years"))


# ---------------------------------------------------------------------------
# 4. 세금 요인
# ---------------------------------------------------------------------------

@dataclass
class TaxFactors:
    meta: FactorMeta = field(default_factory=FactorMeta)
    items: list[str] = field(default_factory=list)   # 예: ["금융소득종합과세 대상"]
    annual_financial_income: Optional[float] = None  # 연간 금융소득(이자+배당) 원 단위

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "items": self.items,
                "annual_financial_income": self.annual_financial_income}

    @staticmethod
    def from_dict(d: dict) -> "TaxFactors":
        return TaxFactors(meta=FactorMeta.from_dict(d.get("meta", {})),
                          items=d.get("items", []),
                          annual_financial_income=d.get("annual_financial_income"))


# ---------------------------------------------------------------------------
# 5. 유동성 필요시기
# ---------------------------------------------------------------------------

@dataclass
class LiquidityEvent:
    when: Optional[str] = None       # "1년 내", "2026-09" 등
    amount: Optional[float] = None   # 필요 금액(원)
    purpose: Optional[str] = None    # "부동산 잔금" 등

    def to_dict(self) -> dict:
        return {"when": self.when, "amount": self.amount, "purpose": self.purpose}

    @staticmethod
    def from_dict(d: dict) -> "LiquidityEvent":
        return LiquidityEvent(when=d.get("when"), amount=d.get("amount"),
                              purpose=d.get("purpose"))


@dataclass
class LiquidityNeeds:
    meta: FactorMeta = field(default_factory=FactorMeta)
    events: list[LiquidityEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(),
                "events": [e.to_dict() for e in self.events]}

    @staticmethod
    def from_dict(d: dict) -> "LiquidityNeeds":
        return LiquidityNeeds(meta=FactorMeta.from_dict(d.get("meta", {})),
                              events=[LiquidityEvent.from_dict(e) for e in d.get("events", [])])


# ---------------------------------------------------------------------------
# 6. 법적 제약
# ---------------------------------------------------------------------------

@dataclass
class LegalConstraints:
    meta: FactorMeta = field(default_factory=FactorMeta)
    items: list[str] = field(default_factory=list)  # 예: ["신탁 진행 중", "증여 계획"]

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "items": self.items}

    @staticmethod
    def from_dict(d: dict) -> "LegalConstraints":
        return LegalConstraints(meta=FactorMeta.from_dict(d.get("meta", {})),
                                items=d.get("items", []))


# ---------------------------------------------------------------------------
# 7. 고객 고유 상황 (앞 6개로 분류 안 되는 특이사항)
# ---------------------------------------------------------------------------

@dataclass
class UniqueSituation:
    meta: FactorMeta = field(default_factory=FactorMeta)
    notes: list[str] = field(default_factory=list)        # 예: ["ESG 선호"]
    excluded_sectors: list[str] = field(default_factory=list)  # 예: ["tobacco", "gambling"]

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "notes": self.notes,
                "excluded_sectors": self.excluded_sectors}

    @staticmethod
    def from_dict(d: dict) -> "UniqueSituation":
        return UniqueSituation(meta=FactorMeta.from_dict(d.get("meta", {})),
                               notes=d.get("notes", []),
                               excluded_sectors=d.get("excluded_sectors", []))


# ---------------------------------------------------------------------------
# 포트폴리오 엔진으로 넘길 정량 제약 (요인 -> 제약 번역 결과)
# ---------------------------------------------------------------------------

@dataclass
class OptimizerConstraints:
    """7요인 분석을 포트폴리오 최적화 엔진이 바로 먹을 수 있는 형태로 번역."""
    max_horizon_years: Optional[float] = None
    min_cash_reserve: Optional[float] = None        # 유동성 대비 최소 현금성 자산(원)
    target_return_min: Optional[float] = None
    target_return_max: Optional[float] = None
    risk_level: Optional[str] = None                # binding 축의 등급
    excluded_sectors: list[str] = field(default_factory=list)
    provisional: bool = False                       # 핵심 요인 신뢰도 '하'면 True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "OptimizerConstraints":
        return OptimizerConstraints(
            max_horizon_years=d.get("max_horizon_years"),
            min_cash_reserve=d.get("min_cash_reserve"),
            target_return_min=d.get("target_return_min"),
            target_return_max=d.get("target_return_max"),
            risk_level=d.get("risk_level"),
            excluded_sectors=d.get("excluded_sectors", []),
            provisional=d.get("provisional", False),
            notes=d.get("notes", []),
        )


# ---------------------------------------------------------------------------
# 전체 분석 결과 (7요인 + 추가질문 + optimizer 제약 + 플래그)
# ---------------------------------------------------------------------------

@dataclass
class Flag:
    """규칙 검증 레이어가 만든 경고. 검토 탭에 심각도순으로 표시."""
    rule_id: str                # 예: "A-1", "B-4"
    severity: str               # Severity 값 (red/yellow/gray)
    message: str
    inline_factor: Optional[str] = None  # 특정 요인 옆 인라인 표시면 그 요인명, 아니면 None(탭)
    resolved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Flag":
        return Flag(rule_id=d["rule_id"], severity=d["severity"], message=d["message"],
                    inline_factor=d.get("inline_factor"), resolved=d.get("resolved", False))


@dataclass
class AnalysisResult:
    """한 상담의 전체 분석 결과. 세션의 JSON 칸에 통째로 저장된다."""
    goal_return: GoalReturn = field(default_factory=GoalReturn)
    risk_tolerance: RiskTolerance = field(default_factory=RiskTolerance)
    horizon: InvestmentHorizon = field(default_factory=InvestmentHorizon)
    tax: TaxFactors = field(default_factory=TaxFactors)
    liquidity: LiquidityNeeds = field(default_factory=LiquidityNeeds)
    legal: LegalConstraints = field(default_factory=LegalConstraints)
    unique: UniqueSituation = field(default_factory=UniqueSituation)

    follow_up_questions: list[str] = field(default_factory=list)
    optimizer_constraints: OptimizerConstraints = field(default_factory=OptimizerConstraints)
    flags: list[Flag] = field(default_factory=list)

    # 운용 예정 총액(원) - 정합성 검사(B-1)에 필요. 텍스트에서 추출되거나 PB가 입력.
    total_investable: Optional[float] = None

    # PB가 최종 확정한 포트폴리오 (없으면 None). 형태:
    # { "weights": [{asset_id, name, category, weight, weight_pct}], "metrics": {...},
    #   "note": "...", "confirmed_at": "ISO 8601" }
    # 자유로운 dict로 둬서 PB 임의 수정도 그대로 저장. 고객 화면 송출에 사용.
    confirmed_portfolio: Optional[dict] = None

    # PB가 확정해 고객 화면에 송출한 절세 전략 (없으면 None).
    # { "candidates": [...], "summary": "...", "ranked": [...], "note": "...", "confirmed_at": "..." }
    confirmed_tax_strategy: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "goal_return": self.goal_return.to_dict(),
            "risk_tolerance": self.risk_tolerance.to_dict(),
            "horizon": self.horizon.to_dict(),
            "tax": self.tax.to_dict(),
            "liquidity": self.liquidity.to_dict(),
            "legal": self.legal.to_dict(),
            "unique": self.unique.to_dict(),
            "follow_up_questions": self.follow_up_questions,
            "optimizer_constraints": self.optimizer_constraints.to_dict(),
            "flags": [f.to_dict() for f in self.flags],
            "total_investable": self.total_investable,
            "confirmed_portfolio": self.confirmed_portfolio,
            "confirmed_tax_strategy": self.confirmed_tax_strategy,
        }

    @staticmethod
    def from_dict(d: dict) -> "AnalysisResult":
        return AnalysisResult(
            goal_return=GoalReturn.from_dict(d.get("goal_return", {})),
            risk_tolerance=RiskTolerance.from_dict(d.get("risk_tolerance", {})),
            horizon=InvestmentHorizon.from_dict(d.get("horizon", {})),
            tax=TaxFactors.from_dict(d.get("tax", {})),
            liquidity=LiquidityNeeds.from_dict(d.get("liquidity", {})),
            legal=LegalConstraints.from_dict(d.get("legal", {})),
            unique=UniqueSituation.from_dict(d.get("unique", {})),
            follow_up_questions=d.get("follow_up_questions", []),
            optimizer_constraints=OptimizerConstraints.from_dict(d.get("optimizer_constraints", {})),
            flags=[Flag.from_dict(f) for f in d.get("flags", [])],
            total_investable=d.get("total_investable"),
            confirmed_portfolio=d.get("confirmed_portfolio"),
            confirmed_tax_strategy=d.get("confirmed_tax_strategy"),
        )
