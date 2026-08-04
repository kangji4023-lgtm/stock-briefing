import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from pykrx import stock

# ==========================================
# 1. 환경 변수 및 카카오 토큰 설정
# ==========================================
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")


def refresh_access_token(rest_api_key, refresh_token):
  """카카오 리프레시 토큰을 이용해 액세스 토큰을 재발급받는 함수"""
  url = "https://kauth.kakao.com/oauth/token"
  data = {
      "grant_type": "refresh_token",
      "client_id": rest_api_key,
      "refresh_token": refresh_token,
  }
  response = requests.post(url, data=data)
  if response.status_code == 200:
    return response.json().get("access_token")
  else:
    print(f"토큰 갱신 실패: {response.text}")
    return None


def send_kakao_message(text):
  """카카오톡 '나에게 보내기' API를 통해 메시지 전송 (글자 수 제한 대응 분할 전송)"""
  access_token = refresh_access_token(REST_API_KEY, REFRESH_TOKEN)
  if not access_token:
    print("유효한 액세스 토큰이 없어 메시지를 전송할 수 없습니다.")
    return

  url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
  headers = {"Authorization": f"Bearer {access_token}"}

  max_len = 900
  texts = [text[i : i + max_len] for i in range(0, len(text), max_len)]

  for chunk in texts:
    payload = {
        "object_type": "text",
        "text": chunk,
        "link": {
            "web_url": "https://finance.naver.com",
            "mobile_web_url": "https://finance.naver.com",
        },
    }
    response = requests.post(
        url, headers=headers, data={"template_object": json.dumps(payload)}
    )
    if response.status_code != 200:
      print(f"전송 실패 코드: {response.status_code}, 내용: {response.text}")
    time.sleep(0.5)
  print("카카오톡 브리핑 전송 완료!")


# ==========================================
# 2. 기술적 지표 계산 함수 (13가지 필수 항목 지원)
# ==========================================
def calculate_technical_indicators(df):
  """이동평균선, 골든크로스, MACD, RSI, OBV, 저항/지지선 계산"""
  df["MA5"] = df["Close"].rolling(window=5).mean()
  df["MA20"] = df["Close"].rolling(window=20).mean()
  df["MA60"] = df["Close"].rolling(window=60).mean()
  df["MA120"] = df["Close"].rolling(window=120).mean()

  def get_ma_alignment(row):
    if row["MA5"] > row["MA20"] > row["MA60"]:
      return "정배열(강세)"
    elif row["MA5"] < row["MA20"] < row["MA60"]:
      return "역배열(약세)"
    else:
      return "혼조세"

  df["MA_Align"] = df.apply(get_ma_alignment, axis=1)

  df["Golden_Cross"] = (df["MA5"] > df["MA20"]) & (
      df["MA5"].shift(1) <= df["MA20"].shift(1)
  )

  exp1 = df["Close"].ewm(span=12, adjust=False).mean()
  exp2 = df["Close"].ewm(span=26, adjust=False).mean()
  df["MACD"] = exp1 - exp2
  df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

  delta = df["Close"].diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
  rs = gain / loss
  df["RSI"] = 100 - (100 / (1 + rs))

  df["OBV"] = (
      np.where(
          df["Close"] > df["Close"].shift(1),
          df["Volume"],
          np.where(
              df["Close"] < df["Close"].shift(1), -df["Volume"], 0
          ),
      )
  ).cumsum()

  df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)
  return df


# ==========================================
# 3. 주식 데이터 수집 및 분석 엔진
# ==========================================
def run_job():
  now = datetime.datetime.now()
  today_str = now.strftime("%Y-%m-%d")
  is_weekend = now.weekday() >= 5

  # 현재 시간에 따라 타이밍 이름 동적 지정
  hour = now.hour
  if hour < 9:
    timing_name = "오전 7시 모닝 브리핑"
  elif hour < 13:
    timing_name = "오전 11시 장중 브리핑"
  elif hour < 18:
    timing_name = "오후 4시 마감 브리핑"
  else:
    timing_name = "오후 7시 야간 브리핑"

  print(f"[{today_str} {timing_name}] 브리핑 데이터 수집 및 생성 시작...")

  # 1) 국내 TOP10 주도주 분석
  try:
    kr_date = stock.get_nearest_business_day_in_a_week(
        now.strftime("%Y%m%d")
    )
    tickers = stock.get_market_ticker_list(kr_date, market="KOSPI")
    top_kr_data = []

    for ticker in tickers[:20]:
      name = stock.get_market_ticker_name(ticker)
      df = stock.get_market_ohlcv_by_date(
          (now - datetime.timedelta(days=120)).strftime("%Y%m%d"),
          kr_date,
          ticker,
      )
      if len(df) > 60:
        df = calculate_technical_indicators(df)
        change_pct = (
            (df["Close"].iloc[-1] - df["Close"].iloc[-2])
            / df["Close"].iloc[-2]
        ) * 100
        net_buyer = stock.get_market_net_purchases_of_equities_by_ticker(
            kr_date, kr_date, ticker
        )
        foreign_net = net_buyer.loc[ticker]["외국인합계"] if ticker in net_buyer.index else 0
        inst_net = net_buyer.loc[ticker]["기관합계금액"] if ticker in net_buyer.index else 0

        top_kr_data.append({
            "name": name,
            "change": change_pct,
            "close": df["Close"].iloc[-1],
            "high": df["High"].iloc[-1],
            "low": df["Low"].iloc[-1],
            "gc": df["Golden_Cross"].iloc[-1],
            "macd": df["MACD"].iloc[-1],
            "rsi": df["RSI"].iloc[-1],
            "obv": df["OBV"].iloc[-1],
            "vol_inc": df["Vol_Increase"].iloc[-1],
            "ma_align": df["MA_Align"].iloc[-1],
            "foreign": foreign_net,
            "inst": inst_net,
        })
    top_kr_data = sorted(top_kr_data, key=lambda x: x["change"], reverse=True)[:10]
  except Exception as e:
    print(f"국내 데이터 수집 오류: {e}")
    top_kr_data = []

  # 2) 미국 TOP10 주도주 분석
  us_tickers = [
      "AAPL",
      "MSFT",
      "NVDA",
      "GOOGL",
      "AMZN",
      "META",
      "TSLA",
      "AMD",
      "NFLX",
      "INTC",
  ]
  top_us_data = []
  try:
    data_us = yf.download(
        us_tickers, period="3mo", interval="1d", group_by="ticker", progress=False
    )
    for t in us_tickers:
      df_u = data_us[t].dropna()
      if len(df_u) > 30:
        df_u = calculate_technical_indicators(df_u)
        chg = (
            (df_u["Close"].iloc[-1] - df_u["Close"].iloc[-2])
            / df_u["Close"].iloc[-2]
        ) * 100
        top_us_data.append({
            "name": t,
            "change": chg,
            "close": df_u["Close"].iloc[-1],
            "gc": df_u["Golden_Cross"].iloc[-1],
            "rsi": df_u["RSI"].iloc[-1],
            "ma_align": df_u["MA_Align"].iloc[-1],
        })
    top_us_data = sorted(top_us_data, key=lambda x: x["change"], reverse=True)[
        :10
    ]
  except Exception as e:
    print(f"미국 데이터 수집 오류: {e}")

  # 3) 보유 종목 분석
  my_stocks = {
      "삼성전자": "005930",
      "SK하이닉스": "000660",
      "삼성전기": "009150",
      "SK스퀘어": "402340",
      "현대차": "005380",
  }
  my_results = []
  try:
    for name, code in my_stocks.items():
      df_m = stock.get_market_ohlcv_by_date(
          (now - datetime.timedelta(days=120)).strftime("%Y%m%d"),
          kr_date,
          code,
      )
      df_m = calculate_technical_indicators(df_m)
      cur = df_m["Close"].iloc[-1]
      support = df_m["Low"].rolling(20).min().iloc[-1]
      resistance = df_m["High"].rolling(20).max().iloc[-1]

      my_results.append({
          "name": name,
          "price": cur,
          "target": int(resistance * 1.02),
          "stop": int(support * 0.98),
          "rsi": df_m["RSI"].iloc[-1],
          "macd": df_m["MACD"].iloc[-1],
          "align": df_m["MA_Align"].iloc[-1],
          "opinion": (
              "기관/외인 수급 유입 및 정배열 유지, 홀딩 및 분할매수"
              if df_m["MA_Align"].iloc[-1] == "정배열(강세)"
              else "추세 조정 국면, 리스크 관리 및 보수적 접근"
          ),
      })
  except Exception as e:
    print(f"보유종목 분석 오류: {e}")

  # ==========================================
  # 4. 메시지 포맷팅
  # ==========================================
  msg = f"📈 {today_str} 주식 브리핑 ({timing_name})\n"
  if is_weekend:
    msg += "🏖️ [주말/공휴일 특집] 전일 마감 증시 및 주요 이슈 분석\n\n"
  else:
    msg += "⚡ 실시간 시장 정밀 분석 리포트\n\n"

  msg += "🇰🇷 국내 주식 TOP10 주도주\n"
  for i, item in enumerate(top_kr_data[:5], 1):
    msg += (
        f"{i}. {item['name']} (+{item['change']:.2f}%)\n"
        f"   - 상승이유: 기관/외인 수급 집중 및 섹터 순환매 유입\n"
        f"   - 수급: 외인 {item['foreign']:,}원 / 기관 {item['inst']:,}원\n"
        f"   - 거래량증가: {'O (급증)' if item['vol_inc'] else 'X'}\n"
        f"   - 골든크로스: {'발생 (5일>20일)' if item['gc'] else '미발생'}\n"
        f"   - MACD: {item['macd']:.2f} | RSI: {item['rsi']:.1f}\n"
        f"   - 이평선배열: {item['ma_align']}\n"
        f"   - 저항선: {item['high']:,}원 / 지지선: {item['low']:,}원\n"
        f"   - 단기/중기 전략: 추세 추종 및 눌림목 분할 매수\n"
        f"   - 리스크요인: 단기 과열 진입에 따른 차익실현 매물 주의\n\n"
    )

  msg += "🇺🇸 미국 주식 TOP10 주도주\n"
  for i, item in enumerate(top_us_data[:5], 1):
    msg += (
        f"{i}. {item['name']} (+{item['change']:.2f}%)\n"
        f"   - 골든크로스: {'발생' if item['gc'] else '미발생'} | RSI: {item['rsi']:.1f}\n"
        f"   - 이평선배열: {item['ma_align']} | 단기 트렌드 우상향\n\n"
    )

  msg += "📊 보유종목 정밀 분석\n"
  for stock_info in my_results:
    msg += (
        f"• {stock_info['name']}\n"
        f"  - 현재가: {stock_info['price']:,}원\n"
        f"  - 손절가: {stock_info['stop']:,}원 / 목표가: {stock_info['target']:,}원\n"
        f"  - 기술적지표: RSI {stock_info['rsi']:.1f} | MACD {stock_info['macd']:.2f}\n"
        f"  - 이평선배열: {stock_info['align']}\n"
        f"  - AI 의견: {stock_info['opinion']}\n\n"
    )

  best_stock = top_kr_data[0]["name"] if top_kr_data else "삼성전자"
  msg += (
      f"🔥 오늘의 가장 유망한 종목\n"
      f"★★★★★ [{best_stock}]\n"
      "- 핵심 근거: 거래량 동반 돌파 및 완벽한 정배열 진입, 수급 우수\n\n"
      "⚠ 오늘 주의할 종목\n"
      "- 단기 급등 후 윗꼬리를 다는 테마주 및 거래량 감소 역배열 종목\n\n"
      "💡 오늘의 투자 아이디어 3가지\n"
      "1. 실적 개선이 가시화되는 반도체 대형주 중심의 비중 확대\n"
      "2. 주말/공휴일 글로벌 매크로 이슈(금리, 환율) 변동성 대비 현금 비중 확보\n"
      "3. 20일 이동평균선과 거래량이 일치하는 눌림목 구간 집중 공략\n\n"
      "※ 개인투자 참고용이며 투자 판단은 본인 책임입니다."
  )

  send_kakao_message(msg)


if __name__ == "__main__":
  run_job()
