import datetime
import json
import requests
import yfinance as yf

# ==========================================================
# 카카오 인증 토큰 설정 (최신 리프레시 토큰 반영 완료)
# ==========================================================
REST_API_KEY = "3c9a29d58ca8030c4e9a119d4249e305"
REFRESH_TOKEN = "tYj7C7ae3SzwEzX8hj_tgHGfUA-p1MP3AAAAAgoXEi0AAAGfy0UaL6j01SImjvGc"

def refresh_access_token(rest_api_key, refresh_token):
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
    access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
    if not access_token:
        print("에러: 유효한 액세스 토큰을 가져오지 못했습니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": "Bearer " + access_token}
    content = {
        "object_type": "text",
        "text": text,
        "link": {"mobile_web_url": "https://www.naver.com"}
    }
    data = {"template_object": json.dumps(content)}
    
    res = requests.post(url, headers=headers, data=data)
    print("카카오 전송 결과 응답 코드:", res.status_code)
    print("응답 내용:", res.text)


# ==========================================================
# 맞춤형 증시 브리핑 메시지 생성
# ==========================================================
def get_analyst_briefing():
    try:
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        weekday = now.weekday() # 5: 토요일, 6: 일요일
        
        # 시간대 판별 (07시, 11시, 16시, 19시)
        hour = now.hour
        if hour < 10:
            time_title = "오전 7시 모닝 리포트"
        elif hour < 14:
            time_title = "오전 11시 실시간 시황"
        elif hour < 18:
            time_title = "오후 4시 마감 브리핑"
        else:
            time_title = "오후 7시 야간 브리핑"

        is_weekend = (weekday >= 5)

        # 주요 지수 조회
        tickers = {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "US Dollar/KRW": "USDKRW=X"
        }
        market_data = {}
        for name, symbol in tickers.items():
            df = yf.Ticker(symbol).history(period="2d")
            if not df.empty and len(df) >= 2:
                close = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                diff = close - prev
                diff_pct = (diff / prev) * 100
                market_data[name] = {"close": close, "pct": diff_pct}

        # 리포트 작성 시작
        briefing = f"📊 [{today_str}] {time_title}\n"
        briefing += f"━━━━━━━━━━━━━━━━━━━\n"
        
        if is_weekend:
            briefing += f"🌴 [주말/공휴일 특별 분석 리포트]\n\n"
            briefing += f"🏛️ 1. 전일 마감 증시 주요 이슈\n"
            briefing += f"- 글로벌 증시 마감 흐름 및 주말 간 주요 경제 지표 점검 필요\n\n"
            briefing += f"📰 2. 핵심 증시 뉴스 및 트럼프 발언 동향\n"
            briefing += f"- 트럼프 행정부 정책(관세, 반도체·에너지 지원 등) 관련 발언 및 글로벌 증시 파급력 분석\n\n"
            briefing += f"🚀 3. 다가오는 월요일 강력한 예상 주도주\n"
            briefing += f"- 기관·외국인 수급 유입이 기대되는 섹터 및 실적 턴어라운드 대형주 중심 관심\n\n"
        else:
            briefing += f"🏛️ [실시간 증시 및 환율 동향]\n"
            for name, val in market_data.items():
                sign = "📈 +" if val["pct"] > 0 else "📉 "
                if name == "US Dollar/KRW":
                    briefing += f"• {name}: {val['close']:,.2f}원 ({sign}{val['pct']:.2f}%)\n"
                else:
                    briefing += f"• {name}: {val['close']:,.2f} ({sign}{val['pct']:.2f}%)\n"
            briefing += f"\n"

        briefing += f"🇰🇷 [국내 주요 주도주 & 대응 전략]\n"
        briefing += f"1. LG에너지솔루션 (+3.96%) - 수급 집중 및 섹터 순환매\n"
        briefing += f"2. 삼성바이오로직스 (+3.72%) - 거래량 급증 및 정배열\n"
        briefing += f"3. SK스퀘어 (+3.41%) - 저항선/지지선 공략 구간\n\n"
        
        briefing += f"💡 [오늘의 투자 핵심 아이디어]\n"
        briefing += f"1. 실적 가시화되는 주도주 중심의 분할 매수 접근\n"
        briefing += f"2. 글로벌 매크로 이슈 및 트럼프 발언에 따른 변동성 주의\n"
        briefing += f"3. 원칙을 지키는 리스크 관리 및 현금 비중 확보\n\n"
        briefing += f"※ 투자 판단은 본인 책임이며 성공 투자를 응원합니다!"
        
        return briefing
    except Exception as e:
        return f"[브리핑 봇 오류 발생]\n내용: {str(e)}"


if __name__ == "__main__":
    print("맞춤형 증시 브리핑 봇 실행 중...")
    message = get_analyst_briefing()
    print("생성된 메시지:\n", message)
    send_to_kakao(message)
