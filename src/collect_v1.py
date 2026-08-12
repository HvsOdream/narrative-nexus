# -*- coding: utf-8 -*-
"""
서사 넥서스 v1.2 — 멀티 종목 수집 배치 (에코프로·금양·삼천당제약)
=============================================================
GitHub Actions에서 매주 실행. 수집 기간: 2022-07-01 ~ 실행일 (롤링).

원칙:
  - raw 불변: data/raw/<source>/ 에 종목별 CSV 저장
  - 빈 응답(0행)은 저장하지 않고 실패 처리 → 기존 raw 보존 (§8.6)
  - 소스 하나가 실패해도 나머지는 계속 진행
"""
import json
import sys
import time
import traceback
from datetime import date
from pathlib import Path

TICKERS = {
    "086520": "에코프로",
    "001570": "금양",
    "000250": "삼천당제약",
}
FROM = "20220701"
TO = date.today().strftime("%Y%m%d")          # 롤링 (실행일까지)
FROM_D = "2022-07-01"
TO_D = date.today().isoformat()
KEYWORDS = ["에코프로", "2차전지", "양극재", "금양", "삼천당제약"]
TRENDS_TIMEFRAME = f"{FROM_D} {TO_D}"

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

RESULTS = {}


def save(df, source: str, name: str, meta: dict | None = None):
    if df is None or len(df) == 0:
        raise RuntimeError("빈 응답(0행) — 차단/스로틀 의심, 기존 raw 보존")
    d = RAW / source
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / f"{name}.csv", encoding="utf-8-sig")
    m = {"saved_at": date.today().isoformat(), "rows": len(df),
         "range": [FROM, TO], **(meta or {})}
    (d / f"{name}_meta.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] {source}/{name}.csv  rows={len(df)}")


def step(key: str, fn, *a, **kw):
    print(f"\n== {key} ==")
    try:
        fn(*a, **kw)
        RESULTS[key] = "ok"
    except Exception as e:
        RESULTS[key] = f"fail: {e}"
        print(f"  [FAIL] {key}: {e}")
        traceback.print_exc(limit=2)


# ── ① 가격·수급 층 (종목별) ─────────────────────────────────

def collect_ohlcv(t):
    from pykrx import stock
    df = stock.get_market_ohlcv_by_date(FROM, TO, t)
    # 실측(2026-08-09): pykrx OHLCV는 액면분할 소급 반영(수정주가)으로 확인됨
    save(df, "pykrx", f"ohlcv_{t}", {"adjusted": True, "note": "실측: 분할 소급 반영"})


def collect_fdr(t):
    import FinanceDataReader as fdr
    df = fdr.DataReader(t, FROM_D, TO_D)
    save(df, "fdr", f"ohlcv_adj_{t}", {"adjusted": True})


def collect_flow(t):
    from pykrx import stock
    df = stock.get_market_trading_value_by_date(FROM, TO, t, detail=True)
    save(df, "pykrx", f"trading_value_{t}")


def collect_short_balance(t):
    from pykrx import stock
    df = stock.get_shorting_balance_by_date(FROM, TO, t)
    save(df, "pykrx", f"short_balance_{t}", {"known_at_rule": "T+2 (미검증 가정)"})


def collect_short_volume(t):
    from pykrx import stock
    df = stock.get_shorting_volume_by_date(FROM, TO, t)
    save(df, "pykrx", f"short_volume_{t}")


def collect_mktcap(t):
    from pykrx import stock
    df = stock.get_market_cap_by_date(FROM, TO, t)
    save(df, "pykrx", f"mktcap_{t}")


# ── ② 실물 접점 ─────────────────────────────────────────────

def collect_dart_holders():
    """DART 소액주주 현황 (mrhlSttus) — 신자 집합의 하드 카운트 (§8.3 네트워크축)."""
    import io
    import os
    import zipfile
    import urllib.request
    import xml.etree.ElementTree as ET
    import json as _json
    import pandas as _pd
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DART_API_KEY 미설정")
    z = urllib.request.urlopen(
        f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}", timeout=120).read()
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(z)).read("CORPCODE.xml"))
    corp = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc in TICKERS:
            corp[sc] = el.findtext("corp_code").strip()
    rows = []
    for t, cc in corp.items():
        for y in range(2022, int(TO[:4]) + 1):
            for rc in ("11013", "11012", "11014", "11011"):
                q = (f"https://opendart.fss.or.kr/api/mrhlSttus.json?crtfc_key={key}"
                     f"&corp_code={cc}&bsns_year={y}&reprt_code={rc}")
                try:
                    j = _json.loads(urllib.request.urlopen(q, timeout=30).read())
                except Exception:
                    continue
                if j.get("status") != "000":
                    continue
                for it in j.get("list", []):
                    rows.append({
                        "ticker": t, "bsns_year": y, "reprt_code": rc,
                        "rcept_no": it.get("rcept_no", ""),
                        "known_at": str(it.get("rcept_no", ""))[:8],
                        "se": it.get("se", ""),
                        "shrholdr_co": it.get("shrholdr_co", ""),
                        "shrholdr_tot_co": it.get("shrholdr_tot_co", ""),
                        "hold_stock_co": it.get("hold_stock_co", ""),
                        "stock_tot_co": it.get("stock_tot_co", ""),
                        "hold_stock_rate": it.get("hold_stock_rate", ""),
                    })
                time.sleep(0.3)
    save(_pd.DataFrame(rows), "dart", "minority_holders",
         {"note": "known_at = rcept_no 앞 8자리(공시접수일) — 발표일 귀속(원칙 2)"})


def collect_usdkrw():
    import FinanceDataReader as fdr
    df = fdr.DataReader("USD/KRW", FROM_D, TO_D)
    save(df, "fdr", "usdkrw")


# ── ③ 서사 층 (Google Trends) ───────────────────────────────

def collect_trends():
    from pytrends.request import TrendReq
    py = TrendReq(hl="ko-KR", tz=540)
    for kw in KEYWORDS:
        py.build_payload([kw], timeframe=TRENDS_TIMEFRAME, geo="KR")
        df = py.interest_over_time()
        if df.empty:
            print(f"  [FAIL] gtrends '{kw}' 결과 없음")
            RESULTS[f"gtrends_{kw}"] = "fail: empty"
            continue
        save(df, "gtrends", f"trends_{kw.replace('/', '_')}",
             {"keyword": kw, "note": "기준 100 상대값 (§1 3-1)"})
        RESULTS[f"gtrends_{kw}"] = "ok"
        time.sleep(5)


def main():
    skip_trends = "--skip-trends" in sys.argv
    print(f"서사 넥서스 collect v1.2 — {list(TICKERS)} {FROM}~{TO}")

    for t, name in TICKERS.items():
        step(f"ohlcv_{t}", collect_ohlcv, t)
        step(f"fdr_{t}", collect_fdr, t)
        time.sleep(3)
        step(f"flow_{t}", collect_flow, t)
        time.sleep(3)
        step(f"short_bal_{t}", collect_short_balance, t)
        time.sleep(3)
        step(f"short_vol_{t}", collect_short_volume, t)
        time.sleep(3)
        step(f"mktcap_{t}", collect_mktcap, t)
        time.sleep(3)
    step("usdkrw", collect_usdkrw)
    step("dart_holders", collect_dart_holders)
    if not skip_trends:
        step("gtrends", collect_trends)

    print("\n===== 수집 결과 요약 =====")
    for k, v in RESULTS.items():
        print(f"  {k}: {v}")
    fails = [k for k, v in RESULTS.items() if v != "ok"]
    print(f"\n실패 {len(fails)}건 — 실패 소스는 다음 배치에서 재시도 (§8.6)")


if __name__ == "__main__":
    main()
