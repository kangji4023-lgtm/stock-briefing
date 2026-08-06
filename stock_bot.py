import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf
import warnings

# 불필요한 경고 차단
warnings.filterwarnings("ignore")

# ==========================================
# 1. 환경 설정 및 종목 관리
# ==========================================
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "3c9a29d58ca8030c4e9a119d4249e305")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "SEB-3upB-Ex2WOcM-6gizd-SzSnmFZ_PAAAAAgoNFZsAAAGf0Jl5c6j01SImjvGc")

TARGET_KR_STOCKS = {
    "삼성전자": "005930", 
    "SK하이닉스": "000660", 
    "삼성전기": "009155", 
    "SK스퀘어": "402340", 
    "현대차": "005380"
}

US_TICKERS = ["TSLA", "GOOGL", "NVDA", "AMD", "INTC"]

# ==========================================
# 2. 카카오톡 안전 전송 모듈 (파싱 오류 원인 제거)
# ==========================================
def refresh_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN,
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"토큰 갱신 예외: {e}")
    return None

def send_kakao_message(text):
    if not text:
        return
    access_token = refresh_access_token()
    if not access_token:
        print("카카오 액세스 토큰 획득 실패")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }

    # 템플릿 객체 대신 안정적인 기본 텍스트 구조 적용
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://www.google.com",
            "mobile_web_url": "https://www.google.com"
        }
    }

    data = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        res_json = response.json()
        if response.status_code == 200 and res_json.get("result_code") == 0:
            print("카카오톡 메시지 전송 성공!")
        else:
            print(f"전송 실패 응답: {response.text}")
    except Exception as e:
        print(f"메시지 전송 예외: {e}")
    time.sleep(1.0)

# ==========================================
# 3. 기술적 지표 계산 모듈
# ==========================================
def calculate_technical_indicators(df):
    if df is None or len(df) < 20:
        return df
    df = df.copy()
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()
    df["MA120"] = df["Close"].rolling(window=120).mean() if len(df) >= 120 else df["MA60"]

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

# ==========================================
# 4. 국내·미국 주식 분석 모듈
# ==========================================
def get_korea_stock_data():
    results = []
    for name, code in TARGET_KR_STOCKS.items():
        try:
            df = yf.download(f"{code}.KS", period="6mo", interval="1d", progress=False)
            if df is not None and len(df) > 10:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = calculate_technical_indicators(df)
                cur = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                chg = ((cur - prev) / prev) * 100
                rsi = float(df["RSI"].iloc[-1]) if "RSI" in df.columns else 50.0
                
                results.append({
                    "name": name,
                    "price": int(cur),
                    "change": chg,
                    "rsi": rsi,
                    "ma20": int(df["MA20"].iloc[-1]) if "MA20" in df.columns else int(cur),
                })
        except Exception as e:
            print(f"국내 종목 수집 오류 ({name}): {e}")
        time.sleep(0.2)
    return results

def get_usa_stock_data():
    results = []
    try:
        data_us = yf.download(US_TICKERS, period="6mo", interval="1d", group_by="ticker", progress=False)
        for t in US_TICKERS:
            try:
                df = data_us[t].dropna()
                if len(df) > 10:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df = calculate_technical_indicators(df)
                    cur = float(df["Close"].iloc[-1])
                    prev = float(df["Close"].iloc[-2])
                    chg = ((cur - prev) / prev) * 100
                    rsi = float(df["RSI"].iloc[-1]) if "RSI" in df.columns else 50.0
                    
                    results.append({
                        "name": t,
                        "close": cur,
                        "change": chg,
                        "rsi": rsi,
                    })
            except Exception as e:
                print(f"미국 종목 수집 오류 ({t}): {e}")
    except Exception as e:
        print(f"미국 전체 데이터 수집 오류: {e}")
    return results

# ==========================================
# 5. 메인 실행 함수
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    print(f"[{today_str}] 브리핑 생성 시작...")

    kr_results = get_korea_stock_data()
    us_results = get_usa_stock_data()

    # 파트 1
    part1 = f"[{today_str} 주식 브리핑 1부]\n\n"
.strip() + "\n"
    part1 += "1. 시장 요약\n- 반도체 대형주 중심 순환매 장세\n\n"
    part1 += "2. 국내 주요종목\n"
    for s in kr_results:
        part1 += f"* {s['name']}: {s['change']:+.2f}% ({s['price']:,}원)\n"

    send_kakao_message(part1)

    # 파트 2
    part2 = f"[{today_str} 주식 브리핑 2부]\n\n"
    part2 += "3. 미국 주요종목\n"
    for s in us_results:
        part2 += f"* {s['name']}: {s['change']:+.2f}% (${s['close']:,.2f})\n"

    send_kakao_message(part2)

    # 파트 3
    part3 = f"[{today_str} 주식 브리핑 3부]\n\n"
    part3 += "4. 추천 종목 및 전략\n"
    part3 += "* 추천: SK하이닉스 / 테슬라\n"
    part3 += "* 전략: 20일선 눌림목 분할 매수 대응"

    send_kakao_message(part3)
    print("모든 브리핑 전송 완료!")

if __name__ == "__main__":
    run_job()
