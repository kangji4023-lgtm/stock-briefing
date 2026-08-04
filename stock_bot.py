import os
import json
import requests

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

if __name__ == "__main__":
    print("주식 브리핑 작업을 실행합니다.")
    
    CLIENT_ID = os.environ.get("KAKAO_REST_API_KEY")
    REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")
    
    if not CLIENT_ID or not REFRESH_TOKEN:
        print("에러: 카카오 API 키 또는 리프레시 토큰이 설정되지 않았습니다.")
    else:
        access_token = refresh_access_token(CLIENT_ID, REFRESH_TOKEN)
        
        if access_token:
            message = "[주식 브리핑 자동화]\n테스트 메시지입니다."
            res = send_kakao_message(access_token, message)
        else:
            print("유효한 액세스 토큰을 받아오지 못했습니다.")
