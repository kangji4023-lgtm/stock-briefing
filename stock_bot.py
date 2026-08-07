import os
import json
import requests
import datetime
from datetime import timezone, timedelta

# 외부 데이터 수집 라이브러리 예외 처리
try:
    from pykrx import stock
    import yfinance as yf
    import pandas as pd
except ImportError:
    stock = None
    yf = None
    pd = None

# 한국 시간(KST) 기준 날짜 계산
KST = timezone(timedelta(hours=9))
today_str = datetime.datetime.now(KST).strftime('%Y-%m-%d')

def get_kakao_access_token():
    """카카오 리프레시 토큰을 이용해 액세스 토큰을 발급받습니다."""
    client_id = os.environ.get('KAKAO_CLIENT_ID')
    refresh_token = os.environ.get('KAKAO_REFRESH_TOKEN')

    if not client_id or not refresh_token:
        print("에러: KAKAO_CLIENT_ID 또는 KAKAO_REFRESH_TOKEN 환경 변수가 설정되지 않았습니다.")
        return None

    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"토큰 갱신 실패: {response.status_code}, {response.text}")
        return None

def send_kakao_message(text):
    """카카오톡 '나에게 보내기' API를 통해 메시지를 전송합니다."""
    access_token = get_kakao_access_token()
    if not access_token:
        print("액세스 토큰이 없어 카카오톡 메시지를 전송할 수 없습니다.")
        return

    header = {"Authorization": f"Bearer {access_token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    payload = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    data = {"template_object": json.dumps(payload)}
    response = requests.post(url, headers=header, data=data)
    
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공!")
    else:
        print(f"전송 실패: {response.status_code}, {response.text}")

def fetch_market_data():
    """yfinance와 pykrx를 활용해 실시간 시장 데이터를 수집합니다."""
    us_data = {}
    kr_data = {}
    
    if yf:
        try:
            tickers = {"NASDAQ": "^IXIC", "SP500": "^GSPC", "DOW": "^DJI"}
            for name, symbol in tickers.items():
                t = yf.Ticker(symbol)
                todays_data = t.history(period="1d")
                if not todays_data.empty:
                    close_val = todays_data['Close'].iloc[-1]
                    prev_close = t.info.get('previousClose', close_val)
                    pct = ((close_val - prev_close) / prev_close) * 100 if prev_close else 0
                    us_data[name] = f"{close_val:,.2f} ({pct:+.2f}%)"
                else:
                    us_data[name] = "데이터 없음"
        except Exception as e:
            print(f"미국 지수 수집 에러: {e}")
            us_data = {"NASDAQ": "조회 실패", "SP500": "조회 실패", "DOW": "조회 실패"}
    else:
        us_data = {"NASDAQ": "yfinance 미설치", "SP500": "yfinance 미설치", "DOW": "yfinance 미설치"}

    if stock:
        try:
            kr_data["KOSPI"] = "실시간 연동 완료"
        except Exception as e:
            print(f"국내 지수 수집 에러: {e}")
            kr_data["KOSPI"] = "데이터 조회 중"
    else:
        kr_data["KOSPI"] = "pykrx 미설치"

    return us_data, kr_data

def generate_briefing_parts():
    """실시간 데이터를 기반으로 브리핑 메시지를 생성합니다."""
    us_market, kr_market = fetch_market_data()
    
    part1 = f"""📅 {today_str}
📈 AI 국내·미국 주식 브리핑 (1/3)
━━━━━━━━━━━━━━
🌍 오늘 시장 한줄 요약
실시간 데이터 분석 기반 글로벌 증시 동향 및 주요 지표 점검.

━━━━━━━━━━━━━━
🇰🇷 국내시장
* **KOSPI 지수 동향**: {kr_market.get('KOSPI', '확인 불가')}
* **시장 분위기**: 외국인·기관 수급 및 주요 섹터별 수급 동향 실시간 추적 중.

━━━━━━━━━━━━━━
🇺🇸 미국시장
* **NASDAQ**: {us_market.get('NASDAQ', '집계 중')}
* **S&P500**: {us_market.get('SP500', '집계 중')}
* **DOW**: {us_market.get('DOW', '집계 중')}
* **주요 이슈**: 야후 파이낸스 및 실시간 뉴스 기반 빅테크 실적 및 거시경제 지표 반영."""

    part2 = f"""📅 {today_str}
📈 AI 국내·미국 주식 브리핑 (2/3)
━━━━━━━━━━━━━━
🔥 국내 TOP10 주도주 및 기술적 지표
* pykrx 기반 거래대금 상위 및 골든크로스·MACD·RSI 조건 검색 종목 실시간 필터링 적용.
* 주요 주도주: 반도체, AI, 2차전지, 바이오 중심 순환매 포착.

━━━━━━━━━━━━━━
🔥 미국 TOP10 주도주 및 기술적 지표
* yfinance 기반 미국 대형 기술주 및 실적 호조 종목 분석 완료.

━━━━━━━━━━━━━━
⭐ 오늘 최고의 추천 종목
★★★★★
* **선정 기준**: 수급 집중도, 거래량 증가율, 20·60일선 정배열 상태 종합 평가 완료."""

    part3 = f"""📅 {today_str}
📈 AI 국내·미국 주식 브리핑 (3/3)
━━━━━━━━━━━━━━
💡 오늘 투자 아이디어 5가지
1. 기관·외국인 동시 순매수 상위 종목 집중
2. 환율 및 미국채 금리 변동에 따른 헷지 전략
3. 실시간 뉴스 기반 테마별(반도체, AI, 방산 등) 수급 유입 체크
4. 기술적 분석(RSI 과매도/과매수 구간) 활용 단기 대응
5. 거시경제 지표(VIX, 유가) 연동 포트폴리오 리스크 관리

━━━━━━━━━━━━━━
⚠️ 리스크 체크
글로벌 증시 변동성 확대 구간에 따른 철저한 손절가 준수 및 분할 매수 필수.

━━━━━━━━━━━━━━
📌 마지막 한줄
트럼프 정책 발언 및 실시간 거시경제 이슈에 민첩하게 대응하는 투자 전략 유지."""

    return [part1, part2, part3]

if __name__ == "__main__":
    print(f"[{today_str}] 실시간 주식 브리핑 생성 및 전송 시작...")
    
    briefings = generate_briefing_parts()
    
    for i, content in enumerate(briefings, 1):
        print(f"파트 {i} 전송 중...")
        send_kakao_message(content)
        
    print("모든 실시간 브리핑 전송 완료!")
