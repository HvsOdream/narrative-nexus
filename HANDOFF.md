# HANDOFF — 서사 넥서스 세션 인계 (BATON)

> 작성: 2026-08-11 클라우드 세션. **새 세션은 이 파일 + README.md만 읽으면 이어받을 수 있다.**
> 정본 코드 = 이 레포. Dropbox 사본(00_Data/Cowork/narrative-nexus/)은 v1.0/1.1로 **구버전** — 아래 Todo 1에서 동기화할 것.

## B — Brief (현재 상태)

- 웹 대시보드 가동 중: https://hvsodream.github.io/narrative-nexus/ (에코프로 index) + /001570.html (금양) + /000250.html (삼천당제약)
- GitHub Actions weekly-batch가 매주 토요일 09:00 KST 자동 실행: collect(3종목, 2022-07~실행일 롤링) → build → dashboard → 자동 커밋
- 이벤트 로그 34건 반영 (data/manual/events.csv, 전 건 출처 URL)
- 에코프로 잠정 라벨(§3.2 시드) 적용 / 금양·삼천당 라벨 없음

## A — Active (확정 자산·실측)

- pykrx OHLCV는 **수정주가**(액면분할 소급 반영)로 실측 확인 → 설계문서 §1 "수정주가 아님" 전제는 정정됨
- 에코프로: 트렌드 z 1차 피크(23-W16, z≈5.0)가 가격 고점(23-W30)을 14주 선행 — 이중 피크 실측
- 금양: 2025-W14부터 거래정지 평평한 캔들 = 가격축 소멸의 완결형 관측
- 삼천당: 2026-W13 피크(주봉 종가 111.1만) 후 붕괴 — 이벤트 마커와 일치
- KRX 세부 API(수급·공매도·시총)는 Actions 러너 IP 차단 → 해당 패널 빈 상태, 매주 자동 재시도 (빈 응답은 저장 안 함 §8.6)
- GitHub push 경로: 클라우드/로컬VM git proxy 차단 → **사용자 브라우저에서 GitHub API fetch(PUT)** 로 파일 반영 (PAT는 Dropbox 00_Data/Cowork/.github-pat, repo scope, ~2026-09-26). 워크플로우 yml만은 웹 에디터(로그인 세션) 필요

## T — Todo (다음 세션 우선순위)

1. **Dropbox 동기화**: 레포의 src/collect_v1.py·build_weekly.py·dashboard.py(v1.2)·data/manual/events.csv를 Dropbox narrative-nexus/에 덮어쓰기 (git clone → device_commit_files)
2. **CLAUDE.md 등록**: 마스터 지침에 "2-3. 진행 중 프로젝트 — 서사 넥서스" 절 신설 (레포 URL·대시보드 URL·이 HANDOFF 참조·트리거 키워드 "서사 넥서스"/"넥서스 대시보드" 등). 버전 규칙(v+0.1, 사본 저장, 변경 이력) 준수
3. **금양·삼천당 라벨링**: 실데이터 보며 사용자와 함께 cycle_labels.csv에 단계 라벨 추가 (해석은 사람 판단 — 원칙 3)
4. 에코프로 잠정 라벨 실데이터 대조·수정 (설계 §6 item 7)
5. (선택) KRX 수급·공매도 **과거 백필 1회를 사용자 로컬에서** 실행하는 하이브리드 검토 — python src/collect_v1.py 한 번이면 과거분 영구 확보

## O — Open (미해결 논점)

- Google Trends 상대값 재스케일 문제: 롤링 수집 시 과거값이 매주 재스케일됨 → point-in-time 원칙(§0-2)과 충돌. 주간 스냅샷 누적 보존 구조 검토 필요
- 트렌드 '금양'·'삼천당제약' 키워드 수집 실패 중(429 추정) — 재시도 관망
- 거래정지 구간의 시각 표현(평평한 캔들 vs 별도 표기) + 네트워크 소멸축(종토방) 시각화 부재 (§8.3)
- 매매 신호 아님 — 관찰기 성격 유지 (모든 확장에서 이 규율 우선)

## N — Note

- 설계 정본: Dropbox narrative-nexus/nexus_design_v1.md (v1.1). 레포의 nexus_design_v1.md는 포인터
- 세션 로그 맥락: 클라우드 세션은 시작 기기(집/연구실)에 바인딩됨 — 연구실에서는 연구실 데스크톱 앱에서 새 작업으로 시작할 것
