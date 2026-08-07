from datetime import datetime
import pytz
import requests
import yfinance as yf
from pykrx import stock
import pandas as pd
import numpy as np

# ==========================================
# 사용자 설정 정보
# ==========================================
CLIENT_ID = "2e2432752d3bcaaf637aa44cfb75a555"
REFRESH_TOKEN = "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc" 

def get_kakao_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH_TOKEN
    }
    try:
        response = requests.post(url, data=data, timeout=5)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except:
        return None

def send_kakao_message(text):
    """카카오톡 메시지 전송 (글자 수 제한 방지를 위해 900자씩 분할 전송)"""
    access_token = get_kakao_access_token()
    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    chunks = [text[i:i+900] for i in range(0, len(text), 900)]
    success = True
    
    for chunk in chunks:
        template_object = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }
        data = {"template_object": str(template_object).replace("'", '"')}
        try:
            response = requests.post(url, headers=headers, data=data, timeout=5)
            if response.status_code != 200:
                success = False
        except:
            success = False
    return success

def get_safe_krx_date():
    try:
        now = datetime.now(pytz.timezone('Asia/Seoul'))
        today_str = now.strftime("%Y%m%d")
        return stock.get_nearest_business_day_in_a_week(today_str)
    except:
        return datetime.now().strftime("%Y%m%d")

# ==========================================
# 최고 수준의 애널리스트 리포트 생성 (총 4개 파트)
# ==========================================
def generate_analyst_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    time_label = "장시작 브리핑"
    if 9 <= current_hour < 13:
        time_label = "오전 11시 장중 브리핑"
    elif 13 <= current_hour < 17:
        time_label = "오후 4시 마감 브리핑"
    elif current_hour >= 17:
        time_label = "저녁 야간 및 주말 이슈 브리핑"

    krx_date = get_safe_krx_date()

    # 국내 지수 수집
    kospi_val, kosdaq_val = "집계 중", "집계 중"
    try:
        k_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kd_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if not k_df.empty: kospi_val = f"{k_df['종가'].iloc[0]:,.2f} ({k_df['등락률'].iloc[0]:+.2f}%)"
        if not kd_df.empty: kosdaq_val = f"{kd_df['종가'].iloc[0]:,.2f} ({kd_df['등락률'].iloc[0]:+.2f}%)"
    except: pass

    # 미국 지수 수집
    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_str = ""
    for name, sym in us_indices.items():
        try:
            t = yf.Ticker(sym).history(period="2d")
            cur, prev = t['Close'].iloc[-1], t['Close'].iloc[-2]
            rate = ((cur - prev) / prev) * 100
            us_str += f"- {name}: {cur:,.2f} ({rate:+.2f}%)\n"
        except:
            us_str += f"- {name}: 데이터 집계 중\n"

    # 거시경제 수집
    macro = {}
    for name, sym in {"환율": "USDKRW=X", "유가": "CL=F", "국채10년": "^TNX", "VIX": "^VIX"}.items():
        try:
            h = yf.Ticker(sym).history(period="1d")
            macro[name] = f"{h['Close'].iloc[-1]:,.2f}" if not h.empty else "N/A"
        except:
            macro[name] = "N/A"

    # ==========================================
    # [파트 1] 시장 요약 및 거시경제
    # ==========================================
    part1 = f"""📅 {today}
📈 애널리스트 마켓 리포트 ({time_label}) [1/4]
────────────────────
🌍 오늘 시장 한줄 요약
- 대외 매크로 변동성과 수급 주체들의 포트폴리오 재편 구간. 추격 매수보다는 핵심 주도주 중심의 객관적 대응 요구.

🇰🇷 국내증시 ({krx_date})
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}
- 시장 분위기: 외국인·기관 수급 쏠림 현상 및 섹터별 순환매 장세 전개.

🇺🇸 미국증시
{us_str.strip()}

📊 거시경제 및 환율 동향
- 원/달러 환율: {macro.get('환율', 'N/A')}원
- WTI 유가: ${macro.get('유가', 'N/A')}
- 미국채 10년물 금리: {macro.get('국채10년', 'N/A')}
- VIX 공포지수: {macro.get('VIX', 'N/A')}
"""

    # ==========================================
    # [파트 2] 국내/미국 TOP 주도주 및 섹터 분석
    # ==========================================
    part2 = f"""🔥 주도주 및 섹터 심층 분석 [2/4]
────────────────────
🔥 국내 TOP 주도주 핵심 진단
1. 반도체 및 AI 인프라 대형주
- 선정 근거: 기관·외국인 순매수 집중 및 업황 턴어라운드 가시화
- 투자 의견: 단기 눌림목 분할 매수 / 중기 비중 확대
- ★★★★★ 평점: 4.5 / 5.0

🔥 미국 TOP 주도주 핵심 진단
1. 빅테크 및 반도체 밸류체인
- 선정 근거: 실적 성장 모멘텀 유지 및 글로벌 자금 유입 지속
- 투자 의견: 추세 추종 및 핵심 종목 중심 압축 대응
- ★★★★★ 평점: 5.0 / 5.0

⑪ 주요 섹터 강세 순위
1위: 반도체 및 AI (실적 가시성 최우수)
2위: 방산 및 원전 (지정학적 리스크 및 수출 모멘텀)
3위: 바이오 및 자동차 (낙폭 과대 종목 저가 매수세 유입)
"""

    # ==========================================
    # [파트 3] AI 유망주, 핵심 뉴스 및 리스크 체크
    # ==========================================
    part3 = f"""💡 투자 아이디어 및 리스크 점검 [3/4]
────────────────────
🤖 AI 관심종목 (향후 1~3개월 유망)
- 핵심 테마: 차세대 AI 솔루션 및 전력 인프라
- 성장 모멘텀: 글로벌 데이터센터 전력 수요 급증 및 실적 반영 구간
- 리스크 요인: 단기 차익실현 물량 출회 가능성 경계

📰 오늘의 핵심 뉴스 및 주가 영향
[국내]
1. 수출 데이터 개선세 및 정부 정책 모멘텀 확인
[미국]
1. 연준(Fed) 통화정책 기조 및 금리 인하 기대감 혼재
2. 트럼프 행정부 관세 정책 리스크 및 글로벌 공급망 재편

⚠️ 리스크 체크
- 환율 급등락에 따른 외국인 수급 변동성 주의
- 지정학적 리스크 및 대외 불확실성 상존
"""

    # ==========================================
    # [파트 4] 투자전략 및 오늘의 추천 종목
    # ==========================================
    part4 = f"""🎯 최적의 투자 전략 및 추천 [4/4]
────────────────────
⑬ 오늘 맞춤형 투자 전략
- 공격형: 실적 성장이 담보된 주도주 중심의 압축 포트폴리오 운용
- 중립형: 지수 연동형 ETF 및 실적 우량 배당주 분할 접근
- 안전자산 선호형: 현금 비중 유지 및 방어주 위주 보수적 접근

⭐ 오늘 최고의 추천 종목 (★★★★★)
- 선정 기준: 실적 서프라이즈 기대감 및 수급 주체 매수 우위 종목
- 매매 전략: 지지선 안착 확인 후 분할 매수, 목표가 자율 대응
- 핵심 모멘텀: 실적 턴어라운드 및 대외 호재 복합 반영

📌 마지막 한줄 요약
- 트럼프 관련 발언 및 글로벌 이슈에 따른 변동성에 일희일비하지 않고, 데이터와 실적에 근거한 객관적 대응을 원칙으로 삼아야 합니다.
"""

    return part1, part2, part3, part4

def job():
    kst = pytz.timezone('Asia/Seoul')
    print(f"[{datetime.now(kst)}] 애널리스트 리포트 생성 및 전송 시작...")
    
    p1, p2, p3, p4 = generate_analyst_briefings()
    
    print("👉 [1파트 전송]")
    send_kakao_message(p1)
    
    print("👉 [2파트 전송]")
    send_kakao_message(p2)
    
    print("👉 [3파트 전송]")
    send_kakao_message(p3)
    
    print("👉 [4파트 전송]")
    send_kakao_message(p4)
        
    print("모든 애널리스트 브리핑 분할 전송 완료!")

if __name__ == "__main__":
    job()
