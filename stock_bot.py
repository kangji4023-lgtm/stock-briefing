import os
import json
import time
from datetime import datetime, timedelta

import pytz
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from pykrx import stock


# =========================================================
# 기본 설정
# =========================================================

KST = pytz.timezone("Asia/Seoul")

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()


# =========================================================
# 공통 함수
# =========================================================

def now_kst():
    return datetime.now(KST)


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_num(value, digits=2):
    if value is None:
        return "조회 실패"

    try:
        value = float(value)

        if digits == 0:
            return f"{value:,.0f}"

        return f"{value:,.{digits}f}"

    except Exception:
        return "조회 실패"


def fmt_rate(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "조회 실패"


# =========================================================
# 카카오 Access Token
# =========================================================

def get_kakao_access_token():

    if not KAKAO_REST_API_KEY:
        print("[KAKAO ERROR] KAKAO_REST_API_KEY가 없습니다.")
        return None

    if not KAKAO_REFRESH_TOKEN:
        print("[KAKAO ERROR] KAKAO_REFRESH_TOKEN이 없습니다.")
        return None

    url = "https://kauth.kakao.com/oauth/token"

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }

    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    try:

        response = requests.post(
            url,
            data=data,
            timeout=15
        )

        print("[KAKAO TOKEN]", response.status_code)

        if response.status_code != 200:
            print("[KAKAO TOKEN ERROR]", response.text[:500])
            return None

        result = response.json()

        access_token = result.get("access_token")

        if not access_token:
            print("[KAKAO TOKEN ERROR] access_token 없음")
            return None

        return access_token

    except Exception as e:

        print("[KAKAO TOKEN EXCEPTION]", e)

        return None


# =========================================================
# 카카오 메시지 분할
#
# 중요:
# 논리적 브리핑 = 최대 900자
# 실제 API 전송 = 190자씩 분할
#
# =========================================================

def split_message(text, max_chars=190):

    text = str(text)

    chunks = []

    while len(text) > max_chars:

        cut = text.rfind("\n", 0, max_chars)

        if cut < 80:
            cut = text.rfind(" ", 0, max_chars)

        if cut < 80:
            cut = max_chars

        chunks.append(text[:cut].strip())

        text = text[cut:].strip()

    if text:
        chunks.append(text)

    return chunks


def send_kakao_message(text):

    access_token = get_kakao_access_token()

    if not access_token:
        print("[KAKAO] Access Token 발급 실패")
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    chunks = split_message(text, 190)

    print(f"[KAKAO] 전송 메시지 수: {len(chunks)}")

    success_count = 0

    for index, chunk in enumerate(chunks, 1):

        template_object = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            }
        }

        data = {
            "template_object": json.dumps(
                template_object,
                ensure_ascii=False
            )
        }

        try:

            response = requests.post(
                url,
                headers=headers,
                data=data,
                timeout=15
            )

            print(
                f"[KAKAO] {index}/{len(chunks)} "
                f"status={response.status_code}"
            )

            if response.status_code == 200:
                success_count += 1
            else:
                print("[KAKAO ERROR]", response.text[:500])

            time.sleep(0.5)

        except Exception as e:

            print("[KAKAO SEND ERROR]", e)

    return success_count == len(chunks)


# =========================================================
# KRX 영업일
# =========================================================

def get_safe_krx_date():

    now = now_kst()

    for offset in range(0, 8):

        date_obj = now - timedelta(days=offset)

        date_str = date_obj.strftime("%Y%m%d")

        try:

            df = stock.get_market_ohlcv_by_ticker(date_str)

            if df is not None and not df.empty:

                return date_str

        except Exception as e:

            print(
                f"[KRX] {date_str} 조회 실패: {e}"
            )

    return now.strftime("%Y%m%d")


# =========================================================
# KRX 지수
# =========================================================

def get_krx_indices(date):

    result = {
        "kospi": None,
        "kosdaq": None
    }

    try:

        df = stock.get_index_ohlcv_by_date(
            date,
            date,
            "1001"
        )

        if df is not None and not df.empty:

            row = df.iloc[-1]

            result["kospi"] = {
                "close": safe_float(row.get("종가")),
                "rate": safe_float(row.get("등락률"))
            }

    except Exception as e:

        print("[KOSPI ERROR]", e)

    try:

        df = stock.get_index_ohlcv_by_date(
            date,
            date,
            "2001"
        )

        if df is not None and not df.empty:

            row = df.iloc[-1]

            result["kosdaq"] = {
                "close": safe_float(row.get("종가")),
                "rate": safe_float(row.get("등락률"))
            }

    except Exception as e:

        print("[KOSDAQ ERROR]", e)

    return result


# =========================================================
# KRX 거래대금 TOP10
# =========================================================

def get_krx_top10(date):

    result = []

    try:

        df = stock.get_market_trading_value_by_ticker(
            date,
            date,
            "ALL"
        )

        if df is None or df.empty:

            print("[KRX] 거래대금 데이터 없음")
            return result

        value_column = None

        for col in ["거래대금", "거래대금합계"]:

            if col in df.columns:
                value_column = col
                break

        if value_column is None:

            print(
                "[KRX] 거래대금 컬럼 없음:",
                list(df.columns)
            )

            return result

        df = df.sort_values(
            by=value_column,
            ascending=False
        ).head(10)

        for ticker, row in df.iterrows():

            try:

                name = stock.get_market_ticker_name(
                    ticker
                )

                ohlcv = stock.get_market_ohlcv_by_date(
                    date,
                    date,
                    ticker
                )

                if ohlcv is not None and not ohlcv.empty:

                    price = safe_float(
                        ohlcv["종가"].iloc[-1]
                    )

                    rate = safe_float(
                        ohlcv["등락률"].iloc[-1]
                    )

                    volume = safe_float(
                        ohlcv["거래량"].iloc[-1]
                    )

                else:

                    price = 0
                    rate = 0
                    volume = 0

                value = safe_float(
                    row[value_column]
                )

                result.append({
                    "ticker": ticker,
                    "name": name,
                    "price": price,
                    "rate": rate,
                    "volume": volume,
                    "value": value
                })

            except Exception as e:

                print(
                    f"[KRX TOP] {ticker} 오류:",
                    e
                )

        return result

    except Exception as e:

        print("[KRX TOP10 ERROR]", e)

        return result


# =========================================================
# 섹터 분류
# =========================================================

def classify_sector(name):

    name = str(name)

    if any(
        x in name
        for x in [
            "삼성전자",
            "하이닉스",
            "한미반도체",
            "반도체",
            "SK스퀘어",
            "이오테크닉스"
        ]
    ):
        return "반도체·AI"

    if any(
        x in name
        for x in [
            "에코프로",
            "엘앤에프",
            "포스코",
            "배터리",
            "LG에너지",
            "삼성SDI"
        ]
    ):
        return "2차전지·소재"

    if any(
        x in name
        for x in [
            "한화",
            "현대로템",
            "한국항공",
            "방산",
            "KAI"
        ]
    ):
        return "방산·중공업"

    if any(
        x in name
        for x in [
            "셀트리온",
            "삼성바이오",
            "바이오",
            "제약",
            "헬스케어"
        ]
    ):
        return "바이오·헬스케어"

    if any(
        x in name
        for x in [
            "현대차",
            "기아",
            "자동차",
            "모비스"
        ]
    ):
        return "자동차·모빌리티"

    return "기타"


# =========================================================
# Yahoo Finance
# =========================================================

def yf_history(symbol, period="6mo"):

    for attempt in range(3):

        try:

            df = yf.Ticker(symbol).history(
                period=period,
                interval="1d",
                auto_adjust=False
            )

            if df is not None and not df.empty:
                return df

        except Exception as e:

            print(
                f"[YF] {symbol} "
                f"{attempt + 1}/3 오류:",
                e
            )

        time.sleep(1)

    return pd.DataFrame()


# =========================================================
# 미국 지수
# =========================================================

def get_us_indices():

    symbols = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI"
    }

    result = {}

    for name, symbol in symbols.items():

        try:

            df = yf_history(
                symbol,
                "5d"
            )

            if len(df) >= 2:

                current = safe_float(
                    df["Close"].iloc[-1]
                )

                previous = safe_float(
                    df["Close"].iloc[-2]
                )

                rate = (
                    (current - previous)
                    / previous
                    * 100
                    if previous
                    else 0
                )

                result[name] = {
                    "value": current,
                    "rate": rate
                }

            else:

                result[name] = {
                    "value": 0,
                    "rate": 0
                }

        except Exception as e:

            print(
                f"[US INDEX] {name}:",
                e
            )

            result[name] = {
                "value": 0,
                "rate": 0
            }

    return result


# =========================================================
# 거시경제
# =========================================================

def get_macro():

    symbols = {
        "환율": "USDKRW=X",
        "WTI": "CL=F",
        "미국채10년": "^TNX",
        "VIX": "^VIX"
    }

    result = {}

    for name, symbol in symbols.items():

        try:

            df = yf_history(
                symbol,
                "5d"
            )

            if not df.empty:

                value = safe_float(
                    df["Close"].iloc[-1]
                )

                result[name] = value

            else:

                result[name] = 0

        except Exception as e:

            print(
                f"[MACRO] {name}:",
                e
            )

            result[name] = 0

    return result


# =========================================================
# 기술적 분석
# =========================================================

def technical_analysis(symbol):

    df = yf_history(
        symbol,
        "6mo"
    )

    if df.empty or len(df) < 60:

        return None

    try:

        close = pd.to_numeric(
            df["Close"],
            errors="coerce"
        ).dropna()

        volume = pd.to_numeric(
            df["Volume"],
            errors="coerce"
        ).fillna(0)

        sma5 = close.rolling(5).mean()
        sma20 = close.rolling(20).mean()
        sma60 = close.rolling(60).mean()

        ema12 = close.ewm(
            span=12,
            adjust=False
        ).mean()

        ema26 = close.ewm(
            span=26,
            adjust=False
        ).mean()

        macd = ema12 - ema26

        signal = macd.ewm(
            span=9,
            adjust=False
        ).mean()

        delta = close.diff()

        gain = delta.clip(
            lower=0
        ).rolling(14).mean()

        loss = (
            -delta.clip(upper=0)
        ).rolling(14).mean()

        rs = gain / loss.replace(
            0,
            np.nan
        )

        rsi = 100 - (
            100 / (1 + rs)
        )

        obv_change = np.where(
            close.diff() > 0,
            volume,
            np.where(
                close.diff() < 0,
                -volume,
                0
            )
        )

        obv = pd.Series(
            obv_change,
            index=close.index
        ).cumsum()

        current = safe_float(
            close.iloc[-1]
        )

        previous = safe_float(
            close.iloc[-2]
        )

        rate = (
            (current - previous)
            / previous
            * 100
            if previous
            else 0
        )

        s5 = safe_float(
            sma5.iloc[-1]
        )

        s20 = safe_float(
            sma20.iloc[-1]
        )

        s60 = safe_float(
            sma60.iloc[-1]
        )

        rsi_value = safe_float(
            rsi.iloc[-1],
            50
        )

        macd_value = safe_float(
            macd.iloc[-1]
        )

        signal_value = safe_float(
            signal.iloc[-1]
        )

        spread = (
            sma5 - sma20
        ).dropna()

        golden = False

        if len(spread) >= 2:

            if (
                spread.iloc[-2] <= 0
                and spread.iloc[-1] > 0
            ):
                golden = True

        if (
            current > s5
            and s5 > s20
            and s20 > s60
        ):
            trend = "강한 상승"

        elif (
            current > s20
            and s20 >= s60
        ):
            trend = "상승"

        elif current >= s60:

            trend = "중립"

        else:

            trend = "조정/하락"

        if rsi_value >= 70:

            rsi_state = "과열"

        elif rsi_value >= 55:

            rsi_state = "상승 우위"

        elif rsi_value > 45:

            rsi_state = "중립"

        elif rsi_value > 30:

            rsi_state = "약세"

        else:

            rsi_state = "과매도"

        macd_state = (
            "상승"
            if macd_value > signal_value
            else "하락"
        )

        obv_state = (
            "매수세 증가"
            if len(obv) >= 5
            and obv.iloc[-1] > obv.iloc[-5]
            else "매수세 둔화"
        )

        score = 0

        if golden:
            score += 3

        if 50 <= rsi_value < 70:
            score += 2

        if macd_value > signal_value:
            score += 2

        if obv_state == "매수세 증가":
            score += 2

        if trend in [
            "강한 상승",
            "상승"
        ]:
            score += 2

        return {
            "price": current,
            "rate": rate,
            "sma5": s5,
            "sma20": s20,
            "sma60": s60,
            "rsi": rsi_value,
            "macd": macd_value,
            "signal": signal_value,
            "golden": golden,
            "trend": trend,
            "rsi_state": rsi_state,
            "macd_state": macd_state,
            "obv_state": obv_state,
            "score": score
        }

    except Exception as e:

        print(
            f"[TA] {symbol}:",
            e
        )

        return None


# =========================================================
# 관심종목
# =========================================================

KOREA_WATCHLIST = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "삼성전기": "009150.KS",
    "SK스퀘어": "402340.KS",
    "현대차": "005380.KS",
    "삼성SDI": "006400.KS",
    "한미반도체": "042700.KS",
    "LS ELECTRIC": "010120.KS"
}


USA_WATCHLIST = {
    "NVIDIA": "NVDA",
    "Microsoft": "MSFT",
    "Apple": "AAPL",
    "Alphabet A": "GOOGL",
    "Amazon": "AMZN",
    "Meta": "META",
    "Tesla": "TSLA",
    "Broadcom": "AVGO"
}


def get_watchlist_analysis():

    korea = []
    usa = []

    for name, symbol in KOREA_WATCHLIST.items():

        result = technical_analysis(
            symbol
        )

        if result:

            korea.append(
                (
                    name,
                    symbol,
                    result
                )
            )

    for name, symbol in USA_WATCHLIST.items():

        result = technical_analysis(
            symbol
        )

        if result:

            usa.append(
                (
                    name,
                    symbol,
                    result
                )
            )

    korea.sort(
        key=lambda x: x[2]["score"],
        reverse=True
    )

    usa.sort(
        key=lambda x: x[2]["score"],
        reverse=True
    )

    return korea, usa


# =========================================================
# 시장 분위기
# =========================================================

def market_mood(krx, us):

    rates = []

    if krx.get("kospi"):
        rates.append(
            krx["kospi"]["rate"]
        )

    if krx.get("kosdaq"):
        rates.append(
            krx["kosdaq"]["rate"]
        )

    if us.get("NASDAQ"):
        rates.append(
            us["NASDAQ"]["rate"]
        )

    if not rates:
        return "시장 데이터 확인 필요"

    avg = sum(rates) / len(rates)

    if avg >= 1.0:
        return "강한 위험선호·매수 우위"

    if avg >= 0.3:
        return "상승 우위"

    if avg <= -1.0:
        return "변동성 확대·하방 압력"

    if avg <= -0.3:
        return "약세·위험관리 필요"

    return "혼조·종목별 차별화"


# =========================================================
# 종목 분석 문구
# =========================================================

def stock_signal(a):

    signals = []

    if a["golden"]:
        signals.append(
            "골든크로스"
        )

    if a["macd"] > a["signal"]:
        signals.append(
            "MACD 상승"
        )

    if a["obv_state"] == "매수세 증가":
        signals.append(
            "OBV 증가"
        )

    if (
        a["trend"]
        in ["상승", "강한 상승"]
    ):
        signals.append(
            "이평 상승"
        )

    if not signals:
        signals.append(
            "강한 기술신호 부족"
        )

    return ", ".join(signals)


# =========================================================
# 900자 파트 안전 처리
# =========================================================

def limit_part(text, limit=900):

    text = str(text)

    if len(text) <= limit:
        return text

    return text[:limit - 20] + "\n…(900자 제한)"


# =========================================================
# 6파트 상세 브리핑
# =========================================================

def generate_briefing():

    now = now_kst()

    today = now.strftime(
        "%Y-%m-%d"
    )

    hour = now.hour

    if hour < 9:

        time_label = (
            "오전 7시 미국장 마감"
        )

    elif hour < 13:

        time_label = (
            "오전 11시 국내장 장중"
        )

    elif hour < 17:

        time_label = (
            "오후 4시 국내장 마감"
        )

    else:

        time_label = (
            "오후 7시 글로벌 대응"
        )

    print(
        f"[BRIEFING] {today} {time_label}"
    )

    # -------------------------------
    # 데이터 수집
    # -------------------------------

    krx_date = get_safe_krx_date()

    indices = get_krx_indices(
        krx_date
    )

    top10 = get_krx_top10(
        krx_date
    )

    us = get_us_indices()

    macro = get_macro()

    kr_watch, us_watch = (
        get_watchlist_analysis()
    )

    mood = market_mood(
        indices,
        us
    )

    # =====================================================
    # PART 1
    # =====================================================

    kospi = indices.get(
        "kospi"
    )

    kosdaq = indices.get(
        "kosdaq"
    )

    p1 = f"""📅 {today} {time_label} [1/6]
━━━━━━━━━━━━━━━━━━
🌍 국내시장 종합 브리핑

■ 시장 분위기
{mood}

■ KOSPI
{fmt_num(kospi["close"]) if kospi else "조회 실패"} / {fmt_rate(kospi["rate"]) if kospi else "조회 실패"}

■ KOSDAQ
{fmt_num(kosdaq["close"]) if kosdaq else "조회 실패"} / {fmt_rate(kosdaq["rate"]) if kosdaq else "조회 실패"}

■ 거래대금 TOP10"""

    for i, item in enumerate(
        top10[:10],
        1
    ):

        p1 += (
            f"\n{i}. {item['name']} "
            f"{item['price']:,.0f}원 "
            f"{item['rate']:+.2f}% "
            f"{item['value']/100000000:,.0f}억"
        )

    p1 += """
\n■ 해석
오늘은 단순 상승률보다 거래대금이 실제로 집중되는 종목을 우선 확인합니다. 거래대금과 거래량이 함께 증가하면서 20일선 위에서 움직이는 종목은 상대적으로 수급이 강한 후보입니다. 반대로 상승률은 높지만 거래대금이 감소하면 추격매수 위험을 확인해야 합니다."""

    # =====================================================
    # PART 2
    # =====================================================

    p2 = f"""📊 글로벌 증시·거시경제 [2/6]
━━━━━━━━━━━━━━━━━━
🇺🇸 미국 주요 지수

NASDAQ
{fmt_num(us["NASDAQ"]["value"])} / {fmt_rate(us["NASDAQ"]["rate"])}

S&P500
{fmt_num(us["S&P500"]["value"])} / {fmt_rate(us["S&P500"]["rate"])}

DOW
{fmt_num(us["DOW"]["value"])} / {fmt_rate(us["DOW"]["rate"])}

■ 핵심 지표
원/달러: {fmt_num(macro["환율"])}원
WTI: ${fmt_num(macro["WTI"])}
미국채10년: {fmt_num(macro["미국채10년"])}
VIX: {fmt_num(macro["VIX"])}

■ 시장 해석
NASDAQ 강세가 이어지면 국내 반도체·AI 관련주의 투자심리에 긍정적일 수 있습니다. 반대로 미국채 금리와 VIX가 동시에 상승하면 성장주와 고밸류 종목의 변동성이 커질 수 있습니다. 원/달러 상승도 외국인 수급에는 부담 요인입니다."""

    # =====================================================
    # PART 3
    # =====================================================

    sector_count = {}

    for item in top10:

        sector = classify_sector(
            item["name"]
        )

        sector_count[sector] = (
            sector_count.get(
                sector,
                0
            ) + 1
        )

    sector_rank = sorted(
        sector_count.items(),
        key=lambda x: x[1],
        reverse=True
    )

    sector_text = "\n".join(
        f"{i}. {sector} ({count}종목)"
        for i, (
            sector,
            count
        ) in enumerate(
            sector_rank[:5],
            1
        )
    )

    if not sector_text:
        sector_text = (
            "섹터 데이터 조회 실패"
        )

    p3 = f"""🔥 오늘의 주도주·섹터 [3/6]
━━━━━━━━━━━━━━━━━━

■ 거래대금 기반 주도섹터

{sector_text}

■ 오늘의 주도주 판단 기준
① 거래대금 증가
② 거래량 증가
③ 상승률
④ 20일선 위 유지
⑤ MACD 방향
⑥ OBV 증가

■ 상승 이유 분석
거래대금 상위 종목은 단순히 많이 오른 종목이 아니라 실제 시장 자금이 집중되는 종목입니다. 반도체·AI는 미국 기술주와 메모리 가격 및 AI 투자 사이클 영향을 함께 봅니다. 방산·중공업은 수주와 정책 이슈, 자동차는 환율·판매량·신차 모멘텀, 2차전지는 원재료 가격과 업황 및 개별 기업 뉴스의 영향을 크게 받습니다.

※ 실제 뉴스가 확인되지 않은 경우 상승 원인을 추측하지 않고 수급·가격 데이터 중심으로 판단합니다."""

    # =====================================================
    # PART 4
    # =====================================================

    p4 = """🇰🇷 국내 핵심종목 기술적 분석 [4/6]
━━━━━━━━━━━━━━━━━━
"""

    for i, (
        name,
        symbol,
        a
    ) in enumerate(
        kr_watch[:8],
        1
    ):

        p4 += (
            f"{i}. {name} "
            f"{a['price']:,.0f}원 "
            f"{a['rate']:+.2f}%\n"
            f"   RSI {a['rsi']:.1f} "
            f"/ MACD {a['macd_state']} "
            f"/ OBV {a['obv_state']}\n"
            f"   5/20/60선 "
            f"{a['sma5']:,.0f}/"
            f"{a['sma20']:,.0f}/"
            f"{a['sma60']:,.0f}\n"
            f"   추세 {a['trend']} "
            f"/ {stock_signal(a)}\n"
        )

    if not kr_watch:

        p4 += (
            "국내 기술적 데이터 조회 실패\n"
        )

    p4 += """
■ 해석
RSI 50~70은 상승 모멘텀을 확인하기 좋은 구간이며 70 이상은 과열 가능성을 점검합니다. MACD가 Signal보다 높으면 단기 모멘텀 우위입니다. OBV가 상승하면 거래량 기준 매수세 개선을 의미할 수 있습니다. 5일선이 20일선을 상향 돌파하는 골든크로스는 다른 지표와 함께 확인해야 합니다."""

    # =====================================================
    # PART 5
    # =====================================================

    p5 = """🇺🇸 미국 핵심종목 기술적 분석 [5/6]
━━━━━━━━━━━━━━━━━━
"""

    for i, (
        name,
        symbol,
        a
    ) in enumerate(
        us_watch[:8],
        1
    ):

        p5 += (
            f"{i}. {name} "
            f"{a['price']:,.2f} "
            f"{a['rate']:+.2f}%\n"
            f"   RSI {a['rsi']:.1f} "
            f"/ MACD {a['macd_state']} "
            f"/ OBV {a['obv_state']}\n"
            f"   추세 {a['trend']} "
            f"/ {stock_signal(a)}\n"
        )

    if not us_watch:

        p5 += (
            "미국 기술적 데이터 조회 실패\n"
        )

    p5 += """
■ 핵심 포인트
NVIDIA·Broadcom은 AI·반도체 투자심리를 확인하는 대표 종목입니다. Microsoft·Alphabet·Amazon·Meta는 대형 기술주 수급과 실적 기대를 확인합니다. Tesla는 상대적으로 변동성이 크므로 RSI와 거래량을 함께 보는 것이 중요합니다. 기술적 신호만으로 실적이나 뉴스의 방향을 단정하지 않습니다."""

    # =====================================================
    # PART 6
    # =====================================================

    focus = (
        kr_watch[:4]
        + us_watch[:4]
    )

    focus.sort(
        key=lambda x: x[2]["score"],
        reverse=True
    )

    p6 = f"""🎯 오늘의 투자전략 [6/6]
━━━━━━━━━━━━━━━━━━

■ 우선 관찰 후보"""

    for name, symbol, a in focus[:5]:

        p6 += (
            f"\n⭐ {name}: "
            f"{a['trend']} / "
            f"RSI {a['rsi']:.1f} / "
            f"{stock_signal(a)}"
        )

    p6 += f"""

■ 매수 전략
장대양봉 직후 추격매수보다 20일선 또는 단기 이동평균선 눌림목을 우선 확인합니다. 골든크로스가 발생했더라도 거래량과 OBV가 동반되는지 확인합니다.

■ 보유 전략
상승 추세 종목은 5일선과 20일선 이탈 여부를 확인합니다. MACD 하락전환과 OBV 감소가 동시에 발생하면 단기 모멘텀 약화를 주의합니다.

■ 리스크
환율 {macro["환율"]:,.2f}원
VIX {macro["VIX"]:,.2f}
미국채10년 {macro["미국채10년"]:,.2f}

■ 최종 판단
오늘은
거래대금 → 거래량 → 20일선 → RSI → MACD → OBV → 뉴스
순서로 확인하는 것이 좋습니다.

※ 본 브리핑은 투자 참고정보이며 실제 투자 판단과 손익 책임은 투자자에게 있습니다."""

    # =====================================================
    # 각 파트 900자 제한
    # =====================================================

    parts = [
        limit_part(p1),
        limit_part(p2),
        limit_part(p3),
        limit_part(p4),
        limit_part(p5),
        limit_part(p6)
    ]

    return parts


# =========================================================
# 실행
# =========================================================

def job():

    print(
        "=" * 60
    )

    print(
        "[START] 주식 브리핑 시작"
    )

    try:

        parts = generate_briefing()

        print(
            f"[INFO] 총 {len(parts)}개 파트 생성"
        )

        success = True

        for index, part in enumerate(
            parts,
            1
        ):

            print(
                f"[PART {index}] "
                f"{len(part)}자"
            )

            result = send_kakao_message(
                part
            )

            if not result:

                success = False

            # 파트 사이 잠시 대기
            time.sleep(1)

        if success:

            print(
                "[SUCCESS] "
                "모든 브리핑 전송 완료"
            )

        else:

            print(
                "[WARNING] "
                "일부 카카오 메시지 전송 실패"
            )

    except Exception as e:

        print(
            "[FATAL ERROR]",
            e
        )

        raise


if __name__ == "__main__":

    job()
