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
