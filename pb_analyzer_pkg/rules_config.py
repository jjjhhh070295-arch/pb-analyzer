"""
규칙 검증 레이어 설정

세법 수치·임계값을 한곳에 모은다. 법 개정 시 이 파일만 수정하면 된다.
각 규칙은 RULE_TOGGLES로 켜고 끌 수 있다(운영 중 특정 규칙이 과민하면 비활성화).

※ 세법 수치는 운영 시점 재확인 필요(★). 2026년 5월 기준값으로 초기화.
"""

from __future__ import annotations

# --- A. 세법 기준 ---
FINANCIAL_INCOME_THRESHOLD = 20_000_000      # A-1 ★ 금융소득종합과세 기준(연, 원, 세전)

# --- A-5. 목표수익률 경고선 ---
GOAL_RETURN_UPPER = 0.25                      # 연 25% 초과 시 경고(차단 아님)
GOAL_RETURN_LOWER = 0.0                       # 음수 목표수익률 경고

# --- B-3. 위험 의향/능력 격차 ---
RISK_LEVEL_ORDER = {"낮음": 0, "중립": 1, "높음": 2}
RISK_GAP_THRESHOLD = 2                         # 등급 차 2 이상이면 경고

# --- B-4/B-5. 목표-위험, 기간-목표 불일치 기준 ---
HIGH_RETURN_FOR_LOW_RISK = 0.10               # 위험 '낮음'인데 목표 10% 초과면 경고
SHORT_HORIZON_YEARS = 1.0                     # 1년 이하인데 고수익 목표면 경고
SHORT_HORIZON_HIGH_RETURN = 0.10

# --- D-3. 신뢰도 전파 대상(핵심 요인) ---
CRITICAL_FACTORS = ("risk_tolerance", "liquidity")

# --- 규칙 on/off 토글 ---
RULE_TOGGLES = {
    "A-1": True, "A-2": True, "A-3": True, "A-4": True, "A-5": True,
    "B-1": True, "B-2": True, "B-3": True, "B-4": True, "B-5": True,
    "C-1": True, "C-2": True, "C-3": True, "C-4": True,
    "D-1": True, "D-3": True,
    # D-2는 PB->고객 전환 게이트(별도 단계)에서 처리하므로 여기엔 없음
}

# --- 민감정보 탐지용(D-1) 정규식 키 ---
# 한국 주민등록번호, 계좌번호 형태(과탐 방지 위해 보수적으로)
SENSITIVE_PATTERNS = {
    "주민등록번호": r"\b\d{6}[-\s]?[1-4]\d{6}\b",
    "계좌번호 추정": r"\b\d{2,6}[-]\d{2,6}[-]\d{2,7}\b",
    "연락처": r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b",
}

# --- A-3/A-4 트리거 키워드 ---
HIGH_DIVIDEND_KEYWORDS = ("고배당", "배당주", "배당 많", "배당이 많")
GIFT_KEYWORDS = ("증여", "상속", "물려", "자녀에게", "가족에게 나눠", "자산 분산")
