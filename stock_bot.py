from datetime import datetime
import os
import json
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
# =========================================================
# 국내 관심종목
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


# =========================================================
# 미국 관심종목
# =========================================================

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
# 현재 한국시간
# =========================================================

def now_kst():

    return datetime.now(KST)


# =========================================================
# 숫자 변환
# =========================================================

def safe_float(value, default=0.0):

    try:

        if pd.isna(value):
            return default

        return float(value)

    except:

        return default


# =========================================================
# 카카오 액세스 토큰 발급
# =========================================================

def get_kakao_access_token():

    if not KAKAO_REST_API_KEY:

        print(
            "❌ KAKAO_REST_API_KEY가 없습니다."
        )

        return None

    if not KAKAO_REFRESH_TOKEN:

        print(
            "❌ KAKAO_REFRESH_TOKEN이 없습니다."
        )

        return None

    url = (
        "https://kauth.kakao.com/oauth/token"
    )

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }

    # Client Secret을 사용하는 카카오 앱이면 추가
    if KAKAO_CLIENT_SECRET:

        data["client_secret"] = (
            KAKAO_CLIENT_SECRET
        )

    try:

        response = requests.post(
            url,
            data=data,
            timeout=15
        )

        print(
            "카카오 토큰 응답:",
            response.status_code
        )

        if response.status_code == 200:

            result = response.json()

            access_token = result.get(
                "access_token"
            )

            if access_token:

                print(
                    "✅ 카카오 액세스 토큰 발급 성공"
                )

                return access_token

            print(
                "❌ access_token이 없습니다."
            )

            return None

        print(
            "❌ 카카오 토큰 발급 실패:"
        )

        print(
            response.text[:500]
        )

        return None

    except Exception as e:

        print(
            "❌ 카카오 토큰 요청 오류:",
            e
        )

        return None


# =========================================================
# 카카오 텍스트 메시지
# =========================================================

def send_kakao_text(text):

    access_token = (
        get_kakao_access_token()
    )

    if not access_token:

        return False

    url = (
        "https://kapi.kakao.com/"
        "v2/api/talk/memo/default/send"
    )

    headers = {
        "Authorization":
            f"Bearer {access_token}",
        "Content-Type":
            "application/x-www-form-urlencoded",
    }

    # 카카오 메시지 길이 제한을 고려
    chunks = [
        text[i:i + 900]
        for i in range(
            0,
            len(text),
            900
        )
    ]

    success = True

    for chunk in chunks:

        template_object = {

            "object_type": "text",

            "text": chunk,

            "link": {

                "web_url":
                    "https://developers.kakao.com",

                "mobile_web_url":
                    "https://developers.kakao.com",
            }
        }

        data = {

            "template_object":
                json.dumps(
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

                print(
                    "❌ 카카오 문자 전송 실패:"
                )

                print(
                    response.text[:500]
                )

                success = False

            else:

                print(
                    "✅ 카카오 문자 전송 성공"
                )

            time.sleep(0.7)

        except Exception as e:

            print(
                "❌ 카카오 문자 오류:",
                e
            )

            success = False

    return success


# =========================================================
# GitHub에 차트 업로드
# =========================================================

def upload_chart_to_github(
    local_path,
    remote_name
):

    if not GITHUB_TOKEN:

        print(
            "❌ GITHUB_TOKEN 없음"
        )

        return None

    if not GITHUB_REPOSITORY:

        print(
            "❌ GITHUB_REPOSITORY 없음"
        )

        return None

    try:

        with open(
            local_path,
            "rb"
        ) as f:

            content = f.read()

        import base64

        encoded = base64.b64encode(
            content
        ).decode("utf-8")

        api_url = (
            "https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/contents/"
            f"{remote_name}"
        )

        headers = {

            "Authorization":
                f"Bearer {GITHUB_TOKEN}",

            "Accept":
                "application/vnd.github+json",

            "X-GitHub-Api-Version":
                "2022-11-28",
        }

        # 기존 파일 확인
        sha = None

        check = requests.get(
            api_url,
            headers=headers,
            timeout=15
        )

        if check.status_code == 200:

            sha = check.json().get(
                "sha"
            )

        payload = {

            "message":
                f"Update chart {remote_name}",

            "content":
                encoded
        }

        if sha:

            payload["sha"] = sha

        response = requests.put(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code not in [
            200,
            201
        ]:

            print(
                "❌ GitHub 차트 업로드 실패:"
            )

            print(
                response.text[:500]
            )

            return None

        # 카카오에서 읽을 수 있는 공개 이미지 주소
        raw_url = (
            "https://raw.githubusercontent.com/"
            f"{GITHUB_REPOSITORY}/main/"
            f"{remote_name}"
        )

        print(
            "✅ 차트 업로드 완료:",
            remote_name
        )

        return raw_url

    except Exception as e:

        print(
            "❌ GitHub 업로드 오류:",
            e
        )

        return None


# =========================================================
# 카카오 이미지 메시지
# =========================================================

def send_kakao_image(
    image_url,
    title,
    description
):

    access_token = (
        get_kakao_access_token()
    )

    if not access_token:

        return False

    url = (
        "https://kapi.kakao.com/"
        "v2/api/talk/memo/default/send"
    )

    headers = {

        "Authorization":
            f"Bearer {access_token}",

        "Content-Type":
            "application/x-www-form-urlencoded",
    }

    template_object = {

        "object_type": "feed",

        "content": {

            "title": title,

            "description":
                description[:200],

            "image_url":
                image_url,

            "image_width":
                1200,

            "image_height":
                800,

            "link": {

                "web_url":
                    image_url,

                "mobile_web_url":
                    image_url,
            }
        }
    }

    data = {

        "template_object":
            json.dumps(
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

            print(
                "✅ 카카오 차트 전송 성공:",
                title
            )

            return True

        print(
            "❌ 카카오 차트 전송 실패:"
        )

        print(
            response.text[:500]
        )

        return False

    except Exception as e:

        print(
            "❌ 카카오 이미지 오류:",
            e
        )

        return False


# =========================================================
# 주식 데이터 다운로드
# =========================================================

def get_stock_data(symbol):

    try:

        df = yf.download(
            symbol,
            period="8mo",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df.empty:

            print(
                "❌ 데이터 없음:",
                symbol
            )

            return None

        # MultiIndex 제거
        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = (
                df.columns
                .get_level_values(0)
            )

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for col in required:

            if col not in df.columns:

                print(
                    "❌ 컬럼 없음:",
                    symbol,
                    col
                )

                return None

        df = df[
            required
        ].copy()

        for col in required:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df.dropna(
            inplace=True
        )

        if len(df) < 70:

            print(
                "❌ 데이터 부족:",
                symbol
            )

            return None

        return df

    except Exception as e:

        print(
            "❌ 주가 데이터 오류:",
            symbol,
            e
        )

        return None


# =========================================================
# 기술적 지표
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    # 이동평균선
    df["MA5"] = (
        df["Close"]
        .rolling(5)
        .mean()
    )

    df["MA20"] = (
        df["Close"]
        .rolling(20)
        .mean()
    )

    df["MA60"] = (
        df["Close"]
        .rolling(60)
        .mean()
    )

    # 거래량 20일 평균
    df["VOL20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
    )

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    delta = df["Close"].diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = (
        gain
        .rolling(14)
        .mean()
    )

    avg_loss = (
        loss
        .rolling(14)
        .mean()
    )

    rs = (
        avg_gain /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    df["RSI"] = (
        100 -
        (
            100 /
            (1 + rs)
        )
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        ema12 - ema26
    )

    df["MACD_SIGNAL"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_HIST"] = (
        df["MACD"] -
        df["MACD_SIGNAL"]
    )

    return df


# =========================================================
# 매수 / 매도 분석
# =========================================================

def analyze_signal(df):

    df = calculate_indicators(
        df
    )

    if len(df) < 65:

        return df, {
            "signal":
                "⚪ 데이터 부족",

            "score": 0
        }

    today = df.iloc[-1]

    yesterday = df.iloc[-2]

    score = 0

    reasons = []

    sell_reasons = []

    # -----------------------------------------------------
    # 골든크로스
    # -----------------------------------------------------

    golden_cross = (

        yesterday["MA20"]
        <=
        yesterday["MA60"]

        and

        today["MA20"]
        >
        today["MA60"]
    )

    # -----------------------------------------------------
    # 데드크로스
    # -----------------------------------------------------

    death_cross = (

        yesterday["MA20"]
        >=
        yesterday["MA60"]

        and

        today["MA20"]
        <
        today["MA60"]
    )

    if golden_cross:

        score += 3

        reasons.append(
            "20일선이 60일선을 상향 돌파"
        )

    # -----------------------------------------------------
    # 정배열
    # -----------------------------------------------------

    if (

        today["MA5"]
        >
        today["MA20"]
        >
        today["MA60"]

    ):

        score += 2

        reasons.append(
            "5·20·60일선 정배열"
        )

    # -----------------------------------------------------
    # 현재가 위치
    # -----------------------------------------------------

    if (
        today["Close"]
        >
        today["MA20"]
    ):

        score += 1

        reasons.append(
            "현재가 20일선 위"
        )

    if (
        today["Close"]
        >
        today["MA60"]
    ):

        score += 1

        reasons.append(
            "현재가 60일선 위"
        )

    # -----------------------------------------------------
    # 거래량
    # -----------------------------------------------------

    volume_ratio = 0

    if (
        safe_float(
            today["VOL20"]
        ) > 0
    ):

        volume_ratio = (
            safe_float(
                today["Volume"]
            )
            /
            safe_float(
                today["VOL20"]
            )
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
    # RSI
    # -----------------------------------------------------

    rsi = safe_float(
        today["RSI"]
    )

    if 50 <= rsi <= 68:

        score += 1

        reasons.append(
            f"RSI {rsi:.1f} 상승 구간"
        )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    macd = safe_float(
        today["MACD"]
    )

    macd_signal = safe_float(
        today["MACD_SIGNAL"]
    )

    if macd > macd_signal:

        score += 1

        reasons.append(
            "MACD 상승 우위"
        )

    # -----------------------------------------------------
    # 매도 조건
    # -----------------------------------------------------

    if death_cross:

        sell_reasons.append(
            "20일선이 60일선 하향 돌파"
        )

    if (
        rsi >= 75
        and
        macd < macd_signal
    ):

        sell_reasons.append(
            "RSI 과열 + MACD 약화"
        )

    if (
        today["Close"]
        <
        today["MA20"]
        and
        macd < macd_signal
    ):

        sell_reasons.append(
            "20일선 이탈 + MACD 약세"
        )

    # -----------------------------------------------------
    # 강력 매수
    # -----------------------------------------------------

    strong_buy = (

        score >= 7

        and

        today["Close"]
        >
        today["MA20"]

        and

        today["Close"]
        >
        today["MA60"]

        and

        macd > macd_signal

        and

        45 <= rsi <= 70
    )

    # -----------------------------------------------------
    # 매수 관심
    # -----------------------------------------------------

    buy = (
        score >= 5
    )

    # -----------------------------------------------------
    # 최종 신호
    # -----------------------------------------------------

    if strong_buy:

        final_signal = (
            "🟢 강력 매수 신호"
        )

    elif buy:

        final_signal = (
            "🟡 매수 관심"
        )

    elif sell_reasons:

        final_signal = (
            "🔴 매도/익절 주의"
        )

    else:

        final_signal = (
            "⚪ 관망"
        )

    result = {

        "signal":
            final_signal,

        "score":
            score,

        "golden_cross":
            golden_cross,

        "death_cross":
            death_cross,

        "price":
            safe_float(
                today["Close"]
            ),

        "ma5":
            safe_float(
                today["MA5"]
            ),

        "ma20":
            safe_float(
                today["MA20"]
            ),

        "ma60":
            safe_float(
                today["MA60"]
            ),

        "rsi":
            rsi,

        "volume_ratio":
            volume_ratio,

        "macd":
            macd,

        "macd_signal":
            macd_signal,

        "reasons":
            reasons,

        "sell_reasons":
            sell_reasons
    }

    return df, result


# =========================================================
# 차트 이미지 생성
# =========================================================

def create_chart(
    symbol,
    name,
    df,
    result
):

    os.makedirs(
        CHART_DIR,
        exist_ok=True
    )

    safe_symbol = (
        symbol
        .replace(".", "_")
        .replace("/", "_")
    )

    chart_file = os.path.join(
        CHART_DIR,
        f"{safe_symbol}.png"
    )

    data = df.tail(
        90
    ).copy()

    fig = plt.figure(
        figsize=(12, 8)
    )

    # =====================================================
    # 가격 차트
    # =====================================================

    ax = fig.add_axes(
        [0.08, 0.32, 0.88, 0.58]
    )

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

    # -----------------------------------------------------
    # 골든크로스 찾기
    # -----------------------------------------------------

    for i in range(
        1,
        len(data)
    ):

        previous = data.iloc[
            i - 1
        ]

        current = data.iloc[
            i
        ]

        if (

            previous["MA20"]
            <=
            previous["MA60"]

            and

            current["MA20"]
            >
            current["MA60"]

        ):

            date = data.index[i]

            price = current[
                "Close"
            ]

            ax.scatter(
                date,
                price,
                s=120,
                marker="^",
                zorder=10
            )

            ax.annotate(
                "GOLDEN CROSS",
                (
                    date,
                    price
                ),
                xytext=(
                    0,
                    18
                ),
                textcoords=
                    "offset points",
                ha="center",
                fontsize=8
            )

    # -----------------------------------------------------
    # 데드크로스
    # -----------------------------------------------------

    for i in range(
        1,
        len(data)
    ):

        previous = data.iloc[
            i - 1
        ]

        current = data.iloc[
            i
        ]

        if (

            previous["MA20"]
            >=
            previous["MA60"]

            and

            current["MA20"]
            <
            current["MA60"]

        ):

            date = data.index[i]

            price = current[
                "Close"
            ]

            ax.scatter(
                date,
                price,
                s=100,
                marker="v",
                zorder=10
            )

            ax.annotate(
                "DEATH CROSS",
                (
                    date,
                    price
                ),
                xytext=(
                    0,
                    -25
                ),
                textcoords=
                    "offset points",
                ha="center",
                fontsize=8
            )

    # -----------------------------------------------------
    # 현재가
    # -----------------------------------------------------

    current_price = (
        result["price"]
    )

    ax.axhline(
        current_price,
        linestyle="--",
        linewidth=0.8
    )

    ax.set_title(
        f"{name} ({symbol})\n"
        f"{result['signal']}  "
        f"점수 {result['score']}/11",
        fontsize=15,
        fontweight="bold"
    )

    ax.set_ylabel(
        "Price"
    )

    ax.grid(
        alpha=0.2
    )

    ax.legend(
        loc="upper left"
    )

    # =====================================================
    # RSI
    # =====================================================

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
        50,
        linestyle=":",
        linewidth=0.8
    )

    rsi_ax.axhline(
        30,
        linestyle="--",
        linewidth=0.8
    )

    rsi_ax.set_ylim(
        0,
        100
    )

    rsi_ax.set_ylabel(
        "RSI"
    )

    rsi_ax.grid(
        alpha=0.2
    )

    # =====================================================
    # 차트 정보
    # =====================================================

    info = (

        f"현재가: "
        f"{current_price:,.0f}\n"

        f"MA5: "
        f"{result['ma5']:,.0f}\n"

        f"MA20: "
        f"{result['ma20']:,.0f}\n"

        f"MA60: "
        f"{result['ma60']:,.0f}\n"

        f"RSI: "
        f"{result['rsi']:.1f}\n"

        f"거래량: "
        f"{result['volume_ratio']:.1f}x\n"

        f"Golden Cross: "
        f"{'YES' if result['golden_cross'] else 'NO'}"
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

    plt.close()

    print(
        "✅ 차트 생성:",
        chart_file
    )

    return chart_file


# =========================================================
# KRX 최근 영업일
# =========================================================

def get_safe_krx_date():

    try:

        now = now_kst()

        today = now.strftime(
            "%Y%m%d"
        )

        return (
            stock
            .get_nearest_business_day_in_a_week(
                today
            )
        )

    except:

        return now_kst().strftime(
            "%Y%m%d"
        )


# =========================================================
# 국내 지수
# =========================================================

def get_kr_indices():

    krx_date = (
        get_safe_krx_date()
    )

    kospi = "집계 중"

    kosdaq = "집계 중"

    try:

        # KOSPI
        k_df = (
            stock
            .get_index_ohlcv_by_date(
                krx_date,
                krx_date,
                "1001"
            )
        )

        if not k_df.empty:

            close = safe_float(
                k_df["종가"].iloc[0]
            )

            change = 0

            if "등락률" in k_df.columns:

                change = safe_float(
                    k_df["등락률"].iloc[0]
                )

            kospi = (
                f"{close:,.2f} "
                f"({change:+.2f}%)"
            )

        # KOSDAQ
        kd_df = (
            stock
            .get_index_ohlcv_by_date(
                krx_date,
                krx_date,
                "2001"
            )
        )

        if not kd_df.empty:

            close = safe_float(
                kd_df["종가"].iloc[0]
            )

            change = 0

            if "등락률" in kd_df.columns:

                change = safe_float(
                    kd_df["등락률"].iloc[0]
                )

            kosdaq = (
                f"{close:,.2f} "
                f"({change:+.2f}%)"
            )

    except Exception as e:

        print(
            "❌ 국내 지수 오류:",
            e
        )

    return (
        krx_date,
        kospi,
        kosdaq
    )


# =========================================================
# 미국 지수 + 거시경제
# =========================================================

def get_us_macro():

    indices = {

        "NASDAQ":
            "^IXIC",

        "S&P500":
            "^GSPC",

        "DOW":
            "^DJI"
    }

    us_text = ""

    us_rates = []

    for name, symbol in indices.items():

        try:

            df = (
                yf.Ticker(symbol)
                .history(
                    period="5d"
                )
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
                    /
                    previous
                    *
                    100
                )

                us_rates.append(
                    rate
                )

                us_text += (
                    f"- {name}: "
                    f"{current:,.2f} "
                    f"({rate:+.2f}%)\n"
                )

            else:

                us_text += (
                    f"- {name}: "
                    f"데이터 부족\n"
                )

        except Exception as e:

            print(
                "미국 지수 오류:",
                name,
                e
            )

            us_text += (
                f"- {name}: "
                f"집계 중\n"
            )

    macro = {}

    macro_symbols = {

        "환율":
            "USDKRW=X",

        "유가":
            "CL=F",

        "국채10년":
            "^TNX",

        "VIX":
            "^VIX"
    }

    for name, symbol in (
        macro_symbols.items()
    ):

        try:

            df = (
                yf.Ticker(symbol)
                .history(
                    period="5d"
                )
            )

            if not df.empty:

                value = safe_float(
                    df["Close"].iloc[-1]
                )

                macro[name] = (
                    f"{value:,.2f}"
                )

            else:

                macro[name] = "N/A"

        except:

            macro[name] = "N/A"

    return (
        us_text,
        macro,
        us_rates
    )


# =========================================================
# 거래대금 TOP 5
# =========================================================

def get_top_kr_stocks():

    krx_date = (
        get_safe_krx_date()
    )

    result = []

    try:

        df = (
            stock
            .get_market_trading_value_by_ticker(
                krx_date,
                krx_date,
                "ALL"
            )
        )

        if df is None or df.empty:

            return result

        df = (
            df
            .sort_values(
                by="거래대금",
                ascending=False
            )
            .head(5)
        )

        for ticker, row in df.iterrows():

            name = (
                stock
                .get_market_ticker_name(
                    ticker
                )
            )

            price = 0

            change = 0

            try:

                ohlcv = (
                    stock
                    .get_market_ohlcv_by_date(
                        krx_date,
                        krx_date,
                        ticker
                    )
                )

                if not ohlcv.empty:

                    price = safe_float(
                        ohlcv["종가"].iloc[0]
                    )

                    if "등락률" in ohlcv.columns:

                        change = safe_float(
                            ohlcv["등락률"].iloc[0]
                        )

            except:

                pass

            result.append({

                "ticker":
                    ticker,

                "name":
                    name,

                "price":
                    price,

                "change":
                    change
            })

    except Exception as e:

        print(
            "❌ 거래대금 TOP 오류:",
            e
        )

    return result


# =========================================================
# 관심종목 전체 분석
# =========================================================

def analyze_watchlist():

    all_stocks = {}

    all_stocks.update(
        KR_STOCKS
    )

    all_stocks.update(
        US_STOCKS
    )

    results = []

    for symbol, name in (
        all_stocks.items()
    ):

        print(
            "📊 분석:",
            name,
            symbol
        )

        df = get_stock_data(
            symbol
        )

        if df is None:

            continue

        df, result = (
            analyze_signal(df)
        )

        result["symbol"] = (
            symbol
        )

        result["name"] = (
            name
        )

        result["df"] = (
            df
        )

        results.append(
            result
        )

    return results


# =========================================================
# 브리핑 생성
# =========================================================

def generate_analyst_briefings(
    results
):

    now = now_kst()

    today = now.strftime(
        "%Y-%m-%d %H:%M"
    )

    hour = now.hour

    if hour < 9:

        label = (
            "장시작 브리핑"
        )

    elif hour < 13:

        label = (
            "오전 11시 장중 브리핑"
        )

    elif hour < 17:

        label = (
            "오후 4시 마감 브리핑"
        )

    else:

        label = (
            "저녁 야간 브리핑"
        )

    krx_date, kospi, kosdaq = (
        get_kr_indices()
    )

    us_text, macro, us_rates = (
        get_us_macro()
    )

    top_stocks = (
        get_top_kr_stocks()
    )

    top_text = ""

    for i, item in enumerate(
        top_stocks,
        1
    ):

        top_text += (

            f"{i}. "
            f"{item['name']} "
            f"{item['price']:,.0f}원 "
            f"({item['change']:+.2f}%)\n"
        )

    if not top_text:

        top_text = (
            "거래대금 데이터 집계 중\n"
        )

    # -----------------------------------------------------
    # 신호별 분류
    # -----------------------------------------------------

    strong = [

        x for x in results

        if x["signal"]
        ==
        "🟢 강력 매수 신호"
    ]

    buy = [

        x for x in results

        if x["signal"]
        ==
        "🟡 매수 관심"
    ]

    sell = [

        x for x in results

        if x["signal"]
        ==
        "🔴 매도/익절 주의"
    ]

    # -----------------------------------------------------
    # 시장 분위기
    # -----------------------------------------------------

    kospi_rate = 0

    try:

        kospi_rate = float(

            kospi
            .split("(")[1]
            .replace(
                "%)",
                ""
            )
        )

    except:

        pass

    if (

        kospi_rate <= -1

        or

        (
            us_rates
            and
            min(us_rates) <= -1.5
        )
    ):

        mood = (
            "변동성 확대 / "
            "하방 압력"
        )

    elif (

        kospi_rate >= 1

        or

        (
            us_rates
            and
            max(us_rates) >= 1.5
        )
    ):

        mood = (
            "상승 모멘텀 강화"
        )

    else:

        mood = (
            "혼조 / 종목별 차별화"
        )

    # -----------------------------------------------------
    # 강력 매수
    # -----------------------------------------------------

    strong_text = ""

    for x in strong[:10]:

        strong_text += (

            f"🟢 {x['name']} "
            f"{x['price']:,.0f} "
            f"[{x['score']}/11]\n"
        )

    if not strong_text:

        strong_text = (
            "현재 강력 매수 조건 "
            "충족 종목 없음\n"
        )

    # -----------------------------------------------------
    # 매수 관심
    # -----------------------------------------------------

    buy_text = ""

    for x in buy[:10]:

        buy_text += (

            f"🟡 {x['name']} "
            f"{x['price']:,.0f} "
            f"[{x['score']}/11]\n"
        )

    if not buy_text:

        buy_text = (
            "현재 매수 관심 종목 없음\n"
        )

    # -----------------------------------------------------
    # 매도
    # -----------------------------------------------------

    sell_text = ""

    for x in sell[:10]:

        sell_text += (

            f"🔴 {x['name']} "
            f"{x['price']:,.0f}\n"
        )

    if not sell_text:

        sell_text = (
            "현재 매도/익절 주의 종목 없음\n"
        )

    # =====================================================
    # PART 1
    # =====================================================

    part1 = f"""
📅 {today}
📊 실시간 주식시장 브리핑
[{label}]
━━━━━━━━━━━━━━━━

🌍 시장 진단

시장 분위기:
{mood}

🇰🇷 국내시장

KOSPI:
{kospi}

KOSDAQ:
{kosdaq}

🔥 거래대금 TOP 5

{top_text.strip()}
"""

    # =====================================================
    # PART 2
    # =====================================================

    part2 = f"""
📊 글로벌 증시
━━━━━━━━━━━━━━━━

🇺🇸 미국 주요지수

{us_text.strip()}

🌎 거시경제

원/달러:
{macro.get('환율', 'N/A')}

WTI:
{macro.get('유가', 'N/A')}

미국채 10년:
{macro.get('국채10년', 'N/A')}

VIX:
{macro.get('VIX', 'N/A')}
"""

    # =====================================================
    # PART 3
    # =====================================================

    part3 = f"""
🎯 기술적 신호 분석
━━━━━━━━━━━━━━━━

🟢 강력 매수 신호

{strong_text.strip()}

🟡 매수 관심

{buy_text.strip()}

🔴 매도/익절 주의

{sell_text.strip()}

📌 분석 기준

① MA5 / MA20 / MA60
② 골든크로스
③ 정배열
④ 거래량
⑤ RSI
⑥ MACD
⑦ 현재가와 이평선 위치

※ 자동 기술적 분석 신호이며
투자 결과를 보장하지 않습니다.
"""

    return (
        part1,
        part2,
        part3
    )


# =========================================================
# 차트 생성 + 카카오 전송
# =========================================================

def send_signal_charts(
    results
):

    # 강력 매수
    strong = [

        x for x in results

        if x["signal"]
        ==
        "🟢 강력 매수 신호"
    ]

    # 매수 관심
    buy = [

        x for x in results

        if x["signal"]
        ==
        "🟡 매수 관심"
    ]

    # 매도 주의
    sell = [

        x for x in results

        if x["signal"]
        ==
        "🔴 매도/익절 주의"
    ]

    # 우선순위
    selected = (
        strong +
        buy +
        sell
    )

    # 카카오톡 폭주 방지를 위해 최대 10개
    selected = selected[:10]

    if not selected:

        send_kakao_text(
            "📈 기술적 신호 알림\n\n"
            "현재 관심종목 중 "
            "매수/매도 신호가 없습니다."
        )

        return

    for x in selected:

        print(
            "📈 차트 생성 및 전송:",
            x["name"]
        )

        chart_file = (
            create_chart(
                x["symbol"],
                x["name"],
                x["df"],
                x
            )
        )

        remote_name = (
            "charts/"
            +
            x["symbol"]
            .replace(
                ".",
                "_"
            )
            +
            ".png"
        )

        image_url = (
            upload_chart_to_github(
                chart_file,
                remote_name
            )
        )

        if not image_url:

            print(
                "❌ 이미지 URL 생성 실패:",
                x["name"]
            )

            continue

        description = (

            f"{x['signal']}\n"

            f"점수: "
            f"{x['score']}/11\n"

            f"현재가: "
            f"{x['price']:,.0f}\n"

            f"RSI: "
            f"{x['rsi']:.1f}\n"

            f"거래량: "
            f"{x['volume_ratio']:.1f}배\n"

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
# 최종 실행
# =========================================================

def job():

    print(
        "=" * 60
    )

    print(
        f"[{now_kst()}]"
    )

    print(
        "🚀 주식 AI 브리핑 시작"
    )

    print(
        "=" * 60
    )

    # -----------------------------------------------------
    # 1. 관심종목 분석
    # -----------------------------------------------------

    results = (
        analyze_watchlist()
    )

    print(
        f"✅ {len(results)}개 종목 분석 완료"
    )

    # -----------------------------------------------------
    # 2. 문자 브리핑
    # -----------------------------------------------------

    p1, p2, p3 = (
        generate_analyst_briefings(
            results
        )
    )

    print(
        "📨 문자 브리핑 전송"
    )

    send_kakao_text(p1)

    time.sleep(1)

    send_kakao_text(p2)

    time.sleep(1)

    send_kakao_text(p3)

    time.sleep(1)

    # -----------------------------------------------------
    # 3. 차트 이미지
    # -----------------------------------------------------

    print(
        "📈 차트 이미지 전송 시작"
    )

    send_signal_charts(
        results
    )

    print(
        "=" * 60
    )

    print(
        "✅ 전체 브리핑 완료"
    )

    print(
        "=" * 60
    )


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    job()
