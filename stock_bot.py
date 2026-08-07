from datetime import datetime
import pytz
import requests
import yfinance as yf
from pykrx import stock
import pandas as pd
import numpy as np

# ==========================================
# 사용자 설정 정보
# ==========================================
CLIENT_ID = "2e2432752d3bcaaf637aa44cfb75a555"
REFRESH_TOKEN = "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc" 

def get_kakao_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH_TOKEN
    }
    try:
        response = requests.post(url, data=data, timeout=5)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except:
        return None

def send_kakao_message(text):
    access_token = get_kakao_access_token()
    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    data = {
        "template_object": str(template_object).replace("'", '"')
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=5)
        return response.status_code == 200
    except:
        return False

def get_safe_krx_date():
    try:
        now = datetime.now(pytz.timezone('Asia/Seoul'))
        today_str = now.strftime("%Y%m%d")
        return stock.get_nearest_business_day_in_a_week(today_str)
    except:
        return datetime.now().strftime("%Y%m%d")

def generate_detailed_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    collected_time = now.strftime("%Y-%m-%d %H:%M:%S")
    krx_date = get_safe_krx_date()
    
    # 1. 국내 주도주 데이터 안전 수집
    krx_details = ""
    try:
        df_trade = stock.get_market_trading_value_by_ticker(krx_date, krx_date, "ALL")
        if df_trade is not None and not df_trade.empty:
            top_tickers = df_trade.sort_values(by="거래대금", ascending=False).head(3).index.tolist()
            for i, ticker in enumerate(top_tickers, 1):
                name = stock.get_market_ticker_name(ticker)
                krx_details += f"\n{i}. {name} (거래대금 상위 수급 유입)"
        else:
            krx_details = "\n- 휴장일 또는 데이터 집계 준비 중"
    except:
        krx_details = "\n- 국내 수급 데이터 집계 중"

    # 2. 미국 및 글로벌 매크로
    us_str = ""
    for name, sym in {"NASDAQ": "^IXIC", "S&P500": "^GSPC"}.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if not hist.empty:
                cur = hist['Close'].iloc[-1]
                us_str += f"- {name}: {cur:,.2f}\n"
            else:
                us_str += f"- {name}: 데이터 없음\n"
        except:
            us_str += f"- {name}: 조회 불가\n"

    # ==========================================
    # [1편]: 국내 시장 브리핑
    # ==========================================
    part1 = f"""📊 {today} 실시간 주식 브리핑 [1편]
⏰ 수집 시각: {collected_time}

🇰🇷 국내 주요 시장 및 주도주
{krx_details}
"""

    # ==========================================
    # [2편]: 글로벌 및 트럼프 이슈 브리핑
    # ==========================================
    part2 = f"""🌍 {today} 글로벌 이슈 브리핑 [2편]
⏰ 수집 시각: {collected_time}

🇺🇸 미국 주요 지수
{us_str.strip()}

🏛️ 트럼프 및 전 세계 주요 이슈
- 트럼프 관세 정책 및 글로벌 무역 압박 리스크 지속 주시
- 미국 연준 정책 방향성과 지정학적 변동성 복합 작용 중
"""

    return part1, part2

def job():
    msg1, msg2 = generate_detailed_briefings()
    send_kakao_message(msg1)
    send_kakao_message(msg2)

if __name__ == "__main__":
    job()
