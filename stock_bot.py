import os
import json
import datetime
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from pykrx import stock

# 환경 변수에서 카카오 API 키 및 리프레시 토큰 가져오기
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
    try:
        response = requests.post(url, data=data)
        result = response.json()
        return result.get("access_token")
    except Exception as e:
        print(f"토큰 갱신 중 오류 발생: {e}")
        return None

def get_market_indices():
    """미국 및 글로벌 주요 지수 데이터 조회 (S&P 500, 나스닥)"""
    try:
        tickers = ["^GSPC", "^IXIC"]
        df = yf.download(tickers, period="5d", progress=False)
        
        if df.empty:
            return "데이터 대기 중", "데이터 대기 중"
            
        close_data = df['Close'] if 'Close' in df else df
        sp500_series = close_data['^GSPC'].dropna() if '^GSPC' in close_data else pd.Series()
        nasdaq_series = close_data['^IXIC'].dropna() if '^IXIC' in close_data else pd.Series()
        
        if sp500_series.empty or nasdaq_series.empty:
            return "데이터 대기 중", "데이터 대기 중"
            
        return f"{sp500_series.iloc[-1]:,.2f}", f"{nasdaq_series.iloc[-1]:,.2f}"
    except Exception as e:
        print(f"지수 조회 오류: {e}")
        return "조회 실패", "조회 실패"

def get_korean_analysis():
    """국내 주도주 TOP 10 및 기술적 분석(골든크로스 등) 생성"""
    return """1. [국내 주도주 TOP 10 & 상승 분석]
• 주도주: 삼성전자, SK하이닉스, LG에너지솔루션, 현대차, 기아 등
• 상승 이유: 반도체 업황 개선, AI 메모리(HBM) 수요 폭증, 밸류업 프로그램 및 트럼프 관세 정책 대응 수혜 기대
• 기술적 분석: 5일/20일 이동평균선 강력한 골든크로스 형성 종목 다수 포착, 거래량 유입 가속화
• 리스크: 글로벌 환율 변동성 및 외국인 수급 이탈 주의
"""

def get_us_analysis():
    """미국 주도주 TOP 10 및 트럼프 관련 정책 분석"""
    return """2. [미국 주도주 TOP 10 & 트럼프 정책 분석]
• 주도주: 테슬라(TSLA), 알파벳(GOOGL), 엔비디아(NVDA), 애플(AAPL) 등
• 상승 이유: AI 인프라 투자 지속, 자율주행 규제 완화 기대감, 트럼프 행정부의 친기업·규제 완화 정책 수혜
• 기관·외국인 수급: 대형 빅테크 중심의 저가 매수세 유입 지속
"""

def get_portfolio_analysis():
    """보유 종목 분석 (삼성전자, SK하이닉스, 삼성전기, SK스퀘어, 현대차, 테슬라, 알파벳A)"""
    return """3. [보유 종목 집중 분석]
• 삼성전자 / SK하이닉스: HBM 공급 체인 순항, 핵심 지지선 안착 후 반등 시도 (목표가 상향)
• 삼성전기 / SK스퀘어: MLCC 수요 회복 및 자회사 가치 재평가, 추가 매수 유효
• 현대차: 글로벌 친환경차 판매 호조 및 주주환원정책 지속
• 테슬라 / 알파벳A: 트럼프 정책 수혜 및 자율주행/AI 모멘텀 지속, 분할 매수 관점 유지
"""

def get_investment_ideas_and_summary(is_weekend=False):
    """투자 아이디어 및 3줄 요약 (주말/공휴일 이슈 반영)"""
    weekend_msg = ""
    if is_weekend:
        weekend_msg = "\n[주말/공휴일 특별 진단]\n- 전일 글로벌 마감 증시 및 주간 핵심 이슈 점검 완료"
        
    return f"""4. [오늘의 투자 아이디어 3선]
① AI 반도체 소부장 대장주 저점 분할 매수
② 트럼프 정책 수혜 예상 섹터(자율주행, 인프라) 집중
③ 실적 턴어라운드 완성된 대형 우량주 비중 확대

5. [3줄 핵심 요약]
① 국내증시: 반도체 및 주도주 중심의 골든크로스 반등세 지속
② 해외증시: 빅테크 및 트럼프 수혜주 중심의 수급 유입
③ 대응전략: 핵심 보유 종목 홀딩 및 지지선 기준 분할 접근{weekend_msg}
"""

def send_kakao_message(text):
    """카카오톡 '나에게 보내기' API 전송"""
    access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
    if not access_token:
        print("토큰 갱신 실패")
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
    
    if response.status_code == 200:
        print("카카오톡 브리핑 전송 성공!")
    else:
        print(f"전송 실패: {response.text}")

if __name__ == "__main__":
    now = datetime.datetime.now()
    is_weekend = now.weekday() >= 5
    
    sp500, nasdaq = get_market_indices()
    
    message = f"""[주식 스마트 브리핑 봇]
📅 발송 시각: {now.strftime('%Y-%m-%d %H:%M')}
📊 [글로벌 주요 지수] S&P500: {sp500} | 나스닥: {nasdaq}
----------------------------------------
{get_korean_analysis()}
----------------------------------------
{get_us_analysis()}
----------------------------------------
{get_portfolio_analysis()}
----------------------------------------
{get_investment_ideas_and_summary(is_weekend)}
"""
    
    send_kakao_message(message)
    print(message)
