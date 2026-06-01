# CLAUDE.md — 프로젝트 작업 맥락

이 파일은 Claude Code가 프로젝트를 이어서 작업할 때 참고하는 맥락 문서다.

## 프로젝트 개요
초고액 자산가(보유자산 30억 이상)를 상대하는 증권사 PB를 돕는 분석 도구.
PB가 고객 상담 내용을 자유 텍스트로 입력하면, 시스템이 **7요인**으로 자동 분석하고
**규칙 검증**으로 세무·정합성·안전 플래그를 달아 PB의 판단을 돕는다.
**최종 투자판단과 책임은 PB에게 있다**(자본시장법상 투자권유·자문 이슈 회피).

## 현재 상태: 풀스택 배포 완료

배포 URL:
- 프론트엔드: **https://pb-analyzer.vercel.app** (Vercel Hobby)
- 백엔드: **https://pb-analyzer-production.up.railway.app** (Railway Trial)
- DB: Supabase (`https://sttnajnzeedkiwcqusjl.supabase.co`, Mumbai region)
- 소스: **https://github.com/jjjhhh070295-arch/pb-analyzer** (monorepo)

자동 배포: `git push`만 하면 Railway·Vercel이 자동 감지·재배포.

## 폴더 구조 (monorepo)
```
pb_analyzer/
├── pb_analyzer_pkg/   ← FastAPI 백엔드 (Railway가 이 폴더를 Root로 인식)
│   ├── main.py        ← 진입점, CORS 화이트리스트
│   ├── Procfile       ← Railway start command
│   ├── routers/       ← customers, sessions, portfolio
│   ├── analyzer.py, extractors.py, validators.py, ...
│   ├── supabase_repositories.py  ← Supabase 구현
│   └── deps.py        ← SUPABASE_URL 있으면 Supabase, 없으면 Excel
└── frontend/          ← Next.js 프론트 (Vercel이 이 폴더를 Root로 인식)
    ├── app/           ← /, /customers/new, /sessions/new, /sessions/[id], /customer/[id]
    ├── components/    ← FactorCard, FlagList, FollowUpPanel, PortfolioTab, EditFactorsModal
    └── lib/api.ts     ← 백엔드 API 클라이언트
```

## 구현 완료 기능 요약

### 1단계 — 분석 (백엔드 로직)
- 7요인 분리 분석(LLM), 13개 규칙 검증, evidence/신뢰도/status 부착
- 더미 시나리오 4종 키워드 분기 (`routers/sessions.py` `_pick_demo_scenario`):
  - "법인·잉여·가업승계" → 보수형 4~6%
  - "부동산·임대·보유세" → 자산 분산 3~5%
  - "사업 매각·예금·인플레이션" → 헤지 5~7%
  - 그 외 → 일반 7~9%

### 2단계 — 포트폴리오 최적화 (`optimizer.py`)
- 리스크 패리티 (`scipy.optimize`)
- 자산 유니버스 8개 ETF, yfinance 실시간 데이터
- 지표: 기대수익률, 하방변동성→0~100 점수, 소르티노, 베타
- risk_level 따라 자산별 비중 상한 조정, excluded_sectors 반영

### 화면 / UI
- **메인**: 고객 검색·목록, 최근 상담 상태, 새 상담 / 결과 보기 / 🗑(세션) / ✕(고객+상담 cascade)
- **PB 결과 화면 (`/sessions/[id]`)**:
  - 탭: 7요인 카드 / 플래그 / 추가질문 / 포트폴리오
  - 검수중에서만: **✎ 7요인 편집** 버튼 → `EditFactorsModal` (4탭, 신뢰도·근거까지 수정)
  - 추가질문 패널에 textarea 답변 → **답변 반영 후 재분석** (`PATCH /sessions/{id}/reanalyze`)
  - 확정 후 **재수정 모드** 버튼 → 검수중으로 되돌리기
  - 헤더 🗑 → 상담 삭제 모달
  - 포트폴리오 탭: 최적화 결과 → **✎ 비중 수정** → 각 자산 % 직접 편집 + PB 메모
  - 골드 **포트폴리오 확정** 버튼 → 고객 화면에 송출
- **고객 화면 (`/customer/[id]`)**: 확정본만, 신뢰도·플래그·내부 메커니즘 전부 숨김. 확정 포트폴리오 있으면 별도 섹션 자동 노출 (지표는 숨기고 비중·PB 코멘트만).

## 디자인 시스템
- `frontend/app/globals.css`에 CSS 변수 정의 (`--navy`, `--gold`, `card-premium`, `btn-navy`, `btn-gold`, `bg-header-gradient`, `badge-confirmed`).
- 네이비(`#1e3a8a`) + 골드(`#d4a14b`) 톤. 모든 헤더는 그라데이션 + 하단 골드 라인.

## 핵심 설계 결정 (변경 시 주의)
1. **요인별 분리 분석**: 각 요인 전용 프롬프트, 단 전체 원문 항상 제공. (`extractors.py`)
2. **위험허용도 이중 축**: willingness/capacity 분리, 더 보수적인 축이 binding.
3. **신뢰도는 상/중/하** 3단계 문자열. `models.Confidence`.
4. **status 3종**: explicit / inferred / missing.
5. **규칙 검증 13개** (`validators.py`, on/off는 `rules_config.RULE_TOGGLES`).
6. **PB ↔ 고객 화면 단방향 게이트**: 확정된 세션만 고객 화면 표시.
7. **저장소·LLM 추상 인터페이스**: `SUPABASE_URL` 환경변수로 Excel↔Supabase 자동 전환, `ANTHROPIC_API_KEY`로 mock↔실제 LLM 자동 전환.
8. **동명이인**: 고유 ID `C0001…`이 진짜 식별자. 상담은 `customer_id`로 묶임.
9. **`AnalysisResult.confirmed_portfolio`**: PB 수정 후 확정한 포트폴리오를 자유 dict로 저장. 고객 화면 송출 대상.

## 알아둬야 할 트랩 / 결정 사항
- **Supabase 키 시스템**: 새 `sb_secret_*` 형식이 아니라 **레거시 JWT(`eyJ...`)** 사용 중. 라이브러리(`supabase>=2.9`)가 새 형식을 인식 못 함.
- **`httpx` 호환**: `supabase 2.3` + `httpx 0.28` 조합은 `proxy` 인자 에러. `supabase>=2.9`로 핀 (requirements.txt).
- **Python**: 로컬 `.venv`는 Python 3.14 (uv 기본), Railway는 nixpacks가 Python 3.13 자동 선택.
- **CORS**: `main.py`에 Vercel 도메인 + `localhost:3000/3002`만 허용. PR preview는 정규식으로 매칭.
- **mock LLM**: ANTHROPIC_API_KEY 없으면 `_pick_demo_scenario`로 키워드 분기된 더미 응답 반환. 키 추가 시 자동으로 진짜 분석으로 전환 (코드 변경 없음).

## 환경변수 (Railway·Vercel·로컬 .env)
- **백엔드 (Railway)**:
  - `SUPABASE_URL` = `https://sttnajnzeedkiwcqusjl.supabase.co`
  - `SUPABASE_SERVICE_KEY` = (Supabase 레거시 JWT)
  - `ANTHROPIC_API_KEY` = (아직 미설정 — 충전 후 추가 예정)
- **프론트 (Vercel)**:
  - `NEXT_PUBLIC_API_URL` = `https://pb-analyzer-production.up.railway.app/api`

## 등록된 데모 고객 (Supabase customers 테이블)
| ID | 이름 | 시나리오 키워드 |
|----|------|-----------------|
| C0001 | 테스트고객 | 기본 |
| C0002 | 강민호 | 법인·가업승계 |
| C0003 | 이정숙 | 부동산 편중 |
| C0004 | 최영진 | 사업 매각·현금 |
| C0005 | 홍길동 | 일반 |

각 시나리오에 맞는 더미 상담 텍스트는 PB가 직접 복사·붙여넣어 분석 실행.

## 다음 후보 작업
- Anthropic API 키 충전 → Railway에 `ANTHROPIC_API_KEY` 추가하면 즉시 실제 분석 작동
- 인증 (비밀번호 게이트 또는 Supabase Auth)
- 상담 이력(같은 고객의 과거 세션) 목록 화면
- 포트폴리오 백테스트 차트
- 알림(PB → 고객 메일 발송 등)
