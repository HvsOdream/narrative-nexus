# -*- coding: utf-8 -*-
"""
서사 넥서스 v1.1 — ①가격·수급 + ③서사(자동 2종) 수집 배치
=============================================================
★ 이 스크립트는 사용자 로컬(Windows)에서 실행합니다. 클라우드/로컬 VM은
  KRX·구글 네트워크가 차단되어 있으므로 Claude가 대신 실행할 수 없습니다.

사전 준비 (1회):
    pip install pykrx finance-datareader pytrends pandas

실행:
    python collect_v1.py            # 전체 수집
    python collect_v1.py --skip-trends   # Google Trends 제외

원칙:
  - raw 불변: 원천 데이터를 가공 없이 data/raw/<source>/ 에 CSV 저장
  - 소스별 파일 분리, 실행일 스탬프 메타(_meta.json) 기록
  - 소스 하나가 실패해도 나머지는 계속 진행 (§8.6 결측 주 허용)
"""
import json
import sys
import time
import traceback
from datetime import date
from pathlib import Path

TICKER = "086520"            # 에코프로
FROM = "20220701"            # 사이클 전 여유 구간 (§6-2)
TO = "20240331"
KEYWORDS = ["에코프로", "2차전지", "양극재"]   # ③층 Google Trends (§1 3-1)
TRENDS_TIMEFRAME = "2022-07-01 2024-03-31"

ROOT = Path(__file__).resolve().parent.parent   # narrative-nexus/
RAW = ROOT / "data" / "raw"

RESULTS = {}   # source -> 'ok'|'fail: ...'


def save(df, source: str, name: str, meta: dict | None = None):
    if df is None or len(df) == 0:
        raise RuntimeError("빈 응답(0행) — 차단/스로틀 의심, 기존 raw 보존")
    d = RAW / source
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.csv"
    df.to_csv(p, encoding="utf-8-sig")
    m = {"saved_at": date.today().isoformat(), "rows": len(df),
         "range": [FROM, TO], **(meta or {})}
    (d / f"{name}_meta.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] {source}/{name}.csv  rows={len(df)}")


def step(source: str):
    """소스별 실패 격리 데코레이터."""
    def deco(fn):
        def wrapper(*a, **kw):
            print(f"\n== {source} ==")
            try:
                fn(*a, **kw)
                RESULTS[source] = "ok"
            except Exception as e:
                RESULTS[source] = f"fail: {e}"
                print(f"  [FAIL] {source}: {e}")
                traceback.print_exc(limit=2)
        return wrapper
    return deco


# ── ① 가격·수급 층 ──────────────────────────────────────────

@step("pykrx_ohlcv")
def collect_ohlcv():
    from pykrx import stock
    df = stock.get_market_ohlcv_by_date(FROM, TO, TICKER)
    # 주의: pykrx OHLCV는 수정주가 아님 (§1 ① 표 하단) — meta에 명시
    save(df, "pykrx", "ohlcv_086520", {"adjusted": False})


@step("fdr_ohlcv_adj")
def collect_fdr():
    import FinanceDataReader as fdr
    df = fdr.DataReader(TICKER, "2022-07-01", "2024-03-31")
    # FDR은 수정주가 — 액면분할(2024-04, 5:1) 검증용 병기 저장
    save(df, "fdr", "ohlcv_adj_086520", {"adjusted": True})


@step("pykrx_trading_value")
def collect_flow():
    from pykrx import stock
    df = stock.get_market_trading_value_by_date(FROM, TO, TICKER, detail=True)
    save(df, "pykrx", "trading_value_086520")


@step("pykrx_short_balance")
def collect_short_balance():
    from pykrx import stock
    df = stock.get_shorting_balance_by_date(FROM, TO, TICKER)
    # known_at(공표 지연)은 build 단계에서 T+2 영업일로 근사 — 실데이터로 확인 필요
    save(df, "pykrx", "short_balance_086520", {"known_at_rule": "T+2 (미검증 가정)"})


@step("pykrx_short_volume")
def collect_short_volume():
    from pykrx import stock
    df = stock.get_shorting_volume_by_date(FROM, TO, TICKER)
    save(df, "pykrx", "short_volume_086520")


@step("pykrx_mktcap")
def collect_mktcap():
    from pykrx import stock
    df = stock.get_market_cap_by_date(FROM, TO, TICKER)
    save(df, "pykrx", "mktcap_086520")


# ── ② 실물 접점 (v1: 환율만 자동) ───────────────────────────

@step("fdr_usdkrw")
def collect_usdkrw():
    import FinanceDataReader as fdr
    df = fdr.DataReader("USD/KRW", "2022-07-01", "2024-03-31")
    save(df, "fdr", "usdkrw")


# ── ③ 서사 층 (자동 2종 중 Google Trends) ───────────────────

@step("gtrends")
def collect_trends():
    from pytrends.request import TrendReq
    py = TrendReq(hl="ko-KR", tz=540)
    for kw in KEYWORDS:
        py.build_payload([kw], timeframe=TRENDS_TIMEFRAME, geo="KR")
        df = py.interest_over_time()
        if df.empty:
            raise RuntimeError(f"'{kw}' 결과 없음")
        safe = kw.replace("/", "_")
        save(df, "gtrends", f"trends_{safe}",
             {"keyword": kw, "note": "기준 100 상대값 (§1 3-1)"})
        time.sleep(5)   # 레이트리밋 회피


def main():
    skip_trends = "--skip-trends" in sys.argv
    print(f"서사 넥서스 collect_v1 — {TICKER}, {FROM}~{TO}")
    print(f"저장 위치: {RAW}")

    collect_ohlcv()
    collect_fdr()
    time.sleep(5)
    collect_flow()
    time.sleep(5)
    collect_short_balance()
    time.sleep(5)
    collect_short_volume()
    time.sleep(5)
    collect_mktcap()
    collect_usdkrw()
    if not skip_trends:
        collect_trends()

    print("\n===== 수집 결과 요약 =====")
    for k, v in RESULTS.items():
        print(f"  {k}: {v}")
    fails = [k for k, v in RESULTS.items() if v != "ok"]
    if fails:
        print(f"\n실패 {len(fails)}건 — 해당 소스만 재실행하거나 다음 주 배치에서 재시도 (§8.6)")
    else:
        print("\n전 소스 수집 완료. 다음 단계: python build_weekly.py")


if __name__ == "__main__":
    main()
