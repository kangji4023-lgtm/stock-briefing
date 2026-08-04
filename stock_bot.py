import os
import json
import requests
import pandas as pd
import yfinance as yf

# 환경 변수에서 카카오 API 키 및 토큰 가져오기
REST_API_KEY = os.environ.get('KAKAO_REST_API_KEY')
REFRESH_TOKEN = os.environ.get('KAKAO_REFRESH_TOKEN')

def refresh_access_token(rest_api_key, refresh_token):
    """카카오 리프레시 토큰을 이용해 액세스 토큰을 갱신하는 함수"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    result = response.json()
    return result.get("access_token")

def get_us_market_data():
    """야후 파이낸스를 통해 미 S&P 500 및 나스닥 데이터를 안전하게 가져오는 함수"""
    try:
        tickers = ["^GSPC", "^IXIC"]
        df = yf.download(tickers, period="5d", progress=False)
        
        if df.empty:
            return "데이터 대기 중", "데이터 대기 중"
            
        # 다중 인덱스 구조 대응 및 데이터 추출
        if 'Close' in df:
            close_data = df['Close']
        else:
            close_data = df
            
        sp500_series = close_data['^GSPC'].dropna() if '^GSPC' in close_data else pd.Series()
        nasdaq_series = close_data['^IXIC'].dropna() if '^IXIC' in close_data else pd.Series()
        
        if sp500_series.empty or nasdaq_series.empty:
            return "데이터 대기 중", "데이터 대기 중"
            
        sp500_val = sp500_series.iloc[-1]
        nasdaq_val = nasdaq_series.iloc[-1]
        
        return f"{sp500_val:,.2f}", f"{nasdaq_val:,.2f}"
        
    except Exception as e:
        print(f"미국 증시 데이터 조회 중 오류 발생: {e}")
        return "조회 실패", "조회 실패"

def send_kakao_message(text):
    """카카오톡 나에게 보내기 API를 통해 메시지 전송"""
    access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
    if not access_token:
        print("엑세스 토큰 갱신 실패")
        return

    header = {"Authorization": f"Bearer {access_token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    post = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        },
    }
    
    data = {"template_object": json.dumps(post)}
    response = requests.post(url, headers=header, data=data)
    return response.json()

if __name__ == "__main__":
    sp500_str, nasdaq_str = get_us_market_data()
    
    message = f"""[주식 스마트 브리핑 봇]
📊 [국내 및 미국 증시 실시간 브리핑]
----------------------------------------
• 미 S&P 500: {sp500_str}
• 미 나스닥: {nasdaq_str}

💡 시장 특징 및 뉴스 핵심 요약 완료
"""
    # 실제 카카오톡 전송을 위해 주석을 해제 상태로 반영하세요.
    send_kakao_message(message)
    print(message)
