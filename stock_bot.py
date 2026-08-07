import requests
import datetime
import json
import time
import yfinance as yf
from pykrx import stock

# ==========================================
# 설정 정보
# ==========================================
CLIENT_ID = "2e2432752d3bcaaf637aa44cfb75a555"
REDIRECT_URI = "https://localhost:3000"
ACCESS_TOKEN = "QSEOyc6vqdKNUGGn9u2Baz6gU3HS5c4SAAAAAQoXEpYAAAGf1ejxRKj01SImjvGc"
REFRESH_TOKEN = "wWN1D_LLRI9rzePTDcq2Ow9rri8NvE7XAAAAAgoXEpYAAAGf1ejxPKj01SImjvGc"

# ==========================================
# 1. 토큰 갱신 함수
# ==========================================
def refresh_access_token():
    global ACCESS_TOKEN
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH_TOKEN
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        token_info = response.json()
        ACCESS_TOKEN = token_info.get("access_token")
        print("Access Token이 성공적으로 갱신되었습니다.")
    else:
        print(f"토큰 갱신 실패: {response.json()}")

# ==========================================
# 2. 카카오톡 메시지 개별 전송 함수
# ==========================================
def send_kakao_message(text):
    global ACCESS_TOKEN
    header = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    data = {"template_object": json.dumps(template)}
    response = requests.post(url, headers=header, data=data)
    
    if response.status_code == 401:
        print("Access Token이 만료되어 갱신을 시도합니다.")
        refresh_access_token()
        header["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        response = requests.post(url, headers=header, data=data)
        
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공!")
    else:
        print(f"전송 실패 (에러코드: {response.status_code}): {response.json()}")

# ==========================================
# 3. 실시간 주가 및 지표 조회 함수
# ==========================================
def get_stock_info(ticker, market="kr"):
    try:
        if market == "kr":
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            start_str = (datetime.datetime.now() - datetime.timedelta(days=150)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(start_str, today_str, ticker)
            if df.empty:
                return {"cp": 0, "tp": 0, "sl": 0, "align": "조회 불가"}
            
            close = df['종가']
            cp = close.iloc[-1]
            ma20 = close.rolling(window=20).mean().iloc[-1]
            ma60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else ma20
            
            tp = cp * 1.05  
            sl = cp * 0.95     
            align = "🟢 정배열" if ma20 > ma60 else "🔴 역배열"
            
            return {"cp": cp, "tp": tp, "sl": sl, "align": align, "unit": "원"}
        
        elif market == "us":
            ticker_obj = yf.Ticker(ticker)
            todays_data = ticker_obj.history(period="3mo")
            if todays_data.empty:
                return {"cp": 0, "tp": 0, "sl": 0, "align": "조회 불가"}
            
            cp = todays_data['Close'].iloc[-1]
            tp = cp * 1.05
            sl = cp * 0.95
            
            return {"cp": cp, "tp": tp, "sl": sl, "align": "미국주식", "unit": "$"}
    except Exception as e:
        return {"cp": 0, "tp": 0, "sl": 0, "align": "오류"}

# ==========================================
# 4. 표 형식으로 가공하여 여러 파트로 나누어 전송하는 함수
# ==========================================
def send_split_briefing():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 데이터 일괄 수집
    stocks = {
        "삼성전자": get_stock_info("005930", "kr"),
        "SK하이닉스": get_stock_info("000660", "kr"),
        "삼성전기": get_stock_info("009150", "kr"),
        "SK스퀘어": get_stock_info("402340", "kr"),
        "현대차": get_stock_info("005380", "kr"),
        "LS ELECTRIC": get_stock_info("010120", "kr"),
        "TSLA": get_stock_info("TSLA", "us"),
        "알파벳(GOOGL)": get_stock_info("GOOGL", "us")
    }

    # 포맷팅 헬퍼 함수 (표 스타일)
    def make_table_row(name, info):
        u = info["unit"]
        if u == "원":
            cp_str = f"{info['cp']:,.0f}{u}"
            tp_str = f"{info['tp']:,.0f}{u}"
            sl_str = f"{info['sl']:,.0f}{u}"
        else:
            cp_str = f"{u}{info['cp']:.2f}"
            tp_str = f"{u}{info['tp']:.2f}"
            sl_str = f"{u}{info['sl']:.2f}"
            
        return f"▪ {name}\n  └ 현재: {cp_str} │ 목표: {tp_str}\n  └ 손절: {sl_str} │ 상태: {info['align']}"

    # 파트 1: 시장 요약 및 국내 주요 종목 (1~4)
    part1 = f"""📈 [{today}] 주식 브리핑 (1/3)
━━━━━━━━━━━━━━━
⚡ [시장 핵심 요약]
• 국내: 반도체 및 주도주 수급 공방
• 미국: 빅테크 등락 및 섹터 순환

📊 [보유종목 시세표 (1)]
{make_table_row('삼성전자', stocks['삼성전자'])}
-----------------
{make_table_row('SK하이닉스', stocks['SK하이닉스'])}
-----------------
{make_table_row('삼성전기', stocks['삼성전기'])}
-----------------
{make_table_row('SK스퀘어', stocks['SK스퀘어'])}"""

    # 파트 2: 나머지 보유종목 (국내 5~6, 미국 1~2)
    part2 = f"""📊 [{today}] 주식 브리핑 (2/3)
━━━━━━━━━━━━━━━
📊 [보유종목 시세표 (2)]
{make_table_row('현대차', stocks['현대차'])}
-----------------
{make_table_row('LS ELECTRIC', stocks['LS ELECTRIC'])}
-----------------
{make_table_row('TSLA (테슬라)', stocks['TSLA'])}
-----------------
{make_table_row('알파벳(GOOGL)', stocks['알파벳(GOOGL)'])}"""

    # 파트 3: 유망주 및 투자 전략
    part3 = f"""💡 [{today}] 주식 브리핑 (3/3)
━━━━━━━━━━━━━━━
🔥 [오늘의 유망주]
★★★★★ 수급 집중 우량주
• 외국인/기관 동반 순매수 및 거래량 유입

💡 [핵심 투자 전략]
1. 실적 모멘텀 보유 주도주 선별 공략
2. 단기 지지선 기준 분할 매수 대응
3. 매크로 변동성 대비 철저한 리스크 관리

📌 [아침 대응] 시초가 수급 강도 필수 체크!"""

    # 순차적 전송
    print("파트 1 전송 중...")
    send_kakao_message(part1)
    time.sleep(1.2)
    
    print("파트 2 전송 중...")
    send_kakao_message(part2)
    time.sleep(1.2)
    
    print("파트 3 전송 중...")
    send_kakao_message(part3)
    print("모든 브리핑 전송 완료!")

# ==========================================
# 5. 실행
# ==========================================
if __name__ == "__main__":
    print(f"[{datetime.datetime.now()}] 표 형식 주식 브리핑 생성 및 전송 시작...")
    send_split_briefing()
