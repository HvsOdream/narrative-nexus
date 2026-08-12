# -*- coding: utf-8 -*-
"""
서사 넥서스 v1.2 — 관찰 대시보드 생성기 (멀티 종목)
nexus.db → docs/<ticker>.html × N + docs/index.html (대표: 에코프로)
"""
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "nexus.db"
DOCS = ROOT / "docs"

TICKERS = {
    "086520": {"name": "에코프로", "keyword": "에코프로", "note": "2023 풀 사이클 (최대 진폭 표본)"},
    "001570": {"name": "금양", "keyword": "금양", "note": "2023 동반 급등 → 몰락 (인물 서사·무한 유예형)"},
    "000250": {"name": "삼천당제약", "keyword": "삼천당제약", "note": "장주기 실타래 → 2026 재점화-붕괴 (§8.4)"},
}


def rows(con, sql, params=()):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, params)]


def build_payload(ticker):
    info = TICKERS[ticker]
    if not DB.exists():
        return {"generated_at": date.today().isoformat(), "ticker": ticker,
                "name": info["name"], "main_keyword": info["keyword"],
                "weeks": [], "price": [], "flow": [], "narrative": [],
                "labels": [], "events": []}
    con = sqlite3.connect(DB)
    weeks = rows(con, "SELECT * FROM weeks ORDER BY week_id")
    price = rows(con, "SELECT * FROM weekly_price WHERE ticker=? ORDER BY week_id", (ticker,))
    flow = rows(con, "SELECT * FROM weekly_flow WHERE ticker=? ORDER BY week_id", (ticker,))
    try:
        narr = rows(con, "SELECT * FROM weekly_narrative ORDER BY week_id")
    except sqlite3.OperationalError:
        narr = []
    try:
        labels = rows(con, """SELECT * FROM cycle_labels WHERE ticker=?
                              ORDER BY week_id, labeled_at""", (ticker,))
    except sqlite3.OperationalError:
        labels = []
    try:
        events = rows(con, "SELECT * FROM events WHERE ticker=? ORDER BY date", (ticker,))
    except sqlite3.OperationalError:
        events = []
    con.close()

    latest = {}
    for l in labels:
        latest[l["week_id"]] = l
    return {"generated_at": date.today().isoformat(), "ticker": ticker,
            "name": info["name"], "main_keyword": info["keyword"],
            "weeks": weeks, "price": price, "flow": flow, "narrative": narr,
            "labels": list(latest.values()), "events": events}


HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>서사 넥서스 — __NAME__</title>
<style>
  .viz-root {
    color-scheme: light;
    --surface-1:#fcfcfb; --page:#f9f9f7;
    --ink-1:#0b0b0b; --ink-2:#52514e; --ink-mut:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
    --up:#e34948; --down:#2a78d6;
    --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4;
    --band-dormant:rgba(137,135,129,.10); --band-genesis:rgba(27,175,122,.12);
    --band-diffusion:rgba(237,161,0,.13); --band-saturation:rgba(227,73,72,.13);
    --band-decay:rgba(74,58,167,.10);
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --surface-1:#1a1a19; --page:#0d0d0d;
      --ink-1:#ffffff; --ink-2:#c3c2b7; --ink-mut:#898781;
      --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
      --up:#e66767; --down:#3987e5;
      --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181;
      --band-dormant:rgba(137,135,129,.14); --band-genesis:rgba(25,158,112,.16);
      --band-diffusion:rgba(201,133,0,.16); --band-saturation:rgba(230,103,103,.16);
      --band-decay:rgba(144,133,233,.14);
    }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--page); color:var(--ink-1);
         font-family:system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif; }
  .wrap { max-width:1080px; margin:0 auto; padding:20px 16px 48px; }
  h1 { font-size:20px; margin:8px 0 2px; }
  .nav { display:flex; gap:8px; margin:0 0 10px; flex-wrap:wrap; }
  .nav a { font-size:13px; text-decoration:none; color:var(--ink-2);
           border:1px solid var(--border); border-radius:16px; padding:4px 12px;
           background:var(--surface-1); }
  .nav a.on { color:var(--ink-1); font-weight:600; border-color:var(--ink-mut); }
  .sub { color:var(--ink-2); font-size:13px; margin-bottom:14px; }
  .sub b { color:var(--ink-1); }
  .caveat { font-size:12px; color:var(--ink-mut); margin:4px 0 16px; }
  .panel { background:var(--surface-1); border:1px solid var(--border);
           border-radius:10px; padding:12px 14px 6px; margin-bottom:14px; }
  .ptitle { font-size:13px; font-weight:600; margin:0 0 2px; }
  .legend { display:flex; flex-wrap:wrap; gap:12px; font-size:12px;
            color:var(--ink-2); margin:2px 0 4px; }
  .legend .sw { display:inline-block; width:10px; height:10px; border-radius:3px;
                margin-right:5px; vertical-align:-1px; }
  svg { display:block; width:100%; height:auto; }
  svg text { font-family:inherit; }
  .tip { position:fixed; pointer-events:none; background:var(--surface-1);
         border:1px solid var(--border); border-radius:8px; padding:8px 10px;
         font-size:12px; color:var(--ink-1); box-shadow:0 4px 14px rgba(0,0,0,.15);
         max-width:320px; display:none; z-index:10; line-height:1.5; }
  .tip .wk { font-weight:600; }
  .tip .ev { color:var(--ink-2); margin-top:4px; }
  table.dt { border-collapse:collapse; font-size:12px; width:100%; }
  table.dt th, table.dt td { border-bottom:1px solid var(--grid); padding:4px 8px;
    text-align:right; font-variant-numeric:tabular-nums; }
  table.dt th:first-child, table.dt td:first-child { text-align:left; }
  details summary { cursor:pointer; font-size:13px; color:var(--ink-2); margin:8px 0; }
  .empty { color:var(--ink-mut); font-size:13px; padding:20px 0 26px; }
</style>
</head>
<body class="viz-root">
<div class="wrap">
  <h1>서사 넥서스 — __NAME__(__TICKER__)</h1>
  <div class="nav">__NAV__</div>
  <div class="sub">주봉 관찰기 · __NOTE__ · 생성일 <b id="gen"></b> · 자동 갱신(GitHub Actions, 토요일)</div>
  <div class="caveat">⚠ 예측기가 아닌 관찰기입니다. 모든 지표는 "서사가 어디쯤 와 있는가"의 기술이며 매매 신호가 아닙니다. 단계 밴드는 해석(띻벨)이고 지표는 사실입니다 — 둘은 분리 저장됩니다.</div>
  <div id="app"></div>
  <details><summary>데이터 표 보기 (접근성·검증용)</summary><div id="tablewrap"></div></details>
</div>
<div class="tip" id="tip"></div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
document.getElementById('gen').textContent = D.generated_at;
const app = document.getElementById('app');
const tip = document.getElementById('tip');

const weeks = D.price.map(p => p.week_id);
const byWeek = arr => { const m={}; arr.forEach(r=>m[r.week_id]=r); return m; };
const flowM = byWeek(D.flow);
const weekMeta = byWeek(D.weeks);
const labelM = byWeek(D.labels);
const trend = {}; const news = {};
D.narrative.forEach(r => {
  if (r.source==='gtrends' && r.keyword===D.main_keyword) trend[r.week_id]=r;
  if (r.source==='bigkinds' && r.keyword===D.main_keyword) news[r.week_id]=r;
});
const evByWeek = {};
D.events.forEach(e => {
  const d = new Date(e.date); if (isNaN(d)) return;
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dow = (t.getUTCDay()+6)%7; t.setUTCDate(t.getUTCDate()-dow+3);
  const y = t.getUTCFullYear();
  const jan4 = new Date(Date.UTC(y,0,4));
  const wno = 1+Math.round(((t-jan4)/86400000 - 3 + ((jan4.getUTCDay()+6)%7))/7);
  const wid = y+'-W'+String(wno).padStart(2,'0');
  (evByWeek[wid] = evByWeek[wid]||[]).push(e);
});

if (!weeks.length) {
  app.innerHTML = '<div class="panel"><div class="empty">이 종목의 데이터가 아직 없습니다. 다음 배치(Actions)에서 수집됩니다.</div></div>';
} else { render(); }

function render() {
const W = 1040, PADL = 56, PADR = 14, plotW = W-PADL-PADR;
const n = weeks.length, step = plotW/n, bw = Math.max(2, Math.min(9, step*0.6));
const X = i => PADL + step*(i+0.5);
const fmtN = v => v==null||isNaN(v) ? '—' :
  Math.abs(v)>=1e12 ? (v/1e12).toFixed(1)+'조' :
  Math.abs(v)>=1e8 ? (v/1e8).toFixed(0)+'억' :
  Math.abs(v)>=1e4 ? Math.round(v).toLocaleString() : (+v.toFixed(3)).toString();
const pct = v => v==null||isNaN(v) ? '—' : (v*100).toFixed(1)+'%';

const STAGE = {dormant:['휴면','--band-dormant'], genesis:['생성','--band-genesis'],
  diffusion:['전파','--band-diffusion'], saturation:['과포화','--band-saturation'],
  decay:['소멸','--band-decay']};

function scale(vals, H, pad=0.06, zero=false) {
  const v = vals.filter(x=>x!=null && !isNaN(x));
  if (!v.length) return { y: () => H/2, lo:0, hi:0, empty:true };
  let lo = Math.min(...v), hi = Math.max(...v);
  if (zero) { lo = Math.min(lo,0); hi = Math.max(hi,0); }
  if (lo===hi) { lo-=1; hi+=1; }
  const r = hi-lo; lo-=r*pad; hi+=r*pad;
  return { y: x => H - (x-lo)/(hi-lo)*H, lo, hi };
}
function ticks(lo, hi, k=4) {
  if (lo===hi) return [];
  const span=(hi-lo)/k, mag=Math.pow(10,Math.floor(Math.log10(span)));
  const stp=[1,2,2.5,5,10].map(m=>m*mag).find(s=>span/s<=1)||mag*10;
  const out=[]; for(let t=Math.ceil(lo/stp)*stp; t<=hi; t+=stp) out.push(t);
  return out;
}
function bands(H) {
  let out='', i=0;
  while (i<n) {
    const l = labelM[weeks[i]];
    if (!l || !STAGE[l.stage]) { i++; continue; }
    let j=i; while (j+1<n && labelM[weeks[j+1]] && labelM[weeks[j+1]].stage===l.stage) j++;
    const x0=PADL+step*i, x1=PADL+step*(j+1);
    out += `<rect x="${x0}" y="0" width="${x1-x0}" height="${H}" fill="var(${STAGE[l.stage][1]})"/>`;
    i=j+1;
  }
  return out;
}
function xAxis(H) {
  let out=''; const every=Math.ceil(n/14);
  for (let i=0;i<n;i+=every) {
    out += `<text x="${X(i)}" y="${H+16}" font-size="10" fill="var(--ink-mut)" text-anchor="middle">${weeks[i].replace('20','')}</text>`;
  }
  return out;
}
function gridY(sc,H,fmt) {
  return ticks(sc.lo,sc.hi).map(t=>
    `<line x1="${PADL}" x2="${W-PADR}" y1="${sc.y(t)}" y2="${sc.y(t)}" stroke="var(--grid)" stroke-width="1"/>`+
    `<text x="${PADL-6}" y="${sc.y(t)+3.5}" font-size="10" fill="var(--ink-mut)" text-anchor="end">${fmt(t)}</text>`).join('');
}
function line(vals, sc, color, dash) {
  let d='', pen=false;
  vals.forEach((v,i)=>{ if(v==null||isNaN(v)){pen=false;return;}
    d += (pen?'L':'M')+X(i).toFixed(1)+','+sc.y(v).toFixed(1); pen=true; });
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="2" ${dash?`stroke-dasharray="${dash}"`:''} stroke-linejoin="round"/>`;
}

function panel(title, legendItems, H, inner, hoverHTML) {
  const div=document.createElement('div'); div.className='panel';
  div.innerHTML = `<p class="ptitle">${title}</p>`+
    (legendItems.length?`<div class="legend">${legendItems.map(([c,t])=>
      `<span><span class="sw" style="background:${c}"></span>${t}</span>`).join('')}</div>`:'')+
    `<svg viewBox="0 0 ${W} ${H+24}" role="img" aria-label="${title}">${inner}
     <line class="xh" x1="0" x2="0" y1="0" y2="${H}" stroke="var(--axis)" stroke-width="1" style="display:none"/>
     <rect class="hit" x="${PADL}" y="0" width="${plotW}" height="${H}" fill="transparent"/></svg>`;
  const svg=div.querySelector('svg'), xh=div.querySelector('.xh');
  svg.addEventListener('mousemove', e=>{
    const r=svg.getBoundingClientRect();
    const mx=(e.clientX-r.left)*(W/r.width);
    const i=Math.max(0,Math.min(n-1,Math.floor((mx-PADL)/step)));
    xh.setAttribute('x1',X(i)); xh.setAttribute('x2',X(i)); xh.style.display='';
    tip.style.display='block'; tip.innerHTML=hoverHTML(i);
    const tw=tip.offsetWidth;
    tip.style.left=Math.min(window.innerWidth-tw-12, e.clientX+14)+'px';
    tip.style.top=(e.clientY+14)+'px';
  });
  svg.addEventListener('mouseleave', ()=>{ xh.style.display='none'; tip.style.display='none'; });
  app.appendChild(div);
}

function emptyPanel(title, msg) {
  const div=document.createElement('div'); div.className='panel';
  div.innerHTML=`<p class="ptitle">${title}</p><div class="empty">${msg}</div>`;
  app.appendChild(div);
}

function hoverCommon(i) {
  const w=weeks[i], p=D.price[i], f=flowM[w]||{}, l=labelM[w], t=trend[w], nn=news[w];
  const wm=weekMeta[w]||{};
  let h=`<div class="wk">${w} <span style="color:var(--ink-mut)">(${wm.week_start||''}~${wm.week_end||''})</span></div>`;
  if (l&&STAGE[l.stage]) h+=`단계: <b>${STAGE[l.stage][0]}${l.substage?' · '+l.substage:''}</b> (${l.confidence||'?'})<br>`;
  h+=`종가 ${fmtN(p.close)}원 · 주간 ${pct(p.ret_w)}<br>`;
  h+=`회전율 ${pct(p.turnover_w)} · 개인비중 ${pct(f.retail_ratio)}<br>`;
  h+=`공매도비중 ${pct(f.short_ratio)} · 잔고증감 ${pct(f.short_bal_wow)}`;
  if (t) h+=`<br>트렌드 ${fmtN(t.raw_count)} (z ${t.z52==null?'—':(+t.z52).toFixed(1)})`;
  if (nn) h+=` · 뉴스 ${fmtN(nn.raw_count)}건`;
  (evByWeek[w]||[]).forEach(e=>{ h+=`<div class="ev">◆ ${e.date} ${e.title}</div>`; });
  return h;
}

/* 패널 1: 주봉 캔들 */
{
  const H=300;
  const sc=scale(D.price.flatMap(p=>[p.high,p.low]),H);
  let inner=bands(H)+gridY(sc,H,fmtN);
  D.price.forEach((p,i)=>{
    if(p.close==null) return;
    const up=p.close>=p.open, c=up?'var(--up)':'var(--down)';
    inner+=`<line x1="${X(i)}" x2="${X(i)}" y1="${sc.y(p.high)}" y2="${sc.y(p.low)}" stroke="${c}" stroke-width="1"/>`;
    const y0=sc.y(Math.max(p.open,p.close)), y1=sc.y(Math.min(p.open,p.close));
    inner+=`<rect x="${X(i)-bw/2}" y="${y0}" width="${bw}" height="${Math.max(1.5,y1-y0)}" fill="${c}" rx="1.5" stroke="var(--surface-1)" stroke-width="1"/>`;
  });
  weeks.forEach((w,i)=>{ if(evByWeek[w])
    inner+=`<path d="M ${X(i)} 6 l 5 5 -5 5 -5 -5 z" fill="var(--s2)" stroke="var(--surface-1)" stroke-width="1"/>`; });
  inner+=`<line x1="${PADL}" x2="${W-PADR}" y1="${H}" y2="${H}" stroke="var(--axis)"/>`+xAxis(H);
  const stagesUsed=[...new Set(D.labels.map(l=>l.stage).filter(s=>STAGE[s]))];
  panel('주봉 (원) · 배경 밴드 = 사이클 단계 라벨 · ◆ = 이벤트',
    [['var(--up)','상승 주'],['var(--down)','하락 주'],
     ...stagesUsed.map(s=>[`var(${STAGE[s][1]})`, STAGE[s][0]+' 밴드']),
     ['var(--s2)','이벤트']],
    H, inner, hoverCommon);
}

/* 패널 2: 수급 */
{
  const H=150;
  const rr=weeks.map(w=>(flowM[w]||{}).retail_ratio);
  const tv=weeks.map((w,i)=>D.price[i].turnover_w);
  const vals=[...rr,...tv].filter(x=>x!=null&&!isNaN(x));
  if (vals.length) {
    const sc=scale(vals,H,0.08,true);
    let inner=bands(H)+gridY(sc,H,v=>pct(v));
    inner+=`<line x1="${PADL}" x2="${W-PADR}" y1="${sc.y(0)}" y2="${sc.y(0)}" stroke="var(--axis)" stroke-width="1"/>`;
    inner+=line(tv,sc,'var(--s3)')+line(rr,sc,'var(--s1)');
    inner+=xAxis(H);
    panel('서사층-B (시장 안): 개인 순매수 비중 · 주간 회전율(손바뀜)',
      [['var(--s1)','개인 순매수 비중'],['var(--s3)','회전율 (거래대금/시총)']],
      H, inner, hoverCommon);
  } else emptyPanel('서사층-B (시장 안)','수급 데이터가 아직 없습니다 (KRX 세부 API 재시도 대기 §8.6).');
}

/* 패널 3: 공매도 */
{
  const H=150;
  const sr=weeks.map(w=>(flowM[w]||{}).short_ratio);
  const sb=weeks.map(w=>(flowM[w]||{}).short_bal_wow);
  const vals=[...sr,...sb].filter(x=>x!=null&&!isNaN(x));
  if (vals.length) {
    const sc=scale(vals,H,0.08,true);
    let inner=bands(H)+gridY(sc,H,v=>pct(v));
    inner+=`<line x1="${PADL}" x2="${W-PADR}" y1="${sc.y(0)}" y2="${sc.y(0)}" stroke="var(--axis)"/>`;
    inner+=line(sb,sc,'var(--s5)','4 3')+line(sr,sc,'var(--s2)');
    inner+=xAxis(H);
    panel('반대 서사: 공매도 비중 · 잔고 주간 증감 (점선, 공표지연 known_at 반영 전 원값)',
      [['var(--s2)','공매도/총거래량'],['var(--s5)','잔고 증감률 (점선)']],
      H, inner, hoverCommon);
  } else emptyPanel('반대 서사 (공매도)','공매도 데이터가 아직 없습니다 (KRX 세부 API 재시도 대기 §8.6).');
}

/* 패널 4: 서사층-A */
{
  const H=150;
  const tz=weeks.map(w=>trend[w]?trend[w].z52:null);
  const nm=weeks.map(w=>news[w]?news[w].momentum:null);
  const vals=[...tz,...nm].filter(x=>x!=null&&!isNaN(x));
  if (vals.length) {
    const sc=scale(vals,H,0.08,true);
    let inner=bands(H)+gridY(sc,H,v=>(+v).toFixed(1));
    inner+=`<line x1="${PADL}" x2="${W-PADR}" y1="${sc.y(0)}" y2="${sc.y(0)}" stroke="var(--axis)"/>`;
    inner+=line(tz,sc,'var(--s4)')+line(nm,sc,'var(--s1)','4 3');
    inner+=xAxis(H);
    panel(`서사층-A (시장 밖): 구글 트렌드 z-score('${D.main_keyword}') · 뉴스 모멘텀 (점선, 빅카인즈 수동)`,
      [['var(--s4)','트렌드 z (52주 롤링)'],['var(--s1)','뉴스 모멘텀 (점선)']],
      H, inner, hoverCommon);
  } else emptyPanel('서사층-A (시장 밖)','트렌드/뉴스 데이터가 아직 없습니다.');
}

/* 데이터 표 */
{
  let t='<table class="dt"><tr><th>주</th><th>종가</th><th>주간수익률</th><th>회전율</th><th>개인비중</th><th>공매도비중</th><th>잔고증감</th><th>트렌드z</th><th>단계</th></tr>';
  weeks.forEach((w,i)=>{
    const p=D.price[i], f=flowM[w]||{}, l=labelM[w];
    t+=`<tr><td>${w}</td><td>${fmtN(p.close)}</td><td>${pct(p.ret_w)}</td><td>${pct(p.turnover_w)}</td><td>${pct(f.retail_ratio)}</td><td>${pct(f.short_ratio)}</td><td>${pct(f.short_bal_wow)}</td><td>${trend[w]&&trend[w].z52!=null?(+trend[w].z52).toFixed(1):'—'}</td><td>${l&&STAGE[l.stage]?STAGE[l.stage][0]+(l.substage?' ('+l.substage+')':''):''}</td></tr>`;
  });
  document.getElementById('tablewrap').innerHTML=t+'</table>';
}
}
</script>
</body>
</html>
"""


HYP_PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>서사 넥서스 — 가설 보드</title>
<style>
  body { margin:0; background:#f9f9f7; color:#0b0b0b;
         font-family:system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif; }
  @media (prefers-color-scheme: dark) { body { background:#0d0d0d; color:#fff; }
    .card, .nav a { background:#1a1a19 !important; border-color:rgba(255,255,255,.1) !important; }
    .muted { color:#898781 !important; } .crit { background:#0d0d0d !important; } }
  .wrap { max-width:860px; margin:0 auto; padding:20px 16px 48px; }
  h1 { font-size:20px; margin:8px 0 2px; }
  .nav { display:flex; gap:8px; margin:0 0 10px; flex-wrap:wrap; }
  .nav a { font-size:13px; text-decoration:none; color:inherit; border:1px solid rgba(11,11,11,.1);
           border-radius:16px; padding:4px 12px; background:#fcfcfb; }
  .tally { font-size:14px; margin:6px 0 16px; }
  .caveat { font-size:12px; color:#898781; margin:4px 0 16px; }
  .card { background:#fcfcfb; border:1px solid rgba(11,11,11,.1); border-radius:10px;
          padding:14px 16px; margin-bottom:14px; }
  .stamp { float:right; font-size:14px; font-weight:700; }
  .title { font-size:15px; font-weight:600; margin:0 0 6px; }
  .stmt { font-size:13px; line-height:1.6; margin:0 0 8px; }
  .crit { font-size:12px; background:#f9f9f7; border-radius:8px; padding:8px 10px; margin:0 0 8px;
          font-variant-numeric:tabular-nums; }
  .muted { font-size:12px; color:#52514e; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🔮 가설 보드 — 봉인과 판정</h1>
  <div class="nav"><a href="index.html">에코프로</a><a href="001570.html">금양</a><a href="000250.html">삼천당제약</a></div>
  <div class="tally"><b>__TALLY__</b> · 갱신 __GEN__ (매주 토요일 자동 판정)</div>
  <div class="caveat">⚠ 사전등록 검증 장치입니다(§8.5). 가설은 봉인 후 수정 불가 — 수정하려면 새 가설로 등록합니다. 판정은 배치가 자동으로 하며, 매매 신호가 아닙니다.</div>
  __CARDS__
</div>
</body>
</html>
"""


def build_hyp_page():
    import csv as _csv
    p = ROOT / "data" / "manual" / "hypotheses.csv"
    if not p.exists():
        return
    with open(p, encoding="utf-8-sig") as f:
        hyps = list(_csv.DictReader(f))
    if not hyps:
        return
    con = sqlite3.connect(DB) if DB.exists() else None
    cards, won, lost, live = [], 0, 0, 0
    for h in hyps:
        status, detail = "open", "판정 대기 (데이터 없음)"
        if con is not None and h["check_type"] == "ret_above":
            thr = float(h["threshold"])
            rows_ = con.execute(
                "SELECT week_id, ret_w FROM weekly_price WHERE ticker=? AND week_id>? AND week_id<=? ORDER BY week_id",
                (h["ticker"], h["start_week"], h["deadline_week"])).fetchall()
            latest = con.execute("SELECT MAX(week_id) FROM weekly_price WHERE ticker=?",
                                 (h["ticker"],)).fetchone()[0]
            vals = [r for _, r in rows_ if r is not None]
            hits = [(w, r) for w, r in rows_ if r is not None and r >= thr]
            best = max(vals) if vals else None
            if hits:
                status = "confirmed"
                detail = f"판정: {hits[0][0]} 주간 +{hits[0][1]*100:.1f}% ≥ +{thr*100:.0f}% 충족"
            elif latest is not None and latest >= h["deadline_week"]:
                status = "refuted"
                b = f" — 판정창 최고 +{best*100:.1f}%" if best is not None else ""
                detail = f"기한({h['deadline_week']}) 내 미출현{b}"
            else:
                b = f"지금까지 최고 주간 {best*100:+.1f}%" if best is not None else "판정창 진입 전"
                detail = f"진행 중 · 관측 {len(rows_)}주 경과 · {b} · 기준 +{float(h['threshold'])*100:.0f}%"
        if status == "confirmed":
            won += 1
            stamp = '<span class="stamp" style="color:#0ca30c">✅ 적중</span>'
        elif status == "refuted":
            lost += 1
            stamp = '<span class="stamp" style="color:#d03b3b">❌ 기각</span>'
        else:
            live += 1
            stamp = '<span class="stamp" style="color:#898781">⏳ 진행 중</span>'
        cards.append(
            f'<div class="card">{stamp}<p class="title">{h["id"]} · {h["title"]}</p>'
            f'<p class="stmt">{h["statement"]}</p>'
            f'<div class="crit">{detail}</div>'
            f'<div class="muted">봉인 {h["sealed_at"]} · 판정창 {h["start_week"]} 초과 ~ {h["deadline_week"]} · {h.get("note","")}</div></div>')
    if con is not None:
        con.close()
    tally = f"통산 {won}승 {lost}패 · 진행 {live}건"
    html = (HYP_PAGE.replace("__CARDS__", "".join(cards))
            .replace("__TALLY__", tally).replace("__GEN__", date.today().isoformat()))
    (DOCS / "hypotheses.html").write_text(html, encoding="utf-8")
    print(f"[DONE] hypotheses.html ({tally})")


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    for ticker, info in TICKERS.items():
        payload = build_payload(ticker)
        nav_parts = []
        for t, v in TICKERS.items():
            cls = ' class="on"' if t == ticker else ''
            nav_parts.append(f'<a href="{t}.html"{cls}>{v["name"]}</a>')
        nav_parts.append('<a href="hypotheses.html">🔮 가설 보드</a>')
        nav = "".join(nav_parts)
        html = (HTML
                .replace("__NAME__", info["name"])
                .replace("__TICKER__", ticker)
                .replace("__NOTE__", info["note"])
                .replace("__NAV__", nav)
                .replace("__PAYLOAD__",
                         json.dumps(payload, ensure_ascii=False, default=str)))
        out = DOCS / f"{ticker}.html"
        out.write_text(html, encoding="utf-8")
        print(f"[DONE] {out} ({len(html)//1024} KB, {len(payload['price'])} weeks)")
    shutil.copyfile(DOCS / "086520.html", DOCS / "index.html")
    print("[DONE] index.html = 086520 (에코프로)")
    build_hyp_page()


if __name__ == "__main__":
    main()
