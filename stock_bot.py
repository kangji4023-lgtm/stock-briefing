import os
import requests
import json

def get_access_token():
    # GitHub Secrets나 환경 변수에서 값 가져오기
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
        response_data = response.json()
        return response_data.get("access_token")
    else:
        print(f"토큰 갱신 실패: {response.status_code}, {response.text}")
        return None

def send_kakao_message(text):
    access_token = get_access_token()
    
    if not access_token:
        print("액세스 토큰이 없어 메시지를 전송할 수 없습니다.")
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

if __name__ == "__main__":
    print("주식 브리핑 생성 및 전송 시작...")
    
    # 파트별 전송 예시
    print("파트 1 전송 중...")
    send_kakao_message("주식 브리핑 파트 1 내용입니다.")
    
    print("파트 2 전송 중...")
    send_kakao_message("주식 브리핑 파트 2 내용입니다.")
    
    print("파트 3 전송 중...")
    send_kakao_message("주식 브리핑 파트 3 내용입니다.")
    
    print("모든 작업이 완료되었습니다.")
