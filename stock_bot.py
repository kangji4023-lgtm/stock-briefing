# ============================================================
# stock_bot.py
# 국내·미국 주식시장 데이터 기반 자동 브리핑
#
# 주요 기능
# 1. KRX 최신 거래일 자동 탐색
# 2. 2026 KRX 로그인 정책 대응
# 3. KOSPI / KOSDAQ
# 4. 국내 거래대금 TOP10
# 5. 국내 주도 섹터 분석
# 6. 국내 관심종목 기술적 분석
# 7. 국내 뉴스 조회
# 8. 미국 지수 및 핵심종목
# 9. 미국 뉴스 조회
# 10. 원달러 / 미국채10년 / VIX / WTI
# 11. 카카오톡 나에게 보내기
# 12. 긴 메시지 자동 분할
#
# GitHub Secrets
# KRX_ID
# KRX_PW
# KAKAO_REST_API_KEY
# KAKAO_REFRESH_TOKEN
# KAKAO_CLIENT_SECRET (사용 중이면 입력)
# ============================================================

import os
import json
import time
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta

import pytz
import requests
import pandas as pd
import numpy as np
import yfinance as yf

from pykrx import stock


# ============================================================
# 0. 기본 설정
# ============================================================

KST = pytz.timezone("Asia/Seoul")

# KRX
KRX_ID = os.environ.get("KRX_ID", "dmswl904").strip()
KRX_PW = os.environ.get("KRX_PW", "kang402300*").strip()

# KAKAO
KAKAO_REST_API_KEY = os.environ.get(
    "KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()

KAKAO_REFRESH_TOKEN = os.environ.get(
    "KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc"
).strip()

KAKAO_CLIENT_SECRET = os.environ.get(
    "KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()

if not KAKAO_REST_API_KEY:
    raise RuntimeError("KAKAO_REST_API_KEY가 없습니다.")

if not KAKAO_REFRESH_TOKEN:
    raise RuntimeError("KAKAO_REFRESH_TOKEN이 없습니다.")

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

# ============================================================
from pathlib import Path
import zipfile, shutil, textwrap, os

root=Path("/mnt/data/stock_market_briefing_v2")
if root.exists(): shutil.rmtree(root)
(root/".github/workflows").mkdir(parents=True)

bot=r'''import os, json, time, re, math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests, pandas as pd, numpy as np
import yfinance as yf
from pykrx import stock as krx

KST=ZoneInfo("Asia/Seoul")
LIMIT=190
KR={
"005930":"삼성전자","000660":"SK하이닉스","009150":"삼성전기","402340":"SK스퀘어",
"005380":"현대차","006400":"삼성SDI","042700":"한미반도체","010120":"LS ELECTRIC",
"012450":"한화에어로스페이스","034020":"두산에너빌리티"}
US={"NVDA":"NVIDIA","MSFT":"Microsoft","AAPL":"Apple","AMZN":"Amazon",
"GOOGL":"Alphabet","META":"Meta","TSLA":"Tesla","AVGO":"Broadcom"}

def now(): return datetime.now(KST)
def pct(x): return "N/A" if pd.isna(x) else f"{x:+.2f}%"
def won(x):
    if pd.isna(x): return "N/A"
    return f"{x:,.0f}"
def rsi(c,n=14):
    d=c.diff(); up=d.clip(lower=0).rolling(n).mean()
    dn=(-d.clip(upper=0)).rolling(n).mean()
    rs=up/dn.replace(0,np.nan)
    return 100-100/(1+rs)
def indicators(df):
    if df.empty: return {}
    c=df["Close"].dropna()
    if len(c)<65:return {}
    ma5=c.rolling(5).mean(); ma20=c.rolling(20).mean(); ma60=c.rolling(60).mean()
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    m=e12-e26; s=m.ewm(span=9,adjust=False).mean()
    v=df["Volume"].reindex(c.index); av=v.rolling(20).mean()
    return {"price":float(c.iloc[-1]),"chg":float((c.iloc[-1]/c.iloc[-2]-1)*100),
            "rsi":float(rsi(c).iloc[-1]),"macd":float(m.iloc[-1]),"signal":float(s.iloc[-1]),
            "ma5":float(ma5.iloc[-1]),"ma20":float(ma20.iloc[-1]),"ma60":float(ma60.iloc[-1]),
            "golden":bool(ma20.iloc[-2]<=ma60.iloc[-2] and ma20.iloc[-1]>ma60.iloc[-1]),
            "volratio":float(v.iloc[-1]/av.iloc[-1]) if av.iloc[-1] else np.nan,
            "dist20":float((c.iloc[-1]/ma20.iloc[-1]-1)*100)}

def yfdata(ticker):
    try:
        x=yf.download(ticker,period="1y",interval="1d",auto_adjust=False,progress=False,threads=False)
        if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
        return x.dropna(how="all")
    except:return pd.DataFrame()

def krdata(code):
    try:
        e=now().strftime("%Y%m%d"); s=(now()-timedelta(days=370)).strftime("%Y%m%d")
        x=krx.get_market_ohlcv_by_date(s,e,code)
        if x.empty:return x
        x.columns=["Open","High","Low","Close","Volume","Change"]
        return x
    except:return pd.DataFrame()

def index(t):
    x=yfdata(t)
    if x.empty:return None
    c=x["Close"].dropna()
    return (float(c.iloc[-1]),float((c.iloc[-1]/c.iloc[-2]-1)*100)) if len(c)>1 else None

def news():
    qs=["한국 증시 삼성전자 SK하이닉스 외국인 기관","미국 증시 NVIDIA Fed 금리","반도체 AI 전력 방산 증시"]
    out=[]
    import xml.etree.ElementTree as ET
    for q in qs:
        try:
            r=requests.get("https://news.google.com/rss/search",
                params={"q":q,"hl":"ko","gl":"KR","ceid":"KR:ko"},timeout=10)
            rt=ET.fromstring(r.text)
            for it in rt.findall(".//item")[:5]:
                title=it.findtext("title","").strip()
                if title: out.append(title)
        except: pass
    # duplicate 제거
    return list(dict.fromkeys(out))[:8]

def reason(x):
    if x["chg"]>=3 and x["volratio"]>=1.5:return "강한 상승+거래량 동반"
    if x["chg"]>=2:return "상승 모멘텀"
    if x["chg"]<=-3 and x["volratio"]>=1.5:return "급락+거래량 증가"
    if x["chg"]<=-2:return "하락 압력"
    if x["rsi"]>=70:return "RSI 과열권"
    if x["rsi"]<=30:return "RSI 과매도권"
    return "뚜렷한 기술 신호 제한"

def action(x):
    # 투자 권유가 아니라 기술조건 표시
    flags=[]
    if x["golden"]:flags.append("20/60GC")
    if x["macd"]>x["signal"]:flags.append("MACD+")
    if x["rsi"]<30:flags.append("RSI과매도")
    if x["rsi"]>70:flags.append("RSI과열")
    if x["volratio"]>=2:flags.append("거래량2배")
    if not flags: flags=["신호중립"]
    return "/".join(flags)

def flows():
    try:
        d=now().strftime("%Y%m%d")
        # 투자자별 전체시장 순매수: 실제 데이터가 없으면 표시하지 않음
        return krx.get_market_net_purchases_of_equities_by_ticker(d,d,"외국인")
    except:return None

def movers():
    try:
        d=now().strftime("%Y%m%d"); x=krx.get_market_ohlcv_by_ticker(d)
        x=x[(x["거래량"]>0)].copy()
        return x.nlargest(3,"등락률"),x.nsmallest(3,"등락률")
    except:return None,None

def token():
    data={"grant_type":"refresh_token","client_id":os.environ["KAKAO_REST_API_KEY"],
          "refresh_token":os.environ["KAKAO_REFRESH_TOKEN"]}
    if os.getenv("KAKAO_CLIENT_SECRET"):data["client_secret"]=os.getenv("KAKAO_CLIENT_SECRET")
    r=requests.post("https://kauth.kakao.com/oauth/token",data=data,timeout=15);r.raise_for_status()
    return r.json()["access_token"]

def send(s):
    p={"template_object":{"object_type":"text","text":s[:LIMIT],
       "link":{"web_url":"https://finance.yahoo.com/","mobile_web_url":"https://finance.yahoo.com/"}}}
    r=requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization":"Bearer "+token(),"Content-Type":"application/x-www-form-urlencoded;charset=utf-8"},
        data={"template_object":json.dumps(p,ensure_ascii=False)},timeout=15)
    r.raise_for_status()

def split(s):
    out=[];cur=""
    for line in s.splitlines():
        if len(cur)+len(line)+1<=LIMIT:cur+=("\n" if cur else "")+line
        else:
            if cur:out.append(cur)
            while len(line)>LIMIT:out.append(line[:LIMIT]);line=line[LIMIT:]
            cur=line
    if cur:out.append(cur)
    return out

def build():
    t=now()
    ki=index("^KS11"); kq=index("^KQ11"); sp=index("^GSPC"); nq=index("^IXIC");vx=index("^VIX");tn=index("^TNX")
    lines=[f"📊 STOCK BRIEF | {t:%m/%d %H:%M} KST"]
    for label,v in [("KOSPI",ki),("KOSDAQ",kq),("S&P500",sp),("NASDAQ",nq),("VIX",vx),("美10Y",tn)]:
        if v:lines.append(f"{label} {v[0]:,.2f} ({v[1]:+.2f}%)")
    lines.append("— 국내 시장 —")
    for code,name in KR.items():
        x=indicators(krdata(code))
        if x:
            lines.append(f"{name} {won(x['price'])} {pct(x['chg'])} RSI{x['rsi']:.0f} 이격{x['dist20']:+.1f}% 거래{x['volratio']:.1f}x {action(x)}")
    lines.append("— 미국 시장 —")
    for tic,name in US.items():
        x=indicators(yfdata(tic))
        if x:
            lines.append(f"{name} ${x['price']:,.2f} {pct(x['chg'])} RSI{x['rsi']:.0f} 이격{x['dist20']:+.1f}% 거래{x['volratio']:.1f}x {action(x)}")
    up,dn=movers()
    if up is not None:
        lines.append("— 국내 급등/급락 —")
        for i,r in up.iterrows():lines.append(f"▲ {i} {r['등락률']:+.2f}% 거래량{int(r['거래량']):,}")
        for i,r in dn.iterrows():lines.append(f"▼ {i} {r['등락률']:+.2f}% 거래량{int(r['거래량']):,}")
    lines.append("— 움직임 해석 —")
    for code,name in list(KR.items())[:6]:
        x=indicators(krdata(code))
        if x:lines.append(f"{name}: {reason(x)}")
    ns=news()
    if ns:
        lines.append("— 주요 뉴스 제목 —")
        lines += ["• "+n[:75] for n in ns[:4]]
    lines.append("※ 뉴스는 원문 확인 전 제목 기준. 데이터 지연·휴장·API 오류 가능. 매매판단용 보조자료.")
    return "\n".join(lines)

if __name__=="__main__":
    for m in split(build()):
        print(m);send(m);time.sleep(1)
'''

req="""requests>=2.32
pandas>=2.2
numpy>=2.0
yfinance>=0.2.60
pykrx>=1.0.48
"""

wf=r'''name: Stock Market Briefing
on:
  workflow_dispatch:
  schedule:
    - cron: "0 22 * * 0-4"
    - cron: "40 23 * * 0-4"
    - cron: "40 6 * * 1-5"
    - cron: "30 13 * * 1-5"
    - cron: "10 20 * * 1-5"
jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - name: Send Kakao briefing
        env:
          KAKAO_REST_API_KEY: ${{ secrets.KAKAO_REST_API_KEY }}
          KAKAO_REFRESH_TOKEN: ${{ secrets.KAKAO_REFRESH_TOKEN }}
          KAKAO_CLIENT_SECRET: ${{ secrets.KAKAO_CLIENT_SECRET }}
        run: python stock_bot.py
'''

readme=r'''# STOCK MARKET BRIEFING v2

## 포함
- KOSPI/KOSDAQ, S&P500/NASDAQ, VIX, 미국10년물
- 국내/미국 관심종목
- 등락률, RSI, MACD, 20/60일 골든크로스
- 20일 이격도
- 거래량/20일 평균 거래량
- 국내 급등/급락 상위
- 외국인 수급 모듈
- 뉴스 RSS 제목
- 조건 기반 움직임 해석
- 카카오톡 자동 분할 발송
- GitHub Actions 자동 실행

## GitHub Secrets
KAKAO_REST_API_KEY
KAKAO_REFRESH_TOKEN
KAKAO_CLIENT_SECRET (사용 앱에서 필요할 때만)

## 중요
공개 데이터/API의 지연·오류·휴장일 때문에 오차 0%는 보장할 수 없습니다.
또한 뉴스 제목만으로 주가의 원인을 확정하지 않습니다. 실제 원인 확인은 원문/공시/거래소 데이터를 함께 확인해야 합니다.

미국장 자동 시각은 서머타임 전환 때문에 현재 cron은 미국 서머타임 기준입니다.
연중 정확한 장 시작/마감 자동화는 거래소 캘린더 기반 스케줄러를 추가하는 것이 권장됩니다.
'''

for fn,txt in [("stock_bot.py",bot),("requirements.txt",req),(".github/workflows/stock_briefing.yml",wf),("README.md",readme)]:
    (root/fn).write_text(txt,encoding="utf-8")
zipfile_path=Path("/mnt/data/stock_market_briefing_v2.zip")
with zipfile.ZipFile(zipfile_path,"w",zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob("*"):
        if p.is_file():z.write(p,p.relative_to(root))
print(zipfile_path)
