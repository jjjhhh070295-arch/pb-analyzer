-- PB 고객 분석 시스템 — Supabase 테이블 DDL
-- Supabase 대시보드 > SQL Editor에서 실행

-- 고객 테이블
CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    birth_date    TEXT NOT NULL,
    primary_pb    TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

-- 상담 세션 테이블
CREATE TABLE IF NOT EXISTS sessions (
    session_id          TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    customer_name       TEXT NOT NULL,
    pb_name             TEXT NOT NULL,
    consult_date        TEXT NOT NULL,
    consult_datetime    TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT '검수중',
    -- 요약 칸 (검색·목록용)
    goal_return_summary TEXT,
    risk_level          TEXT,
    horizon_years       FLOAT,
    unresolved_flags    INTEGER DEFAULT 0,
    follow_up_count     INTEGER DEFAULT 0,
    -- 원문 + 전체 결과
    raw_text            TEXT,
    result_json         TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 조회 성능용 인덱스
CREATE INDEX IF NOT EXISTS idx_sessions_customer ON sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_sessions_pb       ON sessions(pb_name);
CREATE INDEX IF NOT EXISTS idx_sessions_date     ON sessions(consult_date);
CREATE INDEX IF NOT EXISTS idx_sessions_status   ON sessions(status);
