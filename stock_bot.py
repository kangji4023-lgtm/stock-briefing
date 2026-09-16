from datetime import datetime
import os
import json
import base64
import time

import pytz
import requests
import yfinance as yf
from pykrx import stock

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# =========================================================
# 사용자 설정
# =========================================================

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

# =========================================================
# 국내 + 미국 관심종목
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
    "403870.KS": "HPSP",
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
# 공통
# =========================================================

def now_kst():
    return datetime.now(KST)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except:
        return default


# =========================================================
# 카카오 액세스 토큰
# =========================================================

def get_kakao_access_token():

    if not CLIENT_ID or not REFRESH_TOKEN:
        print("❌ KAKAO_REST_API_KEY 또는 KAKAO_REFRESH_TOKEN 없음")
        return None

    url = "https://kauth.kakao.com/oauth/token"

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": REFRESH_TOKEN,
    }

    if CLIENT_SECRET:
        data["client_secret"] = CLIENT_SECRET

    try:
        response = requests.post(
            url,
            data=data,
            timeout=15
        )

        print("카카오 토큰:", response.status_code)

        if response.status_code == 200:
            result = response.json()

            # 카카오가 새로운 refresh token을 주는 경우
            # GitHub Secret 자체는 자동 변경되지 않으므로
            # 로그에는 토큰을 절대 출력하지 않습니다.
            return result.get("access_token")

        print("❌ 카카오 토큰 오류:", response.text[:500])
        return None

    except Exception as e:
        print("❌ 카카오 토큰 요청 오류:", e)
        return None


# =========================================================
# 카카오 텍스트 메시지
# =========================================================

def send_kakao_text(text):

    access_token = get_kakao_access_token()

    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # 너무 긴 메시지를 여러 개로 분할
    chunks = [
        text[i:i + 900]
        for i in range(0, len(text), 900)
    ]

    success = True

    for chunk in chunks:

        template_object = {
            "object_type": "text",
            "text": chunk,
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com",
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

            if response.status_code != 200:
                print("❌ 카카오 텍스트 전송 실패:", response.text)
                success = False

            time.sleep(0.5)

        except Exception as e:
            print("❌ 카카오 메시지 오류:", e)
            success = False

    return success


# =========================================================
# GitHub에 차트 이미지 업로드
# =========================================================

def upload_chart_to_github(local_path, remote_name):

    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("❌ GitHub 환경변수 없음")
        return None

    try:

        with open(local_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        api_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/contents/"
            f"{remote_name}"
        )

        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # 기존 파일 SHA 확인
        sha = None

        check = requests.get(
            api_url,
            headers=headers,
            timeout=15
        )

        if check.status_code == 200:
            sha = check.json().get("sha")

        payload = {
            "message": f"Update stock chart {remote_name}",
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

        if response.status_code not in [200, 201]:
            print("❌ GitHub 업로드 실패:", response.text[:500])
            return None

        # raw.githubusercontent.com
        raw_url = (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_REPOSITORY}/main/{remote_name}"
        )

        return raw_url

    except Exception as e:
        print("❌ GitHub 차트 업로드 오류:", e)
        return None


# =========================================================
# 카카오 이미지 메시지
# =========================================================

def send_kakao_image(image_url, title, description):

    access_token = get_kakao_access_token()

    if not access_token:
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    template_object = {
        "object_type": "feed",
        "content": {
            "title": title,
            "description": description[:200],
            "image_url": image_url,
            "image_width": 1200,
            "image_height": 800,
            "link": {
                "web_url": image_url,
                "mobile_web_url": image_url,
            }
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
            timeout=20
        )

        print(
            f"카카오 이미지 전송 "
            f"{response.status_code}: "
            f"{title}"
        )

        return response.status_code == 200

    except Exception as e:
        print("❌ 카카오 이미지 오류:", e)
        return False


# =========================================================
# 데이터 다운로드
# =========================================================

def get_stock_data(symbol):

    try:

        df = yf.download(
            symbol,
            period="8mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        if df.empty:
            return None

        # yfinance MultiIndex 처리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        for col in required:
            if col not in df.columns:
                return None

        df = df[required].copy()

        for col in required:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df.dropna(inplace=True)

        if len(df) < 70:
            return None

        return df

    except Exception as e:
        print(symbol, "데이터 오류:", e)
        return None


# =========================================================
# 기술적 지표 계산
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    # 이동평균
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    # 거래량 평균
    df["VOL20"] = df["Volume"].rolling(20).mean()

    # RSI
    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

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
        df["MACD"] -
        df["MACD_SIGNAL"]
    )

    # 최근 20일 고점/저점
    df["HIGH20"] = df["High"].rolling(20).max()
    df["LOW20"] = df["Low"].rolling(20).min()

    return df


# =========================================================
# 매수 / 매도 신호 판단
# =========================================================

def analyze_signal(df):

    df = calculate_indicators(df)

    if len(df) < 65:
        return df, {
            "signal": "데이터 부족",
            "score": 0,
        }

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    score = 0
    reasons = []

    # -----------------------------------------------------
    # 1. 골든크로스
    # -----------------------------------------------------

    golden_cross = (
        yesterday["MA20"] <= yesterday["MA60"]
        and today["MA20"] > today["MA60"]
    )

    death_cross = (
        yesterday["MA20"] >= yesterday["MA60"]
        and today["MA20"] < today["MA60"]
    )

    if golden_cross:
        score += 3
        reasons.append("20일선이 60일선을 상향 돌파")

    # -----------------------------------------------------
    # 2. 정배열
    # -----------------------------------------------------

    if (
        today["MA5"] >
        today["MA20"] >
        today["MA60"]
    ):
        score += 2
        reasons.append("5·20·60일선 정배열")

    # -----------------------------------------------------
    # 3. 가격 위치
    # -----------------------------------------------------

    if today["Close"] > today["MA20"]:
        score += 1
        reasons.append("현재가 20일선 위")

    if today["Close"] > today["MA60"]:
        score += 1
        reasons.append("현재가 60일선 위")

    # -----------------------------------------------------
    # 4. 거래량
    # -----------------------------------------------------

    volume_ratio = (
        today["Volume"] /
        today["VOL20"]
        if today["VOL20"] > 0
        else 0
    )

    if volume_ratio >= 1.5:
        score += 2
        reasons.append(
            f"거래량 {volume_ratio:.1f}배 증가"
        )
    elif volume_ratio >= 1.2:
        score += 1
        reasons.append(
            f"거래량 {volume_ratio:.1f}배"
        )

    # -----------------------------------------------------
    # 5. RSI
    # -----------------------------------------------------

    rsi = safe_float(today["RSI"])

    if 50 <= rsi <= 68:
        score += 1
        reasons.append(
            f"RSI {rsi:.1f} 상승추세 구간"
        )

    # -----------------------------------------------------
    # 6. MACD
    # -----------------------------------------------------

    macd = safe_float(today["MACD"])
    signal = safe_float(today["MACD_SIGNAL"])

    if macd > signal:
        score += 1
        reasons.append("MACD 상승 우위")

    # -----------------------------------------------------
    # 강한 매수 조건
    # -----------------------------------------------------

    strong_buy = (
        score >= 7
        and today["Close"] > today["MA20"]
        and today["Close"] > today["MA60"]
        and macd > signal
        and 45 <= rsi <= 70
    )

    buy = score >= 5

    # -----------------------------------------------------
    # 매도 조건
    # -----------------------------------------------------

    sell_reasons = []

    if death_cross:
        sell_reasons.append(
            "20일선이 60일선을 하향 돌파"
        )

    if (
        rsi >= 75
        and macd < signal
    ):
        sell_reasons.append(
            "RSI 과열 + MACD 약화"
        )

    if (
        today["Close"] < today["MA20"]
        and macd < signal
    ):
        sell_reasons.append(
            "20일선 이탈 + MACD 약세"
        )

    if death_cross or (
        rsi >= 75 and macd < signal
    ):
        sell = True
    else:
        sell = False

    # -----------------------------------------------------
    # 최종 신호
    # -----------------------------------------------------

    if strong_buy:
        final_signal = "🟢 강력 매수 신호"

    elif buy:
        final_signal = "🟡 매수 관심"

    elif sell:
        final_signal = "🔴 매도/익절 주의"

    else:
        final_signal = "⚪ 관망"

    return df, {
        "signal": final_signal,
        "score": score,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "rsi": rsi,
        "volume_ratio": volume_ratio,
        "macd": macd,
        "macd_signal": signal,
        "price": safe_float(today["Close"]),
        "ma20": safe_float(today["MA20"]),
        "ma60": safe_float(today["MA60"]),
        "reasons": reasons,
        "sell_reasons": sell_reasons,
    }


# =========================================================
# 차트 생성
# =========================================================

def create_chart(symbol, name, df, result):

    os.makedirs(CHART_DIR, exist_ok=True)

    chart_file = os.path.join(
        CHART_DIR,
        f"{symbol.replace('.', '_')}.png"
    )

    data = df.tail(90).copy()

    fig = plt.figure(
        figsize=(12, 8)
    )

    ax = fig.add_axes(
        [0.08, 0.30, 0.88, 0.62]
    )

    # 가격
    ax.plot(
        data.index,
        data["Close"],
        label="Close",
        linewidth=2
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

    # 골든크로스 표시
    cross_dates = []

    for i in range(1, len(data)):

        prev = data.iloc[i - 1]
        cur = data.iloc[i]

        if (
            prev["MA20"] <= prev["MA60"]
            and cur["MA20"] > cur["MA60"]
        ):
            cross_dates.append(
                (data.index[i], cur["Close"])
            )

    for date, price in cross_dates:

        ax.scatter(
            date,
            price,
            s=100,
            marker="^",
            zorder=10
        )

        ax.annotate(
            "GOLDEN CROSS",
            (date, price),
            xytext=(0, 15),
            textcoords="offset points",
            ha="center",
            fontsize=8
        )

    # 현재가
    current_price = result["price"]

    ax.axhline(
        current_price,
        linestyle="--",
        linewidth=0.8
    )

    signal_text = result["signal"]

    ax.set_title(
        f"{name} ({symbol})  |  {signal_text}",
        fontsize=15,
        fontweight="bold"
    )

    ax.set_ylabel("Price")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left")

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    rsi_ax = fig.add_axes(
        [0.08, 0.08, 0.88, 0.14]
    )

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
        30,
        linestyle="--",
        linewidth=0.8
    )

    rsi_ax.axhline(
        50,
        linestyle=":",
        linewidth=0.8
    )

    rsi_ax.set_ylim(0, 100)
    rsi_ax.set_ylabel("RSI")
    rsi_ax.grid(alpha=0.2)

    # -----------------------------------------------------
    # 정보 박스
    # -----------------------------------------------------

    info = (
        f"Signal : {result['signal']}\n"
        f"Score : {result['score']}/11\n"
        f"Price : {current_price:,.0f}\n"
        f"MA20 : {result['ma20']:,.0f}\n"
        f"MA60 : {result['ma60']:,.0f}\n"
        f"RSI : {result['rsi']:.1f}\n"
        f"Volume : {result['volume_ratio']:.1f}x\n"
        f"Golden Cross : "
        f"{'YES' if result['golden_cross'] else 'NO'}"
    )

    fig.text(
        0.08,
        0.955,
        info,
        fontsize=9,
        va="top",
        family="monospace"
    )

    plt.savefig(
        chart_file,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    return chart_file


# =========================================================
# 국내 지수
# =========================================================

def get_safe_krx_date():

    try:

        now = now_kst()

        today = now.strftime("%Y%m%d")

        return stock.get_nearest_business_day_in_a_week(
            today
        )

    except:

        return now_kst().strftime("%Y%m%d")


def get_kr_indices():

    krx_date = get_safe_krx_date()

    kospi = "집계 중"
    kosdaq = "집계 중"

    try:

        k_df = stock.get_index_price_change_by_ticker(
            krx_date,
            krx_date,
            "1001"
        )

        kd_df = stock.get_index_price_change_by_ticker(
            krx_date,
            krx_date,
            "2001"
        )

        if not k_df.empty:

            kospi = (
                f"{k_df['종가'].iloc[0]:,.2f} "
                f"({k_df['등락률'].iloc[0]:+.2f}%)"
            )

        if not kd_df.empty:

            kosdaq = (
                f"{kd_df['종가'].iloc[0]:,.2f} "
                f"({kd_df['등락률'].iloc[0]:+.2f}%)"
            )

    except Exception as e:

        print("지수 오류:", e)

    return krx_date, kospi, kosdaq


# =========================================================
# 미국 지수 / 거시경제
# =========================================================

def get_us_macro():

    indices = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI",
    }

    us_text = ""
    us_rates = []

    for name, symbol in indices.items():

        try:

            df = yf.Ticker(symbol).history(
                period="5d"
            )

            if len(df) >= 2:

                cur = safe_float(
                    df["Close"].iloc[-1]
                )

                prev = safe_float(
                    df["Close"].iloc[-2]
                )

                rate = (
                    (cur - prev) /
                    prev * 100
                )

                us_rates.append(rate)

                us_text += (
                    f"- {name}: "
                    f"{cur:,.2f} "
                    f"({rate:+.2f}%)\n"
                )

        except:

            us_text += (
                f"- {name}: 집계 중\n"
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
                period="5d"
            )

            if not df.empty:

                macro[name] = (
                    f"{safe_float(df['Close'].iloc[-1]):,.2f}"
                )

            else:

                macro[name] = "N/A"

        except:

            macro[name] = "N/A"

    return us_text, macro, us_rates


# =========================================================
# 시장 거래대금 TOP 5
# =========================================================

def get_top_kr_stocks():

    krx_date = get_safe_krx_date()

    result = []

    try:

        df = stock.get_market_trading_value_by_ticker(
            krx_date,
            krx_date,
            "ALL"
        )

        if df is None or df.empty:
            return result

        df = df.sort_values(
            by="거래대금",
            ascending=False
        ).head(5)

        for ticker, row in df.iterrows():

            name = stock.get_market_ticker_name(
                ticker
            )

            try:

                ohlcv = stock.get_market_ohlcv_by_date(
                    krx_date,
                    krx_date,
                    ticker
                )

                if not ohlcv.empty:

                    price = safe_float(
                        ohlcv["종가"].iloc[0]
                    )

                    change = safe_float(
                        ohlcv["등락률"].iloc[0]
                    )

                else:

                    price = 0
                    change = 0

            except:

                price = 0
                change = 0

            result.append({
                "ticker": ticker,
                "name": name,
                "price": price,
                "change": change,
            })

    except Exception as e:

        print("거래대금 TOP 오류:", e)

    return result


# =========================================================
# 관심종목 전체 분석
# =========================================================

def analyze_watchlist():

    all_stocks = {}

    all_stocks.update(KR_STOCKS)
    all_stocks.update(US_STOCKS)

    results = []

    for symbol, name in all_stocks.items():

        print("분석:", name, symbol)

        df = get_stock_data(symbol)

        if df is None:
            continue

        df, result = analyze_signal(df)

        result["symbol"] = symbol
        result["name"] = name
        result["df"] = df

        results.append(result)

    return results


# =========================================================
# 실시간 리포트
# =========================================================

def generate_analyst_briefings(results):

    now = now_kst()

    today = now.strftime(
        "%Y-%m-%d %H:%M"
    )

    hour = now.hour

    if hour < 9:
        label = "장시작 브리핑"

    elif hour < 13:
        label = "오전 장중 브리핑"

    elif hour < 17:
        label = "오후 마감 브리핑"

    else:
        label = "저녁 야간 브리핑"

    krx_date, kospi, kosdaq = get_kr_indices()

    us_text, macro, us_rates = get_us_macro()

    top_stocks = get_top_kr_stocks()

    top_text = ""

    for i, item in enumerate(
        top_stocks,
        1
    ):

        top_text += (
            f"{i}. {item['name']} "
            f"{item['price']:,.0f}원 "
            f"({item['change']:+.2f}%)\n"
        )

    # 강한 신호
    strong = [
        x for x in results
        if x["signal"] == "🟢 강력 매수 신호"
    ]

    buy = [
        x for x in results
        if x["signal"] == "🟡 매수 관심"
    ]

    sell = [
        x for x in results
        if x["signal"] == "🔴 매도/익절 주의"
    ]

    strong_text = ""

    for x in strong[:10]:

        strong_text += (
            f"🟢 {x['name']} "
            f"{x['price']:,.0f} "
            f"[점수 {x['score']}/11]\n"
        )

    if not strong_text:
        strong_text = "현재 강력 매수 조건 충족 종목 없음\n"

    buy_text = ""

    for x in buy[:10]:

        buy_text += (
            f"🟡 {x['name']} "
            f"{x['price']:,.0f} "
            f"[점수 {x['score']}/11]\n"
        )

    if not buy_text:
        buy_text = "현재 매수 관심 종목 없음\n"

    sell_text = ""

    for x in sell[:10]:

        sell_text += (
            f"🔴 {x['name']} "
            f"{x['price']:,.0f}\n"
        )

    if not sell_text:
        sell_text = "현재 매도/익절 주의 종목 없음\n"

    # 시장 분위기
    kospi_rate = 0

    try:

        if "(" in kospi:
            kospi_rate = float(
                kospi.split("(")[1]
                .replace("%)", "")
            )

    except:
        pass

    if (
        kospi_rate <= -1
        or (
            us_rates
            and min(us_rates) <= -1.5
        )
    ):

        mood = "변동성 확대 / 하방 압력"

    elif (
        kospi_rate >= 1
        or (
            us_rates
            and max(us_rates) >= 1.5
        )
    ):

        mood = "상승 모멘텀 강화"

    else:

        mood = "혼조 / 종목별 차별화"

    part1 = f"""
📅 {today}
📊 실시간 주식시장 브리핑
[{label}]
━━━━━━━━━━━━━━

🌍 시장 진단
시장 분위기: {mood}

🇰🇷 국내시장
KOSPI : {kospi}
KOSDAQ : {kosdaq}

🔥 거래대금 TOP 5
{top_text.strip()}
"""

    part2 = f"""
📊 글로벌 시장
━━━━━━━━━━━━━━

🇺🇸 미국 주요지수

{us_text.strip()}

🌎 거시지표

환율 : {macro.get('환율','N/A')}
WTI : {macro.get('유가','N/A')}
미국채10Y : {macro.get('국채10년','N/A')}
VIX : {macro.get('VIX','N/A')}
"""

    part3 = f"""
🎯 기술적 신호 분석
━━━━━━━━━━━━━━

🟢 강력 매수 신호

{strong_text.strip()}

🟡 매수 관심

{buy_text.strip()}

🔴 매도/익절 주의

{sell_text.strip()}

📌 신호 기준
• MA20/MA60 골든크로스
• MA5 > MA20 > MA60
• 현재가와 이동평균선 위치
• 거래량 증가
• RSI
• MACD

※ 기술적 조건에 따른 자동 분류이며
투자 결과를 보장하는 신호는 아닙니다.
"""

    return part1, part2, part3


# =========================================================
# 차트 생성 + 카카오 전송
# =========================================================

def send_signal_charts(results):

    # 강력 매수 → 매수 관심 → 매도 주의 순
    selected = []

    selected += [
        x for x in results
        if x["signal"] == "🟢 강력 매수 신호"
    ]

    selected += [
        x for x in results
        if x["signal"] == "🟡 매수 관심"
    ]

    selected += [
        x for x in results
        if x["signal"] == "🔴 매도/익절 주의"
    ]

    # 카카오 메시지 폭주 방지
    selected = selected[:10]

    if not selected:

        send_kakao_text(
            "📊 기술적 신호 종목 없음\n"
            "현재 골든크로스·매수 조건을 "
            "충족하는 관심종목이 없습니다."
        )

        return

    for x in selected:

        print(
            "차트 생성:",
            x["name"],
            x["signal"]
        )

        chart_file = create_chart(
            x["symbol"],
            x["name"],
            x["df"],
            x
        )

        remote_name = (
            f"charts/"
            f"{x['symbol'].replace('.', '_')}.png"
        )

        image_url = upload_chart_to_github(
            chart_file,
            remote_name
        )

        if not image_url:

            print(
                "❌ 이미지 URL 생성 실패:",
                x["name"]
            )

            continue

        reasons = x["reasons"]

        description = (
            f"{x['signal']}\n"
            f"점수: {x['score']}/11\n"
            f"RSI: {x['rsi']:.1f}\n"
            f"거래량: {x['volume_ratio']:.1f}배\n"
            f"골든크로스: "
            f"{'발생' if x['golden_cross'] else '없음'}"
        )

        send_kakao_image(
            image_url,
            f"📈 {x['name']} 기술적 분석",
            description
        )

        time.sleep(1)


# =========================================================
# MAIN JOB
# =========================================================

def job():

    print("=" * 60)
    print(
        f"[{now_kst()}] "
        f"주식 AI 브리핑 시작"
    )
    print("=" * 60)

    # -----------------------------------------------------
    # 1. 관심종목 분석
    # -----------------------------------------------------

    results = analyze_watchlist()

    print(
        f"총 {len(results)}개 종목 분석 완료"
    )

    # -----------------------------------------------------
    # 2. 문자 브리핑
    # -----------------------------------------------------

    p1, p2, p3 = generate_analyst_briefings(
        results
    )

    send_kakao_text(p1)
    time.sleep(1)

    send_kakao_text(p2)
    time.sleep(1)

    send_kakao_text(p3)

    # -----------------------------------------------------
    # 3. 차트 이미지
    # -----------------------------------------------------

    send_signal_charts(results)

    print("=" * 60)
    print("✅ 전체 브리핑 완료")
    print("=" * 60)


if __name__ == "__main__":
    job()
