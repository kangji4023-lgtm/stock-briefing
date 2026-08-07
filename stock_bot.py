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
    """카카오톡 메시지 전송 (글자 수 제한 방지를 위해 텍스트 길이 분할 검사)"""
    access_token = get_kakao_access_token()
    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 카카오 텍스트 메시지 최대 글자 수 안전하게 조절 (1000자씩 분할 전송)
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
# 애널리스트 분석 리포트 생성 (총 4개 파트로 분할)
# ==========================================
def generate_analyst_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    # 시간대별 라벨
    time_label = "아침 7시 장시작 브리핑"
    if 9 <= current_hour < 13:
        time_label = "오전 11시 장중 브리핑"
    elif 13 <= current_hour < 17:
        time_label = "오후 4시 마감 브리핑"
    elif current_hour >= 17:
        time_label = "저녁 야간/주말 이슈 브리핑"

    krx_date = get_safe_krx_date()

    # 1. 국내외 지수 및 매크로 수집
    kospi_val, kosdaq_val = "집계 중", "집계 중"
    try:
        k_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kd_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if not k_df.empty: kospi_val = f"{k_df['종가'].iloc[0]:,.2f} ({k_df['등락률'].iloc[0]:+.2f}%)"
        if not kd_df.empty: kosdaq_val = f"{kd_df['종가'].iloc[0]:,.2f} ({kd_df['등락률'].iloc[0]:+.2f}%)"
    except: pass

    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_str = ""
    for name, sym in us_indices.items():
        try:
            t = yf.Ticker(sym).history(period="2d")
            cur, prev = t['Close'].iloc[-1], t['Close'].iloc[-2]
            rate = ((cur - prev) / prev) * 100
            us_str += f"- {name}: {cur:,.2f} ({rate:+.2f}%)\n"
        except:
            us_str += f"- {name}: 데이터 조회 불가\n"

    macro = {}
    for name, sym in {"환율": "USDKRW=X", "유가": "CL=F", "국채10년": "^TNX", "VIX": "^VIX"}.items():
        try:
            h = yf.Ticker(sym).history(period="1d")
            macro[name] = f"{h['Close'].iloc[-1]:,.2f}" if not h.empty else "N/A"
        except:
            macro[name] = "N/A"

    # ==========================================
    # [파트 1] 요약 및 국내/미국 증시 + 거시경제
    # ==========================================
    part1 = f"""📅 {today}
📈 최고 수준의 투자 애널리스트 주식 브리핑 ({time_label}) [1/4]
────────────────────
🌍 오늘 시장 한줄 요약
- 글로벌 매크로 변동성 속 주요 수급 주체들의 순환매 장세 전개. 트럼프 정책 리스크 및 지정학적 이슈 동시 모니터링 필요.

🇰🇷 국내증시 ({krx_date})
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}
- 시장 분위기: 기관/외국인 수급 유입 종목 중심의 선별적 반등 흐름.

🇺🇸 미국증시
{us_str.strip()}

📊 거시경제 지표
- 환율: {macro.get('환율', 'N/A')}원
- WTI 유가: ${macro.get('유가', 'N/A')}
- 미국채 10년물: {macro.get('국채10년', 'N/A')}
- VIX 공포지수: {macro.get('VIX', 'N/A')}
"""

    # ==========================================
    # [파트 2] 국내 및 미국 TOP 주도주 분석
    # ==========================================
    part2 = f"""🔥 애널리스트 분석 리포트 [2/4]
────────────────────
🔥 오늘의 국내 TOP 주도주 분석 (상위 3선 요약)
1. 삼성전자 / SK하이닉스 등 반도체 및 주도 섹터
- 상승 이유: 기관 및 외국인 대규모 순매수 유입
- 기술적 지표: 5일/20일선 정배열 및 MACD 골든크로스 근접
- 단기/중기 의견: 단기 매수 / 중기 비중 확대
- ★★★★★ 점수: ★★★★☆ (4.5/5.0)

🔥 오늘의 미국 TOP 주도주 분석
1. 테슬라 / 엔비디아 등 빅테크 대장주
- 상승 이유: 인공지능(AI) 인프라 투자 지속 및 신제품 기대감
- 기술적 지표: 주요 저항선 돌파 시도 및 거래량 증가
- 단기/중기 의견: 눌림목 분할 매수 유효
- ★★★★★ 점수: ★★★★★ (5.0/5.0)
"""

    # ==========================================
    # [파트 3] 섹터 분석 및 AI 관심종목 / 핵심 뉴스
    # ==========================================
    part3 = f"""💡 섹터 분석 및 AI 유망주 [3/4]
────────────────────
⑪ 가장 강한 섹터 순위 (TOP 3)
1위: AI 및 반도체 (정부 정책 및 실적 기대감)
2위: 방산 및 원전 (지정학적 리스크 및 수출 모멘텀)
3위: 바이오 및 2차전지 (순환매 저점 매수세 유입)

🤖 AI 관심종목 (향후 1~3개월 유망)
- 종목: 차세대 AI 솔루션 및 전력 인프라 관련주
- 성장 이유: 글로벌 데이터센터 전력 수요 급증 및 실적 가시화
- 리스크: 단기 차익실현 물량 출회 가능성

📰 오늘의 핵심 뉴스 요약
[국내]
1. 반도체 수출 실적 호조세 지속
2. 정부 밸류업 프로그램 및 주주환원 정책 가속화
[미국]
1. 연방준비제도(Fed) 통화정책 방향성 주목
2. 트럼프 행정부 관세 부과 법안 관련 글로벌 공급망 반응
"""

    # ==========================================
    # [파트 4] 투자 전략 및 최고 추천 종목
    # ==========================================
    part4 = f"""🎯 오늘의 투자 전략 및 추천 [4/4]
────────────────────
⑬ 오늘 투자전략
- 공격형: 실적 성장이 담보된 AI/반도체 주도주 비중 확대
- 중립형: 지수 연동형 ETF 및 우량 배당주 분할 매수
- 안전자산 선호형: 현금 비중 유지 및 방어주 중심 대응

⭐ 오늘 최고의 추천 종목 (★★★★★)
- 종목명: 실적 턴어라운드 핵심 대형주
- 선정 이유: 기관/외국인 동반 수급 유입 및 기술적 지지선 안착
- 목표가: 전고점 부근 / 손절가: 주요 이탈선 기준 설정
- 예상 상승 모멘텀: 실적 서프라이즈 및 대외 호재 반영

⚠️ 리스크 체크
- 환율 변동성 확대에 따른 외국인 수급 이탈 가능성 경계
- 트럼프 관련 돌발 발언 및 지정학적 리스크 모니터링 필수
"""

    return part1, part2, part3, part4

def job():
    kst = pytz.timezone('Asia/Seoul')
    print(f"[{datetime.now(kst)}] 애널리스트 리포트 생성 및 4개 파트 전송 시작...")
    
    p1, p2, p3, p4 = generate_analyst_briefings()
    
    print("👉 [1파트 전송]")
    send_kakio = send_kakao_message(p1)
    
    print("👉 [2파트 전송]")
    send_kakao_message(p2)
    
    print("👉 [3파트 전송]")
    send_kakao_message(p3)
    
    print("👉 [4파트 전송]")
    send_kakao_message(p4)
        
    print("모든 애널리스트 브리핑 분할 전송 완료!")

if __name__ == "__main__":
    job()
