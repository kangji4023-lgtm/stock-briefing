import datetime
import json
import os
import requests
import yfinance as yf

# ==========================================================
# 1. 카카오 API 설정 (본인의 REST API Key와 리프레시 토큰 입력)
# ==========================================================
REST_API_KEY = "2e2432752d3bcaaf637aa44cfb75a555"
REFRESH_TOKEN = "tYj7C7ae3SzwEzX8hj_tgHGfUA-p1MP3AAAAAgoXEi0AAAGfy0UaL6j01SImjvGc"

def refresh_access_token():
    """리프레시 토큰을 이용해 새로운 액세스 토큰을 재발급 받는 함수"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN
    }
    response = requests.post(url, data=data)
    result = response.json()
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print("토큰 갱신 실패 응답:", result)
        return None

def send_to_kakao(text):
    """발급받은 액세스 토큰으로 카카오톡 '나에게 보내기' 메시지 전송"""
    access_token = refresh_access_token()
    
    if not access_token:
        print("에러: 유효한 액세스 토큰을 가져오지 못했습니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": "Bearer " + access_token
    }
    
    content = {
        "object_type": "text",
        "text": text,
        "link": {
            "mobile_web_url": "https://www.naver.com"
        }
    }
    
    data = {
        "template_object": json.dumps(content)
    }
    
    res = requests.post(url, headers=headers, data=data)
    print("카카오 전송 결과 응답 코드:", res.status_code)
    print("응답 내용:", res.text)


# ==========================================================
# 2. 시간대별 타이틀 및 주식 브리핑 내용 생성
# ==========================================================
def get_time_slot_title():
    now_hour = datetime.datetime.now().hour
    if 6 <= now_hour < 10:
        return "오전 7시 조기 브리핑 (모닝 리포트)"
    elif 10 <= now_hour < 13:
        return "오전 11시 오전장 실시간 리포트"
    elif 13 <= now_hour < 18:
        return "오후 3시 장마감 정밀 분석 리포트"
    else:
        return "오후 7시 야간 브리핑 (시장 정밀 분석)"

def get_stock_briefing():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        slot_title = get_time_slot_title()
        
        briefing_text = f"📈 {today_str} 주식 브리핑 ({slot_title})\n"
        briefing_text += "⚡ 실시간 시장 정밀 분석 리포트\n\n"
        briefing_text += "🇰🇷 국내 주요 주도주 모니터링\n"
        
        stocks = {
            "삼성전자": "005930.KS",
            "SK하이닉스": "000660.KS"
        }
        
        idx = 1
        for name, symbol in stocks.items():
            df = yf.Ticker(symbol).history(period="1mo")
            if not df.empty and len(df) >= 2:
                close_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                diff = close_price - prev_price
                diff_percent = (diff / prev_price) * 100
                
                sign = "(+ " if diff > 0 else "("
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1] if not rsi.empty else 50.0
                
                briefing_text += f"{idx}. {name} {sign}{diff_percent:.2f}%)\n"
                briefing_text += f"   - 현재가: {close_price:,.0f}원\n"
                briefing_text += f"   - RSI: {current_rsi:.1f}\n\n"
            else:
                briefing_text += f"{idx}. {name}: 데이터 수신 대기 중\n\n"
            idx += 1
            
        briefing_text += "💡 오늘도 성공적인 투자 되시길 바랍니다!"
        return briefing_text
    except Exception as e:
        return f"[주식 봇 오류 발생]\n내용: {str(e)}"


# ==========================================================
# 3. 메인 실행부
# ==========================================================
if __name__ == "__main__":
    print("주식 브리핑 봇 실행 중...")
    message = get_stock_briefing()
    print("생성된 메시지:\n", message)
    send_to_kakao(message)
