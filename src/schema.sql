-- =============================================================
-- 서사 넥서스 v1.1 — SQLite 스키마 (설계문서 §4.2 + §8.7 통합)
-- 원칙: raw 불변 / point-in-time(known_at) / 사실·해석 분리
-- =============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 주봉 마스터 (모든 테이블의 기준 축)
CREATE TABLE IF NOT EXISTS weeks (
  week_id TEXT PRIMARY KEY,          -- 'YYYY-Www' (ISO-8601)
  week_start DATE,                   -- 주 첫 거래일
  week_end DATE,                     -- 주 마지막 거래일
  trading_days INTEGER
);

-- ① 가격·수급 (종목 × 주)
CREATE TABLE IF NOT EXISTS weekly_price (
  week_id TEXT, ticker TEXT,
  open REAL, high REAL, low REAL, close REAL, close_adj REAL,
  volume INTEGER, value_traded REAL, mktcap REAL,
  ret_w REAL, turnover_w REAL,
  PRIMARY KEY (week_id, ticker)
);

CREATE TABLE IF NOT EXISTS weekly_flow (
  week_id TEXT, ticker TEXT,
  net_retail REAL, net_foreign REAL, net_inst REAL, net_etc REAL,
  retail_ratio REAL,
  short_vol INTEGER, short_ratio REAL,
  short_bal REAL, short_bal_wow REAL,
  known_at DATE,                     -- 공매도 잔고 공표 지연(T+2 추정) 반영
  PRIMARY KEY (week_id, ticker)
);

CREATE TABLE IF NOT EXISTS weekly_credit (  -- v1: 시장 전체
  week_id TEXT PRIMARY KEY,
  credit_bal REAL, credit_wow REAL, known_at DATE
);

-- ② 실물 접점
CREATE TABLE IF NOT EXISTS weekly_real (
  week_id TEXT, series_id TEXT,      -- 'export_cathode', 'usdkrw', ...
  value REAL, yoy REAL,
  period_start DATE, period_end DATE,-- 집계 대상 기간
  known_at DATE,                     -- 발표일 (귀속 기준, 원칙 2)
  PRIMARY KEY (week_id, series_id)
);

-- ③ 서사 (v1.1: A층 확장 — channel_tier, slogan_hhi)
CREATE TABLE IF NOT EXISTS weekly_narrative (
  week_id TEXT, keyword TEXT, source TEXT,  -- 'gtrends'|'bigkinds'|'dart'|'youtube'
  raw_count REAL, momentum REAL, z52 REAL,
  channel_tier TEXT,                 -- 'trade'|'econ'|'general'|'youtube'|'community' (§8.1 A1)
  slogan_hhi REAL,                   -- 헤드라인 n-gram 집중도 (§8.1 A2)
  PRIMARY KEY (week_id, keyword, source)
);

-- 수동 이벤트 로그 (v1 서사층 중심축)
CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY,
  date DATE, ticker TEXT,
  category TEXT,   -- 'disclosure'|'report'|'youtube'|'news'|'policy'|'short_report'
  title TEXT, source_url TEXT, note TEXT
);

-- 사이클 라벨 (해석 층 — 사실과 분리, 원칙 3. v1.1: network_status, cohort)
CREATE TABLE IF NOT EXISTS cycle_labels (
  week_id TEXT, ticker TEXT,
  stage TEXT,          -- 'dormant'|'genesis'|'diffusion'|'saturation'|'decay'
  substage TEXT,       -- '과포화-1', '재점화' 등 자유 기술
  confidence TEXT,     -- 'H'|'M'|'L'
  evidence TEXT,       -- 판단 근거 서술
  labeled_at DATE, revised_from TEXT,
  network_status TEXT, -- 'active'|'condensed'|'dissolved'|'unknown' (§8.3 소멸 이원화)
  cohort TEXT,         -- 'ignited'|'control_dead' (§8.4 대조군 표식)
  PRIMARY KEY (week_id, ticker, labeled_at)  -- 라벨 수정 이력 보존
);

-- ── §7 실타래 스크리너 ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS threads (
  thread_id INTEGER PRIMARY KEY,
  opened_week TEXT, domain TEXT,     -- 'game'|'policy'|...
  ticker TEXT, theme TEXT,
  precursor_desc TEXT,               -- 전조 근거
  gap_metric REAL,                   -- 등록 시점 갭 크기
  hypothesis TEXT,                   -- 한 줄 가설 (초과 금지)
  status TEXT,                       -- 'candidate'|'watch'|'ignited'|'dropped'
  closed_week TEXT, close_reason TEXT,
  postmortem TEXT,
  -- §8.7 홀림 지수 (등록 시 채점·봉인)
  hook_score INTEGER,                -- FUN9 0~9
  mobilize_score INTEGER,            -- 동원 축 0~10
  falsify_class TEXT,                -- 'weeks'|'event_dated'|'deferred'
  scored_at DATE                     -- 봉인 시점
);

CREATE TABLE IF NOT EXISTS thread_log (
  thread_id INTEGER, week_id TEXT,
  precursor_z REAL, narrative_z REAL, price_ret REAL,
  note TEXT,
  PRIMARY KEY (thread_id, week_id)
);

CREATE TABLE IF NOT EXISTS asset_map (
  domain TEXT, external_id TEXT,     -- steam appid, 법안 키워드 등
  ticker TEXT, weight REAL, note TEXT,
  PRIMARY KEY (domain, external_id, ticker)
);

-- 수집 메타 (소스별 수정주가 여부 등 — §1 ① 주의사항)
CREATE TABLE IF NOT EXISTS source_meta (
  source TEXT PRIMARY KEY,           -- 'pykrx_ohlcv'|'fdr_ohlcv'|...
  adjusted INTEGER,                  -- 수정주가 여부 (0/1/NULL=미확인)
  note TEXT, checked_at DATE
);
