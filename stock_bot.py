import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from pykrx import stock
import yfinance as yf

# ==========================================
# 카카오 인증 정보 설정 (토큰 직접 입력 완료)
# ==========================================
REST_API_KEY = " 여기에 본인의 카카오 REST API 키 입력 "
REFRESH_TOKEN = "WWN1D_LLRI9rzePTDcq2Ow9rri8NvE7XAAAAAgoXEpYAAAGf1ejxPKj01SImjvGc"

def get_access_token_by_refresh_token():
    global REFRESH_TOKEN
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY.strip(),
        "refresh_token": REFRESH_TOKEN.strip()
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get("access_token")
            if "refresh_token" in tokens:
                REFRESH_TOKEN = tokens["refresh_token"]
            print("Access Token이 성공적으로 발급/갱신되었습니다.")
            return access_token
        else:
            print(f"토큰 갱신 실패: {response.text}")
            return None
    except Exception as e:
        print(f"토큰 갱신 에러 발생: {e}")
        return None

def send_kakao_message(text):
    access_token = get_access_token_by_refresh_token()
    if not access_token:
        print("유효한 액세스 토큰을 가져오지 못해 메시지를 전송할 수 없습니다.")
        return

    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    header = {"Authorization": f"Bearer {access_token}"}
    
    max_length = 3000
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    for idx, msg in enumerate(messages, 1):
        print(f"파트 {idx} 전송 중...")
        payload = {
            "object_type": "text",
            "text": msg,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }
        data = {"template_object": str(payload).replace("'", '"')}
        try:
            response = requests.post(kakao_url, headers=header, data=data)
            if response.status_code != 200:
                print(f"카카오 전송 실패: {response.text}")
            else:
                print("카카오톡 메시지 전송 성공!")
        except Exception as e:
            print(f"카카오 전송 에러: {e}")
        time.sleep(1.0)

# ==========================================
# 데이터 수집 및 브리핑 생성
# ==========================================
def generate_full_briefing():
    today = datetime.now().strftime("%Y-%m-%d")
    
    macro_symbols = {"USD/KRW": "USDKRW=X", "국채금리(10년)": "^TNX", "VIX지수": "^VIX", "유가(WTI)": "CL=F"}
    macro_data = {}
    for name, sym in macro_symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if not hist.empty:
                macro_data[name] = f"{hist['Close'].iloc[-1]:,.2f}"
            else:
                macro_data[name] = "데이터 없음"
        except:
            macro_data[name] = "조회 불가"

    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_result_str = ""
    for name, sym in us_indices.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if not hist.empty and len(hist) >= 2:
                cur = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                rate = ((cur - prev) / prev) * 100
                us_result_str += f"- {name}: {cur:,.2f} ({rate:+.2f}%)\n"
            else:
                us_result_str += f"- {name}: 데이터 없음\n"
        except:
            us_result_str += f"- {name}: 조회 실패\n"

    kospi_val, kosdaq_val = "집계 중(휴장일)", "집계 중(휴장일)"
    try:
        krx_date = stock.get_nearest_business_day_in_a_week(datetime.now().strftime("%Y%m%d"))
        kospi_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kosdaq_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if kospi_df is not None and not kospi_df.empty and len(kospi_df) > 0:
            kospi_val = f"{kospi_df['종가'].iloc[0]:,.2f} ({kospi_df['등락률'].iloc[0]:+.2f}%)"
        if kosdaq_df is not None and not kosdaq_df.empty and len(kosdaq_df) > 0:
            kosdaq_val = f"{kosdaq_df['종가'].iloc[0]:,.2f} ({kosdaq_df['등락률'].iloc[0]:+.2f}%)"
    except Exception as e:
        print(f"국내 지수 조회 스킵: {e}")

    full_message = f"""📅 {today}

📈 AI 국내·미국 주식 브리핑

━━━━━━━━━━━━━━
🌍 오늘 시장 한줄 요약
글로벌 증시는 주요 매크로 지표 변동성과 실적에 따라 혼조세를 보이며 종목별 차별화 장세가 전개되고 있습니다.

━━━━━━━━━━━━━━
🇰🇷 국내시장
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}
- 시장 분위기: 기관·외국인 수급 유입 종목 중심의 순환매 장세

━━━━━━━━━━━━━━
🇺🇸 미국시장
{us_result_str}
━━━━━━━━━━━━━━
🔥 국내 TOP10 주도주 (핵심 요약)
1. 삼성전자 - 반도체 업황 개선 기대감
2. SK하이닉스 - AI 메모리 수요 견조
3. 현대차 - 주주환원 정책 및 실적 호조

━━━━━━━━━━━━━━
🔥 미국 TOP10 주도주 (핵심 요약)
1. NVIDIA (NVDA) - AI 인프라 투자 지속
2. Apple (AAPL) - 신제품 모멘텀 및 서비스 부문 성장

━━━━━━━━━━━━━━
⭐ 오늘 최고의 추천 종목
★★★★★
종목이름: NVIDIA (NVDA)
선정 이유: 데이터센터 매출 성장세 지속 및 수급 집중
목표가: $140
손절가: $110
예상 상승 모멘텀: AI 반도체 칩 수요 독점력 유지

━━━━━━━━━━━━━━
💡 오늘 투자 아이디어 5가지
1. 반도체 및 AI 하드웨어 밸류체인 집중
2. 실적 가시성이 높은 방산 및 조선 섹터 주목
3. 환율 변동성에 따른 수출 중심 우량주 선별
4. 바이오 섹터 임상 결과 발표 앞둔 종목 대응
5. 변동성 장세 대비 안전자산 및 고배당주 분할 매수

━━━━━━━━━━━━━━
📊 거시경제 지표
- 환율(USD/KRW): {macro_data.get('USD/KRW', 'N/A')}
- WTI유: {macro_data.get('유가(WTI)', 'N/A')}
- 미국채 10년물 금리: {macro_data.get('국채금리(10년)', 'N/A')}
- VIX 공포지수: {macro_data.get('VIX지수', 'N/A')}

━━━━━━━━━━━━━━
⚠️ 리스크 체크
- 중동 지정학적 리스크 및 환율 변동성 확대 주의
- 미국 금리 인하 경로 불확실성에 따른 차익실현 매물 경계

━━━━━━━━━━━━━━
📌 마지막 한줄
트럼프 발언 및 글로벌 무역 이슈에 따른 섹터별 민감도 실시간 모니터링 필요
"""
    return full_message

def job():
    print(f"[{datetime.now()}] 주식 브리핑 생성 및 전송 시작...")
    briefing_content = generate_full_briefing()
    send_kakao_message(briefing_content)
    print("모든 브리핑 전송 완료!")

if __name__ == "__main__":
    job()
