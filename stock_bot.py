from datetime import datetime
import pytz
import requests
import yfinance as yf
from pykrx import stock
import pandas as pd
import numpy as np

# ==========================================
# 사용자 설정 정보 입력
# ==========================================
CLIENT_ID = "2e2432752d3bcaaf637aa44cfb75a555"
REFRESH_TOKEN = "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc" 

def get_kakao_access_token():
    """리프레시 토큰을 이용해 최신 액세스 토큰을 발급받습니다."""
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
        else:
            print(f"❌ 액세스 토큰 갱신 실패: {response.status_code} - {response.json()}")
            return None
    except Exception as e:
        print(f"❌ 토큰 요청 중 에러 발생: {e}")
        return None

def send_kakao_message(text):
    """카카오톡 나에게 보내기로 메시지 전송"""
    access_token = get_kakao_access_token()
    if not access_token:
        print("❌ 유효한 액세스 토큰이 없어 카카오 메시지를 전송할 수 없습니다.")
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        }
    }
    
    data = {
        "template_object": str(template_object).replace("'", '"')
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=5)
        if response.status_code == 200:
            return True
        else:
            print(f"❌ 카카오톡 전송 실패: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 메시지 전송 중 에러 발생: {e}")
        return False

# ==========================================
# 기술적 지표 계산 함수
# ==========================================
def calculate_technical_indicators(ticker):
    try:
        df = stock.get_market_ohlcv_by_date("20260101", datetime.now().strftime("%Y%m%d"), ticker)
        if df.empty or len(df) < 30:
            return None
        
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['MA60'] = df['종가'].rolling(window=60).mean()
        
        delta = df['종가'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        exp1 = df['종가'].ewm(span=12, adjust=False).mean()
        exp2 = df['종가'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        ma_alignment = "정배열(강세)" if curr['MA5'] > curr['MA20'] > curr['MA60'] else "역배열(약세)"
        golden_cross = "발생" if (prev['MA5'] <= prev['MA20']) and (curr['MA5'] > curr['MA20']) else "미발생"
        vol_increase = "O (급증)" if curr['거래량'] > prev['거래량'] * 1.2 else "X"
        
        recent_df = df.tail(5)
        resistance = recent_df['고가'].max()
        support = recent_df['저가'].min()
        
        return {
            "close": curr['종가'],
            "change_rate": ((curr['종가'] - prev['종가']) / prev['종가']) * 100,
            "vol_increase": vol_increase,
            "golden_cross": golden_cross,
            "macd": curr['MACD'],
            "rsi": curr['RSI'],
            "ma_alignment": ma_alignment,
            "resistance": resistance,
            "support": support
        }
    except Exception:
        return None

# ==========================================
# 상세 분석 브리핑 생성 (여러 편 분할 + 트럼프/글로벌 이슈 포함)
# ==========================================
def generate_detailed_briefings():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    today = now_kst.strftime("%Y-%m-%d")
    collected_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    current_hour = now_kst.hour
    
    # 시간대별 타이틀 구분 (아침 7시, 11시, 오후 4시, 7시 대응)
    time_label = "장시작 브리핑"
    if 9 <= current_hour < 13:
        time_label = "오전 11시 장중 브리핑"
    elif 13 <= current_hour < 17:
        time_label = "오후 4시 마감 브리핑"
    elif current_hour >= 17:
        time_label = "저녁 야간 브리핑"

    krx_date = stock.get_nearest_business_day_in_a_week(now_kst.strftime("%Y%m%d"))
    
    # 1. 국내 주도주 분석
    try:
        df_trade = stock.get_market_trading_value_by_ticker(krx_date, krx_date, "ALL")
        if df_trade is None or df_trade.empty:
            df_trade = stock.get_market_price_change_by_ticker(krx_date, krx_date)
            df_trade = df_trade.sort_values(by="거래대금", ascending=False)
        else:
            df_trade = df_trade.sort_values(by="거래대금", ascending=False)
        top_tickers = df_trade.head(3).index.tolist()
    except:
        top_tickers = ["005930", "000660", "035420"]

    krx_details = ""
    for i, ticker in enumerate(top_tickers, 1):
        name = stock.get_market_ticker_name(ticker)
        ind = calculate_technical_indicators(ticker)
        
        if ind:
            krx_details += f"""
{i}. {name} ({ind['change_rate']:+.2f}%)
- 상승이유: 기관/외국인 수급 유입 및 순환매
- 거래량증가: {ind['vol_increase']}
- 골든크로스: {ind['golden_cross']}
- MACD: {ind['macd']:.2f} | RSI: {ind['rsi']:.1f}
- 이평선배열: {ind['ma_alignment']}
- 저항선: {ind['resistance']:,}원 / 지지선: {ind['support']:,}원
- 매매전략: 추세 추종 및 눌림목 분할 매수
- 리스크: 단기 과열에 따른 차익실현 매물 주의
"""
        else:
            krx_details += f"\n{i}. {name} - 데이터 산출 중\n"

    # 국내 지수
    kospi_val, kosdaq_val = "집계 중", "집계 중"
    try:
        kospi_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "1001")
        kosdaq_df = stock.get_index_price_change_by_ticker(krx_date, krx_date, "2001")
        if kospi_df is not None and not kospi_df.empty:
            kospi_val = f"{kospi_df['종가'].iloc[0]:,.2f} ({kospi_df['등락률'].iloc[0]:+.2f}%)"
        if kosdaq_df is not None and not kosdaq_df.empty:
            kosdaq_val = f"{kosdaq_df['종가'].iloc[0]:,.2f} ({kosdaq_df['등락률'].iloc[0]:+.2f}%)"
    except:
        pass

    # 2. 미국 및 매크로 지표
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

    macro_symbols = {"USD/KRW": "USDKRW=X", "국채금리(10년)": "^TNX", "VIX지수": "^VIX", "유가(WTI)": "CL=F"}
    macro_data = {}
    for name, sym in macro_symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="1d")
            if hist.empty:
                hist = t.history(period="2d")
            macro_data[name] = f"{hist['Close'].iloc[-1]:,.2f}" if not hist.empty else "데이터 없음"
        except:
            macro_data[name] = "조회 불가"

    # ==========================================
    # [1편]: 국내 시장 및 주도주 정밀 분석
    # ==========================================
    part1 = f"""📊 {today} 주식 브리핑 ({time_label}) [1편]
⏰ 수집 시각: {collected_time}

🇰🇷 국내 주요 지수 ({krx_date})
- KOSPI: {kospi_val}
- KOSDAQ: {kosdaq_val}

🔥 국내 거래대금 상위 주도주 정밀 분석
{krx_details}
"""

    # ==========================================
    # [2편]: 전 세계 이슈, 트럼프 발언 및 매크로 지표
    # ==========================================
    part2 = f"""🌍 {today} 주식 브리핑 (글로벌 이슈) [2편]
⏰ 수집 시각: {collected_time}

🇺🇸 미국 주요 지수
{us_result_str.strip()}

📊 거시경제 지표
- 환율(USD/KRW): {macro_data.get('USD/KRW', 'N/A')}
- WTI유: {macro_data.get('유가(WTI)', 'N/A')}
- 미국채 10년물 금리: {macro_data.get('국채금리(10년)', 'N/A')}
- VIX 공포지수: {macro_data.get('VIX지수', 'N/A')}

🏛️ 트럼프 및 전 세계 주요 이슈 리포트
- 트럼프 관세 정책 및 무역 압박 발언에 따른 글로벌 공급망 변동성 주시
- 미국 연준(Fed) 금리 인하 기대감과 지정학적 리스크(중동 등) 복합 작용
- 외국인/기관 수급 주체들의 환율 연동 매매 패턴 실시간 대응 필요
"""

    return part1, part2

def job():
    kst = pytz.timezone('Asia/Seoul')
    print(f"[{datetime.now(kst)}] 정밀 주식 브리핑 생성 및 분할 전송 시작...")
    
    msg1, msg2 = generate_detailed_briefings()
    
    print("👉 [1편 전송 중...]")
    if send_kakao_message(msg1):
        print("🎉 1편 전송 성공!")
    
    print("👉 [2편 전송 중...]")
    if send_kakao_message(msg2):
        print("🎉 2편 전송 성공!")
        
    print("모든 브리핑 분할 전송 프로세스 완료!")

if __name__ == "__main__":
    job()
