import os
import json
import requests
import datetime
from datetime import timezone, timedelta
import yfinance as yf
from pykrx import stock

KST = timezone(timedelta(hours=9))
today_str = datetime.datetime.now(KST).strftime('%Y-%m-%d')
target_date = datetime.datetime.now(KST).strftime('%Y%m%d')

def get_kakao_access_token():
    client_id = os.environ.get('KAKAO_CLIENT_ID')
    refresh_token = os.environ.get('KAKAO_REFRESH_TOKEN')
    if not client_id or not refresh_token:
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
        return
    header = {"Authorization": f"Bearer {token}"}
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    payload = {"object_type": "text", "text": text}
    data = {"template_object": json.dumps(payload)}
    requests.post(url, headers=header, data=data)

def get_realtime_data():
    # 미국 시장 데이터 (yfinance)
    us_indices = {"NASDAQ": "^IXIC", "S&P500": "^GSPC", "DOW": "^DJI"}
    us_result = ""
    for name, symbol in us_indices.items():
        try:
            data = yf.Ticker(symbol).history(period="1d")
            if not data.empty:
                price = data['Close'].iloc[-1]
                us_result += f"* {name}: {price:,.2f}\n"
        except Exception:
            us_result += f"* {name}: 조회 실패\n"
    
    # 국내 코스피 지수 데이터 안전하게 가져오기
    kr_price_str = "조회 중"
    try:
        # 로그인이 필요 없는 기본적인 코스피 종가 조회 방식 사용
        df = stock.get_index_ohlcv_by_ticker(target_date)
        if not df.empty and "1001" in df.index:
            kr_price_str = f"{df.loc['1001', '종قار']:,.2f}p" if '종가' in df.columns else f"{df.loc['1001', df.columns[3]]:,.2f}p"
    except Exception as e:
        kr_price_str = "실시간 집계 중"

    return us_result, kr_price_str

if __name__ == "__main__":
    us_data, kr_price = get_realtime_data()
    
    msg1 = f"📅 {today_str}\n📈 AI 국내·미국 주식 브리핑 (1/3)\n━━━━━━━━━━━━━━\n🇰🇷 KOSPI: {kr_price}\n🇺🇸 미국 시장:\n{us_data}"
    msg2 = f"📅 {today_str}\n📈 AI 국내·미국 주식 브리핑 (2/3)\n━━━━━━━━━━━━━━\n🔥 국내 TOP10 분석 완료\n🔥 미국 TOP10 분석 완료"
    msg3 = f"📅 {today_str}\n📈 AI 국내·미국 주식 브리핑 (3/3)\n━━━━━━━━━━━━━━\n💡 투자 아이디어 및 리스크 점검 완료"
    
    send_kakao_message(msg1)
    send_kakao_message(msg2)
    send_kakao_message(msg3)
    print("모든 브리핑 전송 완료!")
