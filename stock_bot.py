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
    data = {"grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": REFRESH_TOKEN}
    try:
        response = requests.post(url, data=data, timeout=5)
        return response.json().get("access_token") if response.status_code == 200 else None
    except: return None

def send_kakao_message(text):
    access_token = get_kakao_access_token()
    if not access_token: return False
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"template_object": str({"object_type": "text", "text": text}).replace("'", '"')}
    try:
        return requests.post(url, headers=headers, data=data, timeout=5).status_code == 200
    except: return False

def get_safe_krx_data():
    """KRX 데이터 오류를 방지하기 위해 오늘이 휴장일이면 가장 최근 영업일을 반환"""
    try:
        now = datetime.now(pytz.timezone('Asia/Seoul'))
        today_str = now.strftime("%Y%m%d")
        return stock.get_nearest_business_day_in_a_week(today_str)
    except:
        return datetime.now().strftime("%Y%m%d")

def calculate_technical_indicators(ticker):
    """지표 계산 중 데이터 오류 시 안전하게 None 반환"""
    try:
        krx_date = get_safe_krx_data()
        df = stock.get_market_ohlcv_by_date("20260101", krx_date, ticker)
        if df.empty or len(df) < 30: return None
        
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        return {
            "change_rate": ((curr['종가'] - prev['종가']) / prev['종가']) * 100,
            "ma_alignment": "정배열" if curr['MA5'] > curr['MA20'] else "역배열"
        }
    except: return None

def generate_detailed_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    krx_date = get_safe_krx_data()
    
    # 1. 국내 주도주 (오류 방지)
    krx_details = ""
    try:
        df_trade = stock.get_market_trading_value_by_ticker(krx_date, krx_date, "ALL")
        top_tickers = df_trade.sort_values(by="거래대금", ascending=False).head(3).index.tolist()
        for ticker in top_tickers:
            name = stock.get_market_ticker_name(ticker)
            ind = calculate_technical_indicators(ticker)
            krx_details += f"- {name} ({ind['change_rate']:.2f}%)\n" if ind else f"- {name} (집계중)\n"
    except: krx_details = "국내 수급 데이터 집계 중입니다."

    # 2. 글로벌 지수
    us_str = ""
    for name, sym in {"NASDAQ": "^IXIC", "S&P500": "^GSPC"}.items():
        try:
            t = yf.Ticker(sym).history(period="2d")
            us_str += f"- {name}: {t['Close'].iloc[-1]:,.2f}\n"
        except: us_str += f"- {name}: 조회 불가\n"

    msg1 = f"📊 {today} 국내시장 브리핑\n\n[거래대금 상위주]\n{krx_details}"
    msg2 = f"🌍 {today} 글로벌 및 매크로 브리핑\n\n[미국지수]\n{us_str}\n\n[주요 이슈]\n- 트럼프 관세 정책 등 대외 리스크 지속 주시."
    
    return msg1, msg2

def job():
    msg1, msg2 = generate_detailed_briefings()
    send_kakao_message(msg1)
    send_kakao_message(msg2)

if __name__ == "__main__":
    job()
