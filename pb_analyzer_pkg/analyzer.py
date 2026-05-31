"""
분석 오케스트레이터 (Analyzer)

역할:
  - 고객 전체 원문을 받아 7개 요인 추출기를 각각 호출한다(요인별 분리 분석).
  - 한 요인 분석이 실패(LLM 오류·JSON 깨짐)해도 나머지는 살리고, 실패한 요인은
    status=missing 으로 두고 에러를 기록한다. (부분 실패 허용)
  - 결과를 하나의 AnalysisResult로 통합한다.

주의: 이 단계는 '추출'까지만 한다. 규칙 검증(플래그)·optimizer 제약 번역·추가질문 생성은
      다음 단계(validators)에서 결과를 받아 수행한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm_client import LLMClient
from analysis_schema import AnalysisResult
from models import FactorStatus
import extractors


# 요인 이름 -> (추출 함수, AnalysisResult 속성명)
_FACTORS = [
    ("goal_return", extractors.extract_goal_return, "goal_return"),
    ("risk_tolerance", extractors.extract_risk_tolerance, "risk_tolerance"),
    ("horizon", extractors.extract_horizon, "horizon"),
    ("tax", extractors.extract_tax, "tax"),
    ("liquidity", extractors.extract_liquidity, "liquidity"),
    ("legal", extractors.extract_legal, "legal"),
    ("unique", extractors.extract_unique, "unique"),
]


@dataclass
class AnalyzeReport:
    """분석 실행 결과 + 진단 정보."""
    result: AnalysisResult
    errors: dict[str, str] = field(default_factory=dict)  # 요인명 -> 에러 메시지

    @property
    def ok(self) -> bool:
        return not self.errors


def analyze(text: str, llm: LLMClient) -> AnalyzeReport:
    """
    고객 원문을 7요인으로 분석한다.
    text: PB가 입력한 고객 상담 원문
    llm:  LLMClient 구현 (실제 Anthropic 또는 Mock)
    """
    if not text or not text.strip():
        raise ValueError("분석할 고객 상담 원문이 비어 있습니다.")

    result = AnalysisResult()
    errors: dict[str, str] = {}

    for name, fn, attr in _FACTORS:
        try:
            extracted = fn(text, llm)
            setattr(result, attr, extracted)
        except Exception as e:  # 한 요인 실패가 전체를 막지 않게
            errors[name] = f"{type(e).__name__}: {e}"
            # 실패한 요인은 기본값(status=missing) 그대로 둔다

    return AnalyzeReport(result=result, errors=errors)
