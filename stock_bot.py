import os
import json
import requests
import datetime
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))
today_str = datetime.datetime.now(KST).strftime('%Y-%m-%d')

def get_kakao_access_token():
    client_id = os.environ.get('KAKAO_CLIENT_ID')
    refresh_token = os.environ.get('KAKAO_REFRESH_TOKEN')
    if not client_id or not refresh_token:
        print("에러: 토큰 환경 변수 미설정")
        return None
    url = "https://kauth.kakao.com/oauth/token"
    data = {"grant_type": "refresh_token", "client_id": client_id, "refresh_token": refresh_token}
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def send_kakao_message(text):
    token = get_kakao_access_token()
    if not token:
        print("토큰 없음")
        return
    header = {"Authorization": f"Bearer {token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    payload = {"object_type": "text", "text": text}
    data = {"template_object": json.dumps(payload)}
    response = requests.post(url, headers=header, data=data)
    if response.status_code == 200:
        print("전송 성공!")
    else:
        print(f"전송 실패: {response.text}")

if __name__ == "__main__":
    print(f"[{today_str}] 브리핑 전송 시작")
    send_kakao_message(f"[{today_str}] AI 주식 브리핑 테스트 메시지입니다.")
    print("완료")
