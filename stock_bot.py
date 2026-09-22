import os
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from pykrx import stock

# =========================================================
# 기본 설정
# =========================================================
KST = ZoneInfo("Asia/Seoul")

CHART_DIR = Path("charts")
CHART_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# GitHub Actions Secrets
# ---------------------------------------------------------
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()
GITHUB_BRANCH = os.getenv("GITHUB_REF_NAME", "main").strip() or "main"

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# ============================================================
# 국내 관심종목
# ============================================================

KR_STOCKS = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "삼성전기": "009150",
    "SK스퀘어": "402340",
    "현대차": "005380",
    "삼성SDI": "006400",
    "한미반도체": "042700",
    "LS ELECTRIC": "010120",
    "한화에어로스페이스": "012450",
    "두산에너빌리티": "034020",
    "일진전기": "103590",
    "삼성바이오로직스": "207940",
    "셀트리온": "068270",
    "NAVER": "035420",
    "카카오": "035720",
    "현대모비스": "012330",
    "HD현대중공업": "329180",
    "한화오션": "042660",
    "두산로보틱스": "454910",
    "레인보우로보틱스": "277810",
    "HPSP": "403870",
    "PSK홀딩스": "031980",
    "삼천당제약": "000250",
    "현대로템": "064350",
    "LIG넥스원": "079550",
}


# ============================================================
# 미국 관심종목
# ============================================================

US_STOCKS = {
    "NVIDIA": "NVDA",
    "Microsoft": "MSFT",
    "Apple": "AAPL",
    "Amazon": "AMZN",
    "Alphabet": "GOOGL",
    "Meta": "META",
    "Tesla": "TSLA",
    "Broadcom": "AVGO",
    "AMD": "AMD",
    "Palantir": "PLTR",
    "Micron": "MU",
    "ASML": "ASML",
    "Super Micro": "SMCI",
    "Arm": "ARM",
    "TSMC": "TSM",
    "Intel": "INTC",
    "Qualcomm": "QCOM",
    "Marvell": "MRVL",
    "Applied Materials": "AMAT",
    "Oracle": "ORCL",
    "Netflix": "NFLX",
}


# ============================================================
# 섹터 분류
# ============================================================

SECTORS = {

    "반도체": [
        "삼성전자",
        "SK하이닉스",
        "한미반도체",
        "삼성전기",
        "HPSP",
        "PSK홀딩스",
        "NVIDIA",
        "AMD",
        "Micron",
        "ASML",
        "TSMC",
        "Intel",
        "Applied Materials",
    ],

    "AI": [
        "SK하이닉스",
        "한미반도체",
        "NVIDIA",
        "AMD",
        "Broadcom",
        "Palantir",
        "Microsoft",
        "Alphabet",
        "Meta",
    ],

    "2차전지": [
        "삼성SDI",
    ],

    "방산": [
        "한화에어로스페이스",
        "LIG넥스원",
        "현대로템",
    ],

    "원전": [
        "두산에너빌리티",
        "현대건설",
    ],

    "바이오": [
        "삼성바이오로직스",
        "셀트리온",
        "삼천당제약",
    ],

    "자동차": [
        "현대차",
        "현대모비스",
    ],

    "조선": [
        "HD현대중공업",
        "한화오션",
    ],

    "로봇": [
        "두산로보틱스",
        "레인보우로보틱스",
    ],

    "전력/전선": [
        "LS ELECTRIC",
        "일진전기",
    ],
}


# ============================================================
# 유틸
# ============================================================

def clean_number(value):

    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except:
        return 0.0


def fmt_price(value):

    value = clean_number(value)

    if value == 0:
        return "-"

    if value >= 1000:
        return f"{value:,.0f}"

    return f"{value:,.2f}"


def fmt_money(value):

    value = clean_number(value)

    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.1f}조"

    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.1f}억"

    return f"{value:,.0f}"


# ============================================================
# 미국 데이터 다운로드
# ============================================================

def get_yf_data(ticker, period="1y"):

    try:

        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        for col in required:

            if col not in df.columns:
                return None

        df = df[required].copy()

        df.dropna(inplace=True)

        return df

    except Exception as e:

        print(f"YF ERROR {ticker}: {e}")

        return None


# ============================================================
# 국내 데이터
# ============================================================

def get_kr_data(ticker):

    try:

        end = datetime.now(KST).strftime("%Y%m%d")

        start = (
            datetime.now(KST)
            - pd.Timedelta(days=420)
        ).strftime("%Y%m%d")

        df = stock.get_market_ohlcv_by_date(
            start,
            end,
            ticker
        )

        if df is None or df.empty:
            return None

        rename_map = {
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume",
            "거래대금": "Value",
        }

        df = df.rename(columns=rename_map)

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for col in required:

            if col not in df.columns:
                return None

        df = df.copy()

        df.dropna(inplace=True)

        return df

    except Exception as e:

        print(f"KR ERROR {ticker}: {e}")

        return None


# ============================================================
# 기술적 지표
# ============================================================

def add_indicators(df):

    if df is None or len(df) < 30:
        return None

    df = df.copy()

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    # 이동평균
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean()
    df["MA120"] = close.rolling(120).mean()

    # 거래량 평균
    df["VOL20"] = volume.rolling(20).mean()

    # 거래량 증가율
    df["VOL_CHANGE"] = (
        (volume / df["VOL20"]) - 1
    ) * 100

    # RSI
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

    # MACD
    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_SIGNAL"] = (
        df["MACD"]
        .ewm(span=9, adjust=False)
        .mean()
    )

    df["MACD_HIST"] = (
        df["MACD"] -
        df["MACD_SIGNAL"]
    )

    # OBV
    direction = np.sign(
        close.diff()
    ).fillna(0)

    df["OBV"] = (
        direction * volume
    ).cumsum()

    # OBV 추세
    df["OBV_MA20"] = (
        df["OBV"].rolling(20).mean()
    )

    # 오늘 골든크로스
    df["GOLDEN_CROSS"] = (
        (df["MA20"] > df["MA60"]) &
        (df["MA20"].shift(1) <= df["MA60"].shift(1))
    )

    # 60/120 추세
    df["TREND_UP"] = (
        (df["MA20"] > df["MA60"]) &
        (df["MA60"] > df["MA120"])
    )

    return df


# ============================================================
# 국내 외국인 / 기관 수급
# ============================================================

def get_kr_supply(ticker):

    try:

        end = datetime.now(KST).strftime("%Y%m%d")

        start = end

        df = stock.get_market_trading_value_by_date(
            start,
            end,
            ticker
        )

        if df is None or df.empty:
            return 0, 0

        row = df.iloc[-1]

        foreign = 0
        institution = 0

        for col in df.columns:

            col_name = str(col)

            if "외국인" in col_name:
                foreign = clean_number(row[col])

            if "기관" in col_name:
                institution = clean_number(row[col])

        return foreign, institution

    except Exception as e:

        print(f"SUPPLY ERROR {ticker}: {e}")

        return 0, 0


# ============================================================
# 종목 분석
# ============================================================

def analyze_stock(name, ticker, market):

    if market == "KR":

        raw = get_kr_data(ticker)

    else:

        raw = get_yf_data(ticker)

    if raw is None:
        return None

    df = add_indicators(raw)

    if df is None or len(df) < 30:
        return None

    last = df.iloc[-1]

    price = clean_number(last["Close"])

    if price <= 0:
        return None

    prev_price = clean_number(
        df["Close"].iloc[-2]
    )

    change = 0

    if prev_price > 0:

        change = (
            price / prev_price - 1
        ) * 100

    ma20 = clean_number(last["MA20"])
    ma60 = clean_number(last["MA60"])
    ma120 = clean_number(last["MA120"])

    rsi = clean_number(last["RSI"])

    macd = clean_number(last["MACD"])
    macd_signal = clean_number(
        last["MACD_SIGNAL"]
    )

    macd_hist = clean_number(
        last["MACD_HIST"]
    )

    volume_change = clean_number(
        last["VOL_CHANGE"]
    )

    golden_cross = bool(
        last["GOLDEN_CROSS"]
    )

    trend_up = bool(
        last["TREND_UP"]
    )

    # OBV
    obv_up = False

    if len(df) >= 20:

        obv_now = clean_number(
            df["OBV"].iloc[-1]
        )

        obv_old = clean_number(
            df["OBV"].iloc[-20]
        )

        obv_up = obv_now > obv_old

    # ========================================================
    # 기술적 점수
    # ========================================================

    score = 0

    if price > ma20:
        score += 1

    if price > ma60:
        score += 1

    if price > ma120:
        score += 1

    if trend_up:
        score += 1

    if macd > macd_signal:
        score += 1

    if macd_hist > 0:
        score += 1

    if 50 <= rsi <= 70:
        score += 1

    if volume_change >= 20:
        score += 1

    if obv_up:
        score += 1

    if golden_cross:
        score += 1

    # ========================================================
    # 최근 20일 지지 / 저항
    # ========================================================

    recent_high = clean_number(
        df["High"].tail(20).max()
    )

    recent_low = clean_number(
        df["Low"].tail(20).min()
    )

    support = max(
        ma20,
        recent_low
    )

    resistance = recent_high

    # ========================================================
    # 기술적 목표가
    # ========================================================

    target = resistance

    if target <= price:

        target = price * 1.08

    # 리스크 기준가
    stop = ma60

    if stop >= price or stop <= 0:

        stop = price * 0.93

    expected_return = (
        (target / price) - 1
    ) * 100

    # ========================================================
    # 국내 수급
    # ========================================================

    foreign = 0
    institution = 0

    if market == "KR":

        foreign, institution = (
            get_kr_supply(ticker)
        )

    # ========================================================
    # 거래대금
    # ========================================================

    value = 0

    if "Value" in df.columns:

        value = clean_number(
            df["Value"].iloc[-1]
        )

    elif market == "KR":

        value = price * clean_number(
            df["Volume"].iloc[-1]
        )

    return {

        "name": name,
        "ticker": ticker,
        "market": market,

        "price": price,
        "change": change,

        "score": score,

        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,

        "rsi": rsi,

        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,

        "obv_up": obv_up,

        "volume_change": volume_change,

        "golden_cross": golden_cross,
        "trend_up": trend_up,

        "support": support,
        "resistance": resistance,

        "target": target,
        "stop": stop,

        "expected_return":
            expected_return,

        "value": value,

        "foreign": foreign,
        "institution": institution,
    }


# ============================================================
# 시장지수
# ============================================================

def get_index(ticker):

    df = get_yf_data(
        ticker,
        period="10d"
    )

    if df is None or len(df) < 2:
        return None

    price = clean_number(
        df["Close"].iloc[-1]
    )

    prev = clean_number(
        df["Close"].iloc[-2]
    )

    change = 0

    if prev > 0:

        change = (
            price / prev - 1
        ) * 100

    return {
        "price": price,
        "change": change
    }


# ============================================================
# 거시경제
# ============================================================

def get_macro():

    tickers = {

        "USD/KRW": "KRW=X",

        "WTI": "CL=F",

        "미국10년물": "^TNX",

        "VIX": "^VIX",

        "미국달러": "DX-Y.NYB",
    }

    result = {}

    for name, ticker in tickers.items():

        result[name] = get_index(ticker)

    return result


# ============================================================
# 네이버 뉴스
# ============================================================

def get_naver_news(query, count=5):

    if not NAVER_CLIENT_ID:
        return []

    if not NAVER_CLIENT_SECRET:
        return []

    url = (
        "https://openapi.naver.com/"
        "v1/search/news.json"
    )

    headers = {

        "X-Naver-Client-Id":
            NAVER_CLIENT_ID,

        "X-Naver-Client-Secret":
            NAVER_CLIENT_SECRET,
    }

    params = {

        "query": query,

        "display": count,

        "sort": "date",
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code != 200:

            print(
                "NAVER ERROR:",
                response.status_code,
                response.text
            )

            return []

        data = response.json()

        return data.get(
            "items",
            []
        )

    except Exception as e:

        print(
            "NAVER NEWS ERROR:",
            e
        )

        return []


# ============================================================
# 뉴스 제목 정리
# ============================================================

def clean_news_title(title):

    if not title:
        return ""

    return (
        title
        .replace("<b>", "")
        .replace("</b>", "")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&#39;", "'")
    )


# ============================================================
# 미국 Yahoo Finance 뉴스
# ============================================================

def get_us_news(ticker):

    try:

        obj = yf.Ticker(ticker)

        news = obj.news

        if not news:
            return []

        return news[:5]

    except Exception as e:

        print(
            "US NEWS ERROR:",
            ticker,
            e
        )

        return []


# ============================================================
# 국내 전체 분석
# ============================================================

def collect_kr():

    result = []

    for name, ticker in KR_STOCKS.items():

        try:

            item = analyze_stock(
                name,
                ticker,
                "KR"
            )

            if item:
                result.append(item)

        except Exception as e:

            print(
                "KR ANALYZE ERROR:",
                name,
                e
            )

    result.sort(
        key=lambda x: (
            x["score"],
            x["change"]
        ),
        reverse=True
    )

    return result


# ============================================================
# 미국 전체 분석
# ============================================================

def collect_us():

    result = []

    for name, ticker in US_STOCKS.items():

        try:

            item = analyze_stock(
                name,
                ticker,
                "US"
            )

            if item:
                result.append(item)

        except Exception as e:

            print(
                "US ANALYZE ERROR:",
                name,
                e
            )

    result.sort(
        key=lambda x: (
            x["score"],
            x["change"]
        ),
        reverse=True
    )

    return result


# ============================================================
# 골든크로스
# ============================================================

def get_golden(items):

    return [
        x["name"]
        for x in items
        if x["golden_cross"]
    ]


# ============================================================
# 수급 집중매수
# ============================================================

def get_supply_top(items):

    if not items:
        return []

    return sorted(
        items,
        key=lambda x:
        x["foreign"] + x["institution"],
        reverse=True
    )[:5]


# ============================================================
# 섹터 분석
# ============================================================

def sector_analysis(all_items):

    lookup = {
        x["name"]: x
        for x in all_items
    }

    result = []

    for sector, names in SECTORS.items():

        data = []

        for name in names:

            if name in lookup:

                data.append(
                    lookup[name]
                )

        if not data:
            continue

        avg_change = np.mean([
            x["change"]
            for x in data
        ])

        avg_score = np.mean([
            x["score"]
            for x in data
        ])

        result.append({

            "sector": sector,

            "change":
                avg_change,

            "score":
                avg_score,
        })

    result.sort(
        key=lambda x: (
            x["score"],
            x["change"]
        ),
        reverse=True
    )

    return result


# ============================================================
# 메시지용 종목 상세
# ============================================================

def stock_detail(x):

    gc = "✅ 발생" if x["golden_cross"] else "❌"

    macd = (
        "상승"
        if x["macd"] > x["macd_signal"]
        else "하락"
    )

    obv = (
        "상승"
        if x["obv_up"]
        else "약세"
    )

    return (
        f"📌 {x['name']} "
        f"{x['change']:+.2f}%\n"
        f"점수 {x['score']}/10 | "
        f"GC {gc}\n"
        f"RSI {x['rsi']:.1f} | "
        f"MACD {macd} | "
        f"OBV {obv}\n"
        f"거래량 {x['volume_change']:+.1f}%\n"
        f"20선 {fmt_price(x['ma20'])} | "
        f"60선 {fmt_price(x['ma60'])} | "
        f"120선 {fmt_price(x['ma120'])}\n"
        f"지지 {fmt_price(x['support'])} | "
        f"저항 {fmt_price(x['resistance'])}\n"
        f"기술적 목표 {fmt_price(x['target'])} | "
        f"리스크 기준 {fmt_price(x['stop'])}\n"
        f"목표까지 {x['expected_return']:+.1f}%"
    )


# ============================================================
# 시장 한줄 요약
# ============================================================

def market_summary(
    kospi,
    kosdaq,
    nasdaq,
    sp500,
    vix
):

    values = []

    if kospi:
        values.append(
            f"KOSPI {kospi['change']:+.2f}%"
        )

    if kosdaq:
        values.append(
            f"KOSDAQ {kosdaq['change']:+.2f}%"
        )

    if nasdaq:
        values.append(
            f"NASDAQ {nasdaq['change']:+.2f}%"
        )

    if sp500:
        values.append(
            f"S&P500 {sp500['change']:+.2f}%"
        )

    if vix:

        values.append(
            f"VIX {vix['price']:.1f}"
        )

    return " | ".join(values)


# ============================================================
# 브리핑 생성
# ============================================================

def build_briefing():

    print("국내 데이터 수집")

    kr = collect_kr()

    print("미국 데이터 수집")

    us = collect_us()

    print("시장지수 수집")

    kospi = get_index("^KS11")
    kosdaq = get_index("^KQ11")

    nasdaq = get_index("^IXIC")
    sp500 = get_index("^GSPC")
    dow = get_index("^DJI")

    macro = get_macro()

    vix = macro.get("VIX")
    import pandas as pd
import numpy as np

def analyze_technical_indicators(df):
    """
    주가 데이터프레임(단일 종목의 OHLCV)을 받아 
    이동평균선, RSI, 볼린저 밴드를 계산하고 매수 신호를 판단하는 함수
    """
    # 데이터가 부족한 경우 예외 처리
    if df is None or len(df) < 30:
        return None

    # 1. 이동평균선 (단기: 5일, 장기: 20일)
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    # 2. 볼린저 밴드 (20일 기준, 2배 표준편차)
    df['Std'] = df['Close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['Std'] * 2)
    df['Lower'] = df['MA20'] - (df['Std'] * 2)

    # 3. RSI (14일 기준)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 최신일 데이터 기준 판단
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 조건 판단 예시
    # - 골든크로스 (전일 MA5 <= MA20 이고 오늘 MA5 > MA20)
    is_golden_cross = (prev['MA5'] <= prev['MA20']) and (latest['MA5'] > latest['MA20'])
    
    # - RSI 과매도 구간 탈출 또는 적정 구간 (예: RSI 30 ~ 45)
    is_rsi_good = 30 <= latest['RSI'] <= 45

    # - 볼린저 밴드 하단 터치 후 반등 (종가가 하단 밴드 근처이거나 돌파)
    is_bollinger_bounce = latest['Close'] <= latest['Lower'] * 1.02

    # 종합 매수 시그널 점수화 또는 플래그 설정
    signal_score = 0
    if is_golden_cross: signal_score += 1
    if is_rsi_good: signal_score += 1
    if is_bollinger_bounce: signal_score += 1

    return {
        "Close": latest['Close'],
        "RSI": round(latest['RSI'], 2),
        "GoldenCross": is_golden_cross,
        "BollingerBounce": is_bollinger_bounce,
        "Score": signal_score
    }


    # ========================================================
    # 시간대별 제목
    # ========================================================
    KST = ZoneInfo("Asia/Seoul")
    now = datetime.now(KST)
    HOUR = now.hour
    TODAY = now.strftime('%Y-%m-%d')

    if HOUR < 9:

        briefing_type = (
            "🌅 장전 글로벌 브리핑"
        )

    elif HOUR < 15:

        briefing_type = (
            "☀️ 국내 오전장 브리핑"
        )

    elif HOUR < 18:

        briefing_type = (
            "🌇 국내장 마감 브리핑"
        )

    else:

        briefing_type = (
            "🌙 미국장 대응 브리핑"
        )

    lines = []

    # ========================================================
    # HEADER
    # ========================================================

    lines.append(
        f"📅 {TODAY}"
    )

    lines.append(
        "📈 AI 국내·미국 주식 브리핑"
    )

    lines.append(
        briefing_type
    )

    # ========================================================
    # 한줄 요약
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🌍 오늘 시장 한줄 요약"
    )

    lines.append(
        market_summary(
            kospi,
            kosdaq,
            nasdaq,
            sp500,
            vix
        )
    )

    # ========================================================
    # 국내
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🇰🇷 국내시장"
    )

    if kospi:

        lines.append(
            f"KOSPI "
            f"{kospi['price']:,.2f} "
            f"({kospi['change']:+.2f}%)"
        )

    if kosdaq:

        lines.append(
            f"KOSDAQ "
            f"{kosdaq['price']:,.2f} "
            f"({kosdaq['change']:+.2f}%)"
        )

    # ========================================================
    # 미국
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🇺🇸 미국시장"
    )

    if nasdaq:

        lines.append(
            f"NASDAQ "
            f"{nasdaq['price']:,.2f} "
            f"({nasdaq['change']:+.2f}%)"
        )

    if sp500:

        lines.append(
            f"S&P500 "
            f"{sp500['price']:,.2f} "
            f"({sp500['change']:+.2f}%)"
        )

    if dow:

        lines.append(
            f"DOW "
            f"{dow['price']:,.2f} "
            f"({dow['change']:+.2f}%)"
        )

    # ========================================================
    # 국내 TOP10
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🔥 국내 TOP10"
    )

    for i, x in enumerate(kr[:10], 1):

        lines.append(
            f"{i}. {x['name']} "
            f"{x['change']:+.2f}% "
            f"점수 {x['score']}/10"
        )

    # ========================================================
    # 미국 TOP10
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🔥 미국 TOP10"
    )

    for i, x in enumerate(us[:10], 1):

        lines.append(
            f"{i}. {x['name']} "
            f"{x['change']:+.2f}% "
            f"점수 {x['score']}/10"
        )

    # ========================================================
    # 국내 TOP5 상세
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🇰🇷 국내 TOP5 상세"
    )

    for x in kr[:5]:

        lines.append(
            stock_detail(x)
        )

    # ========================================================
    # 미국 TOP5 상세
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🇺🇸 미국 TOP5 상세"
    )

    for x in us[:5]:

        lines.append(
            stock_detail(x)
        )

    # ========================================================
    # 골든크로스
    # ========================================================

    kr_gc = get_golden(kr)
    us_gc = get_golden(us)

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "📈 오늘 골든크로스"
    )

    lines.append(
        "🇰🇷 " +
        (
            ", ".join(kr_gc[:10])
            if kr_gc
            else "감지 없음"
        )
    )

    lines.append(
        "🇺🇸 " +
        (
            ", ".join(us_gc[:10])
            if us_gc
            else "감지 없음"
        )
    )

    # ========================================================
    # 기관/외국인
    # ========================================================

    supply = get_supply_top(kr)

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "💰 국내 외국인·기관 수급"
    )

    for i, x in enumerate(
        supply,
        1
    ):

        lines.append(
            f"{i}. {x['name']} | "
            f"외국인 {fmt_money(x['foreign'])} | "
            f"기관 {fmt_money(x['institution'])}"
        )

    # ========================================================
    # AI 관심종목
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🤖 AI 관심종목"
    )

    for x in kr[:3]:

        lines.append(
            f"⭐ {x['name']} "
            f"점수 {x['score']}/10 | "
            f"RSI {x['rsi']:.1f}"
        )

    for x in us[:2]:

        lines.append(
            f"⭐ {x['name']} "
            f"점수 {x['score']}/10 | "
            f"RSI {x['rsi']:.1f}"
        )

    # ========================================================
    # 섹터
    # ========================================================

    sector_items = sector_analysis(
        kr + us
    )

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🔥 섹터 강도"
    )

    for i, s in enumerate(
        sector_items[:10],
        1
    ):

        lines.append(
            f"{i}. {s['sector']} "
            f"평균 {s['change']:+.2f}% "
            f"점수 {s['score']:.1f}"
        )

    # ========================================================
    # 거시경제
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🌐 거시경제"
    )

    for name, data in macro.items():

        if data:

            lines.append(
                f"{name}: "
                f"{data['price']:.2f} "
                f"({data['change']:+.2f}%)"
            )

    # ========================================================
    # 국내뉴스
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "📰 국내 핵심뉴스 TOP5"
    )

    kr_news = get_naver_news(
        "주식 증시 반도체 AI "
        "방산 원전 금리 환율",
        5
    )

    if kr_news:

        for i, news in enumerate(
            kr_news[:5],
            1
        ):

            title = clean_news_title(
                news.get("title", "")
            )

            lines.append(
                f"{i}. {title}"
            )

    else:

        lines.append(
            "네이버 뉴스 API 미설정"
        )

    # ========================================================
    # 미국뉴스
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "📰 미국 핵심뉴스"
    )

    news_added = 0

    for x in us[:5]:

        news = get_us_news(
            x["ticker"]
        )

        for n in news[:1]:

            title = ""

            if isinstance(n, dict):

                content = n.get(
                    "content",
                    {}
                )

                title = (
                    content.get("title")
                    or n.get("title")
                    or ""
                )

            if title:

                lines.append(
                    f"• {x['name']}: "
                    f"{title}"
                )

                news_added += 1

    if news_added == 0:

        lines.append(
            "Yahoo Finance 뉴스 없음"
        )

    # ========================================================
    # 오늘 급등 후보
    # ========================================================

    momentum = sorted(
        kr + us,
        key=lambda x: (
            x["score"],
            x["volume_change"],
            x["change"]
        ),
        reverse=True
    )

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🚀 오늘 모멘텀 후보 TOP5"
    )

    lines.append(
        "※ 미래 상승확률을 임의로 만들지 않고 "
        "기술적 조건 충족도를 표시합니다."
    )

    for i, x in enumerate(
        momentum[:5],
        1
    ):

        lines.append(
            f"{i}. {x['name']} | "
            f"모멘텀 {x['score']}/10 | "
            f"거래량 {x['volume_change']:+.1f}%"
        )

    # ========================================================
    # 최고의 기술적 관심종목
    # ========================================================

    if momentum:

        best = momentum[0]

        lines.append(
            "\n━━━━━━━━━━━━━━"
        )

        lines.append(
            "⭐ 오늘 기술적 관심종목"
        )

        lines.append(
            stock_detail(best)
        )

    # ========================================================
    # 투자 아이디어
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "💡 오늘 투자 아이디어 5가지"
    )

    ideas = []

    if kr:

        ideas.append(
            f"① 국내 TOP 종목 중 "
            f"20·60·120일선 정배열 여부 확인"
        )

    ideas.append(
        "② 골든크로스 발생과 거래량 증가가 "
        "동시에 나타나는 종목 확인"
    )

    ideas.append(
        "③ RSI 70 이상 종목은 추격매수보다 "
        "눌림 여부 확인"
    )

    ideas.append(
        "④ VIX·미국10년물·환율 상승 여부를 "
        "동시에 확인"
    )

    ideas.append(
        "⑤ 뉴스 발생 후 실제 거래량과 "
        "수급이 따라오는지 확인"
    )

    for idea in ideas[:5]:

        lines.append(idea)

    # ========================================================
    # 리스크
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "⚠️ 리스크 체크"
    )

    if vix:

        if vix["price"] >= 25:

            lines.append(
                "VIX 25 이상: 변동성 확대 구간 확인"
            )

        elif vix["price"] >= 20:

            lines.append(
                "VIX 20 이상: 변동성 주의"
            )

        else:

            lines.append(
                "VIX 20 미만"
            )

    lines.append(
        "환율·금리·유가·지정학 뉴스와 "
        "실제 주가 반응을 함께 확인하세요."
    )

    # ========================================================
    # 트럼프 / 글로벌 이슈
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "🌎 글로벌 이슈"
    )

    lines.append(
        "트럼프 발언·관세·무역정책·"
        "미중관계·금리·지정학 이슈는 "
        "관련 뉴스와 시장 반응을 함께 확인합니다."
    )

    # ========================================================
    # 마지막
    # ========================================================

    lines.append(
        "\n━━━━━━━━━━━━━━"
    )

    lines.append(
        "📌 마지막 한줄"
    )

    lines.append(
        "데이터·뉴스·수급·기술적 지표가 "
        "동시에 개선되는 종목을 우선 관찰하고, "
        "목표가와 리스크 기준을 함께 관리하세요."
    )

    return "\n".join(lines)


# ============================================================
# 카카오 Access Token 갱신
# ============================================================

def get_kakao_access_token():

    if not KAKAO_REST_API_KEY:

        raise Exception(
            "KAKAO_REST_API_KEY가 없습니다."
        )

    if not KAKAO_REFRESH_TOKEN:

        raise Exception(
            "KAKAO_REFRESH_TOKEN이 없습니다."
        )

    url = (
        "https://kauth.kakao.com/oauth/token"
    )

    data = {

        "grant_type":
            "refresh_token",

        "client_id":
            KAKAO_REST_API_KEY,

        "refresh_token":
            KAKAO_REFRESH_TOKEN,
    }

    if KAKAO_CLIENT_SECRET:

        data["client_secret"] = (
            KAKAO_CLIENT_SECRET
        )

    response = requests.post(
        url,
        data=data,
        timeout=20
    )

    if response.status_code != 200:

        raise Exception(
            "카카오 토큰 갱신 실패\n"
            + response.text
        )

    result = response.json()

    access_token = result.get(
        "access_token"
    )

    if not access_token:

        raise Exception(
            "Access Token이 없습니다."
        )

    return access_token


# ============================================================
# 카카오 메시지 전송
# ============================================================

def send_kakao(message):

    access_token = (
        get_kakao_access_token()
    )

    url = (
        "https://kapi.kakao.com/"
        "v2/api/talk/memo/default/send"
    )

    headers = {

        "Authorization":
            f"Bearer {access_token}",

        "Content-Type":
            "application/x-www-form-urlencoded"
            ";charset=utf-8"
    }

    template = {

        "object_type": "text",

        "text": message,

        "link": {

            "web_url":
                "https://finance.naver.com/",

            "mobile_web_url":
                "https://finance.naver.com/"
        },

        "button_title":
            "증권시장 확인"
    }

    data = {

        "template_object":
            json.dumps(
                template,
                ensure_ascii=False
            )
    }

    response = requests.post(
        url,
        headers=headers,
        data=data,
        timeout=20
    )

    if response.status_code != 200:

        raise Exception(
            "카카오 메시지 전송 실패\n"
            + response.text
        )

    print(
        "카카오 메시지 전송 성공"
    )


# ============================================================
# 카카오 메시지 분할
# ============================================================

def split_message(
    text,
    max_length=1800
):
    if text is None:
        return ["브리핑 내용을 생성하지 못했습니다."]

    messages = []

    current = ""

    for line in text.split("\n"):

        if (
            len(current)
            + len(line)
            + 1
            > max_length
        ):

            if current:

                messages.append(
                    current
                )

            current = line

        else:

            if current:

                current += "\n"

            current += line

    if current:

        messages.append(
            current
        )

    return messages


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "AI 국내·미국 주식 브리핑 시작"
    )

    KST = ZoneInfo("Asia/Seoul")
    now = datetime.now(KST)

    print(
        f"한국시간: "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(
        "========================================"
    )


    print(
        "========================================"
    )

    # 환경변수 확인
    if not KAKAO_REST_API_KEY:

        raise Exception(
            "KAKAO_REST_API_KEY 미설정"
        )

    if not KAKAO_REFRESH_TOKEN:

        raise Exception(
            "KAKAO_REFRESH_TOKEN 미설정"
        )

    briefing = build_briefing()

    messages = split_message(
        briefing,
        1800
    )

    print(
        f"전송할 메시지 수: "
        f"{len(messages)}"
    )

    for i, message in enumerate(
        messages,
        1
    ):

        print(
            f"카카오 메시지 "
            f"{i}/{len(messages)} 전송"
        )

        send_kakao(message)

        # API 호출 간격
        time.sleep(2)

    print(
        "========================================"
    )

    print(
        "브리핑 전송 완료"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":

    main()
