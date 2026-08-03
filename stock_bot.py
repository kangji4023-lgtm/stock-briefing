import os
import requests
from bs4 import BeautifulSoup

# 1. 리프레시 토큰으로 새로운 액세스 토큰을 발급받는 함수
def refresh_access_token():
    # 깃허브 시크릿이나 환경변수에 등록된 값 또는 직접 입력한 값을 가져옵니다.
    # 로컬 테스트 시 여기에 직접 카카오 REST API 키와 리프레시 토큰을 넣고 테스트할 수도 있습니다.
    client_key = os.environ.get('KAKAO_REST_API_KEY', '여기에_REST_API키_입력(선택)')
    refresh_token = os.environ.get('KAKAO_REFRESH_TOKEN', '여기에_리프레시토큰_입력')
    
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_key,
        "refresh_token": refresh_token
    }
    
    response = requests.post(url, data=data)
    result = response.json()
    
    # 새로운 액세스 토큰이 반환되면 이를 추출
    if "access_token" in result:
        print("토큰 갱신 성공!")
        return result["access_token"]
    else:
        print("토큰 갱신 실패:", result)
        return None

# 2. 네이버 금융에서 주가 크롤링
def get_stock_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(response.text, 'html.parser')
    try:
        price = soup.select_one('div.today').select_one('span.blind').text
        return price
    except:
        return "가격 정보 없음"

# 3. 카카오톡 나에게 보내기
def send_kakao_message(text):
    access_token = refresh_access_token()
    if not access_token:
        print("유효한 액세스 토큰이 없어 메시지를 전송할 수 없습니다.")
        return

    header = {"Authorization": f"Bearer {access_token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    payload = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://finance.naver.com",
            "mobile_web_url": "https://finance.naver.com"
        }
    }
    
    # 딕셔너리를 파라미터로 전달할 때 json 형태로 전달
    response = requests.post(url, headers=header, json={"template_object": payload})
    print("전송 결과:", response.json())

if __name__ == "__main__":
    print("주식 브리핑 작업을 실행합니다.")
    
    # 삼성전자 (005930) 예시
    samsung_price = get_stock_price("005930")
    
    briefing_text = f"[📈 모닝 주식 브리핑]\n\n- 삼성전자 현재가: {samsung_price}원\n\n오늘도 성공적인 투자 하세요!"
    
    send_kakao_message(briefing_text)
