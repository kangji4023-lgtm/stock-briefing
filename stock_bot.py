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
# 2. 주식 데이터 수집 및 상세 브리핑 내용 생성
# ==========================================================
def get_stock_briefing():
    try:
        # 오늘 날짜를 동적으로 가져오기 (하드코딩 방지)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        briefing_text = f"📈 {today_str} 주식 브리핑 (오전 7시 모닝 브리핑)\n"
        briefing_text += "⚡ 실시간 시장 정밀 분석 리포트\n\n"
        briefing_text += "🇰🇷 국내 주요 주도주\n"
        
        # 분석할 국내 주요 종목 예시 (사용자님의 기존 종목 리스트로 변경 가능)
        stocks = {
            "LG에너지솔루션": "373220.KS",
            "삼성바이오로직스": "207940.KS"
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
                
                # 기술적 지표 간이 계산 (MACD, RSI 등)
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
                briefing_text += f"{idx}. {name}: 데이터 수신 실패\n\n"
            idx += 1
                
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

☆☆<.github/workflows/run.yml>☆☆
name: Stock Briefing Bot

on:
  schedule:
    # 한국 시간(KST) 기준 매일 오전 7시 정각 실행 (UTC 전날 22시)
    - cron: '0 22 * * *'
    
  workflow_dispatch: # 수동 실행 버튼 활성화

jobs:
  run-bot:
    runs-on: ubuntu-latest
    
    env:
      TZ: Asia/Seoul

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install numpy pandas requests pytz yfinance

      - name: Run stock briefing script
        run: |
          if [ -f "stock_bot.py" ]; then
            python stock_bot.py
          else
            echo "Error: stock_bot.py not found!"
            exit 1
          fi
        env:
          TZ: Asia/Seoul
          KAKAO_REST_API_KEY: ${{ secrets.KAKAO_REST_API_KEY }}
          KAKAO_REFRESH_TOKEN: ${{ secrets.KAKAO_REFRESH_TOKEN }}

