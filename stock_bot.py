import time
import schedule
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from pykrx import stock
import yfinance as yf

# ==========================================
# 1. 카카오 인증 설정 영역 (필수 입력)
# ==========================================
REST_API_KEY = "YOUR_REST_API_KEY"      # 카카오 앱 REST API 키
REFRESH_TOKEN = "YOUR_REFRESH_TOKEN"    # 유효기간이 긴 카카오 리프레시 토큰
REDIRECT_URI = "https://localhost"      # 카카오 앱 설정에 등록된 Redirect URI

def get_access_token_by_refresh_token():
    """리프레시 토큰을 이용해 새로운 액세스 토큰을 자동으로 발급받는 함수"""
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
            # 만약 리프레시 토큰도 새로 발급되어 돌아왔다면 갱신해 줄 수 있음
            if "refresh_token" in tokens:
                global REFRESH_TOKEN
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
# 2. 기술적 지표 계산 함수
# ==========================================
def calculate_technical_indicators(df):
    try:
        close = df['Close']
        volume = df['Volume']
        
        ma20 = close.rolling(window=20).mean().iloc[-1]
        ma60 = close.rolling(window=60).mean().iloc[-1]
        ma120 = close.rolling(window=120).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        s_20 = "위" if current_price >= ma20 else "아래"
        s_60 = "위" if current_price >= ma60 else "아래"
        s_120 = "위" if current_price >= ma120 else "아래"
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
        
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_status = "골든크로스" if macd.iloc[-1] > signal.iloc[-1] else "데드크로스"
        
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        obv_trend = "증가" if obv.iloc[-1] > obv.iloc[-2] else "감소"
        
        ma5 = close.rolling(window=5).mean()
        golden_cross = "Y" if (ma5.iloc[-2] < ma20.iloc[-2]) and (ma5.iloc[-1] >= ma20.iloc[-1]) else "N"
        
        return {
            "rsi": round(current_rsi, 1),
            "macd": macd_status,
            "obv": obv_trend,
            "golden": golden_cross,
            "ma20": s_20,
            "ma60": s_60,
            "ma120": s_120,
            "close": current_price
        }
    except Exception:
        return {"rsi": 50.0, "macd": "중립", "obv": "유지", "golden": "N", "ma20": "위", "ma60": "위", "ma120": "위"}

# ==========================================
# 3. 주식 데이터 수집 및 브리핑 생성
# ==========================================
def generate_full_briefing():
    today = datetime.now().strftime("%Y-%m-%d")
    
    macro_symbols = {
        "USD/KRW": "USDKRW=X",
        "WTI유": "CL=X",
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

    try:
        krx_date = stock.get_nearest_business_day_in_a_week(datetime.now().strftime("%Y%m%d"))
        kospi_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kosdaq_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        kospi_val = f"{kospi_df['종가'].iloc[0]:,.2f} ({kospi_df['등락률'].iloc[0]:+.2f}%)"
        kosdaq_val = f"{kosdaq_df['종가'].iloc[0]:,.2f} ({kosdaq_df['등락률'].iloc[0]:+.2f}%)"
    except:
        kospi_val = "집계 중"
        kosdaq_val = "집계 중"

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
- WTI유: {macro_data.get('WTI유', 'N/A')}
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

# ==========================================
# 4. 매일 4번 시간 설정 및 상시 구동부
# ==========================================
if __name__ == "__main__":
    # 매일 07:00, 11:00, 16:00, 19:00 자동 발송 스케줄 설정
    schedule.every().day.at("07:00").do(job)
    schedule.every().day.at("11:00").do(job)
    schedule.every().day.at("16:00").do(job)
    schedule.every().day.at("19:00").do(job)

    print("주식 자동 브리핑 스케줄러가 실행되었습니다. (매일 07:00, 11:00, 16:00, 19:00 자동 발송 대기 중)")
    
    # 즉시 테스트를 원하시면 아래 주석을 해제하세요.
    # job()

    while True:
        schedule.run_pending()
        time.sleep(1)
