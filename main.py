import os
import requests
from datetime import datetime

def send_kakao_memo():
    kakao_token = os.environ.get('KAKAO_TOKEN')
    
    if not kakao_token:
        print("카카오 토큰이 설정되지 않았습니다.")
        return

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M")
    
    if now.weekday() >= 5:
        title = "🏖️ [주말 및 공휴일 전일 마감 증시 이슈 리포트]\n\n"
        body = "• 주말 글로벌 주요 경제 뉴스 및 주간 증시 리뷰를 안내해 드립니다.\n• 다가오는 주의 주요 경제 일정과 주도주 동향을 점검하세요."
    else:
        title = "🚨 [한국 및 미국 주식 브리핑 알림]\n\n"
        body = f"• 기준 시간: {current_time_str}\n• 실시간 미국 주요 주도주 및 국내 증시 핵심 동향 브리핑이 성공적으로 완료되었습니다."

    full_message = title + body

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {kakao_token}"
    }
    data = {
        "template_object": {
            "object_type": "text",
            "text": full_message,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }
    }

    response = requests.post(url, headers=headers, data=data)
    print("카카오톡 전송 결과:", response.status_code, response.text)

if __name__ == "__main__":
    send_kakao_memo()
