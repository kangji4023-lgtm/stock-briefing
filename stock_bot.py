# ============================================================
# stock_bot.py
# 국내·미국 주식시장 데이터 기반 자동 브리핑
#
# 주요 기능
# 1. KRX 최신 거래일 자동 탐색
# 2. 2026 KRX 로그인 정책 대응
# 3. KOSPI / KOSDAQ
# 4. 국내 거래대금 TOP10
# 5. 국내 주도 섹터 분석
# 6. 국내 관심종목 기술적 분석
# 7. 국내 뉴스 조회
# 8. 미국 지수 및 핵심종목
# 9. 미국 뉴스 조회
# 10. 원달러 / 미국채10년 / VIX / WTI
# 11. 카카오톡 나에게 보내기
# 12. 긴 메시지 자동 분할
#
# GitHub Secrets
# KRX_ID
# KRX_PW
# KAKAO_REST_API_KEY
# KAKAO_REFRESH_TOKEN
# KAKAO_CLIENT_SECRET (사용 중이면 입력)
# ============================================================

import os
import json
import time
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta

import pytz
import requests
import pandas as pd
import numpy as np
import yfinance as yf

from pykrx import stock


# ============================================================
# 0. 기본 설정
# ============================================================

KST = pytz.timezone("Asia/Seoul")

# ------------------------------------------------------------
# KRX
# ------------------------------------------------------------

KRX_ID = os.environ.get("KRX_ID", "dmswl904").strip()
KRX_PW = os.environ.get("KRX_PW", "kang402300*").strip()

# ------------------------------------------------------------
# KAKAO
# ------------------------------------------------------------

KAKAO_REST_API_KEY = os.environ.get(
    "KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()

KAKAO_REFRESH_TOKEN = os.environ.get(
    "KAKAO_REFRESH_TOKEN", "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc"
).strip()

KAKAO_CLIENT_SECRET = os.environ.get(
    "KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()


# ============================================================
# 1. 관심종목
# ============================================================

KOREA_WATCHLIST = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "삼성전기": "009150.KS",
    "SK스퀘어": "402340.KS",
    "현대차": "005380.KS",
    "삼성SDI": "006400.KS",
    "한미반도체": "042700.KS",
    "LS ELECTRIC": "010120.KS",
    "한화에어로스페이스": "012450.KS",
    "두산에너빌리티": "034020.KS",
}

USA_WATCHLIST = {
    "NVIDIA": "NVDA",
    "Microsoft": "MSFT",
    "Apple": "AAPL",
    "Alphabet A": "GOOGL",
    "Amazon": "AMZN",
    "Meta": "META",
    "Tesla": "TSLA",
    "Broadcom": "AVGO",
}


# ============================================================
# 2. 국내 섹터
# ============================================================

SECTORS = {
    "반도체·AI": [
        "삼성전자",
        "SK하이닉스",
        "한미반도체",
        "SK스퀘어",
        "삼성전기",
        "이오테크닉스",
        "HPSP",
        "리노공업",
        "원익IPS",
    ],

    "2차전지·배터리": [
        "삼성SDI",
        "LG에너지솔루션",
        "SK이노베이션",
        "에코프로",
        "에코프로비엠",
        "포스코퓨처엠",
        "엘앤에프",
    ],

    "방산·우주항공": [
        "한화에어로스페이스",
        "현대로템",
        "한국항공우주",
        "LIG넥스원",
        "한화시스템",
    ],

    "자동차·모빌리티": [
        "현대차",
        "기아",
        "현대모비스",
        "HL만도",
    ],

    "바이오·헬스케어": [
        "삼성바이오로직스",
        "셀트리온",
        "유한양행",
        "알테오젠",
        "SK바이오팜",
    ],

    "전력·원전·인프라": [
        "LS ELECTRIC",
        "두산에너빌리티",
        "HD현대일렉트릭",
        "효성중공업",
        "두산밥캣",
    ],

    "조선·중공업": [
        "HD한국조선해양",
        "HD현대중공업",
        "삼성중공업",
        "한화오션",
        "HD현대미포",
    ],

    "금융·증권": [
        "KB금융",
        "신한지주",
        "하나금융지주",
        "우리금융지주",
        "메리츠금융지주",
    ],
}


# ============================================================
# 3. 공통 함수
# ============================================================

def now_kst():
    return datetime.now(KST)


def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


def fmt_number(value, digits=2):
    try:
        if value is None or pd.isna(value):
            return "미집계"

        return f"{float(value):,.{digits}f}"

    except Exception:
        return "미집계"


def fmt_rate(value):
    try:
        if value is None or pd.isna(value):
            return "미집계"

        return f"{float(value):+.2f}%"


    except Exception:
        return "미집계"


def fmt_억(value):
    try:
        if value is None or pd.isna(value):
            return "미집계"

        return f"{float(value) / 100000000:,.0f}억"

    except Exception:
        return "미집계"


def clean_text(text):
    if text is None:
        return ""

    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# 4. KRX 환경 확인
# ============================================================

def check_krx_environment():

    print("=" * 70)
    print("KRX 환경 확인")
    print("=" * 70)

    if KRX_ID:
        print("[KRX] KRX_ID 설정됨")
    else:
        print("[KRX] ⚠️ KRX_ID 없음")

    if KRX_PW:
        print("[KRX] KRX_PW 설정됨")
    else:
        print("[KRX] ⚠️ KRX_PW 없음")

    print("=" * 70)


# ============================================================
# 5. KRX 데이터 조회
# ============================================================

def krx_call(func, *args, **kwargs):

    for attempt in range(3):

        try:

            result = func(
                *args,
                **kwargs
            )

            if result is not None:

                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return result

                else:
                    return result

        except Exception as e:

            print(
                f"[KRX] "
                f"{func.__name__} "
                f"{attempt + 1}/3 오류:",
                e
            )

        time.sleep(1.5)

    return pd.DataFrame()


# ============================================================
# 6. 최근 KRX 거래일
# ============================================================

def get_latest_krx_date():

    today = now_kst().date()

    for offset in range(0, 15):

        d = today - timedelta(
            days=offset
        )

        date_str = d.strftime(
            "%Y%m%d"
        )

        try:

            df = krx_call(
                stock.get_market_ohlcv_by_ticker,
                date_str,
                market="KOSPI"
            )

            if (
                isinstance(df, pd.DataFrame)
                and not df.empty
            ):

                print(
                    "[KRX] 최신 거래일:",
                    date_str
                )

                return date_str

        except Exception as e:

            print(
                "[KRX DATE ERROR]",
                e
            )

    print(
        "[KRX] ❌ 최근 거래일 조회 실패"
    )

    return None


# ============================================================
# 7. 국내 시장지수
# ============================================================

def get_index_data(
    ticker,
    date
):

    try:

        df = krx_call(
            stock.get_index_ohlcv_by_date,
            date,
            date,
            ticker
        )

        if df.empty:
            return {
                "value": np.nan,
                "rate": np.nan,
                "success": False
            }

        row = df.iloc[-1]

        return {
            "value": safe_float(
                row.get("종가")
            ),
            "rate": safe_float(
                row.get("등락률")
            ),
            "success": True
        }

    except Exception as e:

        print(
            f"[INDEX {ticker}]",
            e
        )

        return {
            "value": np.nan,
            "rate": np.nan,
            "success": False
        }


def get_domestic_indices(date):

    return {
        "KOSPI": get_index_data(
            "1001",
            date
        ),

        "KOSDAQ": get_index_data(
            "2001",
            date
        ),
    }


# ============================================================
# 8. 전체 종목명 → 티커 캐시
# ============================================================

def build_ticker_map(date):

    ticker_map = {}

    for market in [
        "KOSPI",
        "KOSDAQ"
    ]:

        try:

            tickers = stock.get_market_ticker_list(
                date=date,
                market=market
            )

            for ticker in tickers:

                try:

                    name = stock.get_market_ticker_name(
                        ticker
                    )

                    if name:
                        ticker_map[name] = ticker

                except Exception:
                    continue

        except Exception as e:

            print(
                f"[TICKER MAP {market}]",
                e
            )

    print(
        "[KRX] 종목명 매핑:",
        len(ticker_map)
    )

    return ticker_map


# ============================================================
# 9. 국내 전체 종목 데이터
# ============================================================

def get_all_market_data(date):

    frames = []

    for market in [
        "KOSPI",
        "KOSDAQ"
    ]:

        try:

            df = krx_call(
                stock.get_market_ohlcv_by_ticker,
                date,
                market=market
            )

            if (
                isinstance(df, pd.DataFrame)
                and not df.empty
            ):

                temp = df.copy()
                temp["시장"] = market
                frames.append(temp)

        except Exception as e:

            print(
                f"[MARKET DATA {market}]",
                e
            )

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        axis=0
    )


# ============================================================
# 10. 국내 종목 데이터
# ============================================================

def get_stock_data(
    ticker,
    date
):

    try:

        name = stock.get_market_ticker_name(
            ticker
        )

        df = krx_call(
            stock.get_market_ohlcv_by_date,
            date,
            date,
            ticker
        )

        if df.empty:
            return None

        row = df.iloc[-1]

        return {
            "ticker": ticker,
            "name": name,
            "price": safe_float(
                row.get("종가")
            ),
            "rate": safe_float(
                row.get("등락률")
            ),
            "volume": safe_float(
                row.get("거래량")
            ),
            "value": safe_float(
                row.get("거래대금")
            ),
        }

    except Exception as e:

        print(
            f"[STOCK {ticker}]",
            e
        )

        return None


# ============================================================
# 11. 국내 거래대금 TOP10
# ============================================================

def get_domestic_top10(
    date,
    market_df=None
):

    result = []

    try:

        if (
            market_df is None
            or market_df.empty
        ):

            market_df = get_all_market_data(
                date
            )

        if market_df.empty:
            return result

        value_col = None

        for col in [
            "거래대금",
            "거래대금합계"
        ]:

            if col in market_df.columns:
                value_col = col
                break

        if value_col is None:
            return result

        df = market_df.sort_values(
            value_col,
            ascending=False
        ).head(10)

        for ticker, row in df.iterrows():

            name = stock.get_market_ticker_name(
                ticker
            )

            result.append({
                "ticker": ticker,
                "name": name,
                "price": safe_float(
                    row.get("종가")
                ),
                "rate": safe_float(
                    row.get("등락률")
                ),
                "volume": safe_float(
                    row.get("거래량")
                ),
                "value": safe_float(
                    row.get(value_col)
                ),
                "market": row.get(
                    "시장",
                    ""
                )
            })

    except Exception as e:

        print(
            "[TOP10 ERROR]",
            e
        )

    return result


# ============================================================
# 12. 상승/하락 TOP
# ============================================================

def get_market_rankings(
    market_df
):

    result = {
        "rising": [],
        "falling": []
    }

    if (
        market_df is None
        or market_df.empty
    ):
        return result

    if "등락률" not in market_df.columns:
        return result

    try:

        rising = market_df.sort_values(
            "등락률",
            ascending=False
        ).head(10)

        falling = market_df.sort_values(
            "등락률",
            ascending=True
        ).head(10)

        for ticker, row in rising.iterrows():

            try:

                result["rising"].append({
                    "name":
                        stock.get_market_ticker_name(
                            ticker
                        ),
                    "rate":
                        safe_float(
                            row.get("등락률")
                        )
                })

            except Exception:
                pass

        for ticker, row in falling.iterrows():

            try:

                result["falling"].append({
                    "name":
                        stock.get_market_ticker_name(
                            ticker
                        ),
                    "rate":
                        safe_float(
                            row.get("등락률")
                        )
                })

            except Exception:
                pass

    except Exception as e:

        print(
            "[RANKING ERROR]",
            e
        )

    return result


# ============================================================
# 13. 섹터 분석
# ============================================================

def analyze_sector(
    sector_name,
    names,
    date,
    ticker_map,
    market_df
):

    rows = []

    for name in names:

        ticker = ticker_map.get(
            name
        )

        if not ticker:
            continue

        try:

            if ticker not in market_df.index:
                continue

            row = market_df.loc[ticker]

            rows.append({
                "name": name,
                "ticker": ticker,
                "price": safe_float(
                    row.get("종가")
                ),
                "rate": safe_float(
                    row.get("등락률")
                ),
                "volume": safe_float(
                    row.get("거래량")
                ),
                "value": safe_float(
                    row.get("거래대금")
                )
            })

        except Exception:
            continue

    if not rows:

        return {
            "name": sector_name,
            "count": 0,
            "avg_rate": np.nan,
            "total_value": np.nan,
            "rising": 0,
            "falling": 0,
            "leader": None,
            "strength": 0
        }

    df = pd.DataFrame(rows)

    avg_rate = safe_float(
        df["rate"].mean()
    )

    total_value = safe_float(
        df["value"].sum()
    )

    rising = int(
        (df["rate"] > 0).sum()
    )

    falling = int(
        (df["rate"] < 0).sum()
    )

    leader_row = df.sort_values(
        "value",
        ascending=False
    ).iloc[0]

    strength = 0

    if avg_rate >= 2:
        strength += 4

    elif avg_rate >= 1:
        strength += 3

    elif avg_rate > 0:
        strength += 2

    elif avg_rate <= -2:
        strength -= 4

    elif avg_rate < 0:
        strength -= 2

    if rising > falling:
        strength += 2

    elif falling > rising:
        strength -= 2

    return {
        "name": sector_name,
        "count": len(df),
        "avg_rate": avg_rate,
        "total_value": total_value,
        "rising": rising,
        "falling": falling,
        "leader": leader_row.to_dict(),
        "strength": strength,
    }


def get_sector_analysis(
    date,
    ticker_map,
    market_df
):

    result = []

    for sector_name, names in SECTORS.items():

        result.append(
            analyze_sector(
                sector_name,
                names,
                date,
                ticker_map,
                market_df
            )
        )

    result.sort(
        key=lambda x: (
            x["strength"],
            safe_float(
                x["avg_rate"],
                -999
            )
        ),
        reverse=True
    )

    return result


# ============================================================
# 14. Yahoo Finance
# ============================================================

def yahoo_history(
    symbol,
    period="6mo"
):

    for attempt in range(3):

        try:

            df = yf.Ticker(
                symbol
            ).history(
                period=period,
                interval="1d",
                auto_adjust=False
            )

            if (
                df is not None
                and not df.empty
            ):
                return df

        except Exception as e:

            print(
                f"[YAHOO {symbol}] "
                f"{attempt + 1}/3:",
                e
            )

        time.sleep(1)

    return pd.DataFrame()


# ============================================================
# 15. 기술적 분석
# ============================================================

def technical_analysis(
    symbol
):

    df = yahoo_history(
        symbol,
        "6mo"
    )

    if (
        df is None
        or df.empty
        or len(df) < 60
    ):
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

        sma5 = close.rolling(
            5
        ).mean()

        sma20 = close.rolling(
            20
        ).mean()

        sma60 = close.rolling(
            60
        ).mean()

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
            -delta.clip(
                upper=0
            )
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
            (
                current - previous
            )
            / previous
            * 100
            if previous
            else np.nan
        )

        rsi_value = safe_float(
            rsi.iloc[-1]
        )

        macd_value = safe_float(
            macd.iloc[-1]
        )

        signal_value = safe_float(
            signal.iloc[-1]
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

        golden_cross = False

        if len(sma20.dropna()) >= 2:

            prev5 = safe_float(
                sma5.iloc[-2]
            )

            prev20 = safe_float(
                sma20.iloc[-2]
            )

            if (
                not pd.isna(prev5)
                and not pd.isna(prev20)
                and not pd.isna(s5)
                and not pd.isna(s20)
                and prev5 <= prev20
                and s5 > s20
            ):
                golden_cross = True

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

            trend = "조정·약세"

        if pd.isna(rsi_value):

            rsi_state = "미집계"

        elif rsi_value >= 70:

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
            if (
                not pd.isna(macd_value)
                and not pd.isna(signal_value)
                and macd_value > signal_value
            )
            else "하락"
        )

        obv_state = (
            "증가"
            if (
                len(obv) >= 5
                and obv.iloc[-1]
                > obv.iloc[-5]
            )
            else "감소"
        )

        score = 0

        if golden_cross:
            score += 3

        if (
            not pd.isna(rsi_value)
            and 50 <= rsi_value < 70
        ):
            score += 2

        if macd_state == "상승":
            score += 2

        if obv_state == "증가":
            score += 2

        if trend in [
            "상승",
            "강한 상승"
        ]:
            score += 2

        return {
            "price": current,
            "rate": rate,
            "sma5": s5,
            "sma20": s20,
            "sma60": s60,
            "rsi": rsi_value,
            "rsi_state": rsi_state,
            "macd": macd_value,
            "signal": signal_value,
            "macd_state": macd_state,
            "obv_state": obv_state,
            "golden_cross": golden_cross,
            "trend": trend,
            "score": score
        }

    except Exception as e:

        print(
            f"[TECH ERROR] {symbol}:",
            e
        )

        return None


def get_watchlist_analysis():

    korea = []
    usa = []

    for name, symbol in KOREA_WATCHLIST.items():

        data = technical_analysis(
            symbol
        )

        if data:

            korea.append({
                "name": name,
                "symbol": symbol,
                "data": data
            })

    for name, symbol in USA_WATCHLIST.items():

        data = technical_analysis(
            symbol
        )

        if data:

            usa.append({
                "name": name,
                "symbol": symbol,
                "data": data
            })

    korea.sort(
        key=lambda x:
            x["data"]["score"],
        reverse=True
    )

    usa.sort(
        key=lambda x:
            x["data"]["score"],
        reverse=True
    )

    return korea, usa


# ============================================================
# 16. 미국 지수
# ============================================================

def get_us_indices():

    symbols = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI"
    }

    result = {}

    for name, symbol in symbols.items():

        df = yahoo_history(
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
                (
                    current - previous
                )
                / previous
                * 100
                if previous
                else np.nan
            )

            result[name] = {
                "value": current,
                "rate": rate,
                "success": True
            }

        else:

            result[name] = {
                "value": np.nan,
                "rate": np.nan,
                "success": False
            }

    return result


# ============================================================
# 17. 미국 거시경제
# ============================================================

def get_macro():

    symbols = {
        "원달러": "USDKRW=X",
        "WTI": "CL=F",
        "미국채10년": "^TNX",
        "VIX": "^VIX"
    }

    result = {}

    for name, symbol in symbols.items():

        df = yahoo_history(
            symbol,
            "5d"
        )

        if (
            df is not None
            and not df.empty
        ):

            result[name] = safe_float(
                df["Close"].iloc[-1]
            )

        else:

            result[name] = np.nan

    return result


# ============================================================
# 18. 뉴스
#
# Google News RSS를 사용하여 실제 최신 뉴스 검색.
# 뉴스가 없으면 절대 상승 이유를 추정하지 않음.
# ============================================================

def get_news(
    query,
    limit=3
):

    try:

        encoded = urllib.parse.quote(
            query
        )

        url = (
            "https://news.google.com/rss/search?"
            f"q={encoded}"
            "&hl=ko"
            "&gl=KR"
            "&ceid=KR:ko"
        )

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        if response.status_code != 200:
            return []

        root = ET.fromstring(
            response.content
        )

        items = []

        for item in root.findall(
            ".//item"
        ):

            title = clean_text(
                item.findtext("title")
            )

            link = item.findtext(
                "link"
            )

            pub_date = clean_text(
                item.findtext("pubDate")
            )

            if title:

                items.append({
                    "title": title,
                    "link": link or "",
                    "date": pub_date
                })

            if len(items) >= limit:
                break

        return items

    except Exception as e:

        print(
            "[NEWS ERROR]",
            query,
            e
        )

        return []


def get_stock_news(
    name,
    limit=2
):

    queries = [
        f"{name} 주식",
        f"{name} 증권",
        f"{name} 실적"
    ]

    result = []

    for query in queries:

        news = get_news(
            query,
            limit=limit
        )

        for item in news:

            title = item["title"]

            duplicate = False

            for existing in result:

                if title == existing["title"]:
                    duplicate = True
                    break

            if not duplicate:
                result.append(item)

            if len(result) >= limit:
                return result

    return result


# ============================================================
# 19. 섹터 뉴스
# ============================================================

SECTOR_NEWS_QUERY = {
    "반도체·AI": "삼성전자 SK하이닉스 반도체 AI",
    "2차전지·배터리": "삼성SDI LG에너지솔루션 배터리 2차전지",
    "방산·우주항공": "한화에어로스페이스 방산 우주항공",
    "자동차·모빌리티": "현대차 기아 자동차",
    "바이오·헬스케어": "삼성바이오로직스 셀트리온 바이오",
    "전력·원전·인프라": "LS ELECTRIC 두산에너빌리티 전력 원전",
    "조선·중공업": "HD현대중공업 한화오션 조선",
    "금융·증권": "KB금융 신한지주 금융"
}


def get_sector_news(
    sector_name,
    limit=2
):

    query = SECTOR_NEWS_QUERY.get(
        sector_name,
        sector_name
    )

    return get_news(
        query,
        limit=limit
    )


# ============================================================
# 20. 시장 분위기
# ============================================================

def determine_market_mood(
    indices
):

    values = []

    for market in [
        "KOSPI",
        "KOSDAQ"
    ]:

        item = indices.get(
            market
        )

        if (
            item
            and not pd.isna(
                item["rate"]
            )
        ):

            values.append(
                item["rate"]
            )

    if not values:

        return "국내시장 데이터 확인 필요"

    avg = sum(values) / len(values)

    if avg >= 1.0:
        return "강한 상승"

    if avg >= 0.3:
        return "상승 우위"

    if avg <= -1.0:
        return "하락 압력"

    if avg <= -0.3:
        return "약세"

    return "혼조"


# ============================================================
# 21. 섹터 강도
# ============================================================

def strength_text(score):

    if score >= 6:
        return "매우 강함"

    if score >= 4:
        return "강함"

    if score >= 2:
        return "양호"

    if score >= 0:
        return "중립"

    return "약세"


# ============================================================
# 22. 메시지 분할
# ============================================================

def split_message(
    text,
    max_chars=190
):

    text = str(text).strip()

    if not text:
        return []

    chunks = []

    while len(text) > max_chars:

        cut = text.rfind(
            "\n",
            0,
            max_chars
        )

        if cut < 70:

            cut = text.rfind(
                " ",
                0,
                max_chars
            )

        if cut < 70:
            cut = max_chars

        chunks.append(
            text[:cut].strip()
        )

        text = text[cut:].strip()

    if text:
        chunks.append(text)

    return chunks


# ============================================================
# 23. 카카오 Access Token
# ============================================================

def get_kakao_access_token():

    if not KAKAO_REST_API_KEY:

        print(
            "[KAKAO] REST API KEY 없음"
        )

        return None

    if not KAKAO_REFRESH_TOKEN:

        print(
            "[KAKAO] REFRESH TOKEN 없음"
        )

        return None

    url = (
        "https://kauth.kakao.com/oauth/token"
    )

    data = {
        "grant_type":
            "refresh_token",
        "client_id":
            KAKAO_REST_API_KEY,
        "refresh_token":
            KAKAO_REFRESH_TOKEN
    }

    if KAKAO_CLIENT_SECRET:

        data[
            "client_secret"
        ] = KAKAO_CLIENT_SECRET

    for attempt in range(3):

        try:

            response = requests.post(
                url,
                data=data,
                timeout=20
            )

            print(
                "[KAKAO TOKEN]",
                attempt + 1,
                response.status_code
            )

            if response.status_code == 200:

                result = response.json()

                access_token = result.get(
                    "access_token"
                )

                if access_token:
                    return access_token

            else:

                print(
                    response.text[:500]
                )

        except Exception as e:

            print(
                "[KAKAO TOKEN ERROR]",
                e
            )

        time.sleep(2)

    return None


# ============================================================
# 24. 카카오톡 전송
# ============================================================

def send_kakao_message(
    text
):

    token = get_kakao_access_token()

    if not token:

        return False

    chunks = split_message(
        text,
        max_chars=190
    )

    if not chunks:
        return False

    url = (
        "https://kapi.kakao.com/"
        "v2/api/talk/memo/default/send"
    )

    headers = {
        "Authorization":
            f"Bearer {token}",
        "Content-Type":
            "application/x-www-form-urlencoded;charset=utf-8"
    }

    success = True

    for i, chunk in enumerate(
        chunks,
        1
    ):

        template = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url":
                    "https://developers.kakao.com",
                "mobile_web_url":
                    "https://developers.kakao.com"
            }
        }

        data = {
            "template_object":
                json.dumps(
                    template,
                    ensure_ascii=False
                )
        }

        try:

            response = requests.post(
                url,
                headers=headers,
                data=data,
                timeout=20
            )

            print(
                f"[KAKAO SEND] "
                f"{i}/{len(chunks)} "
                f"HTTP {response.status_code}"
            )

            if response.status_code != 200:

                print(
                    response.text[:500]
                )

                success = False

            time.sleep(0.8)

        except Exception as e:

            print(
                "[KAKAO SEND ERROR]",
                e
            )

            success = False

    return success


# ============================================================
# 25. 브리핑 생성
# ============================================================

def generate_briefing():

    now = now_kst()

    today_text = now.strftime(
        "%Y.%m.%d"
    )

    hour = now.hour

    if hour < 9:
        session = "오전 7시"
    elif hour < 13:
        session = "오전 11시"
    elif hour < 17:
        session = "오후 4시"
    else:
        session = "오후 7시"

    # --------------------------------------------------------
    # KRX
    # --------------------------------------------------------

    krx_date = get_latest_krx_date()

    if not krx_date:

        raise RuntimeError(
            "KRX 최신 거래일 조회 실패"
        )

    print(
        "[BRIEFING] KRX:",
        krx_date
    )

    indices = get_domestic_indices(
        krx_date
    )

    market_df = get_all_market_data(
        krx_date
    )

    ticker_map = build_ticker_map(
        krx_date
    )

    top10 = get_domestic_top10(
        krx_date,
        market_df
    )

    rankings = get_market_rankings(
        market_df
    )

    sectors = get_sector_analysis(
        krx_date,
        ticker_map,
        market_df
    )

    # --------------------------------------------------------
    # 미국
    # --------------------------------------------------------

    us_indices = get_us_indices()

    macro = get_macro()

    korea_watch, usa_watch = (
        get_watchlist_analysis()
    )

    mood = determine_market_mood(
        indices
    )

    # ========================================================
    # ① 국내시장 종합
    # ========================================================

    p1 = f"""📊 {today_text} {session}
🇰🇷 국내시장 종합
━━━━━━━━━━━━━━
시장 분위기: {mood}
기준 거래일: {krx_date}

KOSPI
{fmt_number(indices['KOSPI']['value'])}
{fmt_rate(indices['KOSPI']['rate'])}

KOSDAQ
{fmt_number(indices['KOSDAQ']['value'])}
{fmt_rate(indices['KOSDAQ']['rate'])}

📌 객관적 판단
지수 방향을 기준으로 시장의 전반적인 강약을 판단합니다.
개별 종목 상승 이유는 확인된 뉴스가 있을 때만 설명합니다.

━━━━━━━━━━━━━━
⚠️ 데이터 기준
KRX 실제 거래 데이터 기준.
데이터가 없는 항목은 추정하지 않습니다."""

    # ========================================================
    # ② 오늘의 주도 섹터
    # ========================================================

    p2 = """🔥 오늘의 주도 섹터
━━━━━━━━━━━━━━
"""

    valid_sectors = [
        x for x in sectors
        if x["count"] > 0
    ]

    for i, sector in enumerate(
        valid_sectors[:5],
        1
    ):

        leader = sector.get(
            "leader"
        )

        leader_name = (
            leader["name"]
            if leader
            else "미집계"
        )

        news = get_sector_news(
            sector["name"],
            limit=1
        )

        if news:

            news_text = news[0]["title"]

        else:

            news_text = (
                "확인 가능한 주요 뉴스 없음"
            )

        p2 += (
            f"{i}. {sector['name']}\n"
            f"등락률 {fmt_rate(sector['avg_rate'])} "
            f"| 상승 {sector['rising']}"
            f"/하락 {sector['falling']}\n"
            f"거래대금 {fmt_억(sector['total_value'])}\n"
            f"대표주 {leader_name}\n"
            f"뉴스: {news_text}\n\n"
        )

    p2 += (
        "📌 판단 기준\n"
        "섹터 평균 등락률 + 상승/하락 종목 수 + 거래대금을 함께 봅니다.\n"
        "뉴스가 없으면 상승 원인을 추정하지 않습니다."
    )

    # ========================================================
    # ③ 국내 주도주 TOP10
    # ========================================================

    p3 = """🚀 국내 주도주 TOP10
━━━━━━━━━━━━━━
"""

    if top10:

        for i, item in enumerate(
            top10,
            1
        ):

            p3 += (
                f"{i}. {item['name']} "
                f"{fmt_number(item['price'],0)}원\n"
                f"등락 {fmt_rate(item['rate'])}"
                f" | 거래대금 {fmt_억(item['value'])}\n"
            )

            news = get_stock_news(
                item["name"],
                limit=1
            )

            if news:

                p3 += (
                    f"뉴스: "
                    f"{news[0]['title']}\n"
                )

            else:

                p3 += (
                    "뉴스: 확인 가능한 주요 뉴스 없음\n"
                )

            p3 += "\n"

    else:

        p3 += (
            "거래대금 데이터 미집계\n"
        )

    p3 += (
        "📌 주도주 판단\n"
        "거래대금이 큰 종목을 우선 표시합니다.\n"
        "상승률만 높다는 이유로 주도주라고 단정하지 않습니다."
    )

    # ========================================================
    # ④ 기술적 신호
    # ========================================================

    p4 = """📈 골든크로스·기술적 신호
━━━━━━━━━━━━━━
"""

    if korea_watch:

        for item in korea_watch[:6]:

            a = item["data"]

            signals = []

            if a["golden_cross"]:
                signals.append(
                    "★골든크로스"
                )

            if a["macd_state"] == "상승":
                signals.append(
                    "MACD↑"
                )

            if a["obv_state"] == "증가":
                signals.append(
                    "OBV↑"
                )

            if (
                a["trend"]
                in ["상승", "강한 상승"]
            ):
                signals.append(
                    "추세↑"
                )

            if not signals:
                signals.append(
                    "뚜렷한 신호 없음"
                )

            p4 += (
                f"• {item['name']}\n"
                f"현재 {fmt_number(a['price'],0)}원 "
                f"{fmt_rate(a['rate'])}\n"
                f"추세 {a['trend']} | "
                f"RSI {fmt_number(a['rsi'],1)}\n"
                f"{' / '.join(signals)}\n\n"
            )

    else:

        p4 += (
            "국내 기술적 데이터 미집계\n"
        )

    p4 += (
        "📌 해석\n"
        "골든크로스·MACD·OBV·이동평균선이 같은 방향인지 확인합니다.\n"
        "기술적 신호만으로 매수·매도를 단정하지 않습니다."
    )

    # ========================================================
    # ⑤ 미국시장 + 거시
    # ========================================================

    p5 = """🇺🇸 미국시장·글로벌 변수
━━━━━━━━━━━━━━
"""

    for name in [
        "NASDAQ",
        "S&P500",
        "DOW"
    ]:

        item = us_indices[name]

        p5 += (
            f"{name} "
            f"{fmt_number(item['value'])} "
            f"{fmt_rate(item['rate'])}\n"
        )

    p5 += (
        "\n🌎 주요 변수\n"
        f"원/달러 {fmt_number(macro['원달러'])}원\n"
        f"미국채10년 {fmt_number(macro['미국채10년'])}\n"
        f"VIX {fmt_number(macro['VIX'])}\n"
        f"WTI ${fmt_number(macro['WTI'])}\n"
    )

    p5 += "\n⭐ 미국 핵심종목\n"

    for item in usa_watch[:6]:

        a = item["data"]

        signals = []

        if a["golden_cross"]:
            signals.append(
                "골든크로스"
            )

        if a["macd_state"] == "상승":
            signals.append(
                "MACD↑"
            )

        if a["obv_state"] == "증가":
            signals.append(
                "OBV↑"
            )

        if not signals:
            signals.append(
                "신호 제한적"
            )

        p5 += (
            f"• {item['name']} "
            f"{fmt_number(a['price'])} "
            f"{fmt_rate(a['rate'])} "
            f"RSI {fmt_number(a['rsi'],1)} "
            f"{', '.join(signals)}\n"
        )

    # ========================================================
    # ⑥ 오늘의 결론
    # ========================================================

    strongest_sector = (
        valid_sectors[0]
        if valid_sectors
        else None
    )

    if strongest_sector:

        sector_summary = (
            f"{strongest_sector['name']} "
            f"{fmt_rate(strongest_sector['avg_rate'])}"
        )

    else:

        sector_summary = "확인 필요"

    strongest_stock = (
        top10[0]["name"]
        if top10
        else "확인 필요"
    )

    p6 = f"""🎯 오늘의 투자 판단
━━━━━━━━━━━━━━

🔥 가장 강한 섹터
{sector_summary}

🚀 거래대금 1위
{strongest_stock}

📌 확인 순서
① 시장 방향
② 주도 섹터
③ 거래대금
④ 실제 뉴스
⑤ 기술적 신호
⑥ 리스크

📈 관심 조건
거래대금 증가
+ 거래량 증가
+ 20일선 위
+ MACD 상승
+ OBV 증가
+ 실제 뉴스 확인

⚠️ 주의
급등률만 높은 종목은 추격매수하지 않고 거래량·거래대금·뉴스를 함께 확인합니다.

❗ 중요
확인되지 않은 뉴스나 상승 이유는 추정하지 않습니다.
데이터가 없는 항목은 '미집계'로 표시합니다.

※ 본 내용은 객관적인 시장 데이터와 확인 가능한 뉴스에 기반한 참고정보이며 투자 판단과 손익 책임은 투자자에게 있습니다."""

    return [
        p1,
        p2,
        p3,
        p4,
        p5,
        p6
    ]


# ============================================================
# 26. 실행
# ============================================================

def job():

    print("=" * 70)
    print(
        "📊 국내·미국 주식시장 브리핑 시작"
    )
    print("=" * 70)

    check_krx_environment()

    try:

        parts = generate_briefing()

        print(
            f"[INFO] {len(parts)}개 섹터 메시지 생성"
        )

        all_success = True

        for i, part in enumerate(
            parts,
            1
        ):

            print(
                f"[PART {i}/{len(parts)}]"
            )

            success = send_kakao_message(
                part
            )

            if not success:
                all_success = False

            time.sleep(1)

        if all_success:

            print(
                "✅ 모든 카카오톡 전송 완료"
            )

        else:

            print(
                "⚠️ 일부 카카오톡 전송 실패"
            )

    except Exception as e:

        print(
            "❌ 전체 실행 오류:",
            repr(e)
        )

        # 오류 알림
        try:

            error_message = (
                "⚠️ 주식 브리핑 시스템 오류\n"
                f"{str(e)[:300]}\n\n"
                "GitHub Actions 로그를 확인하세요."
            )

            send_kakao_message(
                error_message
            )

        except Exception as send_error:

            print(
                "[ERROR MESSAGE FAIL]",
                send_error
            )

        # GitHub Actions에서 실제 오류를 확인할 수 있도록
        # 최종적으로 실패 처리
        raise


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    job()
