import os
import requests

def refresh_access_token(client_id, refresh_token):
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token
    }
    # Content-Type 헤더를 추가하여 KOE001 에러 해결
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }
    response = requests.post(url, data=data, headers=headers)
    result = response.json()
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"토큰 갱신 실패: {result}")
        return None

def send_kakao_message(access_token, text):
    header = {"Authorization": f"Bearer {access_token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    data = {
        "template_object": {
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": "https://www.naver.com",
                "mobile_web_url": "https://www.naver.com"
            }
        }
    }
    response = requests.post(url, headers=header, json=data)
    return response.json()

if __name__ == "__main__":
    print("주식 브리핑 작업을 실행합니다.")
    
    CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID")
    REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")
    
    if not CLIENT_ID or not REFRESH_TOKEN:
        print("에러: 카카오 API 키 또는 리프레시 토큰이 설정되지 않았습니다.")
    else:
        access_token = refresh_access_token(CLIENT_ID, REFRESH_TOKEN)
        
        if access_token:
            message = "[주식 브리핑 자동화]\n오늘의 증시 요약 테스트 메시지입니다."
            res = send_kakao_message(access_token, message)
            print("메시지 전송 결과:", res)
        else:
            print("유효한 액세스 토큰이 없어 메시지를 전송할 수 없습니다.")
