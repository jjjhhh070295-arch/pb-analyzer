# PB 고객 분석 시스템 — 1단계 (고객 텍스트 분석)

초고액 자산가(보유자산 30억 이상)를 상대하는 증권사 PB를 위한 분석 도구.
PB가 입력한 고객 상담 원문을 **7요인**으로 자동 분석하고, **규칙 검증**으로
세무·정합성·안전 플래그를 달아 PB의 판단을 돕는다. (최종 판단·책임은 PB에게 있음)

## 분석하는 7요인
목표수익률 · 위험허용도 · 투자기간 · 세금요인 · 유동성 필요시기 · 법적제약 · 고객 고유상황

각 요인은 `{추출값, 근거 인용, 신뢰도(상/중/하), status(explicit/inferred/missing)}` 구조.
위험허용도는 **의향(willingness) / 능력(capacity) 이중 축**으로 분리해 더 보수적인 축을 적용.

## 실행
```bash
pip install openpyxl
python demo.py
```
데모는 가짜 LLM(mock)으로 전체 흐름(등록→분석→검증→저장→불러오기→검수)을 보여준다.

## 실제 Claude API 연동
`demo.py`의 `make_demo_llm()` 대신 실제 클라이언트를 쓰면 된다:
```python
from llm_client import AnthropicLLMClient
llm = AnthropicLLMClient(api_key="sk-...")   # 또는 환경변수 ANTHROPIC_API_KEY
report = analyze(customer_text, llm)
```
`pip install anthropic` 필요. 나머지 흐름은 동일하다.

## 파일 구조
| 파일 | 역할 |
|---|---|
| `models.py` | 데이터 모델·열거형(신뢰도·status·세션상태·심각도), 고객 식별 체계 |
| `customer_repository.py` | 고객 등록·검색·**동명이인 해소**(고유ID+생년월일). 추상 인터페이스 |
| `analysis_schema.py` | **7요인 분석 결과 스키마**. JSON 직렬화/복원 |
| `llm_client.py` | LLM 호출 추상화(실제 Anthropic / mock) + JSON 안전 추출 |
| `extractors.py` | **요인별 추출기**(7개). 요인 집중 프롬프트, 전체 원문은 항상 제공 |
| `analyzer.py` | 7요인 분석 오케스트레이터(부분 실패 허용) |
| `rules_config.py` | 규칙 설정값(세법 기준·임계값·토글). 법 개정 시 여기만 수정 |
| `validators.py` | **규칙 검증 레이어**(A세무·B정합성·C형식·D안전 13규칙) |
| `session_repository.py` | 상담 세션 저장/불러오기(엑셀, 날짜·PB·고객 필터). 추상 인터페이스 |
| `mock_llm.py` | 테스트용 mock LLM 헬퍼 |
| `demo.py` | 1단계 전체 시연 |

## 규칙 검증 레이어 (13개)
- **A 세무**: A-1 금융소득종합과세 판정(2천만원 초과) / A-2 건강보험료 영향 / A-3 고배당 분리과세 검토 / A-4 증여공제 검토 / A-5 비현실 목표수익률 경고(>25%, 차단 아님)
- **B 정합성**: B-1 유동성>운용총액 모순 / B-2 유동성시점>투자기간 / B-3 위험 의향-능력 격차 / B-4 목표-위험 불일치 / B-5 기간-목표 불일치
- **C 형식**: C-1 필수필드 / C-2 status유효성 / C-3 값범위 / C-4 missing→추가질문 자동생성
- **D 안전**: D-1 민감정보 탐지·마스킹 / D-3 신뢰도 전파(잠정 제약)
- **게이트**: D-2는 PB→고객 화면 전환 단계에서 별도 검사

각 규칙은 `rules_config.RULE_TOGGLES`로 on/off 가능.

## 화면 구조 (설계)
- **PB 화면**: 7요인 + 인라인 표시(신뢰도·정보없음·🔎규칙) + 검토 탭(심각도순 🔴🟡⚪) + 추가질문
- **고객 화면**: PB가 **검수·확정한 내용만** 노출(내부 신뢰도·이중축 등 숨김)
- 단방향: 원문 → AI분석 → PB검수·수정·확정 → 고객 화면

## 다음 단계 (미구현)
- 2단계: optimizer 제약 → **포트폴리오 최적화 엔진**(기대수익률·소르티노·베타)
- 웹 UI(Next.js) / 저장소를 Supabase로 교체(추상 인터페이스라 교체 용이)
