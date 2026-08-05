import datetime
import json
import requests
import yfinance as yf

# ==========================================================
# 카카오 액세스 토큰 직접 입력 (토큰 갱신 에러 원천 차단)
# ==========================================================
ACCESS_TOKEN = "AJXH9B9y1ymGUjGmmrcLPaLQ0-UEuBAAAAAPoXEi0AAAGfy0UaNaj01SImjvGc"

def send_to_kakao(text):
    """액세스 토큰을 이용해 카카오톡 '나에게 보내기' 메시지 즉시 전송"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": "Bearer " + ACCESS_TOKEN
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
# 미국 야간 장 반영 애널리스트 모닝 브리핑 생성
# ==========================================================
def get_analyst_briefing():
    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        tickers = {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "US Dollar/KRW": "USDKRW=X"
        }
        
        market_data = {}
        for name, symbol in tickers.items():
            df = yf.Ticker(symbol).history(period="2d")
            if not df.empty and len(df) >= 2:
                close = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                diff = close - prev
                diff_pct = (diff / prev) * 100
                market_data[name] = {"close": close, "pct": diff_pct}

        briefing = f"📊 [{today_str} 모닝 애널리스트 리포트]\n"
        briefing += f"━━━━━━━━━━━━━━━━━━━\n"
        briefing += f"🏛️ [전밤 미국 야간 증시 리뷰]\n\n"
        
        for name, val in market_data.items():
            sign = "📈 +" if val["pct"] > 0 else "📉 "
            if name == "US Dollar/KRW":
                briefing += f"• {name}: {val['close']:,.2f}원 ({sign}{val['pct']:.2f}%)\n"
            else:
                briefing += f"• {name}: {val['close']:,.2f} ({sign}{val['pct']:.2f}%)\n"
                
        briefing += f"\n💡 [오늘 아침 국내장 대응 전략]\n"
        briefing += f"1. 미 증시 마감 흐름 연동 국내외 섹터별 차별화 장세 예상\n"
        briefing += f"2. 환율 변동성에 따른 외국인 수급 동향 집중 모니터링 필요\n"
        briefing += f"3. 추격 매수보다는 핵심 주도주 중심의 눌림목 분할 접근 권장\n\n"
        briefing += f"\"성공적인 투자를 응원합니다. 원칙 지키는 하루 되세요!\""
        
        return briefing
    except Exception as e:
        return f"[애널리스트 봇 오류 발생]\n내용: {str(e)}"


if __name__ == "__main__":
    print("애널리스트 모닝 브리핑 봇 실행 중...")
    message = get_analyst_briefing()
    print("생성된 메시지:\n", message)
    send_to_kakao(message)
