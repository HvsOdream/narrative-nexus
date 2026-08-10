# -*- coding: utf-8 -*-
"""
서사 넥서스 v1.2 — 주봉 정렬 + 파생 지표 (멀티 종목) → nexus.db
=============================================================
집계 규칙 (§2.2): 플로우=합계 / 스톡=last / Trends=원천 주간값 / forward-fill 금지
파생 (§2.4): ret_w, short_ratio, short_bal_wow, turnover_w, news_momentum,
             trend_z(52주 롤링, 부족 시 26주), retail_ratio
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = ["086520", "001570", "000250"]
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
DB = ROOT / "data" / "nexus.db"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def week_id(d: pd.Timestamp) -> str:
    iso = pd.Timestamp(d).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def load_raw(rel: str) -> pd.DataFrame | None:
    p = RAW / rel
    if not p.exists():
        print(f"  [SKIP] raw 없음: {rel}")
        return None
    df = pd.read_csv(p, encoding="utf-8-sig")
    if df.empty:
        print(f"  [SKIP] raw 비어있음: {rel}")
        return None
    df.rename(columns={df.columns[0]: "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df["week_id"] = df["date"].map(week_id)
    return df


def rolling_z(s: pd.Series, win: int = 52, min_win: int = 26) -> pd.Series:
    m = s.rolling(win, min_periods=min_win).mean()
    sd = s.rolling(win, min_periods=min_win).std()
    return (s - m) / sd


def t_plus_2(d: pd.Timestamp) -> pd.Timestamp:
    """공매도 잔고 공표 지연 근사: T+2 영업일 (§2.3 — 실데이터로 확인 필요)."""
    return d + pd.tseries.offsets.BusinessDay(2)


def build_weeks(dailies: list) -> pd.DataFrame:
    alld = pd.concat([d[["date", "week_id"]] for d in dailies]).drop_duplicates("date")
    g = alld.groupby("week_id")["date"]
    return pd.DataFrame({
        "week_id": g.min().index,
        "week_start": g.min().dt.date.astype(str),
        "week_end": g.max().dt.date.astype(str),
        "trading_days": g.count().values,
    })


def build_price(ticker, daily, mktcap, fdr_adj) -> pd.DataFrame:
    col = {"시가": "open", "고가": "high", "저가": "low",
           "종가": "close", "거래량": "volume", "거래대금": "value_traded"}
    d = daily.rename(columns=col)
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    if "value_traded" in d.columns:
        agg["value_traded"] = "sum"
    w = d.sort_values("date").groupby("week_id").agg(agg).reset_index()

    if fdr_adj is not None and "Close" in fdr_adj.columns:
        adj = fdr_adj.sort_values("date").groupby("week_id")["Close"].last()
        w = w.merge(adj.rename("close_adj"), on="week_id", how="left")
    else:
        w["close_adj"] = np.nan

    if mktcap is not None:
        mc = mktcap.rename(columns={"시가총액": "mktcap", "거래대금": "vt2"})
        wm = mc.sort_values("date").groupby("week_id").agg(mktcap=("mktcap", "last"))
        w = w.merge(wm, on="week_id", how="left")
        if "value_traded" not in w.columns or w["value_traded"].isna().all():
            vt = mc.sort_values("date").groupby("week_id")["vt2"].sum()
            w["value_traded"] = w["week_id"].map(vt)

    w = w.sort_values("week_id").reset_index(drop=True)
    w["ret_w"] = w["close"] / w["close"].shift(1) - 1
    for _c in ("value_traded", "mktcap"):
        if _c not in w.columns:
            w[_c] = np.nan
    w["turnover_w"] = w["value_traded"] / w["mktcap"]
    w["ticker"] = ticker
    return w


def build_flow(ticker, tv, sv, sb, price_w) -> pd.DataFrame:
    out = price_w[["week_id"]].copy()

    if tv is not None:
        col = {"개인": "net_retail", "외국인합계": "net_foreign", "외국인": "net_foreign",
               "기관합계": "net_inst", "기타법인": "net_etc"}
        t = tv.rename(columns=col)
        keep = [c for c in ["net_retail", "net_foreign", "net_inst", "net_etc"]
                if c in t.columns]
        wt = t.groupby("week_id")[keep].sum().reset_index()
        denom = wt[keep].abs().sum(axis=1)
        wt["retail_ratio"] = wt.get("net_retail", np.nan) / denom.replace(0, np.nan)
        out = out.merge(wt, on="week_id", how="left")

    if sv is not None:
        scol = next((c for c in sv.columns if "공매도" in c), None)
        tcol = next((c for c in sv.columns if c in ("거래량", "총거래량") or "매수" in c), None)
        if scol:
            ws = sv.groupby("week_id").agg(
                short_vol=(scol, "sum"),
                total_vol=(tcol, "sum") if tcol else (scol, "sum"),
            ).reset_index()
            ws["short_ratio"] = ws["short_vol"] / ws["total_vol"].replace(0, np.nan)
            out = out.merge(ws[["week_id", "short_vol", "short_ratio"]],
                            on="week_id", how="left")

    if sb is not None:
        bcol = next((c for c in sb.columns if "잔고" in c and "금액" not in c), None)
        if bcol:
            b = sb.sort_values("date").groupby("week_id").agg(
                short_bal=(bcol, "last"), last_date=("date", "max")).reset_index()
            b["short_bal_wow"] = b["short_bal"] / b["short_bal"].shift(1) - 1
            b["known_at"] = b["last_date"].map(t_plus_2).dt.date.astype(str)
            out = out.merge(b[["week_id", "short_bal", "short_bal_wow", "known_at"]],
                            on="week_id", how="left")

    out["ticker"] = ticker
    return out


def build_credit() -> pd.DataFrame | None:
    p = MANUAL / "credit_daily.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p, encoding="utf-8-sig")
    if d.empty:
        return None
    d["date"] = pd.to_datetime(d["date"])
    d["week_id"] = d["date"].map(week_id)
    w = d.sort_values("date").groupby("week_id").agg(
        credit_bal=("credit_bal", "last"), last_date=("date", "max")).reset_index()
    w["credit_wow"] = w["credit_bal"] / w["credit_bal"].shift(1) - 1
    w["known_at"] = w["last_date"].dt.date.astype(str)
    return w[["week_id", "credit_bal", "credit_wow", "known_at"]]


def build_narrative() -> pd.DataFrame:
    rows = []
    gdir = RAW / "gtrends"
    if gdir.exists():
        for p in sorted(gdir.glob("trends_*.csv")):
            kw = p.stem.replace("trends_", "")
            df = pd.read_csv(p, encoding="utf-8-sig")
            if df.empty:
                continue
            df.rename(columns={df.columns[0]: "date"}, inplace=True)
            df["date"] = pd.to_datetime(df["date"])
            vcol = next((c for c in df.columns if c not in ("date", "isPartial")), None)
            df["week_id"] = (df["date"] + pd.Timedelta(days=1)).map(week_id)
            g = df.groupby("week_id")[vcol].mean().reset_index()
            g["z52"] = rolling_z(g[vcol])
            for _, r in g.iterrows():
                rows.append((r["week_id"], kw, "gtrends", r[vcol], None,
                             r["z52"], None, None))

    p = MANUAL / "bigkinds_weekly.csv"
    if p.exists():
        df = pd.read_csv(p, encoding="utf-8-sig")
        if not df.empty:
            if "week_id" not in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df["week_id"] = df["date"].map(week_id)
            tier = "channel_tier" if "channel_tier" in df.columns else None
            gcols = ["week_id", "keyword"] + ([tier] if tier else [])
            g = df.groupby(gcols)["count"].sum().reset_index()
            for kw, sub in g.groupby("keyword"):
                tot = sub.groupby("week_id")["count"].sum().sort_index()
                mom = tot / tot.rolling(4, min_periods=2).mean().shift(1) - 1
                z = rolling_z(tot)
                for _, r in sub.iterrows():
                    wid = r["week_id"]
                    rows.append((wid, kw, "bigkinds", r["count"],
                                 float(mom.get(wid, np.nan)), float(z.get(wid, np.nan)),
                                 r[tier] if tier else None, None))

    return pd.DataFrame(rows, columns=[
        "week_id", "keyword", "source", "raw_count", "momentum", "z52",
        "channel_tier", "slogan_hhi"])


def build_labels(weeks: pd.DataFrame) -> pd.DataFrame | None:
    p = MANUAL / "cycle_labels.csv"
    if not p.exists():
        return None
    src = pd.read_csv(p, encoding="utf-8-sig")
    if src.empty:
        return None
    wids = sorted(weeks["week_id"].tolist())
    rows = []
    for _, r in src.iterrows():
        for w in wids:
            if str(r["week_from"]) <= w <= str(r["week_to"]):
                rows.append({
                    "week_id": w, "ticker": str(r["ticker"]).zfill(6),
                    "stage": r["stage"],
                    "substage": r.get("substage") if pd.notna(r.get("substage")) else None,
                    "confidence": r.get("confidence"),
                    "evidence": r.get("evidence"),
                    "labeled_at": r.get("labeled_at"),
                    "revised_from": None,
                    "network_status": r.get("network_status") if "network_status" in src.columns else "unknown",
                    "cohort": r.get("cohort") if "cohort" in src.columns else None,
                })
    return pd.DataFrame(rows) if rows else None


def build_events() -> pd.DataFrame | None:
    p = MANUAL / "events.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, encoding="utf-8-sig", dtype={"ticker": str})
    if df.empty:
        return None
    df["ticker"] = df["ticker"].str.zfill(6)
    return df


def main():
    print(f"build_weekly v1.2 — raw: {RAW}")
    dailies, prices, flows = [], [], []
    for t in TICKERS:
        daily = load_raw(f"pykrx/ohlcv_{t}.csv")
        if daily is None:
            print(f"  [WARN] {t}: OHLCV 없음 — 종목 건너뜀")
            continue
        dailies.append(daily)
        mktcap = load_raw(f"pykrx/mktcap_{t}.csv")
        fdr_adj = load_raw(f"fdr/ohlcv_adj_{t}.csv")
        tv = load_raw(f"pykrx/trading_value_{t}.csv")
        sv = load_raw(f"pykrx/short_volume_{t}.csv")
        sb = load_raw(f"pykrx/short_balance_{t}.csv")
        pw = build_price(t, daily, mktcap, fdr_adj)
        prices.append(pw)
        flows.append(build_flow(t, tv, sv, sb, pw))

    if not dailies:
        print("가용 OHLCV가 없어 중단합니다.")
        return

    weeks = build_weeks(dailies)
    price_w = pd.concat(prices, ignore_index=True)
    flow_w = pd.concat(flows, ignore_index=True)
    credit_w = build_credit()
    narr = build_narrative()
    ev = build_events()
    lbl = build_labels(weeks)

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    weeks.to_sql("weeks", con, if_exists="replace", index=False)

    cols_p = ["week_id", "ticker", "open", "high", "low", "close", "close_adj",
              "volume", "value_traded", "mktcap", "ret_w", "turnover_w"]
    price_w.reindex(columns=cols_p).to_sql("weekly_price", con,
                                           if_exists="replace", index=False)
    cols_f = ["week_id", "ticker", "net_retail", "net_foreign", "net_inst",
              "net_etc", "retail_ratio", "short_vol", "short_ratio",
              "short_bal", "short_bal_wow", "known_at"]
    flow_w.reindex(columns=cols_f).to_sql("weekly_flow", con,
                                          if_exists="replace", index=False)
    if credit_w is not None:
        credit_w.to_sql("weekly_credit", con, if_exists="replace", index=False)
    if not narr.empty:
        narr.to_sql("weekly_narrative", con, if_exists="replace", index=False)
    if ev is not None:
        ev.to_sql("events", con, if_exists="replace", index=False)
    if lbl is not None:
        lbl.to_sql("cycle_labels", con, if_exists="replace", index=False)
    con.commit()

    print(f"\n[DONE] {DB}")
    for t in ["weeks", "weekly_price", "weekly_flow", "weekly_credit",
              "weekly_narrative", "events", "cycle_labels"]:
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {n} rows")
        except sqlite3.OperationalError:
            print(f"  {t}: (없음)")
    con.close()


if __name__ == "__main__":
    main()
