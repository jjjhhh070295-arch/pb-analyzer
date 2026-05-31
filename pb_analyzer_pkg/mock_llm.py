"""
테스트용 Mock LLM 헬퍼

네트워크 없이 분석/검증 흐름을 검증하기 위한 도구.
프롬프트의 '[분석 요인] XXX' 줄을 읽어 해당 요인의 미리 정의된 응답을 돌려준다.
(이전 디버깅에서 배운 교훈: 단순 substring 매칭은 프롬프트 본문에 다른 요인명이
 섞여 있을 때 오작동한다. 반드시 [분석 요인] 줄로 식별한다.)

사용:
    from mock_llm import make_mock_llm, FACTOR_KEYS
    llm = make_mock_llm(responses)   # responses: {요인키: dict}
"""

from __future__ import annotations

import json
import re

from llm_client import MockLLMClient

# 각 추출기 프롬프트의 [분석 요인] 줄 시작 문구
FACTOR_KEYS = {
    "goal_return": "목표수익률",
    "risk_tolerance": "위험허용도",
    "horizon": "투자 기간",
    "tax": "세금 요인",
    "liquidity": "유동성 필요시기",
    "legal": "법적 제약",
    "unique": "고객 고유 상황",
}

_FACTOR_LINE = re.compile(r"\[분석 요인\]\s*(.+)")


def make_mock_llm(responses: dict[str, dict]) -> MockLLMClient:
    """
    responses: 요인키(goal_return 등) -> 그 요인 추출기가 기대하는 JSON dict
    누락된 요인은 빈 객체("{}")를 돌려준다(= status missing 처리됨).
    """
    # 요인키 -> 한글 식별 문구로 변환한 매핑
    by_korean = {FACTOR_KEYS[k]: v for k, v in responses.items() if k in FACTOR_KEYS}

    def responder(system: str, user: str) -> str:
        m = _FACTOR_LINE.search(system)
        if not m:
            return "{}"
        label = m.group(1).strip()
        for korean, payload in by_korean.items():
            if label.startswith(korean):
                return json.dumps(payload, ensure_ascii=False)
        return "{}"

    return MockLLMClient(responder=responder)
