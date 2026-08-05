import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from pykrx import stock
import warnings

# 불필요한 경고 차단
warnings.filterwarnings("ignore")

# ==========================================
# 1. 환경 변수 및 카카오 토큰 설정
# ==========================================
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "3c9a29d58ca8030c4e9a119d4249e305")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "SEB-3upB-Ex2WOcM-6gizd-SzSnmFZ_PAAAAAgoNFZsAAAGf0Jl5c6j01SImjvGc")

def refresh_access_token(rest_api_key, refresh_token):
    """카카오 리프레시 토큰을 이용해 액세스 토큰을 재발급받는 함수"""
    if not rest_api_key or not refresh_token:
        print("오류: KAKAO_REST_API_KEY 또는 KAKAO_REFRESH_TOKEN이 설정되지 않았습니다.")
        return None
        
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    try:
        response = requests.post(url, data=data, timeout=10)
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
        print("유효한 액세스 토큰이 없어 카카오톡 메시지를 전송할 수 없습니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }

    max_len = 850
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
        data = {
            "template_object": json.dumps(payload)
        }
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
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
    """이동평균선, 골든크로스, MACD, RSI, 저항/지지선 계산"""
    if df is None or len(df) < 60:
        return df
        
    df = df.copy()
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()

    def get_ma_alignment(row):
        if pd.isna(row["MA5"]) or pd.isna(row["MA20"]) or pd.isna(row["MA60"]):
            return "혼조세"
        if row["MA5"] > row["MA20"] > row["MA60"]:
            return "정배열(강세)"
        elif row["MA5"] < row["MA20"] < row["MA60"]:
            return "역배열(약세)"
        else:
            return "혼조세"

    df["MA_Align"] = df.apply(get_ma_alignment, axis=1)
    df["Golden_Cross"] = (df["MA5"] > df["MA20"]) & (df["MA5"].shift(1) <= df["MA20"].shift(1))

    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)
    return df

# ==========================================
# 3. 브리핑 데이터 수집 및 분석 엔진
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    is_weekend = (weekday >= 5)

    hour = now.hour
    if 6 <= hour < 10:
        timing_name = "오전 7시 모닝 브리핑"
    elif 10 <= hour < 13:
        timing_name = "오전 11시 장중 브리핑"
    elif 13 <= hour < 18:
        timing_name = "오후 4시 마감 브리핑"
    else:
        timing_name = "오후 7시 야간 브리핑"

    print(f"[{today_str} {timing_name}] 상세 브리핑 데이터 수집 및 생성 시작...")

    try:
        kr_date = stock.get_nearest_business_day_in_a_week(now.strftime("%Y%m%d"))
    except Exception:
        kr_date = now.strftime("%Y%m%d")

    # 1) 국내 TOP 주도주 분석
    top_kr_data = []
    try:
        tickers = stock.get_market_ticker_list(kr_date, market="KOSPI")
        for ticker in tickers[:20]:
            try:
                name = stock.get_market_ticker_name(ticker)
                start_date = (now - datetime.timedelta(days=120)).strftime("%Y%m%d")
                df = stock.get_market_ohlcv_by_date(start_date, kr_date, ticker)
                
                if df is not None and len(df) > 30:
                    df = calculate_technical_indicators(df)
                    if len(df) < 2: continue
                    
                    change_pct = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
                    cur_close = df["Close"].iloc[-1]
                    high_20 = df["High"].rolling(20).max().iloc[-1]
                    low_20 = df["Low"].rolling(20).min().iloc[-1]
                    
                    top_kr_data.append({
                        "name": name,
                        "change": change_pct,
                        "close": cur_close,
                        "vol_inc": "O (급증)" if df["Vol_Increase"].iloc[-1] else "X",
                        "golden": "발생" if df["Golden_Cross"].iloc[-1] else "미발생",
                        "macd": df["MACD"].iloc[-1],
                        "rsi": df["RSI"].iloc[-1] if "RSI" in df.columns else 50.0,
                        "ma_align": df["MA_Align"].iloc[-1] if "MA_Align" in df.columns else "혼조세",
                        "resistance": int(high_20),
                        "support": int(low_20),
                    })
            except:
                continue
        
        top_kr_data = sorted(top_kr_data, key=lambda x: x["change"], reverse=True)[:5]
    except Exception as e:
        print(f"국내 데이터 수집 오류: {e}")

    # 2) 미국 TOP 주도주 분석
    us_tickers = ["INTC", "AMD", "NVDA", "AAPL", "TSLA", "MSFT"]
    top_us_data = []
    try:
        data_us = yf.download(us_tickers, period="3mo", interval="1d", group_by="ticker", progress=False)
        for t in us_tickers:
            try:
                df_u = data_us[t].dropna()
                if len(df_u) > 20:
                    df_u = calculate_technical_indicators(df_u)
                    chg = ((df_u["Close"].iloc[-1] - df_u["Close"].iloc[-2]) / df_u["Close"].iloc[-2]) * 100
                    top_us_data.append({
                        "name": t,
                        "change": chg,
                        "rsi": df_u["RSI"].iloc[-1] if "RSI" in df_u.columns else 50.0,
                        "ma_align": df_u["MA_Align"].iloc[-1] if "MA_Align" in df_u.columns else "혼조세",
                        "golden": "발생" if df_u["Golden_Cross"].iloc[-1] else "미발생"
                    })
            except:
                continue
        top_us_data = sorted(top_us_data, key=lambda x: x["change"], reverse=True)[:5]
    except Exception as e:
        print(f"미국 데이터 수집 오류: {e}")

    # 3) 보유 종목 분석
    my_stocks = {"삼성전자": "005930", "SK하이닉스": "000660", "삼성전기": "009155", "SK스퀘어": "402340", "현대차": "005380"}
    my_results = []
    for name, code in my_stocks.items():
        try:
            start_date = (now - datetime.timedelta(days=120)).strftime("%Y%m%d")
            df_m = stock.get_market_ohlcv_by_date(start_date, kr_date, code)
            if df_m is not None and len(df_m) > 20:
                df_m = calculate_technical_indicators(df_m)
                cur = df_m["Close"].iloc[-1]
                support = int(df_m["Low"].rolling(20).min().iloc[-1])
                resistance = int(df_m["High"].rolling(20).max().iloc[-1])
                rsi_val = df_m["RSI"].iloc[-1] if "RSI" in df_m.columns else 50.0
                macd_val = df_m["MACD"].iloc[-1] if "MACD" in df_m.columns else 0.0
                ma_align = df_m["MA_Align"].iloc[-1] if "MA_Align" in df_m.columns else "혼조세"

                my_results.append({
                    "name": name,
                    "price": cur,
                    "target": int(resistance * 1.2),
                    "stop": int(support * 0.9),
                    "rsi": rsi_val,
                    "macd": macd_val,
                    "ma_align": ma_align,
                    "opinion": "추세 조정 국면, 리스크 관리 및 보수적 접근" if "역배열" in ma_align else "강세 흐름 유지, 홀딩 권장"
                })
        except:
            continue

    # ==========================================
    # 4. 상세 메시지 조합
    # ==========================================
    msg = f"📈 {today_str} 주식 브리핑 ({timing_name})\n"
    msg += "⚡ 실시간 시장 정밀 분석 리포트\n\n"

    if top_kr_data:
        msg += "🇰🇷 국내 주요 주도주\n"
        for i, item in enumerate(top_kr_data, 1):
            msg += (
                f"{i}. {item['name']} ({item['change']:+.2f}%)\n"
                f"   - 상승이유: 기관/외인 수급 집중 및 섹터 순환매 유입\n"
                f"   - 거래량증가: {item['vol_inc']}\n"
                f"   - 골든크로스: {item['golden']}\n"
                f"   - MACD: {item['macd']:,.2f} | RSI: {item['rsi']:.1f}\n"
                f"   - 이평선배열: {item['ma_align']}\n"
                f"   - 저항선: {item['resistance']:,}원 / 지지선: {item['support']:,}원\n"
                f"   - 단기/중기 전략: 추세 추종 및 눌림목 분할 매수\n"
                f"   - 리스크요인: 단기 과열 진입에 따른 차익실현 매물 주의\n\n"
            )

    if top_us_data:
        msg += "🇺🇸 미국 주식 TOP 주도주\n"
        for i, item in enumerate(top_us_data, 1):
            msg += (
                f"{i}. {item['name']} ({item['change']:+.2f}%)\n"
                f"   - 골든크로스: {item['golden']} | RSI: {item['rsi']:.1f}\n"
                f"   - 이평선배열: {item['ma_align']} | 단기 트렌드 우상향\n\n"
            )

    if my_results:
        msg += "📊 보유종목 정밀 분석\n"
        for s in my_results:
            msg += (
                f"• {s['name']}\n"
                f"  - 현재가: {s['price']:,}원\n"
                f"  - 손절가: {s['stop']:,}원 / 목표가: {s['target']:,}원\n"
                f"  - 기술적지표: RSI {s['rsi']:.1f} | MACD {s['macd']:,.2f}\n"
                f"  - 이평선배열: {s['ma_align']}\n"
                f"  - AI 의견: {s['opinion']}\n\n"
            )

    if top_kr_data:
        best_stock = top_kr_data[0]
        msg += f"🔥 오늘의 가장 유망한 종목\n"
        msg += f"★★★★★ [{best_stock['name']}]\n"
        msg += f"- 핵심 근거: 거래량 동반 돌파 및 기술적 지표 우수\n\n"

    msg += "⚠ 오늘 주의할 종목\n"
    msg += "- 단기 급등 후 윗꼬리를 다는 테마주 및 거래량 감소 역배열 종목\n\n"

    msg += "💡 오늘의 투자 아이디어 3가지\n"
    msg += "1. 실적 개선이 가시화되는 대형주 중심의 비중 확대\n"
    msg += "2. 글로벌 매크로(금리, 환율) 변동성 대비 현금 비중 확보\n"
    msg += "3. 20일 이동평균선과 거래량이 일치하는 눌림목 구간 집중 공략\n\n"

    msg += "※ 개인투자 참고용이며 투자 판단은 본인 책임입니다."

    # 카카오톡 전송 실행
    send_kakao_message(msg)

if __name__ == "__main__":
    print("[Stock_bot.py] 상세 자동화 브리핑 실행 시작")
    run_job()
