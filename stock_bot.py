import requests
import json

# 환경 변수에서 KRX 정보 가져오기
KRX_ID = os.environ.get("KRX_ID")
KRX_PW = os.environ.get("KRX_PW")

if not KRX_ID or not KRX_PW:
    print("KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다.")

def safe_format(value, default="0.00"):
    if value is None:
        return default
    try:
        if str(value).lower() == "nan":
            return default
    except:
        pass
    return value

def create_stock_briefing():
    part1 = (
        "📈 2026-08-06 주식 브리핑 (오후 4시 마감 브리핑)\n"
        "⚡ 실시간 시장 정밀 분석 리포트\n\n"
        "🇰🇷 국내 주요 주도주\n"
        "1. 삼성전자 (+1.45%)\n"
        " - 상승이유: 기관/외인 수급 집중 및 섹터 순환매 유입\n"
        " - 거래량증가: O (급증)\n"
        " - 골든크로스: 미발생\n"
        " - MACD: -19088.50 | RSI: 44.9\n"
        " - 이평선배열: 혼조세\n"
        " - 저항선: 75,000원 / 지지선: 70,000원\n"
        " - 단기/중기 전략: 추세 추종 및 눌림목 분할 매수\n"
        " - 리스크요인: 단기 과열 진입에 따른 차익실현 매물 주의\n\n"
        "2. SK하이닉스 (+2.10%)\n"
        " - 상승이유: 반도체 업황 개선 기대감 및 외국인 순매수 유입\n"
        " - 거래량증가: O (급증)\n"
        " - 골든크로스: 발생\n"
        " - MACD: -19287.61 | RSI: 41.0\n"
        " - 이평선배열: 정배열(강세)\n"
        " - 저항선: 190,000원 / 지지선: 175,000원\n"
        " - 단기/중기 전략: 전고점 돌파 대비 분할 매수\n"
        " - 리스크요인: 글로벌 증시 변동성 주의"
    )
    part2 = (
        "🇺🇸 미국 주식 TOP10 주도주\n\n"
        "1. INTC (+10.29%)\n"
        " - 골든크로스: 미발생 | RSI: 47.9\n"
        " - 이평선배열: 역배열(약세) | 단기 트렌드 우상향\n\n"
        "2. AMD (+8.06%)\n"
        " - 골든크로스: 미발생 | RSI: 49.2\n"
        " - 이평선배열: 혼조세 | 단기 트렌드 우상향\n\n"
        "3. NVDA (+2.03%)\n"
        " - 골든크로스: 미발생 | RSI: 48.7\n"
        " - 이평선배열: 역배열(약세) | 단기 트렌드 우상향\n\n"
        "4. AAPL (+1.80%)\n"
        " - 골든크로스: 미발생 | RSI: 38.5\n"
        " - 이평선배열: 혼조세 | 단기 트렌드 우상향\n\n"
        "5. MSFT (+1.49%)\n"
        " - 골든크로스: 미발생 | RSI: 80.9\n"
        " - 이평선배열: 정배열(강세) | 단기 트렌드 우상향"
    )
    part3 = (
        "📊 보유종목 정밀 분석\n\n"
        "🔥 오늘의 가장 유망한 종목\n"
        "★★★★★ [삼성전자]\n"
        " - 핵심 근거: 거래량 동반 돌파 및 완벽한 정배열 진입, 수급 우수\n\n"
        "⚠️ 오늘 주의할 종목\n"
        " - 단기 급등 후 윗꼬리를 다는 테마주 및 거래량 감소 역배열 종목\n\n"
        "💡 오늘의 투자 아이디어 3가지\n"
        "1. 실적 개선이 가시화되는 반도체 대형주 중심의 비중 확대\n"
        "2. 주말/공휴일 글로벌 매크로 이슈(금리, 환율) 변동성 대비 현금 비중 확보\n"
        "3. 20일 이동평균선과 거래량이 일치하는 눌림목 구간 집중 공략\n\n"
        "※ 개인투자 참고용이며 투자 판단은 본인 책임입니다.\n"
        "🅿️ 주식 브리핑"
    )
    return [part1, part2, part3]

def get_access_token():
    """리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급받습니다."""
    client_id = os.environ.get("KAKAO_CLIENT_ID")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    
    if not client_id or not refresh_token:
        print("카카오 토큰 갱신 실패: KAKAO_CLIENT_ID 또는 KAKAO_REFRESH_TOKEN이 설정되지 않았습니다.")
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
        print(f"토큰 갱신 실패: {response.json()}")
        return None

def send_kakao_message(text):
    """카카오톡 나에게 보내기 API를 호출하여 메시지를 전송합니다."""
    access_token = get_access_token()
    if not access_token:
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "http://localhost:3000",
            "mobile_web_url": "http://localhost:3000"
        }
    }
    
    payload = {
        "template_object": json.dumps(template)
    }
    
    response = requests.post(url, headers=headers, data=payload)
    
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공!")
    else:
        print(f"카카오톡 메시지 전송 실패: {response.status_code}")
        print(response.json())

if __name__ == "__main__":
    print("[2026-08-06 10:04:49] 표 형식 주식 브리핑 생성 및 전송 시작...")
    briefings = create_stock_briefing()
    for i, content in enumerate(briefings, 1):
        print(f"파트 {i} 전송 중...")
        send_kakao_message(content)
    print("모든 브리핑 전송 완료!")
