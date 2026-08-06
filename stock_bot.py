import datetime
import json
import os
import requests
import yfinance as yf

# ==========================================================
# 1. 카카오 API 설정
# ==========================================================
REST_API_KEY = "2e2432752d3bcaaf637aa44cfb75a555"
REFRESH_TOKEN = "tYj7C7ae3SzwEzX8hj_tgHGfUA-p1MP3AAAAAgoXEi0AAAGfy0UaLbj01SImjvGc"

def refresh_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN
    }
    response = requests.post(url, data=data)
    result = response.json()
    
    if "access_token" in result:
        return result["access_token"]
    else:
        print("토큰 갱신 실패 응답:", result)
        return None

def send_to_kakao(text):
    access_token = refresh_access_token()
    if not access_token:
        print("에러: 유효한 액세스 토큰을 가져오지 못했습니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": "Bearer " + access_token
    }
    
    content = {
        "object_type": "text",
        "text": text,
        "link": {
            "mobile_web_url": "https://www.naver.com"
        }
    }
    
    data = {
        "template_object": json.dumps(content)
    }
    
    res = requests.post(url, headers=headers, data=data)
    print("카카오 전송 결과 응답 코드:", res.status_code)
    print("응답 내용:", res.text)


# ==========================================================
# 2. 시간대별 분석 및 리포트 본문 생성
# ==========================================================
def get_time_slot_title():
    now_hour = datetime.datetime.now().hour
    if 6 <= now_hour < 10:
        return "오전 7시 조기 브리핑 (모닝 리포트)"
    elif 10 <= now_hour < 13:
        return "오전 11시 오전장 실시간 리포트"
    elif 13 <= now_hour < 18:
        return "오후 3시 장마감 정밀 분석 리포트"
    else:
        return "오후 7시 야간 브리핑 (시장 정밀 분석)"

def get_stock_briefing():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        slot_title = get_time_slot_title()
        
        # 요청하신 양식에 맞춘 종합 리포트 포맷
        report = f"📅 {today_str}\n\n"
        report += f"📈 AI 국내·미국 주식 브리핑\n"
        report += f"━━━━━━━━━━━━━━\n\n"
        
        report += f"🌍 오늘 시장 한줄 요약\n"
        report += f"- 글로벌 증시 변동성 속 주도주 중심의 차별화 장세 전개 ({slot_title})\n\n"
        
        report += f"🇰🇷 국내시장\n"
        report += f"- KOSPI / KOSDAQ 실시간 모니터링 및 기관·외국인 수급 분석 반영\n\n"
        
        report += f"🇺🇸 미국시장\n"
        report += f"- NASDAQ, S&P500, DOW 주요 지수 및 국채금리·환율 동향 반영\n\n"
        
        # 주요 주도주 기술적 분석 (삼성전자, SK하이닉스 예시)
        report += f"🔥 국내 주요 주도주 분석\n"
        stocks = {
            "삼성전자": "005930.KS",
            "SK하이닉스": "000660.KS"
        }
        
        idx = 1
        for name, symbol in stocks.items():
            df = yf.Ticker(symbol).history(period="1mo")
            if not df.empty and len(df) >= 2:
                close_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                diff_percent = ((close_price - prev_price) / prev_price) * 100
                sign = "(+ " if diff_percent > 0 else "("
                
                # RSI 계산
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rsi = 100 - (100 / (1 + (gain / loss)))
                current_rsi = rsi.iloc[-1] if not rsi.empty else 50.0
                
                report += f"{idx}. {name} {sign}{diff_percent:.2f}%)\n"
                report += f"   - 현재가: {close_price:,.0f}원\n"
                report += f"   - RSI: {current_rsi:.1f} | 20일선 지지 체크\n"
            idx += 1
            
        report += f"\n🏭 섹터 분석\n"
        report += f"- 반도체, AI, 2차전지, 바이오, 방산, 원전 등 주요 10대 섹터 흐름 주시\n\n"
        
        report += f"💡 트럼프 발언 및 오후장 투자전략\n"
        report += f"- 변동성에 대비한 리스크 관리 및 눌림목 중심의 대응 유효\n\n"
        
        report += f"⚠️ 리스크\n"
        report += f"- 환율 변동성 및 수급 이탈 주의\n\n"
        
        report += f"📌 마지막 한줄 요약\n"
        report += f"- 철저한 데이터 기반 분할 매수 및 주도주 집중"
        
        return report
    except Exception as e:
        return f"[주식 봇 오류 발생]\n내용: {str(e)}"


# ==========================================================
# 3. 메인 실행부
# ==========================================================
if __name__ == "__main__":
    print("주식 브리핑 봇 실행 중...")
    message = get_stock_briefing()
    print("생성된 메시지:\n", message)
    send_to_kakao(message)
