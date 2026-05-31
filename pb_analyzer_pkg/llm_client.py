"""
LLM 클라이언트 추상화

목적:
  - 분석 엔진이 LLM 호출의 '구체적 구현'에 묶이지 않게 한다.
  - 지금(네트워크 차단 환경)은 MockLLMClient로 흐름을 검증하고,
    Claude Code 실사용 시 AnthropicLLMClient로 교체(또는 API 키만 주입)한다.

각 클라이언트는 complete(system, user) -> str (모델의 텍스트 응답)만 제공한다.
요인별 추출기는 "JSON만 출력하라"는 프롬프트를 주고 이 문자열을 파싱한다.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Callable


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """system 프롬프트와 user 입력을 받아 모델의 텍스트 응답을 반환."""
        ...


# ---------------------------------------------------------------------------
# 실제 Anthropic API 구현 (Claude Code 실사용 시)
# ---------------------------------------------------------------------------

class AnthropicLLMClient(LLMClient):
    """
    실제 Anthropic API 호출 구현.
    API 키는 환경변수 ANTHROPIC_API_KEY 또는 생성자 인자로 주입.
    """

    def __init__(self, model: str = "claude-opus-4-7", api_key: Optional[str] = None,
                 max_tokens: int = 2048):
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def complete(self, system: str, user: str) -> str:
        from anthropic import Anthropic, APIConnectionError, RateLimitError, APIStatusError
        client = Anthropic(api_key=self.api_key)
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                # 요인별 추출 지시문(system)은 분석 내내 동일 → 캐시로 비용 절감
                system=[{
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user}],
            )
        except RateLimitError as e:
            raise RuntimeError(f"Claude API 요청 한도 초과: {e}") from e
        except APIConnectionError as e:
            raise RuntimeError(f"Claude API 연결 실패: {e}") from e
        except APIStatusError as e:
            raise RuntimeError(f"Claude API 오류 ({e.status_code}): {e.message}") from e
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


# ---------------------------------------------------------------------------
# 테스트용 Mock 구현
# ---------------------------------------------------------------------------

class MockLLMClient(LLMClient):
    """
    테스트/데모용. 미리 정해둔 응답을 돌려주거나, 사용자가 준 함수로 응답을 만든다.
    요인별 분석 흐름과 파싱·검증 레이어를 네트워크 없이 끝까지 돌려보기 위한 것.
    """

    def __init__(self, responder: Optional[Callable[[str, str], str]] = None,
                 fixed: Optional[str] = None):
        self._responder = responder
        self._fixed = fixed

    def complete(self, system: str, user: str) -> str:
        if self._responder is not None:
            return self._responder(system, user)
        if self._fixed is not None:
            return self._fixed
        return "{}"


# ---------------------------------------------------------------------------
# 공통 유틸: LLM 응답에서 JSON 안전 추출
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
    """
    LLM이 ```json 펜스나 앞뒤 설명을 붙여도 JSON 객체만 안전하게 뽑아낸다.
    실패 시 ValueError.
    """
    text = text.strip()
    # 코드펜스 제거
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    # 첫 '{' 부터 마지막 '}' 까지
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"응답에서 JSON을 찾을 수 없습니다: {text[:200]}")
    candidate = text[start:end + 1]
    return json.loads(candidate)
