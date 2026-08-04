import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from pykrx import stock

# ==========================================
# 1. 환경 변수 및 카카오 토큰 설정
# ==========================================
# GitHub Secrets에 설정되어야 하는 변수들입니다.
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")

def refresh_access_token(rest_api_key, refresh_token):
    """카카오 리프레시 토큰을 이용해 액세스 토큰을 재발급받는 함수"""
    if not rest_api_key or not refresh_token:
        print("오류: KAKAO_REST_API_KEY 또는 KAKAO_REFRESH_TOKEN 환경 변수가 설정되지 않았습니다.")
        return None
        
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"토큰 갱신 실패: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"토큰 갱신 중 예외 발생: {e}")
        return None

def send_kakao_message(text):
    """카카오톡 '나에게 보내기' API를 통해 메시지 전송 (글자 수 제한 대응 분할 전송)"""
    if not text or len(text.strip()) == 0:
        print("전송할 메시지 내용이 없습니다.")
        return

    access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
    if not access_token:
        print("유효한 액세스 토큰이 없어 메시지를 전송할 수 없습니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}

    # 카카오톡 메시지 글자 수 제한(약 1000자)을 고려하여 분할
    max_len = 900
    texts = [text[i : i + max_len] for i in range(0, len(text), max_len)]

    success_count = 0
    for chunk in texts:
        payload = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://finance.naver.com",
                "mobile_web_url": "https://finance.naver.com",
            },
        }
        try:
            response = requests.post(
                url, headers=headers, data={"template_object": json.dumps(payload)}
            )
            if response.status_code == 200:
                success_count += 1
            else:
                print(f"전송 실패 코드: {response.status_code}, 내용: {response.text}")
        except Exception as e:
            print(f"메시지 전송 중 예외 발생: {e}")
        time.sleep(0.5)
    
    if success_count > 0:
        print(f"카카오톡 브리핑 전송 완료! (총 {success_count}개 섹션)")

# ==========================================
# 2. 기술적 지표 계산 함수
# ==========================================
def calculate_technical_indicators(df):
    """이동평균선, 골든크로스, MACD, RSI, OBV 계산"""
    if df is None or len(df) < 120:
        return df
        
    df = df.copy()
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()
    df["MA120"] = df["Close"].rolling(window=120).mean()

    def get_ma_alignment(row):
        if pd.isna(row["MA5"]) or pd.isna(row["MA20"]) or pd.isna(row["MA60"]):
            return "데이터 부족"
        if row["MA5"] > row["MA20"] > row["MA60"]:
            return "정배열(강세)"
        elif row["MA5"] < row["MA20"] < row["MA60"]:
            return "역배열(약세)"
        else:
            return "혼조세"

    df["MA_Align"] = df.apply(get_ma_alignment, axis=1)

    df["Golden_Cross"] = (df["MA5"] > df["MA20"]) & (
        df["MA5"].shift(1) <= df["MA20"].shift(1)
    )

    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["OBV"] = (
        np.where(
            df["Close"] > df["Close"].shift(1),
            df["Volume"],
            np.where(
                df["Close"] < df["Close"].shift(1), -df["Volume"], 0
            ),
        )
    ).cumsum()

    df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)
    return df

# ==========================================
# 3. 주식 데이터 수집 및 분석 엔진
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # 현재 시간에 따라 타이밍 이름 동적 지정
    hour = now.hour
    if hour < 9:
        timing_name = "오전 7시 모닝 브리핑"
    elif hour < 13:
        timing_name = "오전 11시 장중 브리핑"
    elif hour < 18:
        timing_name = "오후 4시 마감 브리핑"
    else:
        timing_name = "오후 7시 야간 브리핑"

    print(f"[{today_str} {timing_name}] 브리핑 데이터 수집 및 생성 시작...")

    # 기준 날짜 설정 (kr_date가 정의되지 않아 발생하는 오류 방지)
    try:
        kr_date = stock.get_nearest_business_day_in_a_week(now.strftime("%Y%m%d"))
    except Exception as e:
        print(f"기준 날짜 계산 오류: {e}")
        kr_date = now.strftime("%Y%m%d")

    # 1) 국내 TOP10 주도주 분석
    top_kr_data = []
    try:
        tickers = stock.get_market_ticker_list(kr_date, market="KOSPI")
        for ticker in tickers[:20]: # 상위 20개 종목 탐색
            try:
                name = stock.get_market_ticker_name(ticker)
                start_date = (now - datetime.timedelta(days=180)).strftime("%Y%m%d")
                df = stock.get_market_ohlcv_by_date(start_date, kr_date, ticker)
                
                if df is not None and len(df) > 60:
                    df = calculate_technical_indicators(df)
                    if len(df) < 2: continue
                    
                    change_pct = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
                    
                    # 수급 데이터 (에러 방지를 위해 try-except)
                    foreign_net, inst_net = 0, 0
                    try:
                        net_buyer = stock.get_market_net_purchases_of_equities_by_ticker(kr_date, kr_date, ticker)
                        if ticker in net_buyer.index:
                            foreign_net = net_buyer.loc[ticker]["외국인합계"]
                            inst_net = net_buyer.loc[ticker]["기관합계금액"]
                    except:
                        pass

                    top_kr_data.append({
                        "name": name,
                        "change": change_pct,
                        "close": df["Close"].iloc[-1],
                        "high": df["High"].iloc[-1],
                        "low": df["Low"].iloc[-1],
                        "gc": df["Golden_Cross"].iloc[-1],
                        "macd": df["MACD"].iloc[-1],
                        "rsi": df["RSI"].iloc[-1],
                        "vol_inc": df["Vol_Increase"].iloc[-1],
                        "ma_align": df["MA_Align"].iloc[-1],
                        "foreign": foreign_net,
                        "inst": inst_net,
                    })
            except Exception as e:
                print(f"{ticker} 데이터 처리 중 오류: {e}")
                continue
        
        top_kr_data = sorted(top_kr_data, key=lambda x: x["change"], reverse=True)[:10]
    except Exception as e:
        print(f"국내 데이터 전체 수집 오류: {e}")

    # 2) 미국 TOP10 주도주 분석
    us_tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX", "INTC"]
    top_us_data = []
    try:
        data_us = yf.download(us_tickers, period="6mo", interval="1d", group_by="ticker", progress=False)
        for t in us_tickers:
            try:
                df_u = data_us[t].dropna()
                if len(df_u) > 30:
                    df_u = calculate_technical_indicators(df_u)
                    chg = ((df_u["Close"].iloc[-1] - df_u["Close"].iloc[-2]) / df_u["Close"].iloc[-2]) * 100
                    top_us_data.append({
                        "name": t,
                        "change": chg,
                        "close": df_u["Close"].iloc[-1],
                        "gc": df_u["Golden_Cross"].iloc[-1],
                        "rsi": df_u["RSI"].iloc[-1],
                        "ma_align": df_u["MA_Align"].iloc[-1],
                    })
            except:
                continue
        top_us_data = sorted(top_us_data, key=lambda x: x["change"], reverse=True)[:10]
    except Exception as e:
        print(f"미국 데이터 수집 오류: {e}")

    # 3) 보유 종목 분석
    my_stocks = {"삼성전자": "005930", "SK하이닉스": "000660", "삼성전기": "009150", "SK스퀘어": "402340", "현대차": "005380"}
    my_results = []
    for name, code in my_stocks.items():
        try:
            start_date = (now - datetime.timedelta(days=180)).strftime("%Y%m%d")
            df_m = stock.get_market_ohlcv_by_date(start_date, kr_date, code)
            if df_m is not None and len(df_m) > 20:
                df_m = calculate_technical_indicators(df_m)
                cur = df_m["Close"].iloc[-1]
                support = df_m["Low"].rolling(20).min().iloc[-1]
                resistance = df_m["High"].rolling(20).max().iloc[-1]

                my_results.append({
                    "name": name,
                    "price": cur,
                    "target": int(resistance * 1.05),
                    "stop": int(support * 0.95),
                    "rsi": df_m["RSI"].iloc[-1],
                    "macd": df_m["MACD"].iloc[-1],
                    "align": df_m["MA_Align"].iloc[-1],
                    "opinion": (
                        "강세 흐름 유지, 홀딩 권장" if df_m["MA_Align"].iloc[-1] == "정배열(강세)" 
                        else "추세 확인 필요, 비중 조절 권장"
                    ),
                })
        except Exception as e:
            print(f"보유종목 {name} 분석 오류: {e}")

    # ==========================================
    # 4. 메시지 포맷팅 및 전송
    # ==========================================
    msg = f"📈 {today_str} 주식 브리핑 ({timing_name})\n"
    msg += "⚡ 시장 분석 리포트\n\n"

    if top_kr_data:
        msg += "🇰🇷 국내 주식 TOP5\n"
        for i, item in enumerate(top_kr_data[:5], 1):
            msg += (
                f"{i}. {item['name']} (+{item['change']:.2f}%)\n"
                f"   - 현재가: {item['close']:,}원\n"
                f"   - 수급: 외인 {item['foreign']:,} / 기관 {item['inst']:,}\n"
                f"   - RSI: {item['rsi']:.1f} | 상태: {item['ma_align']}\n\n"
            )
    else:
        msg += "🇰🇷 국내 데이터 수집 실패 또는 장 폐쇄\n\n"

    if top_us_data:
        msg += "🇺🇸 미국 주식 TOP5\n"
        for i, item in enumerate(top_us_data[:5], 1):
            msg += f"{i}. {item['name']} (+{item['change']:.2f}%) | RSI: {item['rsi']:.1f}\n"
        msg += "\n"

    if my_results:
        msg += "📊 보유종목 분석\n"
        for s in my_results:
            msg += (
                f"• {s['name']}: {s['price']:,}원\n"
                f"  - 목표: {s['target']:,} / 손절: {s['stop']:,}\n"
                f"  - 의견: {s['opinion']}\n"
            )
        msg += "\n"

    msg += "※ 투자 판단은 본인 책임입니다."

    # 메시지 전송 실행
    send_kakao_message(msg)

if __name__ == "__main__":
    run_job()
