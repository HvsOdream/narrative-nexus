# 서사 넥서스 v1.1 — 관찰 대시보드

> 설계 문서: `nexus_design_v1.md` (v1.1, 2026-08-07) 참조.
> 성격: **예측기가 아닌 관찰기.** 모든 지표는 매매 신호가 아니다.

**웹 대시보드**: https://hvsodream.github.io/narrative-nexus/

## 아키텍처 (완전 자동)

```
GitHub Actions (매주 토요일 09:00 KST + 수동 실행)
  1. collect_v1.py  — pykrx/FDR/pytrends 수집 → data/raw/ (원본 불변)
  2. build_weekly.py — 주봉 정렬 + 파생 지표 → data/nexus.db
  3. dashboard.py   — docs/index.html 재생성
  4. 결과를 레포에 자동 커밋 → GitHub Pages가 즉시 서빙
```

사용자는 아무것도 실행할 필요 없음. 수동 층(아래 CSV)만 가끔 채우면 된다.

## 폴더 구조

```
narrative-nexus/
├── nexus_design_v1.md      # 설계 문서 (단일 기준)
├── .github/workflows/weekly-batch.yml
├── data/
│   ├── raw/                # Actions 수집 산출 (원본 불변 — 수정 금지)
│   ├── manual/             # 수동 수집 CSV 4종 (아래)
│   └── nexus.db            # 가공 층 (SQLite, Actions 산출)
├── src/
│   ├── schema.sql          # v1.1 통합 스키마 (§4.2 + §8.7)
│   ├── collect_v1.py       # 수집 배치
│   ├── build_weekly.py     # 주봉 변환 + 파생 지표
│   └── dashboard.py        # 대시보드 생성
└── docs/index.html         # ★ 웹 대시보드 (Pages 서빙)
```

## 수동 CSV (data/manual/) — GitHub 웹에서 직접 편집 가능

| 파일 | 컬럼 | 비고 |
|---|---|---|
| `events.csv` | date, ticker, category, title, source_url, note | category: disclosure/report/youtube/news/policy/short_report. **v1 서사층 중심축** |
| `bigkinds_weekly.csv` | date, keyword, count, channel_tier | 빅카인즈 건수. channel_tier: trade/econ/general/youtube/community (§8.1 채널 사다리) |
| `credit_daily.csv` | date, credit_bal | 금융투자협회(freesis.kofia.or.kr) 시장 전체 신용융자 잔고 |
| `cycle_labels.csv` | week_from, week_to, ticker, stage, substage, confidence, evidence, labeled_at, cohort | 사이클 단계 라벨(해석 층). 현재 §3.2 잠정 가설 시드 — 실데이터 검증 후 수정 |

편집 후 커밋하면 다음 배치(또는 Actions 수동 실행)에서 대시보드에 반영된다.

## 주의사항 (설계 원칙 요약)

- **주봉이 유일한 시간축** — week_id는 ISO-8601 (`2023-W30`).
- **point-in-time** — 발표일 귀속, `known_at` 컬럼. 공매도 잔고 T+2 지연은 근사값 (§2.3).
- **forward-fill 금지** (저장 층). 시각화 단계에서만 허용.
- pykrx OHLCV는 **수정주가 아님** — FDR 수정주가와 병기 저장.
- 소스 실패는 격리: 실패 소스만 다음 배치에서 재시도 (§8.6 결측 주 허용).
- Google Trends는 Actions IP에서 429가 잦음 — 실패해도 나머지 배치는 정상 진행.

## 로컬 실행 (폴백 — Actions가 죽었을 때만)

```
pip install pykrx finance-datareader pytrends pandas
python src/collect_v1.py && python src/build_weekly.py && python src/dashboard.py
```

## 다음 단계 (설계 §6 체크리스트 잔여)

- [ ] 첫 백필 실행(Actions) → 실데이터 확인
- [ ] 수동 이벤트 로그 15~30건 수집 (item 6)
- [ ] 잠정 라벨 실데이터 대조·수정 (item 7)
- [ ] DART API 키 발급 — 사용자 (item 9)
- [ ] §7 실타래 스크리너 파일럿(게임·정책), 삼천당 해부, 죽은 서사 대조군 (§8.4)
