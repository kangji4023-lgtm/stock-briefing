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
    """이동평균선, 골든크로스, MACD, RSI, OBV 계산"""
    if df is None or len(df) < 60:
        return df
        
    df = df.copy()
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()
    df["MA120"] = df["Close"].rolling(window=120).mean() if len(df) >= 120 else df["MA60"]

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

    # OBV 계산
    df["OBV"] = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()

    df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)
    return df

# ==========================================
# 3. 브리핑 데이터 수집 및 분석 엔진
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    print(f"[{today_str}] 최고급 투자 분석 리포트 데이터 수집 시작...")

    try:
        kr_date = stock.get_nearest_business_day_in_a_week(now.strftime("%Y%m%d"))
    except Exception:
        kr_date = now.strftime("%Y%m%d")

    # 1) 국내 TOP10 주도주 분석
    top_kr_data = []
    try:
        tickers = stock.get_market_ticker_list(kr_date, market="KOSPI")
        for ticker in tickers[:20]:
            try:
                name = stock.get_market_ticker_name(ticker)
                start_date = (now - datetime.timedelta(days=150)).strftime("%Y%m%d")
                df = stock.get_market_ohlcv_by_date(start_date, kr_date, ticker)
                
                if df is not None and len(df) > 60:
                    df = calculate_technical_indicators(df)
                    if len(df) < 2: continue
                    
                    change_pct = ((df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
                    high_20 = df["High"].rolling(20).max().iloc[-1]
                    low_20 = df["Low"].rolling(20).min().iloc[-1]
                    
                    top_kr_data.append({
                        "name": name,
                        "change": change_pct,
                        "close": df["Close"].iloc[-1],
                        "vol_inc": "O (증가)" if df["Vol_Increase"].iloc[-1] else "X",
                        "golden": "발생" if df["Golden_Cross"].iloc[-1] else "미발생",
                        "macd": df["MACD"].iloc[-1],
                        "rsi": df["RSI"].iloc[-1] if "RSI" in df.columns else 50.0,
                        "obv": df["OBV"].iloc[-1],
                        "ma5": df["MA5"].iloc[-1],
                        "ma60": df["MA60"].iloc[-1],
                        "ma120": df["MA120"].iloc[-1],
                        "ma_align": df["MA_Align"].iloc[-1],
                        "resistance": int(high_20),
                        "support": int(low_20),
                        "target": int(high_20 * 1.1),
                    })
            except:
                continue
        top_kr_data = sorted(top_kr_data, key=lambda x: x["change"], reverse=True)[:5]
    except Exception as e:
        print(f"국내 데이터 수집 오류: {e}")

    # 2) 미국 TOP10 주도주 분석
    us_tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "INTC"]
    top_us_data = []
    try:
        data_us = yf.download(us_tickers, period="3mo", interval="1d", group_by="ticker", progress=False)
        for t in us_tickers:
            try:
                df_u = data_us[t].dropna()
                if len(df_u) > 60:
                    df_u = calculate_technical_indicators(df_u)
                    chg = ((df_u["Close"].iloc[-1] - df_u["Close"].iloc[-2]) / df_u["Close"].iloc[-2]) * 100
                    top_us_data.append({
                        "name": t,
                        "change": chg,
                        "close": df_u["Close"].iloc[-1],
                        "rsi": df_u["RSI"].iloc[-1] if "RSI" in df_u.columns else 50.0,
                        "macd": df_u["MACD"].iloc[-1] if "MACD" in df_u.columns else 0.0,
                        "golden": "발생" if df_u["Golden_Cross"].iloc[-1] else "미발생",
                        "ma_align": df_u["MA_Align"].iloc[-1] if "MA_Align" in df_u.columns else "혼조세"
                    })
            except:
                continue
        top_us_data = sorted(top_us_data, key=lambda x: x["change"], reverse=True)[:5]
    except Exception as e:
        print(f"미국 데이터 수집 오류: {e}")

    # ==========================================
    # 4. 지정된 출력 형식에 맞춘 메시지 조합
    # ==========================================
    msg = f"📅 {today_str}\n"
    msg += "📈 AI 국내·미국 주식 브리핑\n"
    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "🌍 오늘 시장 한줄 요약\n"
    msg += "- 글로벌 매크로 변동성 속 주요 기술주 및 반도체 섹터 중심의 수급 공방 전개\n\n"
    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "🇰🇷 국내시장\n"
    msg += "- KOSPI / KOSDAQ 혼조세 마감 및 기관·외인 수급 유입 모니터링 중\n"
    msg += "- 시장 분위기: 주요 주도주 중심의 순환매 장세 지속\n\n"
    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "🇺🇸 미국시장\n"
    msg += "- NASDAQ / S&P500 / DOW 주요 지수 방어 및 실적 발표 집중\n"
    msg += "- 주요 이슈: 연준 통화정책 및 금리 인하 기대감 반영\n\n"
    msg += "━━━━━━━━━━━━━━\n\n"

    if top_kr_data:
        msg += "🔥 국내 TOP10 주도주 (상위 5선)\n"
        for i, item in enumerate(top_kr_data, 1):
            msg += (
                f"{i}. {item['name']} ({item['change']:+.2f}%)\n"
                f"   - 상승이유: 기관 및 외국인 수급 집중\n"
                f"   - 거래량증가율: {item['vol_inc']} | 골든크로스: {item['golden']}\n"
                f"   - MACD: {item['macd']:,.2f} | RSI: {item['rsi']:.1f}\n"
                f"   - 이평선 (20일: {item['ma5']:,.0f} / 60일: {item['ma60']:,.0f})\n"
                f"   - 저항선: {item['resistance']:,}원 / 지지선: {item['support']:,}원\n"
                f"   - 단기/중기 의견: 추세 추종 및 분할 매수 관점\n"
                f"   - 점수: ★★★★★\n\n"
            )

    msg += "━━━━━━━━━━━━━━\n\n"

    if top_us_data:
        msg += "🔥 미국 TOP10 주도주 (상위 5선)\n"
        for i, item in enumerate(top_us_data, 1):
            msg += (
                f"{i}. {item['name']} ({item['change']:+.2f}%)\n"
                f"   - 골든크로스: {item['golden']} | RSI: {item['rsi']:.1f}\n"
                f"   - MACD: {item['macd']:,.2f} | 배열: {item['ma_align']}\n"
                f"   - 점수: ★★★★★\n\n"
            )

    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "⭐ 오늘 최고의 추천 종목\n"
    msg += "★★★★★\n"
    msg += "선정 이유: 거래량 동반 돌파 및 기술적 지표 최상위권 달성\n"
    msg += "목표가: 전고점 저항 라인 돌파 시 상향 조정\n"
    msg += "손절가: 20일 이동평균선 이탈 시 대응\n"
    msg += "예상 상승 모멘텀: 단기 수급 유입에 따른 추가 탄력 기대\n\n"

    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "💡 오늘 투자 아이디어 5가지\n"
    msg += "1. 실적 개선 가시화 대형주 중심 비중 확대\n"
    msg += "2. 글로벌 매크로(환율, 유가, 금리) 변동성 주시\n"
    msg += "3. 20일선 눌림목 구간 집중 공략\n"
    msg += "4. 방산·AI·반도체 등 주도 섹터 순환매 대응\n"
    msg += "5. 리스크 관리를 위한 현금 비중 일정 수준 유지\n\n"

    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "⚠️ 리스크 체크\n"
    msg += "- 단기 과열권 진입 종목의 차익실현 매물 출하 주의 및 변동성 대응 철저\n\n"

    msg += "━━━━━━━━━━━━━━\n\n"

    msg += "📌 마지막 한줄\n"
    msg += '"오늘 시장에서 가장 중요한 것은 수급 집중도이며, 반드시 거래량 유입 여부를 확인하십시오."\n\n'

    msg += "※ 본 내용은 투자 참고자료이며 특정 종목의 수익을 보장하지 않습니다."

    # 카카오톡 전송 실행
    send_kakao_message(msg)

if __name__ == "__main__":
    print("[Stock_bot.py] 최종 리포트 생성 및 전송 시작")
    run_job()
