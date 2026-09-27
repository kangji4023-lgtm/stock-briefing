import os
import re
import time
import html
import requests
import feedparser
import numpy as np
import pandas as pd
import yfinance as yf

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
from pykrx import stock


# ============================================================
# 기본 설정
# ============================================================

KST = ZoneInfo("Asia/Seoul")

TODAY = datetime.now(KST).date()
NOW = datetime.now(KST)

# ------------------------------------------------------------
# 카카오톡
# GitHub Secrets에 저장
# ------------------------------------------------------------
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()
GITHUB_BRANCH = os.getenv("GITHUB_REF_NAME", "main").strip() or "main"

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
# ------------------------------------------------------------
# 네이버 뉴스 API
#
# 선택사항
# 없으면 Google News RSS를 보조 사용
# ------------------------------------------------------------

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")


# ============================================================
# 분석 종목
# ============================================================

KR_STOCKS = {
    "SK하이닉스": "000660",
    "삼성전자": "005930",
    "삼성전기": "009150",
    "LS일렉트릭": "010120",
    "SK스퀘어": "402340",
    "한화에어로스페이스": "012450",
    "삼성SDI": "006400",
    "현대차": "005380",
    "일진전기": "103590",
    "한미반도체": "042700",
    "두산에너빌리티": "034020",
    "HD현대중공업": "329180",
    "한화오션": "042660",
    "NAVER": "035420",
    "카카오": "035720",
}

US_STOCKS = {
    "애플": "AAPL",
    "테슬라": "TSLA",
    "엔비디아": "NVDA",
    "마이크로소프트": "MSFT",
    "아마존": "AMZN",
    "알파벳A": "GOOGL",
    "메타": "META",
    "AMD": "AMD",
    "브로드컴": "AVGO",
    "마이크론": "MU",
    "ARM": "ARM",
    "TSMC": "TSM",
    "ASML": "ASML",
    "오라클": "ORCL",
    "팔란티어": "PLTR",
}


# ============================================================
# 보유종목
# ============================================================

HOLDINGS = [
    "SK하이닉스",
    "삼성전자",
    "삼성전기",
    "LS일렉트릭",
    "SK스퀘어",
    "한화에어로스페이스",
    "삼성SDI",
    "현대차",
    "애플",
    "테슬라",
    "일진전기",
    "엔비디아",
]


# ============================================================
# 공통 함수
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_float(value):
    try:
        if value is None:
            return None

        if pd.isna(value):
            return None

        return float(value)

    except Exception:
        return None


def fmt_price(value, currency="KRW"):

    value = safe_float(value)

    if value is None:
        return "데이터 없음"

    if currency == "KRW":
        return f"{value:,.0f}원"

    return f"${value:,.2f}"


def pct(value):

    value = safe_float(value)

    if value is None:
        return "데이터 없음"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.2f}%"


# ============================================================
# 네이버 금융 국내 가격
# ============================================================

def get_naver_price(code):

    url = f"https://finance.naver.com/item/main.naver?code={code}"

    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        r.raise_for_status()

        tables = pd.read_html(r.text)

        for table in tables:

            text = table.to_string()

            if "현재가" in text:

                values = table.astype(str).values.flatten()

                for value in values:

                    value = value.replace(",", "")

                    if re.fullmatch(r"\d+", value):

                        price = float(value)

                        if price > 100:
                            return price

    except Exception as e:

        print("Naver price error:", e)

    return None


# ============================================================
# Yahoo Finance 국내/미국 데이터
# ============================================================

def get_yahoo_data(ticker):

    try:

        df = yf.download(
            ticker,
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):

            df.columns = df.columns.get_level_values(0)

        df = df.dropna(subset=["Close"])

        return df

    except Exception as e:

        print("Yahoo error:", ticker, e)

        return None


# ============================================================
# 기술적 지표
# ============================================================

def calculate_indicators(df):

    result = {}

    if df is None or len(df) < 30:
        return result

    close = df["Close"].astype(float)

    volume = df["Volume"].astype(float)

    # --------------------------------------------------------
    # 이동평균
    # --------------------------------------------------------

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()

    result["ma20"] = safe_float(ma20.iloc[-1])
    result["ma60"] = safe_float(ma60.iloc[-1])
    result["ma120"] = safe_float(ma120.iloc[-1])

    # --------------------------------------------------------
    # 골든크로스
    # --------------------------------------------------------

    if len(ma20) >= 2 and len(ma60) >= 2:

        previous20 = ma20.iloc[-2]
        previous60 = ma60.iloc[-2]

        current20 = ma20.iloc[-1]
        current60 = ma60.iloc[-1]

        if (
            previous20 <= previous60
            and current20 > current60
        ):
            result["golden_cross"] = True

        else:
            result["golden_cross"] = False

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    delta = close.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()

    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    result["rsi"] = safe_float(rsi.iloc[-1])

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

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

    result["macd"] = safe_float(macd.iloc[-1])

    result["signal"] = safe_float(signal.iloc[-1])

    # --------------------------------------------------------
    # 거래량
    # --------------------------------------------------------

    avg_volume20 = volume.rolling(20).mean()

    current_volume = safe_float(volume.iloc[-1])

    average_volume = safe_float(
        avg_volume20.iloc[-1]
    )

    result["volume"] = current_volume

    result["avg_volume20"] = average_volume

    if average_volume:

        result["volume_ratio"] = (
            current_volume / average_volume
        )

    # --------------------------------------------------------
    # OBV
    # --------------------------------------------------------

    direction = np.sign(close.diff())

    obv = (direction * volume).fillna(0).cumsum()

    result["obv"] = safe_float(obv.iloc[-1])

    if len(obv) >= 20:

        result["obv_20ago"] = safe_float(
            obv.iloc[-20]
        )

    # --------------------------------------------------------
    # 수익률
    # --------------------------------------------------------

    result["return_1d"] = safe_float(
        (close.iloc[-1] / close.iloc[-2] - 1) * 100
    )

    if len(close) >= 5:

        result["return_5d"] = safe_float(
            (close.iloc[-1] / close.iloc[-5] - 1) * 100
        )

    if len(close) >= 20:

        result["return_20d"] = safe_float(
            (close.iloc[-1] / close.iloc[-20] - 1) * 100
        )

    # --------------------------------------------------------
    # 추세 판정
    # --------------------------------------------------------

    current = close.iloc[-1]

    if result.get("ma20") and result.get("ma60"):

        if current > result["ma20"] > result["ma60"]:
            result["trend"] = "상승 추세"

        elif current < result["ma20"] < result["ma60"]:
            result["trend"] = "하락 추세"

        else:
            result["trend"] = "혼조"

    return result


# ============================================================
# 기술적 데이터 분석 문장
# ============================================================

def analyze_technical(ind):

    if not ind:
        return "기술적 데이터 부족"

    reasons = []

    rsi = ind.get("rsi")

    if rsi is not None:

        if rsi >= 70:
            reasons.append("RSI 과열권")

        elif rsi <= 30:
            reasons.append("RSI 침체권")

        else:
            reasons.append(f"RSI {rsi:.1f}")

    if ind.get("golden_cross"):
        reasons.append("20일선이 60일선을 상향 돌파")

    if ind.get("trend"):
        reasons.append(ind["trend"])

    volume_ratio = ind.get("volume_ratio")

    if volume_ratio:

        if volume_ratio >= 2:
            reasons.append("거래량 크게 증가")

        elif volume_ratio >= 1.3:
            reasons.append("거래량 증가")

        elif volume_ratio < 0.7:
            reasons.append("거래량 감소")

    macd = ind.get("macd")
    signal = ind.get("signal")

    if macd is not None and signal is not None:

        if macd > signal:
            reasons.append("MACD 매수 우위")

        else:
            reasons.append("MACD 약세")

    return ", ".join(reasons)


# ============================================================
# 네이버 뉴스 API
# ============================================================

def get_naver_news(query, display=5):

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    url = "https://openapi.naver.com/v1/search/news.json"

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    params = {
        "query": query,
        "display": display,
        "sort": "date"
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        result = []

        for item in data.get("items", []):

            title = clean_text(item.get("title"))

            description = clean_text(
                item.get("description")
            )

            pub_date = item.get("pubDate", "")

            link = item.get("originallink") or item.get("link")

            result.append({
                "title": title,
                "description": description,
                "date": pub_date,
                "link": link,
                "source": "네이버 뉴스"
            })

        return result

    except Exception as e:

        print("Naver news error:", e)

        return []


# ============================================================
# Google News RSS
# 해외뉴스 보조 수집
# ============================================================

def get_google_news(query, display=5):

    try:

        encoded = quote(query)

        url = (
            "https://news.google.com/rss/search?"
            f"q={encoded}"
            "&hl=ko&gl=KR&ceid=KR:ko"
        )

        feed = feedparser.parse(url)

        result = []

        for item in feed.entries[:display]:

            title = clean_text(
                item.get("title", "")
            )

            description = clean_text(
                item.get("summary", "")
            )

            published = item.get(
                "published",
                ""
            )

            link = item.get(
                "link",
                ""
            )

            result.append({
                "title": title,
                "description": description,
                "date": published,
                "link": link,
                "source": "Google News"
            })

        return result

    except Exception as e:

        print("Google news error:", e)

        return []


# ============================================================
# 뉴스 날짜 필터
# ============================================================

def is_recent_news(date_text):

    if not date_text:
        return True

    try:

        parsed = pd.to_datetime(
            date_text,
            utc=True
        )

        local_date = (
            parsed
            .tz_convert(KST)
            .date()
        )

        # 오늘 + 최근 1일
        return local_date >= TODAY - timedelta(days=1)

    except Exception:

        return True


# ============================================================
# 뉴스 수집
# ============================================================

def get_news(name):

    news = []

    # --------------------------------------------------------
    # 네이버
    # --------------------------------------------------------

    naver_news = get_naver_news(
        name,
        display=5
    )

    news.extend(naver_news)

    # --------------------------------------------------------
    # 해외뉴스
    # --------------------------------------------------------

    foreign_query = f"{name} stock OR {name} market"

    google_news = get_google_news(
        foreign_query,
        display=5
    )

    news.extend(google_news)

    # --------------------------------------------------------
    # 날짜 필터
    # --------------------------------------------------------

    news = [
        x for x in news
        if is_recent_news(x.get("date"))
    ]

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    unique = {}

    for item in news:

        key = re.sub(
            r"[^가-힣a-zA-Z0-9]",
            "",
            item["title"]
        ).lower()

        if key not in unique:
            unique[key] = item

    return list(unique.values())[:8]


# ============================================================
# 뉴스 → 종목 영향 분석
# ============================================================

POSITIVE_WORDS = [
    "실적 개선",
    "호실적",
    "수주",
    "증가",
    "상향",
    "성장",
    "개선",
    "투자",
    "계약",
    "수출",
    "공급",
    "AI",
    "기대",
    "매출 증가"
]

NEGATIVE_WORDS = [
    "감소",
    "하향",
    "부진",
    "적자",
    "규제",
    "우려",
    "지연",
    "취소",
    "감산",
    "관세",
    "제재",
    "경쟁 심화",
    "매출 감소"
]


def analyze_news_impact(news):

    if not news:

        return (
            "최근 1일 내 확인된 주요 뉴스가 "
            "충분하지 않아 뉴스 영향은 판단하지 않음."
        )

    positive = 0
    negative = 0

    for item in news:

        text = (
            item["title"]
            + " "
            + item["description"]
        )

        for word in POSITIVE_WORDS:

            if word.lower() in text.lower():
                positive += 1

        for word in NEGATIVE_WORDS:

            if word.lower() in text.lower():
                negative += 1

    if positive > negative:

        direction = "긍정적 요인이 더 많이 확인됨"

    elif negative > positive:

        direction = "부정적 요인이 더 많이 확인됨"

    else:

        direction = "긍정·부정 요인이 혼재"

    return (
        f"{direction}. "
        "단순 기사 수만으로 주가 방향을 확정할 수 없으므로 "
        "기술지표와 함께 확인해야 함."
    )


# ============================================================
# 국내 종목 분석
# ============================================================

def analyze_korean_stock(name, code):

    print("분석:", name)

    yahoo_ticker = f"{code}.KS"

    df = get_yahoo_data(
        yahoo_ticker
    )

    ind = calculate_indicators(df)

    # 네이버 가격
    naver_price = get_naver_price(code)

    # Yahoo 가격
    yahoo_price = None

    if df is not None and not df.empty:

        yahoo_price = safe_float(
            df["Close"].iloc[-1]
        )

    # 뉴스
    news = get_news(name)

    result = {

        "name": name,
        "market": "KR",
        "code": code,

        "naver_price": naver_price,
        "yahoo_price": yahoo_price,

        "indicators": ind,

        "news": news,

        "news_impact":
            analyze_news_impact(news),

        "technical":
            analyze_technical(ind)

    }

    return result


# ============================================================
# 미국 종목 분석
# ============================================================

def analyze_us_stock(name, ticker):

    print("분석:", name)

    df = get_yahoo_data(
        ticker
    )

    ind = calculate_indicators(df)

    yahoo_price = None

    if df is not None and not df.empty:

        yahoo_price = safe_float(
            df["Close"].iloc[-1]
        )

    news = get_news(name)

    return {

        "name": name,
        "market": "US",
        "ticker": ticker,

        "yahoo_price": yahoo_price,

        "indicators": ind,

        "news": news,

        "news_impact":
            analyze_news_impact(news),

        "technical":
            analyze_technical(ind)

    }


# ============================================================
# 종목별 브리핑 생성
# ============================================================

def make_stock_brief(item):

    name = item["name"]

    ind = item["indicators"]

    if item["market"] == "KR":

        price = item["naver_price"]

        price_text = fmt_price(
            price,
            "KRW"
        )

        source = "네이버"

    else:

        price = item["yahoo_price"]

        price_text = fmt_price(
            price,
            "USD"
        )

        source = "Yahoo"

    r1 = pct(
        ind.get("return_1d")
    )

    r5 = pct(
        ind.get("return_5d")
    )

    r20 = pct(
        ind.get("return_20d")
    )

    rsi = ind.get("rsi")

    rsi_text = (
        f"{rsi:.1f}"
        if rsi is not None
        else "데이터 없음"
    )

    volume_ratio = ind.get(
        "volume_ratio"
    )

    if volume_ratio:

        volume_text = (
            f"{volume_ratio:.1f}배"
        )

    else:

        volume_text = "데이터 없음"

    golden = (
        "발생"
        if ind.get("golden_cross")
        else "없음"
    )

    news = item["news"]

    lines = []

    lines.append(
        f"📌 {name}"
    )

    lines.append(
        f"가격: {price_text} ({source})"
    )

    lines.append(
        f"등락: 1일 {r1} / 5일 {r5} / 20일 {r20}"
    )

    lines.append(
        f"추세: {ind.get('trend', '데이터 없음')}"
    )

    lines.append(
        f"RSI: {rsi_text} | "
        f"거래량: {volume_text}"
    )

    lines.append(
        f"골든크로스: {golden}"
    )

    lines.append(
        f"기술분석: {item['technical']}"
    )

    lines.append(
        f"뉴스영향: {item['news_impact']}"
    )

    # --------------------------------------------------------
    # 최근 뉴스 최대 2개
    # --------------------------------------------------------

    if news:

        lines.append("📰 주요 뉴스")

        for n in news[:2]:

            title = n["title"]

            lines.append(
                f"- {title}"
            )

            lines.append(
                f"  출처: {n['source']}"
            )

    else:

        lines.append(
            "📰 최근 주요 뉴스: 없음"
        )

    return "\n".join(lines)


# ============================================================
# 전체 시장 요약
# ============================================================

def make_market_summary(results):

    up = []
    down = []

    for item in results:

        ind = item.get(
            "indicators",
            {}
        )

        ret = ind.get(
            "return_1d"
        )

        if ret is None:
            continue

        if ret > 0:
            up.append(
                (item["name"], ret)
            )

        elif ret < 0:
            down.append(
                (item["name"], ret)
            )

    up.sort(
        key=lambda x: x[1],
        reverse=True
    )

    down.sort(
        key=lambda x: x[1]
    )

    lines = []

    lines.append(
        "📊 오늘의 마켓 브리핑"
    )

    lines.append(
        f"기준일: {TODAY.strftime('%Y-%m-%d')} "
        f"{NOW.strftime('%H:%M')} KST"
    )

    lines.append("")

    if up:

        lines.append("🔺 상승")

        for name, value in up[:5]:

            lines.append(
                f"{name} {value:+.2f}%"
            )

    if down:

        lines.append("")

        lines.append("🔻 하락")

        for name, value in down[:5]:

            lines.append(
                f"{name} {value:+.2f}%"
            )

    lines.append("")

    lines.append(
        "※ 주가 방향은 뉴스만으로 판단하지 않고 "
        "가격·거래량·기술지표를 함께 확인."
    )

    return "\n".join(lines)


# ============================================================
# 보유종목 요약
# ============================================================

def make_holding_summary(results):

    lines = []

    lines.append(
        "💼 보유종목 핵심 체크"
    )

    for item in results:

        if item["name"] not in HOLDINGS:
            continue

        ind = item["indicators"]

        ret = ind.get(
            "return_1d"
        )

        if ret is None:
            continue

        trend = ind.get(
            "trend",
            "데이터 없음"
        )

        golden = (
            "GC"
            if ind.get("golden_cross")
            else "-"
        )

        lines.append(
            f"{item['name']} "
            f"{ret:+.2f}% | "
            f"{trend} | {golden}"
        )

    lines.append("")

    lines.append(
        "GC = 20일 이동평균선이 "
        "60일선을 상향 돌파한 경우"
    )

    return "\n".join(lines)


# ============================================================
# 전체 리포트
# ============================================================

def make_report(results):

    sections = []

    sections.append(
        make_market_summary(results)
    )

    sections.append(
        make_holding_summary(results)
    )

    sections.append(
        "━━━━━━━━━━━━━━"
    )

    # 보유종목 먼저
    ordered = []

    for item in results:

        if item["name"] in HOLDINGS:
            ordered.append(item)

    for item in results:

        if item["name"] not in HOLDINGS:
            ordered.append(item)

    # 너무 길어지는 것을 방지
    for item in ordered:

        sections.append(
            make_stock_brief(item)
        )

        sections.append(
            "━━━━━━━━━━━━━━"
        )

    return "\n".join(sections)


# ============================================================
# 카카오 액세스 토큰
# ============================================================

def refresh_kakao_token():

    url = "https://kauth.kakao.com/oauth/token"

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN
    }

    if KAKAO_CLIENT_SECRET:

        data["client_secret"] = (
            KAKAO_CLIENT_SECRET
        )

    try:

        r = requests.post(
            url,
            data=data,
            timeout=10
        )

        r.raise_for_status()

        token = r.json().get(
            "access_token"
        )

        return token

    except Exception as e:

        print(
            "Kakao token refresh error:",
            e
        )

        return None


# ============================================================
# 카카오 메시지 전송
# ============================================================

def send_kakao_message(access_token, text):

    url = (
        "https://kapi.kakao.com/"
        "v2/api/talk/memo/default/send"
    )

    headers = {
        "Authorization":
            f"Bearer {access_token}"
    }

    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url":
                "https://finance.naver.com/",
            "mobile_web_url":
                "https://finance.naver.com/"
        },
        "button_title": "주식시장 확인"
    }

    data = {
        "template_object":
            requests.utils.requote_uri(
                str(template)
            )
    }

    # Kakao는 JSON 문자열 형태를 요구
    import json

    data = {
        "template_object":
            json.dumps(
                template,
                ensure_ascii=False
            )
    }

    try:

        r = requests.post(
            url,
            headers=headers,
            data=data,
            timeout=10
        )

        print(
            "Kakao:",
            r.status_code,
            r.text
        )

        return r.ok

    except Exception as e:

        print(
            "Kakao send error:",
            e
        )

        return False


# ============================================================
# 긴 메시지 분할
# ============================================================

def split_message(text, max_length=900):

    lines = text.splitlines()

    messages = []

    current = ""

    for line in lines:

        if len(current) + len(line) + 1 <= max_length:

            current += line + "\n"

        else:

            if current.strip():

                messages.append(
                    current.strip()
                )

            current = line + "\n"

    if current.strip():

        messages.append(
            current.strip()
        )

    return messages


# ============================================================
# 실행
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "주식 자동 마켓 브리핑 시작"
    )

    print(
        f"기준일: {TODAY}"
    )

    print(
        f"현재시간: {NOW}"
    )

    print(
        "======================================"
    )

    results = []

    # --------------------------------------------------------
    # 국내
    # --------------------------------------------------------

    for name, code in KR_STOCKS.items():

        try:

            result = analyze_korean_stock(
                name,
                code
            )

            results.append(result)

            time.sleep(0.5)

        except Exception as e:

            print(
                f"{name} 분석 오류:",
                e
            )

    # --------------------------------------------------------
    # 미국
    # --------------------------------------------------------

    for name, ticker in US_STOCKS.items():

        try:

            result = analyze_us_stock(
                name,
                ticker
            )

            results.append(result)

            time.sleep(0.5)

        except Exception as e:

            print(
                f"{name} 분석 오류:",
                e
            )

    if not results:

        print(
            "분석 가능한 데이터가 없습니다."
        )

        return

    # --------------------------------------------------------
    # 리포트 생성
    # --------------------------------------------------------

    report = make_report(
        results
    )

    print(report)

    # --------------------------------------------------------
    # 카카오 토큰
    # --------------------------------------------------------

    if not KAKAO_REST_API_KEY:

        print(
            "KAKAO_REST_API_KEY 없음"
        )

        return

    if not KAKAO_REFRESH_TOKEN:

        print(
            "KAKAO_REFRESH_TOKEN 없음"
        )

        return

    access_token = (
        refresh_kakao_token()
    )

    if not access_token:

        print(
            "카카오 액세스 토큰 발급 실패"
        )

        return

    # --------------------------------------------------------
    # 카카오 메시지 분할
    # --------------------------------------------------------

    messages = split_message(
        report,
        max_length=900
    )

    print(
        f"카카오 전송 메시지 수: "
        f"{len(messages)}"
    )

    for index, message in enumerate(
        messages,
        start=1
    ):

        print(
            f"카카오 {index}/{len(messages)} 전송"
        )

        success = send_kakao_message(
            access_token,
            message
        )

        if not success:

            print(
                f"{index}번 메시지 전송 실패"
            )

        time.sleep(1)

    print(
        "======================================"
    )

    print(
        "주식 자동 마켓 브리핑 완료"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()
