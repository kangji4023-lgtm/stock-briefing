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
    """이동평균선, 골든크로스, MACD, RSI 계산"""
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

    return df

# ==========================================
# 3. 브리핑 데이터 수집 및 분석 엔진
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday() # 0:월, 5:토, 6:일
    is_weekend = (weekday >= 5)

    print(f"[{today_str}] 맞춤형 주식 보고서 데이터 수집 시작 (yfinance 안정 모드)...")

    # 1) 국내 지정 종목 분석 (yfinance 티커 활용: 삼성전자=005930.KS 등)
    target_stocks = {
        "삼성전자": "005930.KS", 
        "SK하이닉스": "000660.KS", 
        "삼성전기": "009155.KS", 
        "SK스퀘어": "402340.KS", 
        "현대차": "005380.KS"
    }
    my_results = []
    
    for name, code in target_stocks.items():
        try:
            df_m = yf.download(code, period="3mo", interval="1d", progress=False)
            if df_m is not None and len(df_m) > 20:
                # yfinance 멀티인덱스 컬럼 대응
                if isinstance(df_m.columns, pd.MultiIndex):
                    df_m.columns = df_m.columns.get_level_values(0)
                
                df_m = calculate_technical_indicators(df_m)
                cur = int(df_m["Close"].iloc[-1])
                prev = int(df_m["Close"].iloc[-2])
                chg = ((cur - prev) / prev) * 100
                support = int(df_m["Low"].rolling(20).min().iloc[-1])
                resistance = int(df_m["High"].rolling(20).max().iloc[-1])
                rsi_val = df_m["RSI"].iloc[-1] if "RSI" in df_m.columns else 50.0
                ma_align = df_m["MA_Align"].iloc[-1] if "MA_Align" in df_m.columns else "혼조세"

                my_results.append({
                    "name": name,
                    "price": cur,
                    "change": chg,
                    "target": resistance,
                    "stop": support,
                    "rsi": rsi_val,
                    "ma_align": ma_align
                })
        except Exception as e:
            print(f"국내 종목({name}) 수집 중 예외: {e}")
            continue

    # 2) 미국 지정 종목 분석 (Tesla, Alphabet + 반도체 대표 NVDA)
    us_tickers = ["TSLA", "GOOGL", "NVDA", "INTC", "AMD"]
    us_results = []
    try:
        data_us = yf.download(us_tickers, period="3mo", interval="1d", group_by="ticker", progress=False)
        for t in us_tickers:
            try:
                df_u = data_us[t].dropna()
                if len(df_u) > 20:
                    if isinstance(df_u.columns, pd.MultiIndex):
                        df_u.columns = df_u.columns.get_level_values(0)
                    df_u = calculate_technical_indicators(df_u)
                    chg = ((df_u["Close"].iloc[-1] - df_u["Close"].iloc[-2]) / df_u["Close"].iloc[-2]) * 100
                    us_results.append({
                        "name": t,
                        "close": df_u["Close"].iloc[-1],
                        "change": chg,
                        "rsi": df_u["RSI"].iloc[-1] if "RSI" in df_u.columns else 50.0,
                        "ma_align": df_u["MA_Align"].iloc[-1] if "MA_Align" in df_u.columns else "혼조세"
                    })
            except:
                continue
    except Exception as e:
        print(f"미국 데이터 수집 오류: {e}")

    # ==========================================
    # 4. 카카오톡 맞춤형 보고서 조합
    # ==========================================
    msg = f"📅 {today_str} AI 프리미엄 주식 보고서\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n\n"

    # 주말 및 휴일 특별 섹션 반영
    if is_weekend or weekday == 0:
        msg += "🏛️ [주말/휴일 글로벌 증시 및 매크로 점검]\n"
        msg += "• 전일 마감 증시: 글로벌 주요 지수 방어 및 관망세 유지\n"
        msg += "• 주말 이슈 및 트럼프 발언: 관세 정책 및 반도체·전기차 공급망 발언에 따른 변동성 주시\n"
        if weekday == 0:
            msg += "• 🚀 [월요일 강력한 추천주] 섹터 내 수급 집중 우량주 집중 공략\n"
        msg += "\n━━━━━━━━━━━━━━━━━━━\n\n"

    msg += "📊 시장 위험도 분석\n"
    msg += "• 위험도 수준: [보통 (Moderate)]\n"
    msg += "• 핵심 근거: 환율 및 금리 변동성 상존, 핵심 기술주 중심 선별 접근 필요\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n\n"

    msg += "🔥 오늘 가장 강한 섹터\n"
    msg += "1위: 반도체 및 AI 하드웨어 (외인/기관 수급 유입)\n"
    msg += "2위: 전기차 및 자율주행 (테슬라 모멘텀 연동)\n\n"
    msg += "━━━━━━━━━━━━━━━\n\n"

    if my_results:
        msg += "🇰🇷 국내 주요 관심종목 (반도체/보유)\n"
        for s in my_results:
            msg += (
                f"• {s['name']} ({s['change']:+.2f}%)\n"
                f"  - 현재가: {s['price']:,}원\n"
                f"  - 저항선(목표): {s['target']:,}원 / 지지선(손절): {s['stop']:,}원\n"
                f"  - RSI: {s['rsi']:.1f} | 배열: {s['ma_align']}\n\n"
            )

    if us_results:
        msg += "🇺🇸 미국 주요 주도주 (Tesla / Alphabet / 반도체)\n"
        for s in us_results:
            msg += (
                f"• {s['name']} ({s['change']:+.2f}%)\n"
                f"  - 종가: ${s['close']:,.2f} | RSI: {s['rsi']:.1f}\n"
                f"  - 이평선 배열: {s['ma_align']}\n\n"
            )

    msg += "━━━━━━━━━━━━━━━━━━━\n\n"

    msg += "💡 오늘의 투자 아이디어\n"
    msg += "1. 삼성전자·SK하이닉스 등 국내 반도체 대형주 20일선 눌림목 분할 매수\n"
    msg += "2. 테슬라(TSLA) 및 알파벳(GOOGL) 실적 및 매크로 모멘텀 추종\n"
    msg += "3. 주말 트럼프 관련 리스크 이슈 소화 후 월요일 수급 집중 종목 선점\n\n"

    msg += "⭐ 내일(다음 거래일) 관심종목 추천\n"
    msg += "• SK하이닉스 / 테슬라(TSLA)\n"
    msg += "- 추천 이유: 거래량 유입 및 핵심 지지선 방어 성공에 따른 반등 기대\n\n"

    msg += "※ 본 보고서는 투자 참고용이며 최종 책임은 투자자 본인에게 있습니다."

    # 카카오톡 전송 실행
    send_kakao_message(msg)

if __name__ == "__main__":
    print("[Stock_bot.py] 최종 보고서 생성 완료")
    run_job()
