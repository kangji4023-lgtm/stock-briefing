import os
import requests

# GitHub Secrets에서 가져온 리프레시 토큰
REFRESH_TOKEN = os.environ.get("KAKAO_TOKEN")
REST_API_KEY = "3c9a29d58ca8030c4e9a119d4249e305"  # 본인의 REST API 키

def get_new_access_token(refresh_token):
    """리프레시 토큰을 사용해 새로운 액세스 토큰을 발급받는 함수"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    tokens = response.json()
    return tokens.get("access_token")

def send_kakao_message(text):
    """카카오톡 '나에게 보내기' API를 호출하는 함수"""
    # 1. 최신 액세스 토큰 갱신
    access_token = get_new_access_token(REFRESH_TOKEN)
    if not access_token:
        print("토큰 갱신 실패: 리프레시 토큰이 만료되었거나 잘못되었습니다.")
        return

    # 2. 메시지 전송 요청
    header = {"Authorization": f"Bearer {access_token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    # 전송할 메시지 내용 (주식 브리핑 내용 작성)
    data = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    response = requests.post(url, headers=header, data={"template_object": str(data).replace("'", '"')})
    print(f"카카오톡 전송 결과: {response.status_code} {response.text}")

if __name__ == "__main__":
    # 테스트 메시지 전송
    message = "📈 [주식 브리핑 자동화 테스트]\n\n리프레시 토큰 자동 갱신 연동이 성공적으로 완료되었습니다!"
    send_kakao_message(message)
