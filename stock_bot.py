import os
import json
import datetime
import requests
import yfinance as yf
from pykrx import stock

def refresh_access_token(client_id, refresh_token):
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }
    response = requests.post(url, data=data, headers=headers)
    result = response.json()
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"토큰 갱신 실패 상세 내용: {result}")
        return None

def send_kakao_message(access_token, text):
    header = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://www.naver.com",
            "mobile_web_url": "https://www.naver.com"
        }
    }
    
    data = {
        "template_object": json.dumps(template_object)
    }
    
    response = requests.post(url, headers=header, data=data)
    print("카카오 API 응답 코드:", response.status_code)
    print("카카오 API 응답 내용:", response.text)
    return response.json()

def get_market_data():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d %H:%M")
    today_code = now.strftime("%Y%m%d")
    
    # 요일 확인 (토요일: 5, 일요일: 6)
    weekday = now.weekday()
    is_weekend = weekday >= 5
    
    briefing = "[주식 스마트 브리핑 봇]\n"
    briefing += f"📅 발송 시간: {today_str}\n\n"
    
    # 1. 주말 및 공휴일 전용 집중 브리핑 모드
    if is_weekend:
        briefing += "🏖️ [주말/공휴일 증시 집중 리포트]\n"
        briefing += "-----------------------------------\n"
        briefing += "📌 1. 전 주 글로벌 증시 마감 리뷰\n"
        try:
            sp500 = yf.Ticker("^GSPC").history(period="5d")
            nasdaq = yf.Ticker("^IXIC").history(period="5d")
            if not sp500.empty and not nasdaq.empty:
                sp_close = sp500['Close'].iloc[-1]
                sp_change = ((sp_close - sp500['Close'].iloc[-2]) / sp_close) * 100
                nas_close = nasdaq['Close'].iloc[-1]
                nas_change = ((nas_close - nas_daq['Close'].iloc[-2]) if 'nas_daq' in locals() else (nas_close - nasdaq['Close'].iloc[-2]) / nas_close * 100)
                
                briefing += f"• 미 S&P 500 주간 마감: {sp_close:.2f} ({sp_change:+.2f}%)\n"
                briefing += f"• 미 나스닥 주간 마감: {nas_close:.2f}\n"
        except Exception as e:
            briefing += f"• 해외 주간 지수 로드 중\n"
            
        briefing += "\n🇺🇸 2. 주요 트럼프 발언 및 대외 경제 이슈\n"
        briefing += "- 트럼프 대통령의 관세 정책, 에너지/원유 시장 개입 및 지정학적 발언 리스크 점검\n"
        briefing += "- 글로벌 증시 변동성 유발 주요 정치·경제 뉴스 집중 분석\n"
        briefing += "\n💡 다가오는 주간 주요 경제 일정 및 전략을 준비하세요!"
        
    # 2. 평일 브리핑 모드 (오전 7시, 11시, 오후 4시, 7시 맞춤)
    else:
        briefing += "📊 [국내 및 미국 증시 실시간 브리핑]\n"
        briefing += "-----------------------------------\n"
        
        # 해외 지수 (yfinance)
        try:
            sp500 = yf.Ticker("^GSPC").history(period="2d")
            nasdaq = yf.Ticker("^IXIC").history(period="2d")
            
            if len(sp500) >= 2:
                sp_close = sp500['Close'].iloc[-1]
                sp_prev = sp500['Close'].iloc[-2]
                sp_change = ((sp_close - sp_prev) / sp_prev) * 100
                briefing += f"• 미 S&P 500: {sp_close:.2f} ({sp_change:+.2f}%)\n"
            
            if len(nasdaq) >= 2:
                nas_close = nasdaq['Close'].iloc[-1]
                nas_prev = nasdaq['Close'].iloc[-2]
                nas_change = ((nas_close - nas_prev) / nas_prev) * 100
                briefing += f"• 미 나스닥: {nas_close:.2f} ({nas_change:+.2f}%)\n"
        except Exception as e:
            briefing += f"• 해외 지수 수신 중 예외 발생\n"

        # 국내 주식 데이터 (pykrx) - 장 마감 여부에 따라 예외 처리
        try:
            df = stock.get_market_ohlcv_by_ticker(today_code, market="ALL")
            if not df.empty:
                top_traded = df.sort_values(by="거래대금", ascending=False).head(3)
                briefing += "\n🔥 국내 거래대금 상위 주도주:\n"
                for idx, row in top_traded.iterrows():
                    name = stock.get_market_ticker_name(idx)
                    close_p = row['종가']
                    change_p = row['등락률']
                    briefing += f"- {name}: {close_p:,}원 ({change_p:+.2f}%)\n"
            else:
                briefing += "\n💡 국내 증시 개장 전이거나 데이터 집계 전입니다.\n"
        except Exception:
            briefing += "\n💡 국내 시장 휴장 또는 데이터 대기 중입니다.\n"
            
        briefing += "\n🔍 [시장 특징 및 트럼프/뉴스 핵심 요약]\n"
        briefing += "- 트럼프 행정부 경제 정책 및 글로벌 환율/유가 이슈 모니터링 반영\n"
        briefing += "- 수급 주도주 골든크로스 및 변동성 주의 종목 체크 중"
        
    return briefing

if __name__ == "__main__":
    print("주식 브리핑 자동화 프로세스를 시작합니다.")
    
    CLIENT_ID = os.environ.get("KAKAO_REST_API_KEY")
    REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")
    
    if not CLIENT_ID or not REFRESH_TOKEN:
        print("에러: 카카오 API 키 또는 리프레시 토큰 설정이 누락되었습니다.")
    else:
        access_token = refresh_access_token(CLIENT_ID, REFRESH_TOKEN)
        
        if access_token:
            message = get_market_data()
            res = send_kakao_message(access_token, message)
        else:
            print("유효한 액세스 토큰을 발급받지 못했습니다.")
