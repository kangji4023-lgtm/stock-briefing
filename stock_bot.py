import requests
import json
import os

# 환경 변수에서 토큰 가져오기 (GitHub Secrets에 등록된 이름과 일치해야 함)
KAKAO_ACCESS_TOKEN = os.environ.get('KAKAO_ACCESS_TOKEN')

def send_kakao_message(text):
    """카카오톡 '나에게 보내기' API를 통해 메시지를 전송하고 응답을 확인하는 함수"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    headers = {
        "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}"
    }
    
    # 기본 텍스트 메시지 형식
    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        })
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        
        # [중요] 카카오 API 서버가 반환한 실제 응답 결과 출력
        print(f"카카오 API 응답 코드(Status): {response.status_code}")
        print(f"카카오 API 응답 본문(JSON): {response.text}")
        
        res_json = response.json()
        
        # 카카오 API 성공 코드인 경우 (통상적으로 result_code가 0이거나 status_code가 200)
        if response.status_code == 200 and res_json.get('result_code') == 0:
            print("카카오톡 메시지 전송 성공!")
        else:
            print("⚠️ 카카오톡 메시지 전송 실패 (카카오 서버 거절)")
            
    except Exception as e:
        print(f"❌ 네트워크 또는 코드 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    print("[2026-08-06] 최고급 애널리스트 AI 주식 브리핑 생성 시작...")
    
    # 예시 브리핑 메시지 전송
    message = "안녕하세요! 오늘의 AI 주식 브리핑입니다."
    send_kakao_message(message)
    
    print("모든 분할 브리핑 전송 완료!")
