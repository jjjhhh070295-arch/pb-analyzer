"""
PB 고객 분석 시스템 - 데이터 모델 정의

핵심 식별 체계:
  - customer_id: 시스템이 자동 부여하는 진짜 식별자 (동명이인 문제 해결의 핵심)
  - name + birth_date: 사람(PB)이 동명이인을 구분하기 위한 표시 정보
모든 상담 이력은 name이 아니라 customer_id로 묶인다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# 열거형 정의
# ---------------------------------------------------------------------------

class Confidence(str, Enum):
    """신뢰도 - 상/중/하 3단계 (PB가 직관적으로 보기 위함)"""
    HIGH = "상"
    MEDIUM = "중"
    LOW = "하"


class FactorStatus(str, Enum):
    """각 분석 요인의 출처 상태"""
    EXPLICIT = "explicit"   # 고객이 명시적으로 말함
    INFERRED = "inferred"   # 정황상 추론됨
    MISSING = "missing"     # 정보 없음 -> 추가질문 필요


class SessionStatus(str, Enum):
    """상담 세션의 진행 상태 (PB 검수 게이트)"""
    DRAFT = "검수중"        # AI 분석 완료, PB 검수 전/중
    CONFIRMED = "확정"      # PB가 검수·확정 -> 고객 화면 노출 가능


class Severity(str, Enum):
    """플래그 심각도 - 검토 탭 정렬용"""
    RED = "red"        # 논리 모순·민감정보 - 반드시 확인
    YELLOW = "yellow"  # 기대-현실 불일치·세무 검토 - 짚어볼 것
    GRAY = "gray"      # 아웃라이어 가능성 - 참고


# ---------------------------------------------------------------------------
# 고객 식별 모델
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    """
    고객 한 명을 나타낸다.
    customer_id가 진짜 식별자이고, name/birth_date는 사람이 구분하기 위한 표시용.
    이름과 생년월일이 모두 같은 극단적 경우라도 customer_id는 항상 고유하다.
    """
    customer_id: str          # 예: "C0001" - 시스템 자동 부여
    name: str
    birth_date: str           # "YYYY-MM-DD" 형식
    primary_pb: str           # 담당 PB명 (동명이인 추가 구분에도 사용)
    registered_at: str        # 등록 시각 ISO 문자열

    def display_label(self) -> str:
        """PB 화면에서 동명이인을 구분해 보여주는 라벨.
        예: '김영수 (1968-03-12, 담당 박상우)'"""
        return f"{self.name} ({self.birth_date}, 담당 {self.primary_pb})"

    def to_row(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_row(row: dict) -> "Customer":
        return Customer(
            customer_id=str(row["customer_id"]),
            name=str(row["name"]),
            birth_date=str(row["birth_date"]),
            primary_pb=str(row["primary_pb"]),
            registered_at=str(row["registered_at"]),
        )


# ---------------------------------------------------------------------------
# 검증 유틸리티
# ---------------------------------------------------------------------------

_BIRTH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_birth_date(value: str) -> str:
    """생년월일 형식(YYYY-MM-DD)과 실제 유효성을 검사. 정규화된 문자열 반환."""
    value = value.strip()
    if not _BIRTH_RE.match(value):
        raise ValueError(f"생년월일은 YYYY-MM-DD 형식이어야 합니다: '{value}'")
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"존재하지 않는 날짜입니다: '{value}'") from e
    if d > date.today():
        raise ValueError(f"생년월일이 미래일 수 없습니다: '{value}'")
    if d.year < 1900:
        raise ValueError(f"생년월일이 너무 과거입니다: '{value}'")
    return value


def validate_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("고객명은 비어 있을 수 없습니다.")
    if len(value) > 50:
        raise ValueError("고객명이 너무 깁니다.")
    return value
