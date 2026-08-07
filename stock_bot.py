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
    """카카오톡 메시지 전송 (900자씩 분할 전송)"""
    access_token = get_kakao_access_token()
    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    chunks = [text[i:i+900] for i in range(0, len(text), 900)]
    success = True
    
    for chunk in chunks:
        template_object = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }
        data = {"template_object": str(template_object).replace("'", '"')}
        try:
            response = requests.post(url, headers=headers, data=data, timeout=5)
            if response.status_code != 200:
                success = False
        except:
            success = False
    return success

def get_safe_krx_date():
    try:
        now = datetime.now(pytz.timezone('Asia/Seoul'))
        today_str = now.strftime("%Y%m%d")
        return stock.get_nearest_business_day_in_a_week(today_str)
    except:
        return datetime.now().strftime("%Y%m%d")

def classify_sector(name):
    """종목명을 받아 실시간 섹터 성격으로 분류"""
    if any(k in name for k in ["바이오", "제약", "셀트리온", "치과", "의료"]):
        return "바이오 및 헬스케어"
    elif any(k in name for k in ["배터리", "에너지", "화학", "엘앤에프", "포스코"]):
        return "2차전지 및 소재"
    elif any(k in name for k in ["차", "모빌리티", "기아", "현대"]):
        return "자동차 및 부품"
    elif any(k in name for k in ["방산", "한화", "현대로템", "KAI"]):
        return "방산 및 중공업"
    elif any(k in name for k in ["반도체", "하이닉스", "삼성전자", "이오테크닉스", "한미반도체"]):
        return "반도체 및 AI 밸류체인"
    else:
        return "기타 핵심 주도 테마"

# ==========================================
# 100% 실시간 동적 반영 애널리스트 리포트 생성
# ==========================================
def generate_analyst_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    time_label = "장시작 브리핑"
    if 9 <= current_hour < 13:
        time_label = "오전 11시 장중 브리핑"
    elif 13 <= current_hour < 17:
        time_label = "오후 4시 마감 브리핑"
    elif current_hour >= 17:
        time_label = "저녁 야간 브리핑"

    krx_date = get_safe_krx_date()

    # 1. 실시간 거래대금 상위 TOP 종목 추출 및 동적 섹터 도출
    realtime_top_stocks = ""
    detected_sectors = []
    try:
        df_trade = stock.get_market_trading_value_by_ticker(krx_date, krx_date, "ALL")
        if df_trade is not None and not df_trade.empty:
            df_top = df_trade.sort_values(by="거래대금", ascending=False).head(5)
            for i, (ticker, row) in enumerate(df_top.iterrows(), 1):
                name = stock.get_market_ticker_name(ticker)
                df_ohlcv = stock.get_market_ohlcv_by_date(krx_date, krx_date, ticker)
                change_rate = 0.0
                close_price = 0
                if not df_ohlcv.empty:
                    close_price = df_ohlcv['종가'].iloc[0]
                    change_rate = df_ohlcv['등락률'].iloc[0] if '등락률' in df_ohlcv.columns else 0.0
                
                realtime_top_stocks += f"{i}. {name} ({close_price:,}원, {change_rate:+.2f}%)\n"
                
                # 상위 종목들의 섹터를 실시간으로 수집
                sec = classify_sector(name)
                if sec not in detected_sectors:
                    detected_sectors.append(sec)
        else:
            realtime_top_stocks = "실시간 거래대금 데이터 집계 준비 중\n"
    except:
        realtime_top_stocks = "실시간 데이터 조회 중 오류 발생\n"

    # 부족한 섹터는 기본 실시간 트렌드 섹터로 채우기
    default_sectors = ["반도체 및 AI 밸류체인", "2차전지 및 소재", "바이오 및 헬스케어", "방산 및 중공업"]
    for ds in default_sectors:
        if ds not in detected_sectors:
            detected_sectors.append(ds)

    sec_1 = detected_sectors[0]
    sec_2 = detected_sectors[1]
    sec_3 = detected_sectors[2]

    # 2. 국내 지수
    kospi_val, kosdaq_val, kospi_rate = "집계 중", "집계 중", 0.0
    try:
        k_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kd_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if not k_df.empty:
            kospi_rate = k_df['등락률'].iloc[0]
            kospi_val = f"{k_df['종가'].iloc[0]:,.2f} ({kospi_rate:+.2f}%)"
        if not kd_df.empty: 
            kosdaq_val = f"{kd_df['종가'].iloc[0]:,.2f} ({kd_df['등락률'].iloc[0]:+.2f}%)"
    except: pass

    # 3. 미국 지수 및 거시경제
    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_str = ""
    us_rates = []
    for name, sym in us_indices.items():
        try:
            t = yf.Ticker(sym).history(period="2d")
            cur, prev = t['Close'].iloc[-1], t['Close'].iloc[-2]
            rate = ((cur - prev) / prev) * 100
            us_rates.append(rate)
            us_str += f"- {name}: {cur:,.2f} ({rate:+.2f}%)\n"
        except:
            us_str += f"- {name}: 데이터 집계 중\n"

    macro = {}
    for name, sym in {"환율": "USDKRW=X", "유가": "CL=F", "국채10년": "^TNX", "VIX": "^VIX"}.items():
        try:
            h = yf.Ticker(sym).history(period="1d")
            macro[name] = f"{h['Close'].iloc[-1]:,.2f}" if not h.empty else "N/A"
        except:
            macro[name] = "N/A"

    # 4. 실시간 시장 분위기 동적 진단
    market_mood = "안정적 순환매"
    if kospi_rate < -1.0 or (us_rates and min(us_rates) < -1.5):
        market_mood = "변동성 확대 및 하방 압력 주의"
    elif kospi_rate > 1.0 or (us_rates and max(us_rates) > 1.5):
        market_mood = "강력한 매수세 유입 및 상승 주도"

    # ==========================================
    # 파트별 메시지 구성 (100% 실시간 동적)
    # ==========================================
    part1 = f"""📅 {today} 실시간 마켓 리포트 ({time_label}) [1/3]
────────────────────
🌍 오늘 시장 실시간 진단
- 시장 분위기: {market_mood}
- 실시간 수급 유입 종목 중심 선별 대응.

🇰🇷 국내증시 ({krx_date})
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}

🔥 [실시간 국내 거래대금 상위 TOP 5]
{realtime_top_stocks.strip()}
"""

    part2 = f"""📊 글로벌 증시 및 실시간 섹터 [2/3]
────────────────────
🇺🇸 미국 주요 지수 (실시간)
{us_str.strip()}

📊 거시경제 지표 (실시간)
- 원/달러 환율: {macro.get('환율', 'N/A')}원
- WTI유: ${macro.get('유가', 'N/A')}
- 미국채 10년물: {macro.get('국채10년', 'N/A')}
- VIX 공포지수: {macro.get('VIX', 'N/A')}

⑪ 실시간 수급 주도 섹터 순위
1위: {sec_1} (거래대금 최상위 집중)
2위: {sec_2} (수급 유입 포착)
3위: {sec_3} (순환매 대응 영역)
"""

    part3 = f"""🎯 실시간 맞춤 투자 전략 및 리스크 [3/3]
────────────────────
⭐ 오늘의 실시간 대응 전략
- 시장 분위기({market_mood})에 따라 무리한 추격 매수보다는 실시간 수급 상위 종목의 눌림목을 노리십시오.

⚠️ 실시간 리스크 체크
- 실시간 환율({macro.get('환율', 'N/A')}원)과 VIX({macro.get('VIX', 'N/A')}) 변동에 따른 외국인 수급 이탈 여부를 예의주시하세요.
"""

    return part1, part2, part3

def job():
    kst = pytz.timezone('Asia/Seoul')
    print(f"[{datetime.now(kst)}] 완전 동적 실시간 리포트 전송 시작...")
    
    p1, p2, p3 = generate_analyst_briefings()
    
    send_kakao_message(p1)
    send_kakao_message(p2)
    send_kakao_message(p3)
        
    print("완전 동적 실시간 리포트 전송 완료!")

if __name__ == "__main__":
    job()
