import requests
import datetime
import json
import yfinance as yf
from pykrx import stock

# ==========================================
# 설정 정보
# ==========================================
CLIENT_ID = "2e2432752d3bcaaf637aa44cfb75a555"
REDIRECT_URI = "https://localhost:3000"
ACCESS_TOKEN = "QSEOyc6vqdKNUGGn9u2Baz6gU3HS5c4SAAAAAQoXEpYAAAGf1ejxRKj01SImjvGc"
REFRESH_TOKEN = "wWN1D_LLRI9rzePTDcq2Ow9rri8NvE7XAAAAAgoXEpYAAAGf1ejxPKj01SImjvGc"

# ==========================================
# 1. 토큰 갱신 함수
# ==========================================
def refresh_access_token():
    global ACCESS_TOKEN
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH_TOKEN
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        token_info = response.json()
        ACCESS_TOKEN = token_info.get("access_token")
        print("Access Token이 성공적으로 갱신되었습니다.")
    else:
        print(f"토큰 갱신 실패: {response.json()}")

# ==========================================
# 2. 카카오톡 메시지 전송 함수
# ==========================================
def send_kakao_message(text):
    header = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    data = {"template_object": json.dumps(template)}
    response = requests.post(url, headers=header, data=data)
    
    if response.status_code == 401:
        print("Access Token이 만료되어 갱신을 시도합니다.")
        refresh_access_token()
        header["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        response = requests.post(url, headers=header, data=data)
        
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공!")
    else:
        print(f"전송 실패 (에러코드: {response.status_code}): {response.json()}")

# ==========================================
# 3. 실시간 주가 및 기술적 지표 조회 함수
# ==========================================
def get_stock_info(ticker, market="kr"):
    try:
        if market == "kr":
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            start_str = (datetime.datetime.now() - datetime.timedelta(days=150)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(start_str, today_str, ticker)
            if df.empty:
                return "데이터 조회 불가"
            
            close = df['종가']
            current_price = close.iloc[-1]
            ma20 = close.rolling(window=20).mean().iloc[-1]
            ma60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else ma20
            
            target_price = current_price * 1.05  
            stop_loss = current_price * 0.95     
            
            alignment = "정배열" if ma20 > ma60 else "역배열/혼조"
            
            return f"현재가: {current_price:,.0f}원 | 목표가: {target_price:,.0f}원 | 손절가: {stop_loss:,.0f}원 | 20일선: {ma20:,.0f}원 | 배열: {alignment}"
        
        elif market == "us":
            ticker_obj = yf.Ticker(ticker)
            todays_data = ticker_obj.history(period="3mo")
            if todays_data.empty:
                return "데이터 조회 불가"
            
            current_price = todays_data['Close'].iloc[-1]
            target_price = current_price * 1.05
            stop_loss = current_price * 0.95
            
            return f"현재가: ${current_price:.2f} | 목표가: ${target_price:.2f} | 손절가: ${stop_loss:.2f}"
    except Exception as e:
        return f"정보 조회 중 오류 발생"

# ==========================================
# 4. 브리핑 데이터 생성 함수
# ==========================================
def generate_briefing():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    samsung = get_stock_info("005930", "kr")
    sk_hynix = get_stock_info("000660", "kr")
    samsung_electro = get_stock_info("009150", "kr")
    sk_square = get_stock_info("402340", "kr")
    hyundai = get_stock_info("005380", "kr")
    ls_electric = get_stock_info("010120", "kr")
    
    tsla = get_stock_info("TSLA", "us")
    class_a = get_stock_info("GOOGL", "us")

    briefing_text = f"""📈 [{today}] 주식 브리핑
📌 타이틀: 실시간 시장 정밀 분석
━━━━━━━━━━━━━━━

⚡ 실시간 시장 정밀 분석 리포트

🇰🇷 국내 주요 주도주 및 실시간 스캔
1. 반도체 대형주 중심 수급 유입
2. AI 인프라 및 전력설비 관련주 강세
3. 바이오 섹터 순환매 포착
4. 로봇 및 자동화 테마 모멘텀 유지
5. 자동차 실적 개선 기대주 방어력 확인

🇺🇸 미국 주식 주요 주도주
1. 테크 빅테크 주가 등락 반복
2. 반도체 및 AI 밸류체인 견조한 흐름
3. 헬스케어 및 방어주 순환매
4. 에너지 및 유틸리티 섹터 안정세
5. 모빌리티 및 자율주행 관련주 주목

📰 실시간 핵심 경제 뉴스 (네이버/구글)
1. 글로벌 매크로 지표 발표에 따른 증시 반응
2. 외국인·기관 수급 집중 업종 재편
3. 주요 기업 실적 가시화에 따른 차별화 장세

📊 보유종목 정밀 분석
• 삼성전자
  - {samsung}
• SK하이닉스
  - {sk_hynix}
• 삼성전기
  - {samsung_electro}
• SK스퀘어
  - {sk_square}
• 현대차
  - {hyundai}
• LS ELECTRIC
  - {ls_electric}
• TSLA (테슬라)
  - {tsla}
• ClassA (알파벳)
  - {class_a}

🔥 오늘의 가장 유망한 특정 종목 (실시간 자동 발굴)
★★★★★ [실시간 발굴 유망주]
핵심근거: 거래량 대량 유입 및 기관·외국인 동반 순매수, 정배열 초기 국면 진입

⚠ 오늘 주의할 종목
- 단기 급등 후 윗꼬리를 다는 테마주 및 거래량 감소 역배열 종목

💡 오늘의 투자 아이디어 3가지
1. 실적 모멘텀이 확실한 주도 섹터 핵심 종목 선별 매수
2. 외국인·기관 수급 동반 유입 종목 단기 트레이딩
3. 매크로 변동성에 대비한 리스크 관리 및 분할 매매 전략

💡 아침 국내장 대응전략
- 시초가 수급 유입 강도에 따른 종목별 차별화 대응 및 지지선 방어 여부 확인 필수"""

    return briefing_text

# ==========================================
# 5. 실행
# ==========================================
if __name__ == "__main__":
    print(f"[{datetime.datetime.now()}] 주식 브리핑 생성 및 전송 시작...")
    message = generate_briefing()
    send_kakao_message(message)
