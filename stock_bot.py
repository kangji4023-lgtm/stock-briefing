# ============================================================
# stock_bot.py
# 국내·미국 주식시장 데이터 기반 자동 브리핑
#
# 주요 기능
# 1. KRX 최신 거래일 자동 탐색
# 2. 2026 KRX 로그인 정책 대응
# 3. KOSPI / KOSDAQ
# 4. 국내 거래대금 TOP5
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

# KRX
KRX_ID = os.environ.get("KRX_ID", "dmswl904").strip()
KRX_PW = os.environ.get("KRX_PW", "kang402300*").strip()

# KAKAO
KAKAO_REST_API_KEY = os.environ.get(
    "KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()

KAKAO_REFRESH_TOKEN = os.environ.get(
    "KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc"
).strip()

KAKAO_CLIENT_SECRET = os.environ.get(
    "KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555"
).strip()

if not KAKAO_REST_API_KEY:
    raise RuntimeError("KAKAO_REST_API_KEY가 없습니다.")

if not KAKAO_REFRESH_TOKEN:
    raise RuntimeError("KAKAO_REFRESH_TOKEN이 없습니다.")

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "M9NhxMubg3Xm1qFrO2dyq0IkO69xtbI0AAAAAgoNIFoAAAGgnv2Bdaj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

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

        data = technical_analysis(symbol)
