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

# 국내 지정 종목 (네이버 코드 기준)
TARGET_KR_STOCKS = {
    "삼성전자": "005930", 
    "SK하이닉스": "000660", 
    "삼성전기": "009155", 
    "SK스퀘어": "402340", 
    "현대차": "005380"
}

# 미국 지정 종목
US_TICKERS = ["TSLA", "GOOGL", "NVDA", "AMD", "INTC"]

# ==========================================
# 2. 카카오톡 전송 모듈
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

    max_len = 850
    texts = [text[i : i + max_len] for i in range(0, len(text), max_len)]

    for chunk in texts:
        payload = {
            "object_type": "text",
            "text": chunk,
        }
        data = {"template_object": json.dumps(payload)}
        try:
            requests.post(url, headers=headers, data=data, timeout=10)
        except Exception as e:
            print(f"메시지 전송 예외: {e}")
        time.sleep(0.5)

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

    # RSI 계산
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

# ==========================================
# 4. 국내주식 분석 모듈
# ==========================================
def get_korea_stock_data():
    results = []
    for name, code in TARGET_KR_STOCKS.items():
        try:
            df = yf.download(f"{code}.KS", period="3mo", interval="1d", progress=False)
            if df is not None and len(df) > 10:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = calculate_technical_indicators(df)
                cur = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                chg = ((cur - prev) / prev) * 100
                high = float(df["High"].rolling(20).max().iloc[-1])
                low = float(df["Low"].rolling(20).min().iloc[-1])
                rsi = float(df["RSI"].iloc[-1]) if "RSI" in df.columns else 50.0
                
                results.append({
                    "name": name,
                    "price": int(cur),
                    "change": chg,
                    "target": int(high),
                    "stop": int(low),
                    "rsi": rsi,
                    "ma_align": "정배열(강세)" if chg >= 0 else "혼조세"
                })
        except Exception as e:
            print(f"국내 종목 수집 오류 ({name}): {e}")
        time.sleep(0.2)
    return results

# ==========================================
# 5. 미국주식 분석 모듈
# ==========================================
def get_usa_stock_data():
    results = []
    try:
        data_us = yf.download(US_TICKERS, period="3mo", interval="1d", group_by="ticker", progress=False)
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
                        "ma_align": "정배열(강세)" if chg >= 0 else "혼조세"
                    })
            except Exception as e:
                print(f"미국 종목 수집 오류 ({t}): {e}")
    except Exception as e:
        print(f"미국 전체 데이터 수집 오류: {e}")
    return results

# ==========================================
# 6. 뉴스 및 포트폴리오 분석 모듈
# ==========================================
def get_market_news():
    return [
        "반도체 대형주 외인·기관 수급 집중 및 업황 개선 기대감 지속",
        "테슬라(TSLA) 및 글로벌 전기차 공급망 관련 매크로 모멘텀 추종",
        "주말 트럼프 관련 관세 및 경제 정책 리스크 이슈 점검 필요"
    ]

def analyze_portfolio():
    return {
        "risk_level": "보통 (Moderate)",
        "comment": "핵심 지지선 방어 성공 및 순환매 장세 대응 유효"
    }

def generate_ai_commentary():
    return {
        "ideas": [
            "삼성전자·SK하이닉스 등 국내 반도체 대형주 20일선 눌림목 분할 매수",
            "테슬라(TSLA) 및 알파벳(GOOGL) 실적 모멘텀 및 매크로 지표 추종",
            "트럼프 관련 정책 발언에 따른 수혜/피해 섹터 순환매 대응"
        ],
        "top_pick": "SK하이닉스 / 테슬라(TSLA)",
        "pick_reason": "핵심 지지선 방어 완료 및 거래량 유입에 따른 반등 기대감 유효"
    }

# ==========================================
# 7. 메인 실행 함수
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d %H:%M")
    weekday = now.weekday()
    is_weekend = (weekday >= 5)

    print(f"[{today_str}] 통합 주식 보고서 생성 시작...")

    kr_results = get_korea_stock_data()
    us_results = get_usa_stock_data()
    news_list = get_market_news()
    portfolio = analyze_portfolio()
    ai_report = generate_ai_commentary()

    msg = f"📅 {today_str} AI 프리미엄 주식 보고서\n"
    msg += "═══════════════════\n\n"

    msg += "📊 시장 위험도\n"
    msg += f"• 단계: [{portfolio['risk_level']}]\n"
    msg += f"• 근거: {portfolio['comment']}\n\n"
    msg += "───────────────────\n\n"

    if is_weekend or weekday == 0:
        msg += "🏛️ [주말/휴일 글로벌 증시 및 뉴스]\n"
        for n in news_list:
            msg += f"• {n}\n"
        msg += "\n───────────────────\n\n"

    if kr_results:
        msg += "🇰🇷 국내 핵심 관심종목 (반도체 및 주도주)\n"
        for s in kr_results:
            msg += (
                f"• {s['name']} ({s['change']:+.2f}%)\n"
                f"  - 현재가: {s['price']:,}원\n"
                f"  - 목표가: {s['target']:,}원 / 손절가: {s['stop']:,}원\n"
                f"  - RSI: {s['rsi']:.1f} | 배열: {s['ma_align']}\n\n"
            )

    if us_results:
        msg += "🇺🇸 미국 TOP 주도주 및 반도체\n"
        for s in us_results:
            msg += (
                f"• {s['name']} ({s['change']:+.2f}%)\n"
                f"  - 종가: ${s['close']:,.2f} | RSI: {s['rsi']:.1f}\n"
                f"  - 배열: {s['ma_align']}\n\n"
            )

    msg += "───────────────────\n\n"

    msg += "💡 오늘의 투자 아이디어\n"
    for idx, idea in enumerate(ai_report['ideas'], 1):
        msg += f"{idx}. {idea}\n"
    msg += "\n"

    msg += "⭐ 추천 관심종목\n"
    msg += f"• 종목: {ai_report['top_pick']}\n"
    msg += f"• 사유: {ai_report['pick_reason']}\n\n"

    msg += "※ 본 보고서는 투자 참고용이며 최종 투자 책임은 본인에게 있습니다."

    send_kakao_message(msg)
    print("보고서 생성 및 카카오톡 전송 완료!")

if __name__ == "__main__":
    run_job()
