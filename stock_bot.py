import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ==========================================================
# 1. 환경 변수 및 카카오 토큰 설정
# ==========================================================
# GitHub Secrets에 등록된 키를 환경변수에서 안전하게 가져옵니다.
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")

def refresh_access_token(rest_api_key, refresh_token):
    """카카오 리프레시 토큰을 이용해 새로운 액세스 토큰을 재발급 받는 함수"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    result = response.json()
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print("토큰 갱신 실패 응답:", result)
        return None

def send_to_kakao(text):
    """발급받은 토큰으로 카카오톡 '나에게 보내기' 메시지를 전송하는 함수"""
    access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
    
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
# 2. 주식 데이터 수집 및 브리핑 내용 생성
# ==========================================================
def get_stock_briefing():
    try:
        # 예시: 주요 지수 (S&P 500, 나스닥 등) 데이터 가져오기
        tickers = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "US Dollar/KRW": "USDKRW=X"}
        
        briefing_text = "[📈 오늘의 모닝 주식 브리핑]\n\n"
        
        for name, symbol in tickers.items():
            data = yf.Ticker(symbol).history(period="2d")
            if len(data) >= 2:
                close_price = data['Close'].iloc[-1]
                prev_price = data['Close'].iloc[-2]
                diff = close_price - prev_price
                diff_percent = (diff / prev_price) * 100
                
                sign = "📈 +" if diff > 0 else "📉 "
                briefing_text += f"• {name}: {close_price:,.2f} ({sign}{diff_percent:.2f}%)\n"
            else:
                briefing_text += f"• {name}: 데이터 확인 불가\n"
                
        return briefing_text
    except Exception as e:
        return f"[주식 봇 오류 발생]\n내용: {str(e)}"


# ==========================================================
# 3. 메인 실행부
# ==========================================================
if __name__ == "__main__":
    print("주식 브리핑 봇 실행 중...")
    
    # 1. 주식 브리핑 텍스트 생성
    message = get_stock_briefing()
    print("생성된 메시지:\n", message)
    
    # 2. 카카오톡으로 전송
    send_to_kakao(message)
