# CLAUDE.md — 프로젝트 작업 맥락

이 파일은 Claude Code가 프로젝트를 이어서 작업할 때 참고하는 맥락 문서다.

## 프로젝트 개요
초고액 자산가(보유자산 30억 이상)를 상대하는 증권사 PB를 돕는 분석 도구.
PB가 고객 상담 내용을 자유 텍스트로 입력하면, 시스템이 **7요인**으로 자동 분석하고
**규칙 검증**으로 세무·정합성·안전 플래그를 달아 PB의 판단을 돕는다.
**최종 투자판단과 책임은 PB에게 있다**(자본시장법상 투자권유·자문 이슈 회피 — 시스템은 분석 보조 도구).

전체는 2단계로 구성된다:
- **1단계(완료):** 고객 텍스트 → 7요인 분석 + 규칙 검증 + 저장/불러오기
- **2단계(미구현):** 7요인에서 번역된 제약 → 포트폴리오 최적화 엔진

## 현재 상태 (1단계 완료, 백엔드 로직)
`python demo.py` 로 전체 흐름이 동작한다(가짜 LLM 사용, API 키 불필요):
고객 등록(동명이인 처리) → 7요인 분석 → 규칙 검증 → 엑셀 저장 → 불러오기 → PB 검수 확정.

## 핵심 설계 결정 (변경 시 주의)
1. **요인별 분리 분석**: 7요인을 각각 별도 LLM 호출로 추출(정확도↑). 단, 각 프롬프트에
   전체 원문을 항상 제공해 맥락 유지. (`extractors.py`)
2. **위험허용도 이중 축**: 의향(willingness)/능력(capacity)을 분리하고 더 보수적인 축을 binding으로 적용.
3. **신뢰도는 상/중/하** 3단계(숫자 점수 아님). `models.Confidence`.
4. **status 3종**: explicit(명시)/inferred(추론)/missing(정보없음). missing은 추측 금지 + 추가질문 생성.
5. **규칙 검증 13개**(A세무·B정합성·C형식·D안전). `validators.py`. on/off는 `rules_config.RULE_TOGGLES`.
6. **화면 분리**: PB 화면(작업·검수, 전체 노출) / 고객 화면(검수·확정본만 노출). 단방향 게이트.
7. **저장소·LLM은 추상 인터페이스**: 엑셀→Supabase, mock→실제 API 교체를 쉽게.
8. **동명이인**: 고유ID(C0001…)가 진짜 식별자, 이름+생년월일은 표시·구분용. 상담은 customer_id로 묶임.

## 실제 Claude API 연동 방법
```python
from llm_client import AnthropicLLMClient
llm = AnthropicLLMClient(api_key="sk-...")   # 또는 환경변수 ANTHROPIC_API_KEY
# 이후 analyze(text, llm) 그대로 사용
```
모델 문자열은 `llm_client.AnthropicLLMClient`의 기본값(`claude-opus-4-7`) 또는 인자로 지정.

## 다음 작업 (우선순위)
### A. 2단계 포트폴리오 최적화 엔진 (핵심 미구현)
- 입력: `AnalysisResult.optimizer_constraints`
  (max_horizon_years, min_cash_reserve, target_return_min/max, risk_level, excluded_sectors, provisional)
- 자산 유니버스: 국내주식·해외주식·ETF·리츠·원자재(금·은·구리)·달러
- 가격 데이터: `yfinance`(일별 종가로 시작, 실시간은 후순위)
- 출력 지표: 기대수익률, **소르티노 지수**, 시장지수 대비 **베타**
- **미확정 설계 결정 2가지 (구현 전 사용자와 합의 필요):**
  1. 최적화 방법론: 단순 평균-분산(MVO)은 입력오차에 쏠림 심함 →
     리스크패리티 / Black-Litterman / 제약강화 MVO 중 선택.
  2. 시각화 위험축 정의: "기대수익률 vs 위험도" 화면에서 위험축을
     소르티노(높을수록 좋음)로 쓰면 직관과 반대 → 위험축은 하방변동성/MDD 계열을
     0~100 변환 권장, 소르티노는 별도 "위험조정 성과 점수"로 표시.
- `excluded_sectors`(예: tobacco/gambling)를 종목 배제 규칙으로 매핑하는 분류표 필요.

### B. 웹 UI (Next.js + TailwindCSS, 추천 스택)
- PB 화면: 7요인 카드 + 인라인 표시(신뢰도·정보없음·🔎규칙) + 검토 탭(심각도순 🔴🟡⚪) + 추가질문 패널
- 고객 화면: 확정본만, 내부 메커니즘(신뢰도·이중축) 숨김
- D-2 게이트: PB→고객 전환 시 미해결 빨강 플래그 있으면 경고

### C. 저장소 Supabase 교체 (선택)
- `CustomerRepository` / `SessionRepository` 추상 클래스를 Supabase 구현으로 갈아끼우면 됨.
- 테이블: customers, sessions(+ audit_log 신설 권장).

## 주의사항
- **세법 수치는 `rules_config.py`에만** 둔다(금융소득종합과세 2천만원 등). 법 개정 시 여기만 수정.
- 세무 규칙 중 A-2/A-3/A-4는 "확정"이 아니라 "PB 검토 필요" 플래그로만 작동(오판 방지).
- 민감정보(D-1)는 주민번호·연락처·계좌번호 패턴 탐지. 과탐 방지를 위해 구체적 패턴 우선.
- 분석 결과는 세션 엑셀의 `result_json` 칸에 전체 저장되고, 펼친 칸은 검색·요약용.

## 빠른 검증
```bash
pip install openpyxl
python demo.py          # 전체 흐름
```
