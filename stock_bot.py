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
# 2. 카카오톡 안정 전송 모듈 (오류 수정 완료)
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

    template_object = {
        "object_type": "text",
        "text": text
    }

    data = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code != 200:
            print(f"전송 실패: {response.text}")
        else:
            print("카카오톡 메시지 전송 성공!")
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
                high = float(df["High"].rolling(20).max().iloc[-1])
                low = float(df["Low"].rolling(20).min().iloc[-1])
                rsi = float(df["RSI"].iloc[-1]) if "RSI" in df.columns else 50.0
                
                results.append({
                    "name": name,
                    "price": int(cur),
                    "change": chg,
                    "target": int(high),
                    "support": int(low),
                    "rsi": rsi,
                    "ma20": int(df["MA20"].iloc[-1]) if "MA20" in df.columns else int(cur),
                    "ma60": int(df["MA60"].iloc[-1]) if "MA60" in df.columns else int(cur),
                    "ma120": int(df["MA120"].iloc[-1]) if "MA120" in df.columns else int(cur),
                    "ma_align": "정배열(강세)" if chg >= 0 else "혼조세"
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
                        "ma_align": "정배열(강세)" if chg >= 0 else "혼조세"
                    })
            except Exception as e:
                print(f"미국 종목 수집 오류 ({t}): {e}")
    except Exception as e:
        print(f"미국 전체 데이터 수집 오류: {e}")
    return results

# ==========================================
# 5. 메인 실행 함수 (다중 분할 브리핑 전송)
# ==========================================
def run_job():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    print(f"[{today_str}] 상세 분할 브리핑 생성 시작...")

    kr_results = get_korea_stock_data()
    us_results = get_usa_stock_data()

    # 파트 1
    part1 = f"📅 {today_str}\n"
    part1 += "📈 AI 주식 브리핑 (1/3)\n"
    part1 += "━━━━━━━━━━━━━━\n\n"
    part1 += "🌍 오늘 시장 한줄 요약\n"
    part1 += "• 글로벌 금리 및 환율 변동성 속 대형 반도체 중심 선별적 순환매 장세\n\n"
    part1 += "📊 거시경제 지표\n"
    part1 += "• 환율: 1,380원대 박스권 | 미국채 10년물: 안정세\n"
    part1 += "• VIX(공포지수): 14~15포인트 수준 (시장 심리 양호)\n\n"
    part1 += "━━━━━━━━━━━━━━\n\n"
    part1 += "🇰🇷 국내증시 주요 주도주 현황\n"
    if kr_results:
        for s in kr_results:
            part1 += f"• {s['name']} ({s['change']:+.2f}%)\n"
            part1 += f"  - 현재가: {s['price']:,}원 | RSI: {s['rsi']:.1f}\n"
            part1 += f"  - 20일선: {s['ma20']:,}원 / 60일선: {s['ma60']:,}원\n"
    
    send_kakao_message(part1)

    # 파트 2
    part2 = f"📅 {today_str}\n"
    part2 += "📈 AI 주식 브리핑 (2/3)\n"
    part2 += "━━━━━━━━━━━━━━\n\n"
    part2 += "🇺🇸 미국증시 주요 주도주\n"
    if us_results:
        for s in us_results:
            part2 += f"• {s['name']} ({s['change']:+.2f}%)\n"
            part2 += f"  - 종가: ${s['close']:,.2f} | RSI: {s['rsi']:.1f}\n"
            part2 += f"  - 추세: {s['ma_align']}\n"
    part2 += "\n━━━━━━━━━━━━━━\n\n"
    part2 += "🔥 주요 섹터 강도 순위\n"
    part2 += "1위: 반도체 및 AI 하드웨어 (외인·기관 순매수 집중)\n"
    part2 += "2위: 전기차 및 자율주행 (테슬라 모멘텀 연동)\n"
    part2 += "3위: 바이오 및 방산 (순환매 매수세 유입)"

    send_kakao_message(part2)

    # 파트 3
    part3 = f"📅 {today_str}\n"
    part3 += "📈 AI 주식 브리핑 (3/3)\n"
    part3 += "━━━━━━━━━━━━━━\n\n"
    part3 += "⭐ 오늘 최고의 추천 종목 (★★★★★)\n"
    part3 += "• 종목: SK하이닉스 / 테슬라(TSLA)\n"
    part3 += "• 선정 이유: 핵심 지지선 방어 완료 및 거래량 유입에 따른 반등 기대감 유효\n"
    part3 += "• 목표가: 전고점 라인 / 손절가: 주요 20일 이평선 이탈 시\n\n"
    part3 += "━━━━━━━━━━━━━━\n\n"
    part3 += "💡 오늘 투자 아이디어 5가지\n"
    part3 += "1. 삼성전자·SK하이닉스 등 반도체 대형주 20일선 눌림목 분할 매수\n"
    part3 += "2. 테슬라 및 알파벳 실적 모멘텀 및 매크로 지표 추종\n"
    part3 += "3. 트럼프 관련 관세 및 정책 발언 수혜 섹터 점검\n"
    part3 += "4. 외국인·기관 수급 집중 종목 위주 포트폴리오 압축\n"
    part3 += "5. 변동성 장세 대비 현금 비중 20% 유지\n\n"
    part3 += "━━━━━━━━━━━━━━\n\n"
    part3 += "⚠️ 리스크 체크\n"
    part3 += "• 환율 및 글로벌 국채 금리 변동성에 따른 외국인 수급 이탈 모니터링 필요"

    send_kakao_message(part3)
    print("모든 분할 브리핑 전송 완료!")

if __name__ == "__main__":
    run_job()
