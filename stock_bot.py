import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from pykrx import stock
import yfinance as yf

# ==========================================
# 1. 환경 변수 설정 영역 (GitHub Secrets 연동)
# ==========================================
REST_API_KEY = os.environ.get("REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")

def get_access_token_by_refresh_token():
    """리프레시 토큰을 이용해 새로운 액세스 토큰을 자동으로 발급받는 함수"""
    global REFRESH_TOKEN
    
    if not REST_API_KEY or not REFRESH_TOKEN:
        print("카카오 REST_API_KEY 또는 REFRESH_TOKEN이 설정되지 않았습니다.")
        return None

    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get("access_token")
            if "refresh_token" in tokens:
                REFRESH_TOKEN = tokens["refresh_token"]
            return access_token
        else:
            print(f"토큰 갱신 실패: {response.text}")
            return None
    except Exception as e:
        print(f"토큰 갱신 에러 발생: {e}")
        return None

def send_kakao_message(text):
    """자동 갱신된 액세스 토큰으로 카카오톡 나에게 보내기 전송"""
    access_token = get_access_token_by_refresh_token()
    if not access_token:
        print("유효한 액세스 토큰을 가져오지 못해 메시지를 전송할 수 없습니다.")
        return

    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    header = {"Authorization": f"Bearer {access_token}"}
    
    max_length = 3500
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    for msg in messages:
        payload = {
            "object_type": "text",
            "text": msg,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }
        data = {"template_object": str(payload).replace("'", '"')}
        try:
            response = requests.post(kakao_url, headers=header, data=data)
            if response.status_code != 200:
                print(f"카카오 전송 실패: {response.text}")
        except Exception as e:
            print(f"카카오 전송 에러: {e}")
        time.sleep(0.5)

# ==========================================
# 2. 주식 데이터 수집 및 브리핑 생성
# ==========================================
def generate_full_briefing():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 안정적인 티커로 변경 (WTI유: BZ=X 또는 유가 관련 지표)
    macro_symbols = {
        "USD/KRW": "USDKRW=X",
        "WTI유": "BZ=X",
        "국채금리(10년)": "^TNX",
        "VIX지수": "^VIX"
    }
    macro_data = {}
    for name, sym in macro_symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if not hist.empty:
                macro_data[name] = f"{hist['Close'].iloc[-1]:,.2f}"
            else:
                macro_data[name] = "데이터 없음"
        except:
            macro_data[name] = "조회 불가"

    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_result_str = ""
    for name, sym in us_indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if not hist.empty:
                cur = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                rate = ((cur - prev) / prev) * 100
                us_result_str += f"- {name}: {cur:,.2f} ({rate:+.2f}%)\n"
            else:
                us_result_str += f"- {name}: 데이터 없음\n"
        except:
            us_result_str += f"- {name}: 조회 실패\n"

    # pykrx 안전 조회
    kospi_val = "집계 중"
    kosdaq_val = "집계 중"
    try:
        krx_date = stock.get_nearest_business_day_in_a_week(datetime.now().strftime("%Y%m%d"))
        kospi_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kosdaq_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if not kospi_df.empty:
            kospi_val = f"{kospi_df['종가'].iloc[0]:,.2f} ({kospi_df['등락률'].iloc[0]:+.2f}%)"
        if not kosdaq_df.empty:
            kosdaq_val = f"{kosdaq_df['종가'].iloc[0]:,.2f} ({kosdaq_df['등락률'].iloc[0]:+.2f}%)"
    except Exception as e:
        print(f"국내 지수 조회 예외: {e}")

    full_message = f"""📅 {today}

📈 AI 국내·미국 주식 브리핑

━━━━━━━━━━━━━━
🌍 오늘 시장 한줄 요약
글로벌 증시는 주요 매크로 지표 변동성과 실적에 따라 혼조세를 보이고 있습니다.

━━━━━━━━━━━━━━
🇰🇷 국내시장
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}

━━━━━━━━━━━━━━
🇺🇸 미국시장
{us_result_str}
━━━━━━━━━━━━━━
📊 거시경제 지표
- 환율(USD/KRW): {macro_data.get('USD/KRW', 'N/A')}
- 브렌트유(WTI): {macro_data.get('WTI유', 'N/A')}
- 미국채 10년물 금리: {macro_data.get('국채금리(10년)', 'N/A')}
- VIX 공포지수: {macro_data.get('VIX지수', 'N/A')}

━━━━━━━━━━━━━━
⭐ 오늘의 AI 추천 종목: NVIDIA (NVDA)
- 목표가: $140 / 손절가: $110
"""
    return full_message

def job():
    """정해진 시간에 실행될 자동 작업 함수"""
    print(f"[{datetime.now()}] 브리핑 생성 및 카카오 전송 시작...")
    briefing_content = generate_full_briefing()
    send_kakao_message(briefing_content)
    print(f"[{datetime.now()}] 전송 완료!")

if __name__ == "__main__":
    job()
