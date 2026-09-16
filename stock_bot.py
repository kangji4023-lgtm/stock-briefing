from datetime import datetime
import os
import json
import base64
import time
from pathlib import Path

import pytz
import requests
import yfinance as yf
from pykrx import stock
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# =========================================================
# STOCK BRIEFING - FINAL
# 국내/미국 주식 + 기술적 신호 + 차트 + 카카오톡
# =========================================================

KST = pytz.timezone("Asia/Seoul")
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

# 차트를 너무 많이 보내 카카오톡이 폭주하지 않도록 제한
MAX_CHARTS_TO_SEND = 10


# =========================================================
# 관심종목
# =========================================================

KR_STOCKS = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "009150.KS": "삼성전기",
    "402340.KS": "SK스퀘어",
    "005380.KS": "현대차",
    "006400.KS": "삼성SDI",
    "042700.KS": "한미반도체",
    "010120.KS": "LS ELECTRIC",
    "012450.KS": "한화에어로스페이스",
    "034020.KS": "두산에너빌리티",
    "039030.KQ": "이오테크닉스",
    "403870.KQ": "HPSP",
    "031980.KQ": "피에스케이홀딩스",
}

US_STOCKS = {
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "GOOGL": "Alphabet",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "META": "Meta",
    "AVGO": "Broadcom",
    "AMD": "AMD",
    "TSM": "TSMC",
    "SMH": "반도체 ETF",
    "SOXL": "반도체 3X ETF",
}


# =========================================================
# 공통 유틸
# =========================================================

def now_kst():
    return datetime.now(KST)


def safe_float(value, default=np.nan):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_num(value, digits=0):
    value = safe_float(value)
    if pd.isna(value):
        return "N/A"
    return f"{value:,.{digits}f}"


def split_message(text, limit=850):
    """카카오 메시지가 너무 길어지지 않도록 안전하게 분할."""
    if not text:
        return []

    chunks = []
    current = ""

    for line in text.splitlines(True):
        if len(current) + len(line) <= limit:
            current += line
        else:
            if current:
                chunks.append(current.rstrip())
            # 한 줄 자체가 긴 경우
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line

    if current:
        chunks.append(current.rstrip())

    return chunks


# =========================================================
# 카카오 인증
# =========================================================

def get_kakao_access_token():
    if not KAKAO_REST_API_KEY:
        print("❌ KAKAO_REST_API_KEY가 없습니다.")
        return None

    if not KAKAO_REFRESH_TOKEN:
        print("❌ KAKAO_REFRESH_TOKEN이 없습니다.")
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
        response = requests.post(url, data=data, timeout=20)

        print("카카오 토큰 응답:", response.status_code)

        if response.status_code != 200:
            print("❌ 카카오 토큰 발급 실패")
            print(response.text[:500])
            return None

        result = response.json()
        access_token = result.get("access_token")

        if not access_token:
            print("❌ access_token이 없습니다.")
            print(result)
            return None

        print("✅ 카카오 액세스 토큰 발급 성공")
        return access_token

    except Exception as e:
        print("❌ 카카오 인증 오류:", repr(e))
        return None


def kakao_request(template_object):
    access_token = get_kakao_access_token()

    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
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
            timeout=20
        )

        if response.status_code == 200:
            return True

        print("❌ 카카오 전송 실패:", response.status_code)
        print(response.text[:1000])
        return False

    except Exception as e:
        print("❌ 카카오 요청 오류:", repr(e))
        return False


def send_kakao_text(text):
    chunks = split_message(text, 850)

    if not chunks:
        return False

    all_ok = True

    for chunk in chunks:
        template = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com",
            },
        }

        ok = kakao_request(template)
        all_ok = all_ok and ok
        time.sleep(0.8)

    return all_ok


def send_kakao_image(image_url, title, description):
    """
    Kakao Feed 템플릿으로 차트 이미지를 전송.
    image_url은 인터넷에서 직접 접근 가능한 공개 HTTPS 이미지여야 합니다.
    """

    if not image_url.startswith("https://"):
        print("❌ 공개 HTTPS 이미지 URL이 아닙니다:", image_url)
        return False

    template = {
        "object_type": "feed",
        "content": {
            "title": title[:200],
            "description": description[:200],
            "image_url": image_url,
            "image_width": 1200,
            "image_height": 800,
            "link": {
                "web_url": image_url,
                "mobile_web_url": image_url,
            },
        },
    }

    return kakao_request(template)


# =========================================================
# GitHub 차트 업로드
# =========================================================

def github_upload_chart(local_path, remote_path):
    """
    GitHub 저장소에 차트를 올리고 raw.githubusercontent.com URL을 반환.
    저장소는 공개(Public)여야 카카오가 이미지를 읽을 수 있습니다.
    """

    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN이 없습니다.")
        return None

    if not GITHUB_REPOSITORY:
        print("❌ GITHUB_REPOSITORY가 없습니다.")
        return None

    local_path = Path(local_path)

    try:
        content = base64.b64encode(
            local_path.read_bytes()
        ).decode("utf-8")

        api_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/contents/{remote_path}"
        )

        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        sha = None

        check = requests.get(
            api_url,
            headers=headers,
            timeout=20
        )

        if check.status_code == 200:
            sha = check.json().get("sha")
        elif check.status_code != 404:
            print("❌ GitHub 기존 파일 확인 실패")
            print(check.text[:500])
            return None

        payload = {
            "message": f"Update stock chart: {remote_path}",
            "content": content,
        }

        if sha:
            payload["sha"] = sha

        response = requests.put(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code not in (200, 201):
            print("❌ GitHub 차트 업로드 실패")
            print(response.text[:1000])
            return None

        raw_url = (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_REPOSITORY}/"
            f"{GITHUB_BRANCH}/"
            f"{remote_path}"
        )

        print("✅ GitHub 업로드:", raw_url)
        return raw_url

    except Exception as e:
        print("❌ GitHub 업로드 오류:", repr(e))
        return None


# =========================================================
# 데이터 수집
# =========================================================

def download_history(symbol, period="8mo"):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            print("❌ 데이터 없음:", symbol)
            return None

        # yfinance가 MultiIndex를 반환하는 경우 처리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        missing = [c for c in required if c not in df.columns]

        if missing:
            print("❌ 필요한 컬럼 없음:", symbol, missing)
            return None

        df = df[required].copy()

        for col in required:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df.dropna(inplace=True)

        if len(df) < 70:
            print("❌ 분석 데이터 부족:", symbol, len(df))
            return None

        return df

    except Exception as e:
        print("❌ 주가 데이터 오류:", symbol, repr(e))
        return None


# =========================================================
# 기술적 지표
# =========================================================

def add_indicators(df):
    df = df.copy()

    # 이동평균
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    # 거래량
    df["VOL20"] = df["Volume"].rolling(20).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL20"]

    # RSI 14
    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["Close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["Close"].ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["MACD_HIST"] = (
        df["MACD"] - df["MACD_SIGNAL"]
    )

    return df


# =========================================================
# 신호 분석
# =========================================================

def analyze_stock(df):
    df = add_indicators(df)

    if len(df) < 65:
        return df, {
            "signal": "⚪ 데이터 부족",
            "score": 0,
            "reasons": [],
            "sell_reasons": [],
        }

    t = df.iloc[-1]
    p = df.iloc[-2]

    score = 0
    reasons = []
    sell_reasons = []

    ma5 = safe_float(t["MA5"])
    ma20 = safe_float(t["MA20"])
    ma60 = safe_float(t["MA60"])
    price = safe_float(t["Close"])

    rsi = safe_float(t["RSI"])
    volume_ratio = safe_float(t["VOL_RATIO"])

    macd = safe_float(t["MACD"])
    macd_signal = safe_float(t["MACD_SIGNAL"])

    golden_cross = (
        safe_float(p["MA20"]) <= safe_float(p["MA60"])
        and ma20 > ma60
    )

    death_cross = (
        safe_float(p["MA20"]) >= safe_float(p["MA60"])
        and ma20 < ma60
    )

    # 골든크로스
    if golden_cross:
        score += 3
        reasons.append("20일선 → 60일선 골든크로스")

    # 정배열
    if ma5 > ma20 > ma60:
        score += 2
        reasons.append("5·20·60일선 정배열")

    # 가격 위치
    if price > ma20:
        score += 1
        reasons.append("현재가 20일선 위")

    if price > ma60:
        score += 1
        reasons.append("현재가 60일선 위")

    # 거래량
    if not pd.isna(volume_ratio):
        if volume_ratio >= 1.5:
            score += 2
            reasons.append(
                f"거래량 {volume_ratio:.1f}배 급증"
            )
        elif volume_ratio >= 1.2:
            score += 1
            reasons.append(
                f"거래량 {volume_ratio:.1f}배"
            )

    # RSI
    if not pd.isna(rsi):
        if 50 <= rsi <= 68:
            score += 1
            reasons.append(
                f"RSI {rsi:.1f} 상승 추세 구간"
            )

    # MACD
    if not pd.isna(macd) and not pd.isna(macd_signal):
        if macd > macd_signal:
            score += 1
            reasons.append("MACD 시그널 상회")

    # 매도/익절 주의
    if death_cross:
        sell_reasons.append(
            "20일선 → 60일선 데드크로스"
        )

    if (
        not pd.isna(rsi)
        and rsi >= 75
        and macd < macd_signal
    ):
        sell_reasons.append(
            "RSI 과열 후 MACD 약화"
        )

    if (
        price < ma20
        and macd < macd_signal
    ):
        sell_reasons.append(
            "20일선 이탈 + MACD 약세"
        )

    # 강력 매수 신호
    # '매수 추천'이 아니라 기술적 조건이 많이 겹친 상태를 표시
    strong_buy = (
        score >= 7
        and price > ma20 > ma60
        and macd > macd_signal
        and 45 <= rsi <= 70
    )

    if strong_buy:
        signal = "🟢 강력 매수 조건"
    elif score >= 5:
        signal = "🟡 매수 관심 조건"
    elif sell_reasons:
        signal = "🔴 매도/익절 주의"
    else:
        signal = "⚪ 관망"

    result = {
        "signal": signal,
        "score": score,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "price": price,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "rsi": rsi,
        "volume_ratio": volume_ratio,
        "macd": macd,
        "macd_signal": macd_signal,
        "reasons": reasons,
        "sell_reasons": sell_reasons,
    }

    return df, result


# =========================================================
# 차트 생성
# =========================================================

def create_chart(symbol, name, df, result):
    chart_dir = Path("charts")
    chart_dir.mkdir(parents=True, exist_ok=True)

    safe_symbol = (
        symbol
        .replace(".", "_")
        .replace("/", "_")
        .replace("^", "")
    )

    chart_file = chart_dir / f"{safe_symbol}.png"

    data = df.tail(90).copy()

    fig = plt.figure(figsize=(12, 8))

    ax = fig.add_axes([0.08, 0.34, 0.88, 0.55])

    ax.plot(
        data.index,
        data["Close"],
        label="Close",
        linewidth=2
    )

    ax.plot(
        data.index,
        data["MA5"],
        label="MA5",
        linewidth=1
    )

    ax.plot(
        data.index,
        data["MA20"],
        label="MA20",
        linewidth=1.5
    )

    ax.plot(
        data.index,
        data["MA60"],
        label="MA60",
        linewidth=1.5
    )

    # 골든/데드크로스 표시
    for i in range(1, len(data)):
        prev = data.iloc[i - 1]
        cur = data.iloc[i]

        if (
            safe_float(prev["MA20"]) <= safe_float(prev["MA60"])
            and safe_float(cur["MA20"]) > safe_float(cur["MA60"])
        ):
            d = data.index[i]
            y = safe_float(cur["Close"])

            ax.scatter(
                d,
                y,
                s=120,
                marker="^",
                zorder=10
            )

            ax.annotate(
                "GOLDEN CROSS",
                (d, y),
                xytext=(0, 18),
                textcoords="offset points",
                ha="center",
                fontsize=8
            )

        if (
            safe_float(prev["MA20"]) >= safe_float(prev["MA60"])
            and safe_float(cur["MA20"]) < safe_float(cur["MA60"])
        ):
            d = data.index[i]
            y = safe_float(cur["Close"])

            ax.scatter(
                d,
                y,
                s=110,
                marker="v",
                zorder=10
            )

            ax.annotate(
                "DEATH CROSS",
                (d, y),
                xytext=(0, -25),
                textcoords="offset points",
                ha="center",
                fontsize=8
            )

    current_price = result["price"]

    ax.axhline(
        current_price,
        linestyle="--",
        linewidth=0.8
    )

    ax.set_title(
        f"{name} ({symbol}) | {result['signal']} | "
        f"기술적 점수 {result['score']}/11",
        fontsize=14,
        fontweight="bold"
    )

    ax.set_ylabel("Price")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left")

    # RSI
    rsi_ax = fig.add_axes([0.08, 0.10, 0.88, 0.15])

    rsi_ax.plot(
        data.index,
        data["RSI"],
        linewidth=1.5
    )

    rsi_ax.axhline(
        70,
        linestyle="--",
        linewidth=0.8
    )

    rsi_ax.axhline(
        50,
        linestyle=":",
        linewidth=0.8
    )

    rsi_ax.axhline(
        30,
        linestyle="--",
        linewidth=0.8
    )

    rsi_ax.set_ylim(0, 100)
    rsi_ax.set_ylabel("RSI")
    rsi_ax.grid(alpha=0.2)

    # 오른쪽 정보
    info = (
        f"현재가   {fmt_num(result['price'])}\n"
        f"MA5      {fmt_num(result['ma5'])}\n"
        f"MA20     {fmt_num(result['ma20'])}\n"
        f"MA60     {fmt_num(result['ma60'])}\n"
        f"RSI      {fmt_num(result['rsi'], 1)}\n"
        f"거래량   {fmt_num(result['volume_ratio'], 1)}x\n"
        f"골든크로스 {'YES' if result['golden_cross'] else 'NO'}"
    )

    fig.text(
        0.82,
        0.965,
        info,
        fontsize=8,
        va="top",
        family="monospace"
    )

    plt.savefig(
        chart_file,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close(fig)

    print("✅ 차트 생성:", chart_file)

    return chart_file


# =========================================================
# KRX 날짜 / 지수
# =========================================================

def get_safe_krx_date():
    try:
        today = now_kst().strftime("%Y%m%d")
        return stock.get_nearest_business_day_in_a_week(today)
    except Exception as e:
        print("KRX 날짜 오류:", repr(e))
        return now_kst().strftime("%Y%m%d")


def get_kr_indices():
    date = get_safe_krx_date()

    kospi = "집계 중"
    kosdaq = "집계 중"

    try:
        k = stock.get_index_ohlcv_by_date(
            date, date, "1001"
        )

        if not k.empty:
            close = safe_float(k["종가"].iloc[0])
            rate = safe_float(k["등락률"].iloc[0])
            kospi = f"{close:,.2f} ({rate:+.2f}%)"
    except Exception as e:
        print("KOSPI 오류:", repr(e))

    try:
        kq = stock.get_index_ohlcv_by_date(
            date, date, "2001"
        )

        if not kq.empty:
            close = safe_float(kq["종가"].iloc[0])
            rate = safe_float(kq["등락률"].iloc[0])
            kosdaq = f"{close:,.2f} ({rate:+.2f}%)"
    except Exception as e:
        print("KOSDAQ 오류:", repr(e))

    return date, kospi, kosdaq


# =========================================================
# 거래대금 TOP 5
# =========================================================

def get_top_kr_stocks():
    date = get_safe_krx_date()
    result = []

    try:
        df = stock.get_market_trading_value_by_ticker(
            date,
            date,
            "ALL"
        )

        if df is None or df.empty:
            return result

        df = df.sort_values(
            by="거래대금",
            ascending=False
        ).head(5)

        for ticker, row in df.iterrows():
            name = stock.get_market_ticker_name(ticker)

            price = np.nan
            change = np.nan

            try:
                ohlcv = stock.get_market_ohlcv_by_date(
                    date,
                    date,
                    ticker
                )

                if not ohlcv.empty:
                    price = safe_float(
                        ohlcv["종가"].iloc[0]
                    )

                    if "등락률" in ohlcv.columns:
                        change = safe_float(
                            ohlcv["등락률"].iloc[0]
                        )
            except Exception:
                pass

            result.append({
                "ticker": ticker,
                "name": name,
                "price": price,
                "change": change,
            })

    except Exception as e:
        print("❌ 거래대금 TOP 오류:", repr(e))

    return result


# =========================================================
# 미국 지수 / 거시
# =========================================================

def get_us_macro():
    indices = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI",
    }

    us_text = []
    us_rates = []

    for name, symbol in indices.items():
        try:
            df = yf.Ticker(symbol).history(
                period="5d",
                interval="1d"
            )

            if len(df) >= 2:
                cur = safe_float(df["Close"].iloc[-1])
                prev = safe_float(df["Close"].iloc[-2])

                rate = (
                    (cur - prev) / prev * 100
                    if prev
                    else np.nan
                )

                if not pd.isna(rate):
                    us_rates.append(rate)

                us_text.append(
                    f"- {name}: {fmt_num(cur, 2)} "
                    f"({rate:+.2f}%)"
                )
            else:
                us_text.append(
                    f"- {name}: 데이터 부족"
                )

        except Exception as e:
            print("미국 지수 오류:", name, repr(e))
            us_text.append(
                f"- {name}: 집계 중"
            )

    macro = {}

    symbols = {
        "환율": "USDKRW=X",
        "유가": "CL=F",
        "국채10년": "^TNX",
        "VIX": "^VIX",
    }

    for name, symbol in symbols.items():
        try:
            df = yf.Ticker(symbol).history(
                period="5d",
                interval="1d"
            )

            if not df.empty:
                macro[name] = fmt_num(
                    df["Close"].iloc[-1],
                    2
                )
            else:
                macro[name] = "N/A"

        except Exception:
            macro[name] = "N/A"

    return "\n".join(us_text), macro, us_rates


# =========================================================
# 전체 관심종목 분석
# =========================================================

def analyze_watchlist():
    stocks = {}
    stocks.update(KR_STOCKS)
    stocks.update(US_STOCKS)

    results = []

    for symbol, name in stocks.items():
        print(f"📊 분석: {name} ({symbol})")

        df = download_history(symbol)

        if df is None:
            continue

        try:
            analyzed_df, signal = analyze_stock(df)

            signal["symbol"] = symbol
            signal["name"] = name
            signal["df"] = analyzed_df

            results.append(signal)

        except Exception as e:
            print(
                f"❌ 분석 실패: {name} ({symbol})",
                repr(e)
            )

    return results


# =========================================================
# 시장 분위기
# =========================================================

def get_market_mood(kospi_text, us_rates):
    kospi_rate = np.nan

    try:
        kospi_rate = float(
            kospi_text.split("(")[1]
            .replace("%)", "")
        )
    except Exception:
        pass

    if (
        not pd.isna(kospi_rate)
        and kospi_rate <= -1.0
    ):
        return "변동성 확대 / 하방 압력 주의"

    if (
        us_rates
        and min(us_rates) <= -1.5
    ):
        return "미국 증시 약세 / 변동성 주의"

    if (
        not pd.isna(kospi_rate)
        and kospi_rate >= 1.0
    ):
        return "국내 상승 모멘텀 강화"

    if (
        us_rates
        and max(us_rates) >= 1.5
    ):
        return "미국 증시 상승 모멘텀"

    return "혼조 / 종목별 차별화"


# =========================================================
# 브리핑 생성
# =========================================================

def generate_briefings(results):
    now = now_kst()
    today = now.strftime("%Y-%m-%d %H:%M")

    hour = now.hour

    if hour < 9:
        label = "장시작 브리핑"
    elif hour < 13:
        label = "오전 11시 장중 브리핑"
    elif hour < 17:
        label = "오후 4시 마감 브리핑"
    else:
        label = "저녁 야간 브리핑"

    krx_date, kospi, kosdaq = get_kr_indices()
    us_text, macro, us_rates = get_us_macro()
    top = get_top_kr_stocks()

    mood = get_market_mood(kospi, us_rates)

    top_text = "\n".join(
        [
            f"{i}. {x['name']} "
            f"{fmt_num(x['price'])}원 "
            f"({safe_float(x['change']):+.2f}%)"
            for i, x in enumerate(top, 1)
        ]
    )

    if not top_text:
        top_text = "거래대금 데이터 집계 중"

    strong = [
        x for x in results
        if x["signal"] == "🟢 강력 매수 조건"
    ]

    buy = [
        x for x in results
        if x["signal"] == "🟡 매수 관심 조건"
    ]

    sell = [
        x for x in results
        if x["signal"] == "🔴 매도/익절 주의"
    ]

    def signal_lines(items):
        if not items:
            return "해당 조건 종목 없음"

        return "\n".join(
            [
                f"{x['name']} "
                f"{fmt_num(x['price'])} "
                f"[{x['score']}/11]"
                for x in items[:10]
            ]
        )

    strong_text = signal_lines(strong)
    buy_text = signal_lines(buy)
    sell_text = signal_lines(sell)

    p1 = f"""📅 {today}
📊 실시간 주식시장 브리핑
[{label}]
━━━━━━━━━━━━━━━━

🌍 시장 진단
시장 분위기: {mood}

🇰🇷 국내시장
KOSPI: {kospi}
KOSDAQ: {kosdaq}
기준일: {krx_date}

🔥 국내 거래대금 TOP 5
{top_text}
"""

    p2 = f"""📊 글로벌 증시
━━━━━━━━━━━━━━━━

🇺🇸 미국 주요지수
{us_text}

🌎 거시경제
원/달러: {macro.get('환율', 'N/A')}
WTI: {macro.get('유가', 'N/A')}
미국채 10년: {macro.get('국채10년', 'N/A')}
VIX: {macro.get('VIX', 'N/A')}
"""

    p3 = f"""🎯 기술적 신호 분석
━━━━━━━━━━━━━━━━

🟢 강력 매수 조건
{strong_text}

🟡 매수 관심 조건
{buy_text}

🔴 매도/익절 주의
{sell_text}

📌 판단에 사용한 기술지표
① MA5 / MA20 / MA60
② 골든크로스 / 데드크로스
③ 정배열
④ 거래량
⑤ RSI(14)
⑥ MACD
⑦ 현재가와 이동평균선 위치

⚠️ 기술적 조건을 자동 표시한 정보이며
투자 결과를 보장하는 신호가 아닙니다.
"""

    return p1, p2, p3


# =========================================================
# 차트 생성 + 업로드 + 카카오 전송
# =========================================================

def send_signal_charts(results):
    # 신호가 있는 종목을 우선
    priority = [
        x for x in results
        if x["signal"] == "🟢 강력 매수 조건"
    ]

    priority += [
        x for x in results
        if x["signal"] == "🟡 매수 관심 조건"
    ]

    priority += [
        x for x in results
        if x["signal"] == "🔴 매도/익절 주의"
    ]

    # 중복 제거
    selected = []
    seen = set()

    for x in priority:
        if x["symbol"] not in seen:
            selected.append(x)
            seen.add(x["symbol"])

    selected = selected[:MAX_CHARTS_TO_SEND]

    if not selected:
        send_kakao_text(
            "📈 기술적 차트 알림\n\n"
            "현재 관심종목 중 차트 전송 대상 "
            "기술적 조건 종목이 없습니다."
        )
        return

    for x in selected:
        try:
            chart_file = create_chart(
                x["symbol"],
                x["name"],
                x["df"],
                x
            )

            remote_path = (
                f"charts/"
                f"{x['symbol'].replace('.', '_').replace('/', '_')}.png"
            )

            image_url = github_upload_chart(
                chart_file,
                remote_path
            )

            if not image_url:
                continue

            reasons = " / ".join(
                x["reasons"][:3]
            )

            if x["sell_reasons"]:
                reasons += " / " + " / ".join(
                    x["sell_reasons"][:2]
                )

            description = (
                f"{x['signal']}\n"
                f"점수 {x['score']}/11 | "
                f"현재가 {fmt_num(x['price'])}\n"
                f"RSI {fmt_num(x['rsi'], 1)} | "
                f"거래량 {fmt_num(x['volume_ratio'], 1)}배\n"
                f"{reasons}"
            )

            send_kakao_image(
                image_url,
                f"📈 {x['name']} 기술적 차트",
                description
            )

            time.sleep(1)

        except Exception as e:
            print(
                f"❌ 차트 전송 실패: {x['name']}",
                repr(e)
            )


# =========================================================
# 메인
# =========================================================

def job():
    print("=" * 60)
    print(f"[{now_kst()}] 🚀 STOCK BRIEFING START")
    print("=" * 60)

    # 1. 종목 분석
    results = analyze_watchlist()

    print(
        f"✅ 분석 완료: {len(results)}개 종목"
    )

    # 2. 텍스트 브리핑
    p1, p2, p3 = generate_briefings(results)

    print("📨 카카오 텍스트 전송")

    send_kakao_text(p1)
    time.sleep(1)

    send_kakao_text(p2)
    time.sleep(1)

    send_kakao_text(p3)
    time.sleep(1)

    # 3. 차트
    print("📈 차트 생성/업로드/전송")

    send_signal_charts(results)

    print("=" * 60)
    print("✅ STOCK BRIEFING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    job()
